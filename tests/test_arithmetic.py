"""Test suite for arithmetic instructions.

Covers: ADD, ADC, SUB, SUBI, SBC, SBCI, INC, DEC, MUL, DIV, NEG, ADIW, SBIW
"""

import pytest

from tiny8 import assemble
from tiny8.cpu import SREG_C, SREG_H, SREG_N, SREG_S, SREG_V, SREG_Z


class TestADD:
    """Test ADD instruction and flag behavior."""

    def test_add_basic(self, cpu_with_program, helper):
        """Test basic addition without overflow."""
        cpu = cpu_with_program("""
            ldi r0, 10
            ldi r1, 20
            add r0, r1
        """)
        helper.assert_register(cpu, 0, 30)

    def test_add_overflow_unsigned(self, cpu_with_program, helper):
        """Test unsigned overflow sets carry flag."""
        cpu = cpu_with_program("""
            ldi r0, 0xFF
            ldi r1, 0x01
            add r0, r1
        """)
        helper.assert_register(cpu, 0, 0x00)
        helper.assert_flags(cpu, {SREG_C: True, SREG_Z: True, SREG_H: True})

    def test_add_signed_overflow(self, cpu_with_program, helper):
        """Test signed overflow (positive + positive = negative)."""
        cpu = cpu_with_program("""
            ldi r0, 0x7F
            ldi r1, 0x01
            add r0, r1
        """)
        helper.assert_register(cpu, 0, 0x80)
        helper.assert_flags(
            cpu,
            {
                SREG_N: True,  # Result negative
                SREG_V: True,  # Signed overflow
                SREG_S: False,  # S = N ^ V = 1 ^ 1 = 0
                SREG_H: True,  # Half carry from bit 3
                SREG_C: False,  # No unsigned carry
                SREG_Z: False,  # Not zero
            },
        )

    def test_add_zero_flag(self, cpu_with_program, helper):
        """Test zero flag with result of zero."""
        cpu = cpu_with_program("""
            ldi r0, 0x00
            ldi r1, 0x00
            add r0, r1
        """)
        helper.assert_register(cpu, 0, 0)
        helper.assert_flag(cpu, SREG_Z, True, "Z")

    @pytest.mark.parametrize(
        "a,b,expected,carry",
        [
            (0, 0, 0, False),
            (1, 1, 2, False),
            (128, 128, 0, True),
            (255, 1, 0, True),
            (127, 1, 128, False),
        ],
    )
    def test_add_parametrized(self, cpu_with_program, helper, a, b, expected, carry):
        """Test ADD with various input combinations."""
        cpu = cpu_with_program(f"""
            ldi r0, {a}
            ldi r1, {b}
            add r0, r1
        """)
        helper.assert_register(cpu, 0, expected)
        helper.assert_flag(cpu, SREG_C, carry, "C")


class TestADC:
    """Test ADC (Add with Carry) instruction."""

    def test_adc_with_carry_clear(self, cpu_with_program, helper):
        """Test ADC when carry is 0."""
        cpu = cpu_with_program("""
            ldi r0, 10
            ldi r1, 5
            adc r0, r1
        """)
        helper.assert_register(cpu, 0, 15)

    def test_adc_with_carry_set(self, cpu, helper):
        """Test ADC when carry is 1."""
        asm = assemble("""
            ldi r0, 10
            ldi r1, 5
            adc r0, r1
        """)
        cpu.load_program(asm)
        cpu.set_flag(SREG_C, True)  # Set carry before execution
        cpu.run()
        helper.assert_register(cpu, 0, 16)  # 10 + 5 + 1

    def test_adc_chain_addition(self, cpu, helper):
        """Test multi-byte addition using ADC."""
        asm = assemble("""
            ; Add 0x0201 + 0x0304 = 0x0505
            ldi r0, 0x01    ; Low byte 1
            ldi r1, 0x02    ; High byte 1
            ldi r2, 0x04    ; Low byte 2
            ldi r3, 0x03    ; High byte 2
            add r0, r2      ; Add low bytes
            adc r1, r3      ; Add high bytes with carry
        """)
        cpu.load_program(asm)
        cpu.run()
        helper.assert_registers(cpu, {0: 0x05, 1: 0x05})


