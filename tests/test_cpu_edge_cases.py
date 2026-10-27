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

    def test_operand_formatting_none_operand(self):
        """Test formatting instruction when operand list contains None."""
        cpu = CPU()
        cpu.program = [("NOP", ())]
        cpu._build_predecoded()
        assert cpu._predecoded[0][2] == "NOP"

    def test_operand_formatting_with_exception(self):
        """Test operand formatting fallback when operand str() raises an exception."""
        cpu = CPU()

        class BadOperand:
            def __str__(self):
                raise ValueError("Cannot format")

            def __repr__(self):
                raise ValueError("Cannot format")

        cpu.program = [("LDI", (("reg", 16), BadOperand()))]
        cpu._build_predecoded()
        # Fallback catches the exception and falls back to base instruction mnemonic
        assert cpu._predecoded[0][2] == "LDI"

    def test_jmp_with_invalid_label(self):
        """Test JMP with invalid label raises KeyError."""
        cpu = CPU()
        program = [("JMP", ("nonexistent_label",))]
        cpu.load_program(program)
        with pytest.raises(KeyError, match="Label nonexistent_label not found"):
            cpu.step()

    def test_run_rebuilds_predecoded_when_missing_or_mismatched(self):
        """Test fast-path rebuilds predecoded list when missing or length mismatched."""
        cpu = CPU(trace_enabled=False)
        cpu.load_program([("NOP", ())])
        cpu._predecoded = []
        cpu.run(max_steps=10, show_progress=False)
        assert cpu.step_count == 1
        assert len(cpu._predecoded) == 1

    def test_run_fast_path_not_implemented_instruction(self):
        """Test fast-path raises NotImplementedError for unknown instructions."""
        cpu = CPU(trace_enabled=False)
        cpu.load_program([("UNKNOWN_OPCODE", ())])
        with pytest.raises(
            NotImplementedError, match="Instruction UNKNOWN_OPCODE not implemented"
        ):
            cpu.run(max_steps=10, show_progress=False)


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
        from tiny8.cpu import SREG_N, SREG_S, SREG_V, SREG_Z

        cpu = CPU()
        asm = assemble("""
            ldi r16, 0x80
            ldi r17, 0xFF
            and r16, r17
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 0x80
        assert cpu.get_flag(SREG_N) is True
        assert cpu.get_flag(SREG_Z) is False
        assert cpu.get_flag(SREG_V) is False
        assert cpu.get_flag(SREG_S) is True

    def test_set_flags_logical_zero(self):
        """Test _set_flags_logical with zero result."""
        from tiny8.cpu import SREG_N, SREG_S, SREG_V, SREG_Z

        cpu = CPU()
        asm = assemble("""
            ldi r16, 0xFF
            ldi r17, 0x00
            and r16, r17
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 0x00
        assert cpu.get_flag(SREG_Z) is True
        assert cpu.get_flag(SREG_N) is False
        assert cpu.get_flag(SREG_V) is False
        assert cpu.get_flag(SREG_S) is False

    def test_mul_result_storage(self):
        """Test MUL stores result in R1:R0 per AVR DS40002198A."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 10
            ldi r17, 20
            mul r16, r17
        """)
        cpu.load_program(asm)
        cpu.run()
        # Result 200 = 0x00C8, so r0=200, r1=0
        assert cpu.read_reg(0) == 200  # low byte in R0
        assert cpu.read_reg(1) == 0  # high byte in R1


