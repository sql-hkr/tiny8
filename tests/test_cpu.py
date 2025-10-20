"""Unit tests for the tiny8 CPU and instruction implementations.

Tests are small and self-contained; they exercise arithmetic, logical,
memory and control-flow instructions implemented by the CPU.
"""

import unittest

from tiny8 import CPU, assemble, assemble_file


class Tiny8TestCase(unittest.TestCase):
    """Base test case providing helpers and a fresh CPU for each test."""

    def setUp(self) -> None:
        self.cpu = CPU()

    def run_asm(self, src: str = None, path: str = None, max_cycles: int = 1000):
        """Assemble the provided source or file, load into CPU and run.

        Returns the CPU instance for assertions.
        """
        if path:
            prog, labels = assemble_file(path)
        else:
            prog, labels = assemble(src)
        self.cpu.load_program(prog, labels)
        self.cpu.run(max_cycles=max_cycles)
        return self.cpu


class TestCPU(Tiny8TestCase):
    def test_ldi_add_mul_div_and_logic(self):
        # verify multiple arithmetic/logical operations in one compact test
        src = """
            ldi r0, 10
            ldi r1, 20
            add r0, r1
            ldi r2, 6
            ldi r3, 7
            mul r2, r3
            ldi r4, 20
            ldi r5, 3
            div r4, r5
            ldi r6, $0F
            ldi r7, $F0
            and r6, r7
            ldi r8, $AA
            ldi r9, $55
            eor r8, r9
            ldi r10, 0
            ldi r11, 1
            or r10, r11
        """
        cpu = self.run_asm(src)
        self.assertEqual(cpu.read_reg(0), 30)  # 10 + 20
        self.assertEqual(cpu.read_reg(2), 42)  # 6 * 7 low byte
        self.assertEqual(cpu.read_reg(4), 6)  # 20 // 3
        self.assertEqual(cpu.read_reg(5), 2)  # remainder in r5
        self.assertEqual(cpu.read_reg(6), 0x00)
        self.assertEqual(cpu.read_reg(8), 0xFF)
        self.assertEqual(cpu.read_reg(10), 1)

    def test_inc_dec_shift(self):
        src = """
            ldi r12, 1
            inc r12
            ldi r13, 4
            lsl r13
            ldi r14, 8
            lsr r14
            ldi r15, 0
            dec r15
        """
        cpu = self.run_asm(src)
        self.assertEqual(cpu.read_reg(12), 2)
        self.assertEqual(cpu.read_reg(13), 8)
        self.assertEqual(cpu.read_reg(14), 4)
        self.assertEqual(cpu.read_reg(15), 255)

    def test_sbi_cbi_and_io(self):
        src = """
            ldi r0, 0
            out 100, r0
            sbi 100, 2
            cbi 100, 2
        """
        cpu = self.run_asm(src)
        self.assertEqual(cpu.read_ram(100), 0)

    def test_fib_no_overflow(self):
        # Load the fibonacci program but don't run so we can set the input first
        prog, labels = assemble_file("examples/fibonacci.asm")
        self.cpu.load_program(prog, labels)
        # compute fib(7) => 13
        self.cpu.write_reg(17, 7)
        self.cpu.run(max_cycles=200)
        self.assertEqual(self.cpu.read_reg(16), 13)


class TestInstructions(Tiny8TestCase):
    def test_adc_with_carry(self):
        src = """
            ldi r0, 200
            ldi r1, 100
            adc r0, r1
        """
        # assemble/load but set carry flag before executing ADC
        prog, labels = assemble(src)
        self.cpu.load_program(prog, labels)
        self.cpu.set_flag(0, True)
        self.cpu.run()
        self.assertEqual(self.cpu.read_reg(0), 301 & 0xFF)
        self.assertTrue(self.cpu.get_flag(0))

    def test_cp_and_branch(self):
        src = """
            ldi r0, 5
            ldi r1, 5
            cp r0, r1
            breq equal
            ldi r2, 1
            jmp done
        equal:
            ldi r2, 2
        done:
            nop
        """
        cpu = self.run_asm(src)
        self.assertEqual(cpu.read_reg(2), 2)

    def test_push_pop_and_call(self):
        src = """
            ldi r3, 55
            push r3
            ldi r3, 0
            pop r4
            call func
            jmp done
        func:
            ldi r5, 9
            ret
        done:
            nop
        """
        cpu = self.run_asm(src, max_cycles=50)
        self.assertEqual(cpu.read_reg(4), 55)
        self.assertEqual(cpu.read_reg(5), 9)

    def test_ld_st_and_rotations(self):
        src = """
            ldi r8, 150    ; address
            ldi r9, 77     ; value
            st r8, r9
            ldi r10, 150
            ld r11, r10
            ldi r12, 0b10000000
            ldi r13, 1
            lsl r12
            lsr r13
        """
        cpu = self.run_asm(src)
        self.assertEqual(cpu.read_reg(11), 77)
        self.assertEqual(cpu.read_reg(12), 0)
        self.assertTrue(cpu.get_flag(0))


if __name__ == "__main__":
    unittest.main()