class TestSUB:
    """Test SUB and SUBI instructions."""

    def test_sub_basic(self, cpu_with_program, helper):
        """Test basic subtraction."""
        cpu = cpu_with_program("""
            ldi r0, 30
            ldi r1, 10
            sub r0, r1
        """)
        helper.assert_register(cpu, 0, 20)

    def test_sub_with_borrow(self, cpu_with_program, helper):
        """Test subtraction with borrow (negative result)."""
        cpu = cpu_with_program("""
            ldi r0, 5
            ldi r1, 10
            sub r0, r1
        """)
        helper.assert_register(cpu, 0, 251)  # -5 in two's complement = 0xFB
        helper.assert_flag(cpu, SREG_C, True, "C")  # Borrow set
        helper.assert_flag(cpu, SREG_N, True, "N")  # Negative

    def test_subi_immediate(self, cpu_with_program, helper):
        """Test SUBI with immediate value."""
        cpu = cpu_with_program("""
            ldi r16, 100
            subi r16, 42
        """)
        helper.assert_register(cpu, 16, 58)

    def test_sub_zero_result(self, cpu_with_program, helper):
        """Test subtraction resulting in zero."""
        cpu = cpu_with_program("""
            ldi r0, 42
            ldi r1, 42
            sub r0, r1
        """)
        helper.assert_register(cpu, 0, 0)
        helper.assert_flag(cpu, SREG_Z, True, "Z")


class TestSBC:
    """Test SBC (Subtract with Carry) instruction."""

    def test_sbc_with_carry_clear(self, cpu_with_program, helper):
        """Test SBC when carry/borrow is 0."""
        cpu = cpu_with_program("""
            ldi r0, 20
            ldi r1, 5
            sbc r0, r1
        """)
        helper.assert_register(cpu, 0, 15)

    def test_sbc_with_borrow_set(self, cpu, helper):
        """Test SBC when carry/borrow is 1."""
        asm = assemble("""
            ldi r0, 20
            ldi r1, 5
            sbc r0, r1
        """)
        cpu.load_program(asm)
        cpu.set_flag(SREG_C, True)  # Set borrow
        cpu.run()
        helper.assert_register(cpu, 0, 14)  # 20 - 5 - 1

    def test_sbci_immediate(self, cpu, helper):
        """Test SBCI with immediate value."""
        asm = assemble("""
            ldi r16, 100
            sbci r16, 10
        """)
        cpu.load_program(asm)
        cpu.set_flag(SREG_C, True)
        cpu.run()
        helper.assert_register(cpu, 16, 89)  # 100 - 10 - 1


class TestINCDEC:
    """Test INC and DEC instructions."""

    def test_inc_basic(self, cpu_with_program, helper):
        """Test basic increment."""
        cpu = cpu_with_program("""
            ldi r0, 42
            inc r0
        """)
        helper.assert_register(cpu, 0, 43)

    def test_inc_overflow(self, cpu_with_program, helper):
        """Test increment overflow (0xFF -> 0x00)."""
        cpu = cpu_with_program("""
            ldi r0, 0xFF
            inc r0
        """)
        helper.assert_register(cpu, 0, 0)
        helper.assert_flag(cpu, SREG_Z, True, "Z")

    def test_inc_signed_overflow(self, cpu_with_program, helper):
        """Test increment with signed overflow (0x7F -> 0x80)."""
        cpu = cpu_with_program("""
            ldi r0, 0x7F
            inc r0
        """)
        helper.assert_register(cpu, 0, 0x80)
        helper.assert_flag(cpu, SREG_V, True, "V")  # Signed overflow
        helper.assert_flag(cpu, SREG_N, True, "N")  # Negative

    def test_dec_basic(self, cpu_with_program, helper):
        """Test basic decrement."""
        cpu = cpu_with_program("""
            ldi r0, 42
            dec r0
        """)
        helper.assert_register(cpu, 0, 41)

    def test_dec_underflow(self, cpu_with_program, helper):
        """Test decrement underflow (0x00 -> 0xFF)."""
        cpu = cpu_with_program("""
            ldi r0, 0
            dec r0
        """)
        helper.assert_register(cpu, 0, 0xFF)
        helper.assert_flag(cpu, SREG_N, True, "N")

    @pytest.mark.parametrize(
        "value,inc_result,dec_result",
        [
            (0, 1, 255),
            (1, 2, 0),
            (127, 128, 126),
            (128, 129, 127),
            (255, 0, 254),
        ],
    )
    def test_inc_dec_parametrized(
        self, cpu_with_program, helper, value, inc_result, dec_result
    ):
        """Test INC and DEC with various values."""
        cpu = cpu_with_program(f"""
            ldi r0, {value}
            ldi r1, {value}
            inc r0
            dec r1
        """)
        helper.assert_register(cpu, 0, inc_result)
        helper.assert_register(cpu, 1, dec_result)