class TestSREGCompliance:
    """Comprehensive tests for AVR DS40002198A Status Register (SREG) compliance."""

    def test_sreg_bit_positions(self):
        """Verify exact SREG bit indices: I=7, T=6, H=5, S=4, V=3, N=2, Z=1, C=0."""
        from tiny8.cpu import (
            SREG_C,
            SREG_H,
            SREG_I,
            SREG_N,
            SREG_S,
            SREG_T,
            SREG_V,
            SREG_Z,
        )

        cpu = CPU()
        flags = [
            (SREG_C, 0, 0x01),
            (SREG_Z, 1, 0x02),
            (SREG_N, 2, 0x04),
            (SREG_V, 3, 0x08),
            (SREG_S, 4, 0x10),
            (SREG_H, 5, 0x20),
            (SREG_T, 6, 0x40),
            (SREG_I, 7, 0x80),
        ]
        for flag_const, bit_idx, bit_mask in flags:
            assert flag_const == bit_idx
            cpu.sreg = 0
            cpu.set_flag(flag_const, True)
            assert cpu.sreg == bit_mask
            assert cpu.get_flag(flag_const) is True
            cpu.set_flag(flag_const, False)
            assert cpu.sreg == 0
            assert cpu.get_flag(flag_const) is False

    def test_sreg_flags_add_half_carry_and_overflow(self):
        """Test ADD calculates H, V, S, N, Z, C and preserves I, T."""
        from tiny8.cpu import (
            SREG_C,
            SREG_H,
            SREG_I,
            SREG_N,
            SREG_S,
            SREG_T,
            SREG_V,
            SREG_Z,
        )

        cpu = CPU()
        cpu.set_flag(SREG_I, True)
        cpu.set_flag(SREG_T, True)
        # 0x0F + 0x01 = 0x10 (Half Carry set, no overflow, no carry, not zero)
        cpu._set_flags_add(0x0F, 0x01, 0, 0x10)
        assert cpu.get_flag(SREG_I) is True
        assert cpu.get_flag(SREG_T) is True
        assert cpu.get_flag(SREG_H) is True
        assert cpu.get_flag(SREG_C) is False
        assert cpu.get_flag(SREG_Z) is False
        assert cpu.get_flag(SREG_N) is False
        assert cpu.get_flag(SREG_V) is False
        assert cpu.get_flag(SREG_S) is False

        # Signed overflow: 127 + 1 = 128 (0x7F + 0x01 = 0x80)
        # Pos + Pos = Neg -> V=1, N=1, S = N ^ V = 0
        cpu._set_flags_add(0x7F, 0x01, 0, 0x80)
        assert cpu.get_flag(SREG_V) is True
        assert cpu.get_flag(SREG_N) is True
        assert cpu.get_flag(SREG_S) is False
        assert cpu.get_flag(SREG_H) is True
        assert cpu.get_flag(SREG_C) is False

    def test_sreg_flags_sub_half_borrow_and_overflow(self):
        """Test SUB calculates H, V, S, N, Z, C and preserves I, T."""
        from tiny8.cpu import (
            SREG_C,
            SREG_H,
            SREG_N,
            SREG_S,
            SREG_V,
            SREG_Z,
        )

        cpu = CPU()
        # 0x10 - 0x01 = 0x0F (Half borrow: (0 - 1) < 0 -> H=1, no unsigned borrow -> C=0)
        cpu._set_flags_sub(0x10, 0x01, 0, 0x0F)
        assert cpu.get_flag(SREG_H) is True
        assert cpu.get_flag(SREG_C) is False
        assert cpu.get_flag(SREG_Z) is False
        assert cpu.get_flag(SREG_N) is False
        assert cpu.get_flag(SREG_V) is False
        assert cpu.get_flag(SREG_S) is False

        # Signed underflow: -128 - 1 = +127 (0x80 - 0x01 = 0x7F)
        # Neg - Pos = Pos -> V=1, N=0, S = N ^ V = 1
        cpu._set_flags_sub(0x80, 0x01, 0, 0x7F)
        assert cpu.get_flag(SREG_V) is True
        assert cpu.get_flag(SREG_N) is False
        assert cpu.get_flag(SREG_S) is True
        assert cpu.get_flag(SREG_C) is False

    def test_sreg_logical_preserves_c_h_t_i(self):
        """Test logical ops (AND, OR, EOR) clear V, set S=N, and preserve C, H, T, I."""
        from tiny8.cpu import (
            SREG_C,
            SREG_H,
            SREG_I,
            SREG_N,
            SREG_S,
            SREG_T,
            SREG_V,
            SREG_Z,
        )

        cpu = CPU()
        cpu.set_flag(SREG_C, True)
        cpu.set_flag(SREG_H, True)
        cpu.set_flag(SREG_T, True)
        cpu.set_flag(SREG_I, True)
        cpu.set_flag(SREG_V, True)

        # Result is 0x80 (Negative, non-zero)
        cpu._set_flags_logical(0x80)
        assert cpu.get_flag(SREG_C) is True  # Preserved
        assert cpu.get_flag(SREG_H) is True  # Preserved
        assert cpu.get_flag(SREG_T) is True  # Preserved
        assert cpu.get_flag(SREG_I) is True  # Preserved
        assert cpu.get_flag(SREG_V) is False  # Cleared
        assert cpu.get_flag(SREG_N) is True  # Set
        assert cpu.get_flag(SREG_S) is True  # S = N ^ V = 1 ^ 0 = 1
        assert cpu.get_flag(SREG_Z) is False  # Non-zero

    def test_sreg_inc_dec_preserves_c_h_t_i(self):
        """Test INC and DEC preserve C, H, T, I while updating S, V, N, Z."""
        from tiny8.cpu import (
            SREG_C,
            SREG_H,
            SREG_I,
            SREG_N,
            SREG_S,
            SREG_T,
            SREG_V,
            SREG_Z,
        )

        cpu = CPU()
        cpu.set_flag(SREG_C, True)
        cpu.set_flag(SREG_H, True)
        cpu.set_flag(SREG_T, True)
        cpu.set_flag(SREG_I, True)

        # INC from 0x7F to 0x80 -> Signed overflow V=1, N=1, S=0
        cpu._set_flags_inc(0x7F, 0x80)
        assert cpu.get_flag(SREG_C) is True  # Preserved
        assert cpu.get_flag(SREG_H) is True  # Preserved
        assert cpu.get_flag(SREG_T) is True  # Preserved
        assert cpu.get_flag(SREG_I) is True  # Preserved
        assert cpu.get_flag(SREG_V) is True
        assert cpu.get_flag(SREG_N) is True
        assert cpu.get_flag(SREG_S) is False
        assert cpu.get_flag(SREG_Z) is False

        # DEC from 0x80 to 0x7F -> Signed overflow V=1, N=0, S=1
        cpu._set_flags_dec(0x80, 0x7F)
        assert cpu.get_flag(SREG_C) is True  # Preserved
        assert cpu.get_flag(SREG_H) is True  # Preserved
        assert cpu.get_flag(SREG_V) is True
        assert cpu.get_flag(SREG_N) is False
        assert cpu.get_flag(SREG_S) is True
        assert cpu.get_flag(SREG_Z) is False

    def test_cpu_fast_path_run_and_invoker(self):
        """Test CPU fast-path execution loop without progress or tracing."""
        from tiny8.cpu import _make_invoker

        cpu = CPU()
        cpu.trace_enabled = False
        asm = assemble("""
            ldi r16, 1
            ldi r17, 2
            add r16, r17
        """)
        cpu.load_program(asm)
        cpu.run(show_progress=False)
        assert cpu.read_reg(16) == 3

        # Test _make_invoker with 3+ operands fallback
        called_args = []

        def dummy_handler(a, b, c):
            called_args.extend([a, b, c])

        inv_n = _make_invoker(dummy_handler, (1, 2, 3))
        assert inv_n is not None
        inv_n()
        assert called_args == [1, 2, 3]
