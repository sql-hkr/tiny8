"""Test suite for control flow instructions.

Covers: JMP, RJMP, CALL, RCALL, RET, RETI, BR* (branches), CP, CPI, CPSE
"""

import pytest

from tiny8.cpu import SREG_C, SREG_Z


class TestJMP:
    """Test JMP and RJMP (Jump) instructions."""

    def test_jmp_forward(self, cpu_with_program, helper):
        """Test jumping forward to a label."""
        cpu = cpu_with_program("""
            ldi r0, 0
            jmp skip
            ldi r0, 99
        skip:
            ldi r0, 42
        """)
        helper.assert_register(cpu, 0, 42)

    def test_jmp_backward_loop(self, cpu_with_program, helper):
        """Test backward jump creating a loop."""
        cpu = cpu_with_program("""
            ldi r0, 0
            ldi r1, 5
        loop:
            inc r0
            dec r1
            brne loop
        """)
        helper.assert_register(cpu, 0, 5)

    def test_conditional_jump_pattern(self, cpu_with_program, helper):
        """Test conditional execution with jumps."""
        cpu = cpu_with_program("""
            ldi r0, 10
            ldi r1, 10
            cp r0, r1
            brne not_equal
            ldi r2, 1
            jmp done
        not_equal:
            ldi r2, 0
        done:
            nop
        """)
        helper.assert_register(cpu, 2, 1)  # Should take equal branch


class TestBranches:
    """Test conditional branch instructions."""

    def test_brne_branch_taken(self, cpu_with_program, helper):
        """Test BRNE when Z=0 (not equal)."""
        cpu = cpu_with_program("""
            ldi r0, 5
            ldi r1, 10
            cp r0, r1
            brne taken
            ldi r2, 0
            jmp done
        taken:
            ldi r2, 1
        done:
            nop
        """)
        helper.assert_register(cpu, 2, 1)

    def test_brne_branch_not_taken(self, cpu_with_program, helper):
        """Test BRNE when Z=1 (equal)."""
        cpu = cpu_with_program("""
            ldi r0, 10
            ldi r1, 10
            cp r0, r1
            brne taken
            ldi r2, 0
            jmp done
        taken:
            ldi r2, 1
        done:
            nop
        """)
        helper.assert_register(cpu, 2, 0)

    def test_breq_branch_taken(self, cpu_with_program, helper):
        """Test BREQ when Z=1 (equal)."""
        cpu = cpu_with_program("""
            ldi r0, 42
            ldi r1, 42
            cp r0, r1
            breq equal
            ldi r2, 0
            jmp done
        equal:
            ldi r2, 1
        done:
            nop
        """)
        helper.assert_register(cpu, 2, 1)

    def test_brcs_carry_set(self, cpu_with_program, helper):
        """Test BRCS when carry flag is set."""
        cpu = cpu_with_program("""
            ldi r0, 5
            ldi r1, 10
            cp r0, r1
            brcs carry_set
            ldi r2, 0
            jmp done
        carry_set:
            ldi r2, 1
        done:
            nop
        """)
        helper.assert_register(cpu, 2, 1)

    def test_brcc_carry_clear(self, cpu_with_program, helper):
        """Test BRCC when carry flag is clear."""
        cpu = cpu_with_program("""
            ldi r0, 10
            ldi r1, 5
            cp r0, r1
            brcc carry_clear
            ldi r2, 0
            jmp done
        carry_clear:
            ldi r2, 1
        done:
            nop
        """)
        helper.assert_register(cpu, 2, 1)

    def test_brge_greater_equal(self, cpu_with_program, helper):
        """Test BRGE (branch if greater or equal, signed)."""
        cpu = cpu_with_program("""
            ldi r0, 10
            ldi r1, 5
            cp r0, r1
            brge greater
            ldi r2, 0
            jmp done
        greater:
            ldi r2, 1
        done:
            nop
        """)
        helper.assert_register(cpu, 2, 1)

    def test_brlt_less_than(self, cpu_with_program, helper):
        """Test BRLT (branch if less than, signed)."""
        cpu = cpu_with_program("""
            ldi r0, 5
            ldi r1, 10
            cp r0, r1
            brlt less
            ldi r2, 0
            jmp done
        less:
            ldi r2, 1
        done:
            nop
        """)
        helper.assert_register(cpu, 2, 1)

    @pytest.mark.parametrize(
        "a,b,branch,expected",
        [
            (10, 10, "breq", 1),  # Equal
            (10, 5, "brne", 1),  # Not equal
            (5, 10, "brcs", 1),  # Carry set (a < b)
            (10, 5, "brcc", 1),  # Carry clear (a >= b)
        ],
    )
    def test_branches_parametrized(
        self, cpu_with_program, helper, a, b, branch, expected
    ):
        """Test various branch conditions."""
        cpu = cpu_with_program(f"""
            ldi r0, {a}
            ldi r1, {b}
            cp r0, r1
            {branch} taken
            ldi r2, 0
            jmp done
        taken:
            ldi r2, 1
        done:
            nop
        """)
        helper.assert_register(cpu, 2, expected)


