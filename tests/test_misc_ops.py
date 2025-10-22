import unittest

from tiny8 import CPU, assemble
from tiny8.cpu import SREG_C, SREG_N, SREG_Z


class TestMiscOps(unittest.TestCase):
    def setUp(self):
        self.cpu = CPU()

    def run_asm(self, src: str):
        prog, labels = assemble(src)
        self.cpu.load_program(prog, labels)
        self.cpu.run()
        return self.cpu

    def test_com_sets_c_and_flags(self):
        src = """
            ldi r0, $00
            com r0
        """
        cpu = self.run_asm(src)
        self.assertEqual(cpu.read_reg(0), 0xFF)
        self.assertTrue(cpu.get_flag(SREG_C))
        self.assertTrue(cpu.get_flag(SREG_N))
        self.assertFalse(cpu.get_flag(SREG_Z))

    def test_neg_behaves_like_sub_from_zero(self):
        src = """
            ldi r1, $01
            neg r1
        """
        cpu = self.run_asm(src)
        self.assertEqual(cpu.read_reg(1), 0xFF)
        self.assertTrue(cpu.get_flag(SREG_C))

    def test_swap_nibbles(self):
        src = """
            ldi r2, $AB
            swap r2
        """
        cpu = self.run_asm(src)
        self.assertEqual(cpu.read_reg(2), 0xBA)

    def test_tst_sets_flags_but_no_store(self):
        src = """
            ldi r3, $00
            tst r3
        """
        cpu = self.run_asm(src)
        self.assertTrue(cpu.get_flag(SREG_Z))

    def test_andi_ori_eori(self):
        src = """
            ldi r4, $F0
            andi r4, $0F
            ldi r5, $0F
            ori r5, $F0
            ldi r6, $FF
            eori r6, $FF
        """
        cpu = self.run_asm(src)
        self.assertEqual(cpu.read_reg(4), 0x00)
        self.assertTrue(cpu.get_flag(SREG_Z))
        self.assertEqual(cpu.read_reg(5), 0xFF)
        self.assertEqual(cpu.read_reg(6), 0x00)

    def test_subi_and_sbc(self):
        # test subi on r7
        src1 = """
            ldi r7, $05
            subi r7, $03
        """
        cpu1 = CPU()
        prog1, labels1 = assemble(src1)
        cpu1.load_program(prog1, labels1)
        cpu1.run()
        self.assertEqual(cpu1.read_reg(7), 0x02)

        # test subi resulting in borrow on r8
        src2 = """
            ldi r8, $02
            subi r8, $03
        """
        cpu2 = CPU()
        prog2, labels2 = assemble(src2)
        cpu2.load_program(prog2, labels2)
        cpu2.run()
        self.assertEqual(cpu2.read_reg(8), 0xFF)
        self.assertTrue(cpu2.get_flag(SREG_C))

        # test sbc separately
        src3 = """
            ldi r9, $03
            ldi r10, $02
            sbc r9, r10
        """
        cpu3 = CPU()
        prog3, labels3 = assemble(src3)
        cpu3.load_program(prog3, labels3)
        cpu3.run()
        self.assertEqual(cpu3.read_reg(9), 0x01)
        self.assertFalse(cpu3.get_flag(SREG_C))

    def test_adiw(self):
        cpu = CPU()
        # set r24:r25 = 0x00FF
        cpu.write_reg(24, 0xFF)
        cpu.write_reg(25, 0x00)
        prog, labels = assemble("""
            adiw r24, $0001
        """)
        cpu.load_program(prog, labels)
        cpu.run()
        # expect 0x00FF + 1 = 0x0100 -> r24=0x00, r25=0x01
        self.assertEqual(cpu.read_reg(24), 0x00)
        self.assertEqual(cpu.read_reg(25), 0x01)

    def test_reti_pushes_and_returns(self):
        cpu = CPU()
        # simulate an interrupt by pushing a return address then calling reti
        # we use trigger_interrupt which already pushes PC and jumps to vector
        cpu.interrupts[1] = True
        # program: reti; ldi r0,$55 (should run after RETI returns to pushed ret)
        prog, labels = assemble("""
            reti
            ldi r0, $55
        """)
        cpu.load_program(prog, labels)
        # trigger vector 1 (should push return and jump to instruction 0)
        cpu.trigger_interrupt(1)
        # now run - reti should pop and return to our ldi
        cpu.run()
        self.assertEqual(cpu.read_reg(0), 0x55)

    def test_sbrs_sbrc(self):
        cpu = CPU()
        prog, labels = assemble("""
            ldi r0, $01
            sbrs r0, 0
            ldi r1, $AA
            ldi r2, $BB
        """)
        cpu.load_program(prog, labels)
        cpu.run()
        # sbrs should skip the ldi r1 and execute ldi r2
        self.assertEqual(cpu.read_reg(1), 0x00)
        self.assertEqual(cpu.read_reg(2), 0xBB)

    def test_sbis_sbic(self):
        cpu = CPU()
        # set RAM[10] bit0 = 0, so sbic should skip and sbis should not
        cpu.write_ram(10, 0x00)
        prog, labels = assemble("""
            sbis 10, 0
            ldi r3, $11
            sbic 10, 0
            ldi r4, $22
        """)
        cpu.load_program(prog, labels)
        cpu.run()
        # sbis sees bit clear -> should not skip, so r3 gets loaded
        self.assertEqual(cpu.read_reg(3), 0x11)
        # sbic sees bit clear -> skip next -> r4 should remain 0
        self.assertEqual(cpu.read_reg(4), 0x00)

    def test_sbiw_rjmp_rcall(self):
        cpu = CPU()
        # test sbiw subtracts from r6:r7 word
        cpu.write_reg(6, 0x00)
        cpu.write_reg(7, 0x01)
        prog1, labels1 = assemble("""
            sbiw r6, $0001
        """)
        cpu.load_program(prog1, labels1)
        cpu.run()
        # 0x0100 - 1 = 0x00FF -> r6=0xFF, r7=0x00
        self.assertEqual(cpu.read_reg(6), 0xFF)
        self.assertEqual(cpu.read_reg(7), 0x00)

        # rjmp: jump relative +2 (skip next two instructions)
        prog2, labels2 = assemble("""
            rjmp 2
            ldi r8, $01
            ldi r9, $02
            ldi r10, $03
        """)
        cpu.load_program(prog2, labels2)
        cpu.run()
        # rjmp +2 should land executing ldi r10
        self.assertEqual(cpu.read_reg(8), 0x00)
        self.assertEqual(cpu.read_reg(9), 0x00)
        self.assertEqual(cpu.read_reg(10), 0x03)

        # rcall relative +1 should call next instruction (simulate push/pop)
        prog3, labels3 = assemble("""
            rcall 1
            ldi r11, $99
            ldi r12, $77
        """)
        cpu.load_program(prog3, labels3)
        cpu.run()
        # rcall +1 jumps to ldi r11; ensure r11 loaded
        self.assertEqual(cpu.read_reg(11), 0x99)

    def test_adiw_flags_edge_cases(self):
        cpu = CPU()
        # Case: carry out from 0xFFFF + 1
        cpu.write_reg(20, 0xFF)  # low
        cpu.write_reg(21, 0xFF)  # high -> word = 0xFFFF
        prog, labels = assemble("""
            adiw r20, $0001
        """)
        cpu.load_program(prog, labels)
        cpu.run()
        # expect wrap to 0x0000, Z=1, C=1
        self.assertEqual((cpu.read_reg(21) << 8) | cpu.read_reg(20), 0x0000)
        self.assertTrue(cpu.get_flag(1))  # Z
        self.assertTrue(cpu.get_flag(0))  # C

    def test_sbiw_flags_edge_cases(self):
        cpu = CPU()
        # Case: borrow from 0x0000 - 1
        cpu.write_reg(18, 0x00)
        cpu.write_reg(19, 0x00)
        prog, labels = assemble("""
            sbiw r18, $0001
        """)
        cpu.load_program(prog, labels)
        cpu.run()
        # expect wrap to 0xFFFF, Z=0, C=1
        self.assertEqual((cpu.read_reg(19) << 8) | cpu.read_reg(18), 0xFFFF)
        self.assertFalse(cpu.get_flag(1))  # Z
        self.assertTrue(cpu.get_flag(0))  # C


if __name__ == "__main__":
    unittest.main()
