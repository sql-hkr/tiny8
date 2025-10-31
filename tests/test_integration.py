"""Integration tests for complete programs and examples.

Tests real-world programs like Fibonacci and bubble sort.
"""

import pytest


class TestBubbleSort:
    """Test bubble sort program."""

    @pytest.mark.slow
    def test_bubblesort_example(self, cpu_from_file, helper):
        """Test the bubble sort example program."""
        cpu = cpu_from_file("examples/bubblesort.asm", max_steps=15000)

        # Read sorted array from memory
        sorted_array = [cpu.read_ram(i) for i in range(100, 132)]

        # Verify array is sorted
        for i in range(len(sorted_array) - 1):
            assert sorted_array[i] >= sorted_array[i + 1], (
                f"Array not sorted at index {i}: {sorted_array[i]} > {sorted_array[i + 1]}"
            )

    @pytest.mark.slow
    def test_bubblesort_deterministic(self, cpu_from_file):
        """Test that bubble sort produces consistent results."""
        # Run twice and compare
        from tiny8 import CPU, assemble_file

        asm = assemble_file("examples/bubblesort.asm")

        cpu1 = CPU()
        cpu1.load_program(asm)
        cpu1.run(max_steps=15000)
        result1 = [cpu1.read_ram(i) for i in range(100, 132)]

        cpu2 = CPU()
        cpu2.load_program(asm)
        cpu2.run(max_steps=15000)
        result2 = [cpu2.read_ram(i) for i in range(100, 132)]

        # Both should produce identical sorted results
        assert result1 == result2, "Bubble sort should be deterministic"


class TestCPUState:
    """Test CPU state management and inspection."""

    def test_register_read_write(self, cpu, helper):
        """Test reading and writing registers."""
        # Registers are 8-bit, so values are masked to 0-255
        for i in range(32):
            value = (i * 10) & 0xFF
            cpu.write_reg(i, value)
            helper.assert_register(cpu, i, value)

    def test_memory_read_write(self, cpu, helper):
        """Test reading and writing memory."""
        # RAM size is 2048 by default, so test addresses within that range
        for addr in [0, 100, 255, 1000, 2047]:
            cpu.write_ram(addr, addr & 0xFF)
            helper.assert_memory(cpu, addr, addr & 0xFF)

    def test_flag_operations(self, cpu, helper):
        """Test flag get/set operations."""
        from tiny8.cpu import SREG_C, SREG_N, SREG_V, SREG_Z

        for flag in [SREG_C, SREG_Z, SREG_N, SREG_V]:
            cpu.set_flag(flag, True)
            helper.assert_flag(cpu, flag, True)
            cpu.set_flag(flag, False)
            helper.assert_flag(cpu, flag, False)

    def test_pc_sp_operations(self, cpu):
        """Test PC and SP get/set operations."""
        # PC and SP are directly accessible attributes
        cpu.pc = 0x100
        assert cpu.pc == 0x100

        cpu.sp = 0x500
        assert cpu.sp == 0x500

    def test_step_trace(self, cpu_with_program):
        """Test that step trace is recorded."""
        cpu = cpu_with_program("""
            ldi r0, 10
            ldi r1, 20
            add r0, r1
        """)

        assert hasattr(cpu, "step_trace"), "CPU should have step_trace"
        assert len(cpu.step_trace) > 0, "Step trace should not be empty"

        # Verify trace contains expected keys
        for entry in cpu.step_trace:
            assert "pc" in entry
            assert "sp" in entry
            assert "sreg" in entry
            assert "regs" in entry
            assert "mem" in entry


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_register_number(self, cpu):
        """Test that invalid register access is handled."""
        # Registers are 0-31, accessing outside should fail gracefully
        with pytest.raises((IndexError, ValueError)):
            cpu.write_reg(32, 100)

    def test_infinite_loop_protection(self, cpu):
        """Test that max_steps prevents infinite loops."""
        from tiny8 import assemble

        asm = assemble("""
        loop:
            jmp loop
        """)
        cpu.load_program(asm)
        cpu.run(max_steps=100)

        # Should stop after 100 steps
        assert len(cpu.step_trace) <= 100

    def test_empty_program(self, cpu):
        """Test running with no program loaded."""
        from tiny8 import assemble

        asm = assemble("")
        cpu.load_program(asm)
        cpu.run(max_steps=10)

        # Should handle gracefully
        assert True