class TestCALL:
    """Test CALL and RET (Subroutine call/return) instructions."""

    def test_call_ret_basic(self, cpu_with_program, helper):
        """Test basic subroutine call and return."""
        cpu = cpu_with_program("""
            ldi r0, 0
            call increment
            jmp done
        increment:
            inc r0
            ret
        done:
            nop
        """)
        helper.assert_register(cpu, 0, 1)

    def test_call_with_parameters(self, cpu_with_program, helper):
        """Test subroutine with register parameters."""
        cpu = cpu_with_program("""
            ldi r0, 10
            ldi r1, 20
            call add_nums
            jmp done
        add_nums:
            add r0, r1
            ret
        done:
            nop
        """)
        helper.assert_register(cpu, 0, 30)

    def test_nested_calls(self, cpu_with_program, helper):
        """Test nested subroutine calls."""
        cpu = cpu_with_program("""
            ldi r0, 5
            call double
            jmp done
        double:
            call add_self
            ret
        add_self:
            add r0, r0
            ret
        done:
            nop
        """)
        helper.assert_register(cpu, 0, 10)

    def test_call_preserves_registers(self, cpu_with_program, helper):
        """Test that subroutine can preserve registers via stack."""
        cpu = cpu_with_program("""
            ldi r0, 100
            ldi r1, 200
            call modify_r0
            jmp done
        modify_r0:
            push r1
            ldi r1, 50
            add r0, r1
            pop r1
            ret
        done:
            nop
        """)
        # 100 + 50 = 150, r1 should be preserved as 200
        helper.assert_registers(cpu, {0: 150, 1: 200})


class TestCompare:
    """Test CP, CPC, CPI (Compare) instructions."""

    def test_cp_equal(self, cpu_with_program, helper):
        """Test CP when values are equal."""
        cpu = cpu_with_program("""
            ldi r0, 42
            ldi r1, 42
            cp r0, r1
        """)
        helper.assert_flag(cpu, SREG_Z, True, "Z")
        helper.assert_flag(cpu, SREG_C, False, "C")

    def test_cp_less_than(self, cpu_with_program, helper):
        """Test CP when first < second."""
        cpu = cpu_with_program("""
            ldi r0, 10
            ldi r1, 20
            cp r0, r1
        """)
        helper.assert_flag(cpu, SREG_C, True, "C")  # Borrow set
        helper.assert_flag(cpu, SREG_Z, False, "Z")

    def test_cp_greater_than(self, cpu_with_program, helper):
        """Test CP when first > second."""
        cpu = cpu_with_program("""
            ldi r0, 20
            ldi r1, 10
            cp r0, r1
        """)
        helper.assert_flag(cpu, SREG_C, False, "C")
        helper.assert_flag(cpu, SREG_Z, False, "Z")

    def test_cpi_immediate(self, cpu_with_program, helper):
        """Test CPI with immediate value."""
        cpu = cpu_with_program("""
            ldi r16, 100
            cpi r16, 100
        """)
        helper.assert_flag(cpu, SREG_Z, True, "Z")

    def test_cpse_skip_if_equal(self, cpu_with_program, helper):
        """Test CPSE skips next instruction when equal."""
        cpu = cpu_with_program("""
            ldi r0, 42
            ldi r1, 42
            ldi r2, 0
            cpse r0, r1
            ldi r2, 99
        """)
        helper.assert_register(cpu, 2, 0)  # LDI should be skipped

    def test_cpse_no_skip_if_not_equal(self, cpu_with_program, helper):
        """Test CPSE doesn't skip when not equal."""
        cpu = cpu_with_program("""
            ldi r0, 42
            ldi r1, 43
            ldi r2, 0
            cpse r0, r1
            ldi r2, 99
        """)
        helper.assert_register(cpu, 2, 99)  # LDI should execute


