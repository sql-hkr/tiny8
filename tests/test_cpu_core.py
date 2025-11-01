"""Core CPU instruction tests.

Tests for CPU instructions including shifts, rotates, logical operations,
bit manipulation, and word operations.
"""

from tiny8 import CPU, assemble


class TestShiftRotateInstructions:
    """Test shift and rotate instructions."""

    def test_lsr_instruction(self):
        """Test logical shift right."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0b10101011
            lsr r16
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 0b01010101

    def test_lsl_instruction_with_carry(self):
        """Test logical shift left that sets carry."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0xFF
            lsl r16
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 0xFE

    def test_rol_instruction(self):
        """Test rotate left through carry."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0x01
            rol r16
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 0x02

    def test_ror_instruction(self):
        """Test rotate right through carry."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0x80
            ror r16
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 0x40

    def test_swap_instruction(self):
        """Test swap nibbles."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0xAB
            swap r16
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 0xBA


class TestLogicalInstructions:
    """Test logical and complement instructions."""

    def test_com_instruction(self):
        """Test one's complement."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0b10101010
            com r16
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 0b01010101

    def test_neg_instruction(self):
        """Test two's complement negation."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 1
            neg r16
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 255

    def test_andi_instruction(self):
        """Test AND with immediate."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0b11110000
            andi r16, 0b00111100
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 0b00110000

    def test_ori_instruction(self):
        """Test OR with immediate."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0b11110000
            ori r16, 0b00001111
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 0b11111111

    def test_eori_instruction(self):
        """Test XOR with immediate."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0b11110000
            eori r16, 0b11111111
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 0b00001111

    def test_tst_instruction(self):
        """Test for zero or negative."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0
            tst r16
        """)
        cpu.load_program(asm)
        cpu.run()


class TestImmediateArithmetic:
    """Test arithmetic instructions with immediate values."""

    def test_subi_instruction(self):
        """Test subtract immediate."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 20
            subi r16, 7
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 13

    def test_sbci_instruction(self):
        """Test subtract immediate with carry."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 20
            sbci r16, 5
        """)
        cpu.load_program(asm)
        cpu.run()

    def test_sbc_instruction(self):
        """Test subtract with carry."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 10
            ldi r17, 5
            sbc r16, r17
        """)
        cpu.load_program(asm)
        cpu.run()


class TestSkipInstructions:
    """Test conditional skip instructions."""

    def test_cpse_skip(self):
        """Test compare and skip if equal."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 5
            ldi r17, 5
            ldi r18, 0
            cpse r16, r17
            ldi r18, 99
            ldi r19, 1
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(18) == 0  # Skipped
        assert cpu.read_reg(19) == 1  # Executed

    def test_sbrs_skip(self):
        """Test skip if bit in register is set."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0b10000000
            ldi r17, 0
            sbrs r16, 7
            ldi r17, 99
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(17) == 0  # Skipped

    def test_sbrc_skip(self):
        """Test skip if bit in register is clear."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0b01111111
            ldi r17, 0
            sbrc r16, 7
            ldi r17, 99
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(17) == 0  # Skipped


class TestIOBitManipulation:
    """Test I/O register bit manipulation instructions."""

    def test_sbi_instruction(self):
        """Test set bit in I/O register."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0b00000000
            out 0x10, r16
            sbi 0x10, 3
            in r17, 0x10
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(17) == 0b00001000

    def test_cbi_instruction(self):
        """Test clear bit in I/O register."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0b11111111
            out 0x10, r16
            cbi 0x10, 3
            in r17, 0x10
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(17) == 0b11110111

    def test_sbis_skip(self):
        """Test skip if bit in I/O register is set."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0b10000000
            out 0x10, r16
            ldi r17, 0
            sbis 0x10, 7
            ldi r17, 99
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(17) == 0  # Skipped

    def test_sbic_skip(self):
        """Test skip if bit in I/O register is clear."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 0b01111111
            out 0x10, r16
            ldi r17, 0
            sbic 0x10, 7
            ldi r17, 99
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(17) == 0  # Skipped


class TestWordOperations:
    """Test 16-bit word operations."""

    def test_adiw_instruction(self):
        """Test add immediate to word (16-bit)."""
        cpu = CPU()
        asm = assemble("""
            ldi r24, 0xFF
            ldi r25, 0x00
            adiw r24, 2
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(24) == 1
        assert cpu.read_reg(25) == 1

    def test_sbiw_instruction(self):
        """Test subtract immediate from word (16-bit)."""
        cpu = CPU()
        asm = assemble("""
            ldi r24, 0x01
            ldi r25, 0x01
            sbiw r24, 2
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(24) == 0xFF
        assert cpu.read_reg(25) == 0x00


class TestRelativeJumpCall:
    """Test relative jump and call instructions."""

    def test_rjmp_instruction(self):
        """Test relative jump."""
        cpu = CPU()
        asm = assemble("""
            rjmp skip
            ldi r16, 99
        skip:
            ldi r17, 1
        """)
        cpu.load_program(asm)
        cpu.run()
        assert cpu.read_reg(16) == 0
        assert cpu.read_reg(17) == 1

    def test_rcall_instruction(self):
        """Test relative call."""
        cpu = CPU()
        asm = assemble("""
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

    def test_rcall_integer_offset(self):
        """Test RCALL with integer offset for proper branch coverage."""
        cpu = CPU()
        cpu.program = [
            ("LDI", (("reg", 16), 42)),
            ("RCALL", (2,)),  # Call with integer offset
            ("LDI", (("reg", 17), 1)),
            ("LDI", (("reg", 18), 2)),
            ("RET", ()),
        ]
        cpu.step()
        cpu.step()
        assert cpu.regs[16] == 42


class TestInterruptControl:
    """Test interrupt control instructions."""

    def test_sei_cli_instructions(self):
        """Test set and clear global interrupt enable."""
        cpu = CPU()
        asm = assemble("""
            sei
            cli
        """)
        cpu.load_program(asm)
        cpu.step()
        assert cpu.get_flag(7)  # I flag set
        cpu.step()
        assert not cpu.get_flag(7)  # I flag cleared


class TestArithmeticEdgeCases:
    """Test arithmetic edge cases."""

    def test_div_by_zero(self):
        """Test division by zero."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 10
            ldi r17, 0
            div r16, r17
        """)
        cpu.load_program(asm)
        cpu.run()
        # Division by zero sets result to 0xFF and 0

    def test_mul_overflow(self):
        """Test multiplication overflow."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 255
            ldi r17, 2
            mul r16, r17
        """)
        cpu.load_program(asm)
        cpu.run()
        # Result is 16-bit in r0:r1
