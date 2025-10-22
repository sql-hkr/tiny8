import unittest

from tiny8 import CPU, assemble


class TestMCUControl(unittest.TestCase):
    def setUp(self):
        self.cpu = CPU()

    def test_nop_and_ser_clr(self):
        prog, labels = assemble("""
            ser r0
            clr r1
            nop
        """)
        self.cpu.load_program(prog, labels)
        self.cpu.run()
        self.assertEqual(self.cpu.read_reg(0), 0xFF)
        self.assertEqual(self.cpu.read_reg(1), 0x00)

    def test_sbi_cbi(self):
        prog, labels = assemble("""
            ldi r0, 0
            out 50, r0
            sbi 50, 1
            cbi 50, 1
        """)
        self.cpu.load_program(prog, labels)
        self.cpu.run()
        self.assertEqual(self.cpu.read_ram(50), 0)
