"""Test suite for data transfer instructions.

Covers: LDI, MOV, LD, ST, IN, OUT, PUSH, POP, LDS, STS
"""

import pytest


class TestLDI:
    """Test LDI (Load Immediate) instruction."""

    def test_ldi_basic(self, cpu_with_program, helper):
        """Test loading immediate values into registers."""
        cpu = cpu_with_program("""
            ldi r16, 42
            ldi r17, 0xFF
            ldi r18, 0x00
        """)
        helper.assert_registers(cpu, {16: 42, 17: 255, 18: 0})

    def test_ldi_hex_binary_formats(self, cpu_with_program, helper):
        """Test different number formats in LDI."""
        cpu = cpu_with_program("""
            ldi r20, $FF
            ldi r21, 0xFF
            ldi r22, 0b11111111
            ldi r23, 255
        """)
        for reg in [20, 21, 22, 23]:
            helper.assert_register(cpu, reg, 255)

    @pytest.mark.parametrize(
        "reg,value", [(16, 0), (17, 1), (18, 127), (19, 128), (20, 255)]
    )
    def test_ldi_parametrized(self, cpu_with_program, helper, reg, value):
        """Test LDI with various registers and values."""
        cpu = cpu_with_program(f"""
            ldi r{reg}, {value}
        """)
        helper.assert_register(cpu, reg, value)


class TestMOV:
    """Test MOV (Copy register) instruction."""

    def test_mov_basic(self, cpu_with_program, helper):
        """Test copying value between registers."""
        cpu = cpu_with_program("""
            ldi r0, 123
            mov r1, r0
        """)
        helper.assert_register(cpu, 1, 123)

    def test_mov_chain(self, cpu_with_program, helper):
        """Test chaining MOV operations."""
        cpu = cpu_with_program("""
            ldi r0, 42
            mov r1, r0
            mov r2, r1
            mov r3, r2
        """)
        for reg in [0, 1, 2, 3]:
            helper.assert_register(cpu, reg, 42)

    def test_mov_preserves_source(self, cpu_with_program, helper):
        """Test that MOV doesn't modify source register."""
        cpu = cpu_with_program("""
            ldi r0, 100
            mov r1, r0
            ldi r2, 200
            mov r3, r2
        """)
        helper.assert_registers(cpu, {0: 100, 1: 100, 2: 200, 3: 200})


class TestLDST:
    """Test LD (Load from RAM) and ST (Store to RAM) instructions."""

    def test_st_ld_basic(self, cpu_with_program, helper):
        """Test storing and loading from memory."""
        cpu = cpu_with_program("""
            ldi r16, 100       ; Address
            ldi r17, 42        ; Value
            st r16, r17        ; Store value to MEM[100]
            ldi r18, 0         ; Clear r18
            ld r18, r16        ; Load from MEM[100]
        """)
        helper.assert_register(cpu, 18, 42)
        helper.assert_memory(cpu, 100, 42)

    def test_st_multiple_addresses(self, cpu_with_program, helper):
        """Test storing to multiple memory locations."""
        cpu = cpu_with_program("""
            ldi r20, 100
            ldi r21, 11
            st r20, r21
            
            ldi r20, 101
            ldi r21, 22
            st r20, r21
            
            ldi r20, 102
            ldi r21, 33
            st r20, r21
        """)
        helper.assert_memory(cpu, 100, 11)
        helper.assert_memory(cpu, 101, 22)
        helper.assert_memory(cpu, 102, 33)

    def test_ld_uninitialized_memory(self, cpu_with_program, helper):
        """Test loading from uninitialized memory returns 0."""
        cpu = cpu_with_program("""
            ldi r16, 200
            ld r17, r16
        """)
        helper.assert_register(cpu, 17, 0)

    def test_memory_array_operations(self, cpu_with_program, helper):
        """Test writing and reading array in memory."""
        cpu = cpu_with_program("""
            ; Write array [10, 20, 30, 40, 50]
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
        """)
        for i, value in enumerate([10, 20, 30, 40, 50]):
            helper.assert_memory(cpu, 100 + i, value)


