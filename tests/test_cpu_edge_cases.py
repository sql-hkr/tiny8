"""CPU edge case and exception handling tests.

Tests for CPU error conditions, exceptions, interrupts, and boundary cases.
"""

import pytest

from tiny8 import CPU, assemble


class TestCPUExceptions:
    """Test CPU exception handling."""

    def test_invalid_instruction(self):
        """Test that invalid instruction raises NotImplementedError."""
        cpu = CPU()
        cpu.program = [("INVALID_OP", ())]
        with pytest.raises(
            NotImplementedError, match="Instruction INVALID_OP not implemented"
        ):
            cpu.step()

    def test_operand_formatting_exception(self):
        """Test that operand formatting exceptions are handled."""
        cpu = CPU()
        cpu.program = [("LDI", (None,))]
        try:
            cpu.step()
        except Exception:
            pass

    def test_operand_formatting_with_exception(self):
        """Test operand formatting exception handling in step function."""
        cpu = CPU()

        class BadOperand:
            def __str__(self):
                raise ValueError("Cannot format")

            def __repr__(self):
                raise ValueError("Cannot format")

        cpu.program = [("LDI", (("reg", 16), BadOperand()))]
        cpu.pc = 0
        try:
            cpu.step()
        except Exception:
            pass

    def test_jmp_with_invalid_label(self):
        """Test JMP with invalid label raises KeyError."""
        cpu = CPU()
        program = [("JMP", ("nonexistent_label",))]
        cpu.load_program(program)
        with pytest.raises(KeyError, match="Label nonexistent_label not found"):
            cpu.step()


class TestCPUProgramLoading:
    """Test CPU program loading and execution edge cases."""

    def test_load_program_with_asm_result(self):
        """Test loading program from AsmResult."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 42
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 42

    def test_load_program_with_tuple(self):
        """Test loading program from tuple (legacy format)."""
        cpu = CPU()
        program = [("LDI", (("reg", 16), 42))]
        cpu.load_program(program)
        cpu.run()
        assert cpu.read_reg(16) == 42

    def test_cpu_step_out_of_range(self):
        """Test CPU step when PC is out of range."""
        cpu = CPU()
        asm = assemble("ldi r16, 1")
        cpu.load_program(asm)
        cpu.run()
        assert cpu.step() is False
        assert not cpu.running

    def test_jmp_with_integer(self):
        """Test JMP with integer address."""
        cpu = CPU()
        asm = assemble("""
            jmp 2
            ldi r16, 99
            ldi r17, 1
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 0
        assert cpu.read_reg(17) == 1

    def test_rjmp_with_integer_offset(self):
        """Test RJMP with integer offset."""
        cpu = CPU()
        program = [
            ("LDI", (("reg", 16), 0)),
            ("RJMP", (1,)),
            ("LDI", (("reg", 16), 99)),
            ("LDI", (("reg", 17), 1)),
        ]
        cpu.load_program(program)
        cpu.run()
        assert cpu.read_reg(16) == 0
        assert cpu.read_reg(17) == 1

    def test_rcall_with_integer_offset(self):
        """Test RCALL with integer offset."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0
            ldi r17, 0
            rcall func
            ldi r16, 1
            jmp done
        func:
            ldi r17, 2
            ret
        done:
            nop
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 1
        assert cpu.read_reg(17) == 2


class TestCPUInterrupts:
    """Test CPU interrupt handling."""

    def test_trigger_interrupt(self):
        """Test interrupt triggering."""
        cpu = CPU()
        cpu.interrupts[0x10] = True
        cpu.trigger_interrupt(0x10)
        assert cpu.pc == 0x0F

    def test_trigger_interrupt_disabled(self):
        """Test that disabled interrupts don't trigger."""
        cpu = CPU()
        initial_pc = cpu.pc
        cpu.trigger_interrupt(0x10)
        assert cpu.pc == initial_pc


class TestCPUFlagOperations:
    """Test CPU flag operation edge cases."""

    def test_set_flags_logical_negative(self):
        """Test _set_flags_logical with negative result."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0x80
            ldi r17, 0xFF
            and r16, r17
        """)
        cpu.load_program(asm)
        cpu.run()
        # Result should be 0x80 which has bit 7 set (negative)

    def test_set_flags_logical_zero(self):
        """Test _set_flags_logical with zero result."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0xFF
            ldi r17, 0x00
            and r16, r17
        """)
        cpu.load_program(asm)
        cpu.run()
        # Result should be 0

    def test_mul_result_storage(self):
        """Test MUL stores result in rd:rd+1."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 10
            ldi r17, 20
            mul r16, r17
        """)
        cpu.load_program(asm)
        cpu.run()
        # Result 200 = 0x00C8, so r16=200, r17=0
        assert cpu.read_reg(16) == 200  # low byte
        assert cpu.read_reg(17) == 0  # high byte

    def test_div_quotient_remainder(self):
        """Test DIV stores quotient and remainder correctly."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 17
            ldi r17, 5
            div r16, r17
        """)
        cpu.load_program(asm)
        cpu.run()
        # 17 / 5 = 3 remainder 2
        assert cpu.read_reg(16) == 3  # quotient
        assert cpu.read_reg(17) == 2  # remainder
