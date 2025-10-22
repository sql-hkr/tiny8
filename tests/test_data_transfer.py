import unittest

from tiny8 import CPU, assemble


class TestDataTransfer(unittest.TestCase):
    def setUp(self):
        self.cpu = CPU()

    def run_asm(self, src: str):
        prog, labels = assemble(src)
        self.cpu.load_program(prog, labels)
        self.cpu.run()
        return self.cpu

    def test_ldi_mov_ld_st(self):
        src = """
            ldi r0, 123
            ldi r1, 5
            mov r2, r0
            ldi r3, 10
            st r3, r2
            ldi r4, 10
            ld r5, r4
        """
        cpu = self.run_asm(src)
        self.assertEqual(cpu.read_reg(0), 123)
        self.assertEqual(cpu.read_reg(2), 123)
        self.assertEqual(cpu.read_ram(10), 123)
        self.assertEqual(cpu.read_reg(5), 123)

    def test_push_pop_call_ret(self):
        src = """
            ldi r6, 77
            push r6
            ldi r6, 0
            pop r7
            call fn
            jmp done
        fn:
            ldi r8, 9
            ret
        done:
            nop
        """
        cpu = self.run_asm(
            src,
        )
        self.assertEqual(cpu.read_reg(7), 77)
        self.assertEqual(cpu.read_reg(8), 9)