class TestAssembler:
    """Test assembler features."""

    def test_assemble_comments(self, cpu_with_program, helper):
        """Test that comments are properly ignored."""
        cpu = cpu_with_program("""
            ; This is a comment
            ldi r0, 42  ; Inline comment
            ldi r1, 99
            ; Another comment
            add r0, r1  ; Final comment
        """)
        helper.assert_register(cpu, 0, 141)

    def test_assemble_labels(self, cpu_with_program, helper):
        """Test label resolution."""
        cpu = cpu_with_program("""
        start:
            ldi r0, 0
            jmp middle
        skip:
            ldi r0, 99
        middle:
            ldi r0, 42
        """)
        helper.assert_register(cpu, 0, 42)

    def test_assemble_number_formats(self, cpu_with_program, helper):
        """Test different number format support."""
        cpu = cpu_with_program("""
            ldi r16, 255        ; Decimal
            ldi r17, $FF        ; Hex $
            ldi r18, 0xFF       ; Hex 0x
            ldi r19, 0b11111111 ; Binary
        """)
        for reg in [16, 17, 18, 19]:
            helper.assert_register(cpu, reg, 255)

    def test_assemble_case_insensitive(self, cpu_with_program, helper):
        """Test that mnemonics are case-insensitive."""
        cpu = cpu_with_program("""
            LDI r0, 10
            ldi r1, 20
            ADD r0, r1
            add r2, r0
        """)
        helper.assert_registers(cpu, {0: 30, 1: 20})


class TestPerformance:
    """Performance and stress tests."""

    @pytest.mark.slow
    def test_long_execution(self, cpu_with_program, helper):
        """Test program with many iterations."""
        cpu = cpu_with_program(
            """
            ldi r0, 0
            ldi r1, 100
        loop:
            inc r0
            dec r1
            brne loop
        """,
            max_steps=10000,
        )
        helper.assert_register(cpu, 0, 100)

    @pytest.mark.slow
    def test_deep_call_stack(self, cpu_with_program, helper):
        """Test deep recursion-like call stack."""
        # Create a chain of calls
        calls = "\n".join([f"call func{i}" for i in range(10)])
        funcs = "\n".join([f"func{i}:\n    nop\n    ret" for i in range(10)])

        cpu = cpu_with_program(
            f"""
            ldi r0, 0
            {calls}
            jmp done
            {funcs}
        done:
            nop
        """,
            max_steps=5000,
        )
        # Should complete without stack overflow
        assert True

    @pytest.mark.slow
    def test_large_memory_operations(self, cpu_with_program, helper):
        """Test operations on large memory ranges."""
        # Write to 256 memory locations
        writes = "\n".join(
            [f"ldi r0, {i}\nldi r1, {i}\nst r0, r1" for i in range(0, 256, 10)]
        )

        cpu = cpu_with_program(writes, max_steps=10000)

        # Verify some values
        for i in range(0, 256, 10):
            helper.assert_memory(cpu, i, i)


@pytest.mark.integration
class TestCompletePrograms:
    """Integration tests for complete, realistic programs."""

    def test_sum_array(self, cpu_with_program, helper):
        """Test program that sums an array in memory."""
        cpu = cpu_with_program("""
            ; Initialize array [100-104] = [10, 20, 30, 40, 50]
            ldi r0, 100
            ldi r1, 10
            st r0, r1
            inc r0
            ldi r1, 20
            st r0, r1
            inc r0
            ldi r1, 30
            st r0, r1
            inc r0
            ldi r1, 40
            st r0, r1
            inc r0
            ldi r1, 50
            st r0, r1
            
            ; Sum array
            ldi r2, 0       ; sum
            ldi r3, 100     ; address
            ldi r4, 5       ; count
        loop:
            ld r5, r3
            add r2, r5
            inc r3
            dec r4
            brne loop
        """)
        helper.assert_register(cpu, 2, 150)  # 10+20+30+40+50

    def test_find_maximum(self, cpu_with_program, helper):
        """Test program that finds maximum value in array."""
        cpu = cpu_with_program("""
            ; Initialize array
            ldi r0, 100
            ldi r1, 25
            st r0, r1
            inc r0
            ldi r1, 75
            st r0, r1
            inc r0
            ldi r1, 42
            st r0, r1
            inc r0
            ldi r1, 99
            st r0, r1
            inc r0
            ldi r1, 10
            st r0, r1
            
            ; Find max
            ldi r2, 100     ; address
            ld r3, r2       ; max = first element
            ldi r4, 4       ; remaining count
        loop:
            inc r2
            ld r5, r2
            cp r3, r5
            brcs update_max
            jmp check_done
        update_max:
            mov r3, r5
        check_done:
            dec r4
            brne loop
        """)
        helper.assert_register(cpu, 3, 99)  # Maximum value
