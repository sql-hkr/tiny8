"""Assembler functionality tests.

Tests for assembler parsing, number formats, and edge cases.
"""

import pytest

from tiny8 import assemble, assemble_file


class TestAssemblerBasics:
    """Test basic assembler functionality."""

    def test_assemble_file_missing(self):
        """Test assembling non-existent file."""
        with pytest.raises(FileNotFoundError):
            assemble_file("nonexistent.asm")

    def test_assemble_empty_string(self):
        """Test assembling empty string."""
        result = assemble("")
        assert len(result.program) == 0

    def test_assemble_only_comments(self):
        """Test assembling file with only comments."""
        result = assemble("""
            ; This is a comment
            ; Another comment
        """)
        assert len(result.program) == 0


class TestNumberParsing:
    """Test number parsing in assembler."""

    def test_parse_number_hex_dollar(self):
        """Test parsing hex immediate with $ prefix."""
        from tiny8.assembler import _parse_number

        assert _parse_number("$FF") == 255
        assert _parse_number("$10") == 16

    def test_parse_number_hex_0x(self):
        """Test parsing hex immediate with 0x prefix."""
        from tiny8.assembler import _parse_number

        assert _parse_number("0xFF") == 255
        assert _parse_number("0x10") == 16

    def test_parse_number_binary(self):
        """Test parsing binary immediate."""
        from tiny8.assembler import _parse_number

        assert _parse_number("0b1111") == 15
        assert _parse_number("0b10101010") == 170

    def test_parse_number_decimal(self):
        """Test parsing decimal immediate."""
        from tiny8.assembler import _parse_number

        assert _parse_number("100") == 100
        assert _parse_number("255") == 255

    def test_parse_number_with_hash(self):
        """Test parsing immediate with # marker."""
        from tiny8.assembler import _parse_number

        assert _parse_number("#100") == 100
        assert _parse_number("#$FF") == 255

    def test_parse_number_invalid(self):
        """Test parsing invalid immediate raises ValueError."""
        from tiny8.assembler import _parse_number

        with pytest.raises(ValueError):
            _parse_number("not_a_number")
        with pytest.raises(ValueError):
            _parse_number("label_name")


class TestAssemblerWithFiles:
    """Test assembler with actual files."""

    def test_assemble_file_with_actual_file(self, tmp_path):
        """Test assembling from actual file."""
        asm_file = tmp_path / "test.asm"
        asm_file.write_text("""
            ldi r16, 42
            ldi r17, 100
        """)

        result = assemble_file(str(asm_file))
        assert len(result.program) == 2

    def test_parse_number_empty_token(self):
        """Test parsing empty token or hash only raises ValueError."""
        from tiny8.assembler import _parse_number

        with pytest.raises(ValueError, match="Unable to parse numeric token"):
            _parse_number("")
        with pytest.raises(ValueError, match="Unable to parse numeric token"):
            _parse_number("#")

    def test_parse_displacement_operands(self):
        """Test parsing instructions with displacement addressing."""
        from tiny8.assembler import assemble

        asm_text = """
            ldd r16, Y+2
            std Y+3, r17
            ldd r18, Y + 4
            std Z + 5, r19
            ldd r20, r28+6
            ldd r23, 28+7
            ld r21, X
            st Y, r22
        """
        res = assemble(asm_text)
        assert res.program[0] == ("LDD", (("reg", 16), ("disp", 28, 2)))
        assert res.program[1] == ("STD", (("disp", 28, 3), ("reg", 17)))
        assert res.program[2] == ("LDD", (("reg", 18), ("disp", 28, 4)))
        assert res.program[3] == ("STD", (("disp", 30, 5), ("reg", 19)))
        assert res.program[4] == ("LDD", (("reg", 20), ("disp", 28, 6)))
        assert res.program[5] == ("LDD", (("reg", 23), ("disp", 28, 7)))
        assert res.program[6] == ("LD", (("reg", 21), ("reg", 26)))
        assert res.program[7] == ("ST", (("reg", 28), ("reg", 22)))
