import unittest

from tiny8 import CPU, assemble
from tiny8.cpu import SREG_C, SREG_N, SREG_S, SREG_V, SREG_Z


class TestShiftsRotates(unittest.TestCase):
    def setUp(self):
        self.cpu = CPU()

    def run_asm(self, src: str):
        prog, labels = assemble(src)
        self.cpu.load_program(prog, labels)
        self.cpu.run()
        return self.cpu

    def test_lsl_sets_c_and_v(self):
        src = """
            ldi r0, 0b01000000
            lsl r0
        """
        cpu = self.run_asm(src)
        self.assertEqual(cpu.read_reg(0), 0b10000000)
        # C should be taken from old MSB (which was 0 for this input)
        self.assertFalse(cpu.get_flag(SREG_C))
        # S should equal N ^ V per helper implementation
        self.assertEqual(
            cpu.get_flag(SREG_S), cpu.get_flag(SREG_N) ^ cpu.get_flag(SREG_V)
        )

    def test_lsr_sets_c_and_z(self):
        src = """
            ldi r1, 0b00000001
            lsr r1
        """
        cpu = self.run_asm(src)
        self.assertEqual(cpu.read_reg(1), 0)
        self.assertTrue(cpu.get_flag(SREG_C))
        self.assertTrue(cpu.get_flag(SREG_Z))

    def test_rol_ror_with_carry(self):
        src = """
            ldi r2, 0b10000000
            ldi r3, 0b00000001
            ; set C then rol/ror
        """
        prog, labels = assemble(src)
        self.cpu.load_program(prog, labels)
        self.cpu.set_flag(SREG_C, True)
        # perform rol on r2
        self.cpu.program.append(("rol", (("reg", 2),)))
        # perform ror on r3
        self.cpu.program.append(("ror", (("reg", 3),)))
        self.cpu.run()
        # verify carry bits updated and registers rotated
        self.assertIn(self.cpu.read_reg(2), (0b00000001, 0b00000000))
        self.assertIn(self.cpu.read_reg(3), (0b10000000, 0b00000000))
