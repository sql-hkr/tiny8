import unittest

from tiny8 import CPU, assemble
from tiny8.cpu import SREG_C, SREG_I, SREG_Z


class TestControlFlow(unittest.TestCase):
    def setUp(self):
        self.cpu = CPU()

    def run_asm(self, src: str):
        prog, labels = assemble(src)
        self.cpu.load_program(prog, labels)
        self.cpu.run()
        return self.cpu

    def test_branch_on_zero_and_carry(self):
        src = """
            ldi r0, 1
            ldi r1, 1
            sub r0, r1
            breq is_zero
            ldi r2, 1
            jmp done
        is_zero:
            ldi r2, 2
        done:
            nop
        """
        cpu = self.run_asm(src)
        self.assertTrue(cpu.get_flag(SREG_Z))
        self.assertEqual(cpu.read_reg(2), 2)

    def test_brcc_brcs(self):
        # Build a small program where we set the carry then immediately hit BRCS
        prog, labels = assemble("""
            ldi r3, 0
            ldi r4, 0
            ; placeholder
        """)
        self.cpu.load_program(prog, labels)
        # set carry immediately before inserting the branch
        self.cpu.set_flag(SREG_C, True)
        # append a branch instruction which should be taken when C==1
        self.cpu.program.append(("brcs", ("label1",)))
        # destination: skip the following ldi if branch taken
        self.cpu.labels["label1"] = len(self.cpu.program) + 1
        self.cpu.program.append(("ldi", (("reg", 5), 9)))
        self.cpu.run()
        # If branch taken, r5 should not have been set to 9
        self.assertNotEqual(self.cpu.read_reg(5), 9)

    def test_sei_cli(self):
        cpu = CPU()
        prog, labels = assemble("""
            sei
            cli
        """)
        cpu.load_program(prog, labels)
        cpu.run()
        # after sei then cli the I bit should be cleared
        self.assertFalse(cpu.get_flag(SREG_I))

    def test_sbci_behaviour(self):
        # show that SBCI subtracts immediate and includes carry
        cpu = CPU()
        prog, labels = assemble("""
            ldi r0, $00
            ldi r1, $02
            ldi r2, $01
            ; set carry to 1
            ldi r3, $01
            ; simulate carry set
        """)
        # initialize r1 and set carry
        cpu.write_reg(1, 2)
        cpu.set_flag(SREG_C, True)
        # perform sbci on r1 (2 - 1 - carry(1) = 0)
        prog2, labels2 = assemble("""
            sbci r1, $01
        """)
        cpu.load_program(prog2, labels2)
        cpu.run()
        self.assertEqual(cpu.read_reg(1), 0x00)
        self.assertTrue(cpu.get_flag(SREG_Z))

    def test_cpse_skips_next(self):
        cpu = CPU()
        prog, labels = assemble("""
            ldi r4, $05
            ldi r5, $05
            cpse r4, r5
            ldi r6, $AA
            ldi r7, $BB
        """)
        cpu.load_program(prog, labels)
        cpu.run()
        # If cpse skipped the next instruction, r6 should remain zero and r7 should be loaded
        self.assertEqual(cpu.read_reg(6), 0x00)
        self.assertEqual(cpu.read_reg(7), 0xBB)

    def test_brlt(self):
        # BRLT: branch when signed (Rd < Rr). Use -1 (0xFF) < 1 (0x01)
        src = """
            ldi r0, $FF    ; -1
            ldi r1, $01    ; 1
            cp r0, r1
            brlt less
            ldi r2, $01
            jmp done
        less:
            ldi r2, $02
        done:
            nop
        """
        cpu = self.run_asm(src)
        # -1 < 1 so branch taken -> r2 == 2
        self.assertEqual(cpu.read_reg(2), 0x02)

    def test_brge(self):
        # BRGE: branch when signed (Rd >= Rr). Use 1 >= -1
        src2 = """
            ldi r0, $01    ; 1
            ldi r1, $FF    ; -1
            cp r0, r1
            brge ge
            ldi r2, $01
            jmp done
        ge:
            ldi r2, $02
        done:
            nop
        """
        cpu2 = self.run_asm(src2)
        # 1 >= -1 so branch taken -> r2 == 2
        self.assertEqual(cpu2.read_reg(2), 0x02)

    def test_brmi(self):
        # BRMI: branch when negative (N == 1)
        src = """
            ldi r0, $FF    ; -1
            ldi r1, $00    ; 0
            cp r0, r1
            brmi neg
            ldi r2, $01
            jmp done
        neg:
            ldi r2, $02
        done:
            nop
        """
        cpu = self.run_asm(src)
        # -1 < 0 so negative -> branch taken -> r2 == 2
        self.assertEqual(cpu.read_reg(2), 0x02)

    def test_brpl(self):
        # BRPL: branch when plus (N == 0)
        src2 = """
            ldi r0, $02    ; 2
            ldi r1, $FF    ; -1
            cp r0, r1
            brpl plus
            ldi r2, $01
            jmp done2
        plus:
            ldi r2, $02
        done2:
            nop
        """
        cpu2 = self.run_asm(src2)
        # 2 >= -1 so non-negative -> branch taken -> r2 == 2
        self.assertEqual(cpu2.read_reg(2), 0x02)