class TestLoops:
    """Integration tests for loop patterns."""

    def test_count_up_loop(self, cpu_with_program, helper):
        """Test counting up with loop."""
        cpu = cpu_with_program("""
            ldi r0, 0
            ldi r1, 0
            ldi r2, 10
        loop:
            inc r0
            inc r1
            cp r1, r2
            brne loop
        """)
        helper.assert_register(cpu, 0, 10)
        helper.assert_register(cpu, 1, 10)

    def test_count_down_loop(self, cpu_with_program, helper):
        """Test counting down with loop."""
        cpu = cpu_with_program("""
            ldi r0, 0
            ldi r1, 10
        loop:
            inc r0
            dec r1
            brne loop
        """)
        helper.assert_register(cpu, 0, 10)
        helper.assert_register(cpu, 1, 0)

    def test_nested_loops(self, cpu_with_program, helper):
        """Test nested loop structure."""
        cpu = cpu_with_program("""
            ldi r0, 0
            ldi r1, 3
        outer:
            ldi r2, 2
        inner:
            inc r0
            dec r2
            brne inner
            dec r1
            brne outer
        """)
        helper.assert_register(cpu, 0, 6)  # 3 * 2

    def test_while_loop_pattern(self, cpu_with_program, helper):
        """Test while loop pattern with condition at start."""
        cpu = cpu_with_program("""
            ldi r0, 0
            ldi r1, 5
        loop:
            cp r1, r0
            breq done
            inc r0
            jmp loop
        done:
            nop
        """)
        helper.assert_register(cpu, 0, 5)

    @pytest.mark.parametrize("count,expected", [(1, 1), (5, 5), (10, 10), (20, 20)])
    def test_loop_iterations_parametrized(
        self, cpu_with_program, helper, count, expected
    ):
        """Test loop with different iteration counts."""
        cpu = cpu_with_program(f"""
            ldi r0, 0
            ldi r1, {count}
        loop:
            inc r0
            dec r1
            brne loop
        """)
        helper.assert_register(cpu, 0, expected)


class TestControlFlowIntegration:
    """Complex integration tests for control flow."""

    def test_if_else_pattern(self, cpu_with_program, helper):
        """Test if-else control structure."""
        cpu = cpu_with_program("""
            ldi r0, 10
            ldi r1, 5
            ldi r2, 0
            cp r0, r1
            brcs else_branch
            ldi r2, 1
            jmp endif
        else_branch:
            ldi r2, 2
        endif:
            nop
        """)
        helper.assert_register(cpu, 2, 1)

    def test_switch_case_pattern(self, cpu_with_program, helper):
        """Test switch-case like pattern."""
        cpu = cpu_with_program("""
            ldi r0, 2
            ldi r1, 0
            cpi r0, 1
            breq case1
            cpi r0, 2
            breq case2
            cpi r0, 3
            breq case3
            jmp default
        case1:
            ldi r1, 10
            jmp endswitch
        case2:
            ldi r1, 20
            jmp endswitch
        case3:
            ldi r1, 30
            jmp endswitch
        default:
            ldi r1, 99
        endswitch:
            nop
        """)
        helper.assert_register(cpu, 1, 20)

    def test_function_with_early_return(self, cpu_with_program, helper):
        """Test function with multiple return points."""
        cpu = cpu_with_program("""
            ldi r0, 0
            call check_value
            jmp done
        check_value:
            cpi r0, 0
            brne not_zero
            ldi r1, 100
            ret
        not_zero:
            ldi r1, 200
            ret
        done:
            nop
        """)
        helper.assert_register(cpu, 1, 100)
