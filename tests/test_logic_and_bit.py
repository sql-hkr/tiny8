import unittest

from tiny8 import CPU, assemble
from tiny8.cpu import SREG_N, SREG_Z


class TestLogicAndBit(unittest.TestCase):
    def setUp(self):
        self.cpu = CPU()

    def run_asm(self, src: str):
        prog, labels = assemble(src)
        self.cpu.load_program(prog, labels)
        self.cpu.run()
        return self.cpu

    def test_and_eor_or_flags(self):
        # Run AND alone and check flags
        src_and = """
            ldi r0, $F0
            ldi r1, $0F
            and r0, r1
        """
        cpu = self.run_asm(src_and)
        self.assertEqual(cpu.read_reg(0), 0x00)
        self.assertTrue(cpu.get_flag(SREG_Z))

        # Run EOR alone and check N
        src_eor = """
            ldi r2, $AA
            ldi r3, $55
            eor r2, r3
        """
        cpu = self.run_asm(src_eor)
        self.assertEqual(cpu.read_reg(2), 0xFF)
        self.assertTrue(cpu.get_flag(SREG_N))

        # Run OR alone
        src_or = """
            ldi r4, $01
            ldi r5, $02
            or r4, r5
        """
        cpu = self.run_asm(src_or)
        self.assertEqual(cpu.read_reg(4), 0x03)

    def test_sbi_cbi_behavior(self):
        src = """
            ldi r10, 0x00
            out 200, r10
            sbi 200, 3
            sbi 200, 7
            cbi 200, 3
        """
        cpu = self.run_asm(src)
        self.assertEqual(cpu.read_ram(200), 0x80)
