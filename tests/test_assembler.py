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