class TestMUL:
    """Test MUL (Multiply) instruction."""

    def test_mul_basic(self, cpu_with_program, helper):
        """Test basic multiplication."""
        cpu = cpu_with_program("""
            ldi r0, 6
            ldi r1, 7
            mul r0, r1
        """)
        helper.assert_register(cpu, 0, 42)  # Low byte
        helper.assert_register(cpu, 1, 0)  # High byte

    def test_mul_with_overflow(self, cpu_with_program, helper):
        """Test multiplication producing 16-bit result."""
        cpu = cpu_with_program("""
            ldi r2, 200
            ldi r3, 100
            mul r2, r3
        """)
        # 200 * 100 = 20000 = 0x4E20
        helper.assert_register(cpu, 2, 0x20)  # Low byte
        helper.assert_register(cpu, 3, 0x4E)  # High byte

    def test_mul_zero(self, cpu_with_program, helper):
        """Test multiplication by zero."""
        cpu = cpu_with_program("""
            ldi r4, 42
            ldi r5, 0
            mul r4, r5
        """)
        helper.assert_register(cpu, 4, 0)
        helper.assert_register(cpu, 5, 0)
        helper.assert_flag(cpu, SREG_Z, True, "Z")

    @pytest.mark.parametrize(
        "a,b,low,high",
        [
            (1, 1, 1, 0),
            (15, 15, 225, 0),
            (16, 16, 0, 1),
            (255, 255, 1, 254),
            (128, 2, 0, 1),
        ],
    )
    def test_mul_parametrized(self, cpu_with_program, helper, a, b, low, high):
        """Test MUL with various input combinations."""
        cpu = cpu_with_program(f"""
            ldi r0, {a}
            ldi r1, {b}
            mul r0, r1
        """)
        helper.assert_register(cpu, 0, low)
        helper.assert_register(cpu, 1, high)


class TestDIV:
    """Test DIV (Division) instruction."""

    def test_div_basic(self, cpu_with_program, helper):
        """Test basic division."""
        cpu = cpu_with_program("""
            ldi r0, 42
            ldi r1, 7
            div r0, r1
        """)
        helper.assert_register(cpu, 0, 6)  # Quotient
        helper.assert_register(cpu, 1, 0)  # Remainder

    def test_div_with_remainder(self, cpu_with_program, helper):
        """Test division with remainder."""
        cpu = cpu_with_program("""
            ldi r2, 100
            ldi r3, 7
            div r2, r3
        """)
        helper.assert_register(cpu, 2, 14)  # 100 // 7 = 14
        helper.assert_register(cpu, 3, 2)  # 100 % 7 = 2

    def test_div_by_one(self, cpu_with_program, helper):
        """Test division by 1."""
        cpu = cpu_with_program("""
            ldi r4, 123
            ldi r5, 1
            div r4, r5
        """)
        helper.assert_register(cpu, 4, 123)
        helper.assert_register(cpu, 5, 0)

    @pytest.mark.parametrize(
        "dividend,divisor,quotient,remainder",
        [
            (10, 3, 3, 1),
            (20, 4, 5, 0),
            (255, 16, 15, 15),
            (100, 100, 1, 0),
            (7, 10, 0, 7),
        ],
    )
    def test_div_parametrized(
        self, cpu_with_program, helper, dividend, divisor, quotient, remainder
    ):
        """Test DIV with various input combinations."""
        cpu = cpu_with_program(f"""
            ldi r0, {dividend}
            ldi r1, {divisor}
            div r0, r1
        """)
        helper.assert_register(cpu, 0, quotient)
        helper.assert_register(cpu, 1, remainder)


class TestNEG:
    """Test NEG (Two's complement negation) instruction."""

    def test_neg_positive(self, cpu_with_program, helper):
        """Test negation of positive number."""
        cpu = cpu_with_program("""
            ldi r0, 42
            neg r0
        """)
        helper.assert_register(cpu, 0, 214)  # -42 in two's complement
        helper.assert_flag(cpu, SREG_N, True, "N")

    def test_neg_zero(self, cpu_with_program, helper):
        """Test negation of zero."""
        cpu = cpu_with_program("""
            ldi r0, 0
            neg r0
        """)
        helper.assert_register(cpu, 0, 0)
        helper.assert_flag(cpu, SREG_Z, True, "Z")

    def test_neg_max_negative(self, cpu_with_program, helper):
        """Test negation of 0x80 (most negative number)."""
        cpu = cpu_with_program("""
            ldi r0, 0x80
            neg r0
        """)
        helper.assert_register(cpu, 0, 0x80)
        helper.assert_flag(cpu, SREG_V, True, "V")  # Overflow


class TestWordOperations:
    """Test ADIW and SBIW (16-bit word operations)."""

    def test_adiw_basic(self, cpu_with_program, helper):
        """Test add immediate to word."""
        cpu = cpu_with_program("""
            ldi r24, 0x00
            ldi r25, 0x01
            adiw r24, 1
        """)
        helper.assert_register(cpu, 24, 0x01)
        helper.assert_register(cpu, 25, 0x01)

    def test_sbiw_basic(self, cpu_with_program, helper):
        """Test subtract immediate from word."""
        cpu = cpu_with_program("""
            ldi r24, 0x05
            ldi r25, 0x00
            sbiw r24, 3
        """)
        helper.assert_register(cpu, 24, 0x02)
        helper.assert_register(cpu, 25, 0x00)