class TestINOUT:
    """Test IN (Input from port) and OUT (Output to port) instructions."""

    def test_out_in_basic(self, cpu_with_program, helper):
        """Test writing and reading I/O ports."""
        cpu = cpu_with_program("""
            ldi r16, 123
            out 50, r16
            in r17, 50
        """)
        helper.assert_register(cpu, 17, 123)
        helper.assert_memory(cpu, 50, 123)

    def test_out_multiple_ports(self, cpu_with_program, helper):
        """Test writing to multiple I/O ports."""
        cpu = cpu_with_program("""
            ldi r20, 10
            out 0x10, r20
            ldi r21, 20
            out 0x20, r21
            ldi r22, 30
            out 0x30, r22
        """)
        helper.assert_memory(cpu, 0x10, 10)
        helper.assert_memory(cpu, 0x20, 20)
        helper.assert_memory(cpu, 0x30, 30)


class TestPUSHPOP:
    """Test PUSH and POP (Stack operations) instructions."""

    def test_push_pop_basic(self, cpu_with_program, helper):
        """Test basic stack push and pop."""
        cpu = cpu_with_program("""
            ldi r16, 42
            push r16
            ldi r16, 0
            pop r17
        """)
        helper.assert_register(cpu, 17, 42)

    def test_push_pop_multiple(self, cpu_with_program, helper):
        """Test multiple push/pop operations (LIFO)."""
        cpu = cpu_with_program("""
            ldi r16, 10
            ldi r17, 20
            ldi r18, 30
            push r16
            push r17
            push r18
            pop r20
            pop r21
            pop r22
        """)
        helper.assert_registers(cpu, {20: 30, 21: 20, 22: 10})

    def test_stack_preserves_registers(self, cpu_with_program, helper):
        """Test stack for temporary register storage."""
        cpu = cpu_with_program("""
            ldi r0, 100
            ldi r1, 200
            push r0
            push r1
            ; Modify registers
            ldi r0, 999
            ldi r1, 888
            ; Restore from stack
            pop r1
            pop r0
        """)
        helper.assert_registers(cpu, {0: 100, 1: 200})

    @pytest.mark.parametrize(
        "values",
        [
            [1, 2, 3],
            [10, 20, 30, 40, 50],
            [255, 0, 128, 64],
        ],
    )
    def test_push_pop_sequence(self, cpu_with_program, helper, values):
        """Test push/pop with various sequences."""
        push_code = "\n".join(
            [f"ldi r{i + 16}, {v}\npush r{i + 16}" for i, v in enumerate(values)]
        )
        pop_code = "\n".join([f"pop r{i}" for i in range(len(values))])

        cpu = cpu_with_program(push_code + "\n" + pop_code)

        for i, value in enumerate(reversed(values)):
            helper.assert_register(cpu, i, value)


class TestDataTransferIntegration:
    """Integration tests combining multiple data transfer instructions."""

    def test_copy_memory_block(self, cpu_with_program, helper):
        """Test copying a block of memory."""
        cpu = cpu_with_program("""
            ; Initialize source memory [100-102]
            ldi r0, 100
            ldi r1, 11
            st r0, r1
            inc r0
            ldi r1, 22
            st r0, r1
            inc r0
            ldi r1, 33
            st r0, r1
            
            ; Copy to destination [200-202]
            ldi r2, 100
            ldi r3, 200
            ld r4, r2
            st r3, r4
            inc r2
            inc r3
            ld r4, r2
            st r3, r4
            inc r2
            inc r3
            ld r4, r2
            st r3, r4
        """)
        for i in range(3):
            src_val = cpu.read_ram(100 + i)
            dst_val = cpu.read_ram(200 + i)
            assert src_val == dst_val, f"Memory copy failed at offset {i}"

    def test_swap_registers_via_stack(self, cpu_with_program, helper):
        """Test swapping register values using stack."""
        cpu = cpu_with_program("""
            ldi r16, 42
            ldi r17, 99
            push r16
            push r17
            pop r16
            pop r17
        """)
        helper.assert_registers(cpu, {16: 99, 17: 42})
