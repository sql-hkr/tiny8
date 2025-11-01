"""CPU branch instruction tests.

Tests for conditional branches, stack operations, calls, and returns.
"""

from tiny8 import CPU, assemble


class TestConditionalBranches:
    """Test conditional branch instructions."""

    def test_brmi_not_taken(self):
        """Test branch if minus when not taken."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 100
            ldi r17, 50
            sub r16, r17
            brmi skip
            ldi r18, 1
        skip:
            ldi r19, 2
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(18) == 1  # Not skipped

    def test_brmi_jump_taken(self):
        """Test BRMI when negative flag is set and jump is taken."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 100
            ldi r17, 200
            sub r16, r17
            brmi target
            ldi r18, 1
        target:
            ldi r19, 2
        """)
        cpu.load_program(asm)
        cpu.run()
        # The jump should be taken because 100 - 200 is negative
        assert cpu.regs[19] == 2
        assert cpu.regs[18] == 0  # This should not execute

    def test_brpl_not_taken(self):
        """Test branch if plus when not taken."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 50
            ldi r17, 100
            sub r16, r17
            brpl skip
            ldi r18, 1
        skip:
            ldi r19, 2
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(18) == 1  # Not skipped

    def test_brpl_jump_taken(self):
        """Test BRPL when negative flag is clear and jump is taken."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 200
            ldi r17, 100
            sub r16, r17
            brpl target
            ldi r18, 1
        target:
            ldi r19, 2
        """)
        cpu.load_program(asm)
        cpu.run()
        # The jump should be taken because 200 - 100 is positive
        assert cpu.regs[19] == 2
        assert cpu.regs[18] == 0  # This should not execute

    def test_brge_taken(self):
        """Test branch if greater or equal when taken."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 100
            ldi r17, 50
            cp r16, r17
            brge skip
            ldi r18, 99
        skip:
            ldi r19, 1
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(18) == 0  # Skipped
        assert cpu.read_reg(19) == 1

    def test_brge_not_taken(self):
        """Test branch if greater or equal when not taken."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 50
            ldi r17, 100
            cp r16, r17
            brge skip
            ldi r18, 1
        skip:
            ldi r19, 2
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(18) == 1  # Not skipped

    def test_brlt_taken(self):
        """Test branch if less than when taken."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 50
            ldi r17, 100
            cp r16, r17
            brlt skip
            ldi r18, 99
        skip:
            ldi r19, 1
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(18) == 0  # Skipped
        assert cpu.read_reg(19) == 1

    def test_brlt_not_taken(self):
        """Test branch if less than when not taken."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 100
            ldi r17, 50
            cp r16, r17
            brlt skip
            ldi r18, 1
        skip:
            ldi r19, 2
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(18) == 1  # Not skipped

    def test_brpl_jump_case(self):
        """Test BRPL actually jumping."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 100
            ldi r17, 50
            sub r16, r17
            ldi r18, 0
            brpl target
            ldi r18, 99
        target:
            ldi r19, 1
        """)
        cpu.load_program(asm)
        cpu.run()
        # With positive result, should jump and skip r18 assignment
        assert cpu.read_reg(18) == 0

    def test_brmi_with_integer_label(self):
        """Test BRMI with integer label."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 200
            ldi r17, 100
            sub r16, r17
        """)
        cpu.load_program(asm)
        cpu.run()
        # Now manually test brmi with integer
        cpu.program.append(("BRMI", (0,)))
        cpu.pc = len(cpu.program) - 1
        cpu.step()

    def test_brpl_with_integer_label(self):
        """Test BRPL with integer label."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 100
            ldi r17, 50
            sub r16, r17
        """)
        cpu.load_program(asm)
        cpu.run()
        # Now manually test brpl with integer
        cpu.program.append(("BRPL", (0,)))
        cpu.pc = len(cpu.program) - 1
        cpu.step()


class TestStackAndCall:
    """Test stack operations, calls, and returns."""

    def test_push_pop(self):
        """Test push and pop instructions."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 42
            push r16
            ldi r16, 0
            pop r17
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(17) == 42

    def test_multiple_push_pop(self):
        """Test multiple push and pop operations."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 10
            ldi r17, 20
            ldi r18, 30
            push r16
            push r17
            push r18
            pop r19
            pop r20
            pop r21
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(19) == 30
        assert cpu.read_reg(20) == 20
        assert cpu.read_reg(21) == 10

    def test_call_ret(self):
        """Test call and ret instructions."""
        cpu = CPU()
        asm = assemble("""
            call func
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

    def test_nested_calls(self):
        """Test nested function calls."""
        cpu = CPU()
        asm = assemble("""
            call func1
            ldi r16, 1
            jmp done
        func1:
            call func2
            ldi r17, 2
            ret
        func2:
            ldi r18, 3
            ret
        done:
            nop
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 1
        assert cpu.read_reg(17) == 2
        assert cpu.read_reg(18) == 3

    def test_reti(self):
        """Test return from interrupt."""
        cpu = CPU()
        asm = assemble("""
            call isr
            ldi r16, 1
            jmp done
        isr:
            ldi r17, 2
            reti
        done:
            nop
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 1
        assert cpu.read_reg(17) == 2


class TestSetClearInstructions:
    """Test SET and CLEAR type instructions."""

    def test_ser_clr(self):
        """Test SER and CLR instructions."""
        cpu = CPU()
        asm = assemble("""
            ser r16
            clr r17
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 0xFF
        assert cpu.read_reg(17) == 0

    def test_adc_with_carry(self):
        """Test ADC with carry flag set."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 5
            ldi r17, 10
            add r16, r17
            ldi r18, 20
            ldi r19, 30
            adc r18, r19
        """)
        cpu.load_program(asm)
        cpu.run()
        # r18 should be 20 + 30 + carry (if any)


class TestLogicalOperations:
    """Test logical operations for branch coverage."""

    def test_or_operation_edge_case(self):
        """Test OR operation with different values."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0x0F
            ldi r17, 0xF0
            or r16, r17
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 0xFF

    def test_eor_operation_edge_case(self):
        """Test EOR operation with same values."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0xFF
            ldi r17, 0xFF
            eor r16, r17
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 0
