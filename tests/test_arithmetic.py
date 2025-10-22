import unittest

from tiny8 import CPU, assemble
from tiny8.cpu import SREG_C, SREG_H, SREG_N, SREG_S, SREG_V, SREG_Z


class TestArithmetic(unittest.TestCase):
    def setUp(self):
        self.cpu = CPU()

    def run_asm(self, src: str):
        prog, labels = assemble(src)
        self.cpu.load_program(prog, labels)
        self.cpu.run()
        return self.cpu

    def test_add_basic_and_flags(self):
        # 0x7F + 0x01 -> 0x80: tests N,V (overflow), Z, C, H
        src = """
            ldi r0, $7F
            ldi r1, $01
            add r0, r1
        """
        cpu = self.run_asm(src)
        self.assertEqual(cpu.read_reg(0), 0x80)
        # N = 1 (bit7 set), V = 1 (signed overflow), S = N ^ V = 0
        self.assertTrue(cpu.get_flag(SREG_N))
        self.assertTrue(cpu.get_flag(SREG_V))
        self.assertFalse(cpu.get_flag(SREG_S))
        # Z = 0, C = 0, H = 1 (carry from bit3)
        self.assertFalse(cpu.get_flag(SREG_Z))
        self.assertFalse(cpu.get_flag(SREG_C))
        self.assertTrue(cpu.get_flag(SREG_H))

    def test_add_with_carry(self):
        # 0xFF + 0x01 -> 0x00 with carry
        src = """
            ldi r2, $FF
            ldi r3, $01
            add r2, r3
        """
        cpu = self.run_asm(src)
        self.assertEqual(cpu.read_reg(2), 0x00)
        self.assertTrue(cpu.get_flag(SREG_Z))
        self.assertTrue(cpu.get_flag(SREG_C))

    def test_adc_uses_carry_in(self):
        # ADC should include carry in
        src = """
            ldi r4, $FF
            ldi r5, $00
            adc r4, r5
        """
        prog, labels = assemble(src)
        self.cpu.load_program(prog, labels)
        # set carry before run
        self.cpu.set_flag(SREG_C, True)
        self.cpu.run()
        self.assertEqual(self.cpu.read_reg(4), 0x00)
        self.assertTrue(self.cpu.get_flag(SREG_C))

    def test_sub_and_cp_flags(self):
        # 0x00 - 0x01 -> 0xFF with borrow
        src = """
            ldi r6, $00
            ldi r7, $01
            sub r6, r7
        """
        cpu = self.run_asm(src)
        self.assertEqual(cpu.read_reg(6), 0xFF)
        self.assertTrue(cpu.get_flag(SREG_C))
        self.assertTrue(cpu.get_flag(SREG_N))

    def test_inc_overflow_flag(self):
        src = """
            ldi r8, $7F
            inc r8
        """
        cpu = self.run_asm(src)
        self.assertEqual(cpu.read_reg(8), 0x80)
        self.assertTrue(cpu.get_flag(SREG_V))
        self.assertTrue(cpu.get_flag(SREG_N))

    def test_dec_overflow_flag(self):
        src = """
            ldi r9, $80
            dec r9
        """
        cpu = self.run_asm(src)
        self.assertEqual(cpu.read_reg(9), 0x7F)
        self.assertTrue(cpu.get_flag(SREG_V))
        self.assertFalse(cpu.get_flag(SREG_N))
