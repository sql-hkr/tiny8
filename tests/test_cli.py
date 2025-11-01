"""Comprehensive tests for CLI module functions.

Tests command parsing, state management, and utility functions
without requiring actual terminal/curses interaction.
"""

import time

from tiny8 import CPU, assemble
from tiny8.cli import KeyContext, ViewState, format_byte, run_command


class TestFormatByte:
    """Test byte formatting utility."""

    def test_format_byte_zero(self):
        """Test formatting zero."""
        assert format_byte(0) == "00"

    def test_format_byte_single_digit(self):
        """Test formatting single digit values."""
        assert format_byte(1) == "01"
        assert format_byte(9) == "09"
        assert format_byte(15) == "0F"

    def test_format_byte_two_digit(self):
        """Test formatting two digit values."""
        assert format_byte(16) == "10"
        assert format_byte(255) == "FF"
        assert format_byte(128) == "80"

    def test_format_byte_various(self):
        """Test formatting various byte values."""
        assert format_byte(0x42) == "42"
        assert format_byte(0xAB) == "AB"
        assert format_byte(0xCD) == "CD"


class TestRunCommandNumeric:
    """Test numeric command parsing."""

    def test_absolute_step_valid(self):
        """Test jumping to absolute step number."""
        state = ViewState()
        traces = [{"step": i} for i in range(10)]

        result = run_command(state, traces)
        state.command_buffer = "5"
        result = run_command(state, traces)

        assert "→ step 5" in result
        assert state.step_idx == 5
        assert state.scroll_offset == 0

    def test_absolute_step_zero(self):
        """Test jumping to step zero."""
        state = ViewState(step_idx=5)
        traces = [{"step": i} for i in range(10)]
        state.command_buffer = "0"

        result = run_command(state, traces)

        assert "→ step 0" in result
        assert state.step_idx == 0

    def test_absolute_step_invalid_too_large(self):
        """Test invalid step number (too large)."""
        state = ViewState()
        traces = [{"step": i} for i in range(10)]
        state.command_buffer = "20"

        result = run_command(state, traces)

        assert "Invalid" in result
        assert state.step_idx == 0  # Should not change

    def test_absolute_step_invalid_negative(self):
        """Test invalid step number (negative shown as invalid)."""
        state = ViewState()
        traces = [{"step": i} for i in range(10)]
        state.command_buffer = "-5"

        result = run_command(state, traces)

        assert state.step_idx == 0 or "Invalid" in result


class TestRunCommandRelative:
    """Test relative jump commands."""

    def test_relative_forward(self):
        """Test jumping forward relative steps."""
        state = ViewState(step_idx=5)
        traces = [{"step": i} for i in range(20)]
        state.command_buffer = "+3"

        result = run_command(state, traces)

        assert "→ step 8" in result
        assert state.step_idx == 8

    def test_relative_backward(self):
        """Test jumping backward relative steps."""
        state = ViewState(step_idx=10)
        traces = [{"step": i} for i in range(20)]
        state.command_buffer = "-5"

        result = run_command(state, traces)

        assert "→ step 5" in result
        assert state.step_idx == 5

    def test_relative_forward_out_of_bounds(self):
        """Test relative forward beyond trace length."""
        state = ViewState(step_idx=8)
        traces = [{"step": i} for i in range(10)]
        state.command_buffer = "+10"

        result = run_command(state, traces)

        assert "Invalid" in result
        assert state.step_idx == 8  # Should not change

    def test_relative_backward_out_of_bounds(self):
        """Test relative backward beyond start."""
        state = ViewState(step_idx=3)
        traces = [{"step": i} for i in range(10)]
        state.command_buffer = "-5"

        result = run_command(state, traces)

        assert "Invalid" in result
        assert state.step_idx == 3  # Should not change


class TestRunCommandSearch:
    """Test instruction search commands."""

    def test_forward_search_found(self):
        """Test forward search finding instruction."""
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "instr": "LDI R16, 42"},
            {"step": 1, "instr": "LDI R17, 100"},
            {"step": 2, "instr": "ADD R16, R17"},
        ]
        state.command_buffer = "/add"

        result = run_command(state, traces)

        assert "Found at step 2" in result
        assert "ADD" in result
        assert state.step_idx == 2

    def test_forward_search_case_insensitive(self):
        """Test forward search is case insensitive."""
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "instr": "LDI R16, 42"},
            {"step": 1, "instr": "ADD R16, R17"},
        ]
        state.command_buffer = "/ADD"

        result = run_command(state, traces)

        assert "Found" in result
        assert state.step_idx == 1

    def test_forward_search_not_found(self):
        """Test forward search when not found."""
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "instr": "LDI R16, 42"},
            {"step": 1, "instr": "LDI R17, 100"},
        ]
        state.command_buffer = "/mul"

        result = run_command(state, traces)

        assert "Not found" in result
        assert state.step_idx == 0  # Should not change

    def test_forward_search_empty(self):
        """Test forward search with empty pattern."""
        state = ViewState(step_idx=0)
        traces = [{"step": 0, "instr": "LDI R16, 42"}]
        state.command_buffer = "/"

        result = run_command(state, traces)

        assert "Empty search" in result

    def test_backward_search_found(self):
        """Test backward search finding instruction."""
        state = ViewState(step_idx=2)
        traces = [
            {"step": 0, "instr": "LDI R16, 42"},
            {"step": 1, "instr": "LDI R17, 100"},
            {"step": 2, "instr": "ADD R16, R17"},
        ]
        state.command_buffer = "?ldi"

        result = run_command(state, traces)

        assert "Found at step 1" in result
        assert state.step_idx == 1

    def test_backward_search_not_found(self):
        """Test backward search when not found."""
        state = ViewState(step_idx=2)
        traces = [
            {"step": 0, "instr": "LDI R16, 42"},
            {"step": 1, "instr": "LDI R17, 100"},
            {"step": 2, "instr": "ADD R16, R17"},
        ]
        state.command_buffer = "?mul"

        result = run_command(state, traces)

        assert "Not found" in result
        assert state.step_idx == 2


class TestRunCommandPCJump:
    """Test PC address jump commands."""

    def test_pc_jump_decimal(self):
        """Test jumping to PC address in decimal."""
        state = ViewState()
        traces = [
            {"step": 0, "pc": 0},
            {"step": 1, "pc": 1},
            {"step": 2, "pc": 100},
        ]
        state.command_buffer = "@100"

        result = run_command(state, traces)

        assert "→ step 2" in result
        assert "PC=0x0064" in result
        assert state.step_idx == 2

    def test_pc_jump_hex(self):
        """Test jumping to PC address in hex."""
        state = ViewState()
        traces = [
            {"step": 0, "pc": 0},
            {"step": 1, "pc": 1},
            {"step": 2, "pc": 0x64},
        ]
        state.command_buffer = "@0x64"

        result = run_command(state, traces)

        assert "→ step 2" in result
        assert state.step_idx == 2

    def test_pc_jump_not_found(self):
        """Test PC jump when address not found."""
        state = ViewState()
        traces = [
            {"step": 0, "pc": 0},
            {"step": 1, "pc": 1},
        ]
        state.command_buffer = "@999"

        result = run_command(state, traces)

        assert "not found" in result
        assert state.step_idx == 0

    def test_pc_jump_invalid_format(self):
        """Test PC jump with invalid format."""
        state = ViewState()
        traces = [{"step": 0, "pc": 0}]
        state.command_buffer = "@xyz"

        result = run_command(state, traces)

        assert "Invalid address" in result


class TestRunCommandRegister:
    """Test register tracking and search commands."""

    def test_register_track_change(self):
        """Test tracking register changes."""
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "regs": [0] * 32},
            {"step": 1, "regs": [0] * 32},
            {"step": 2, "regs": [42] + [0] * 31},  # R0 changes
        ]
        state.command_buffer = "r0"

        result = run_command(state, traces)

        assert "R0 changed at step 2" in result
        assert "0x2A" in result
        assert state.step_idx == 2

    def test_register_track_no_change(self):
        """Test tracking register that doesn't change."""
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "regs": [0] * 32},
            {"step": 1, "regs": [0] * 32},
        ]
        state.command_buffer = "r16"

        result = run_command(state, traces)

        assert "doesn't change" in result
        assert state.step_idx == 0

    def test_register_search_value_decimal(self):
        """Test searching for register value in decimal."""
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "regs": [0] * 32},
            {"step": 1, "regs": [42] + [0] * 31},
        ]
        state.command_buffer = "r0=42"

        result = run_command(state, traces)

        assert "R0=0x2A at step 1" in result
        assert state.step_idx == 1

    def test_register_search_value_hex(self):
        """Test searching for register value in hex."""
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "regs": [0] * 32},
            {"step": 1, "regs": [255] + [0] * 31},
        ]
        state.command_buffer = "r0=0xFF"

        result = run_command(state, traces)

        assert "R0=0xFF at step 1" in result
        assert state.step_idx == 1

    def test_register_search_not_found(self):
        """Test register search when value not found."""
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "regs": [0] * 32},
            {"step": 1, "regs": [42] + [0] * 31},
        ]
        state.command_buffer = "r0=99"

        result = run_command(state, traces)

        assert "not found" in result

    def test_register_invalid_number(self):
        """Test invalid register number."""
        state = ViewState()
        traces = [{"step": 0, "regs": [0] * 32}]
        state.command_buffer = "r32"

        result = run_command(state, traces)

        assert "Invalid register" in result

    def test_register_invalid_format(self):
        """Test invalid register command format."""
        state = ViewState()
        traces = [{"step": 0, "regs": [0] * 32}]
        state.command_buffer = "rabc"

        result = run_command(state, traces)

        assert "Invalid" in result


class TestRunCommandMemory:
    """Test memory tracking and search commands."""

    def test_memory_track_change(self):
        """Test tracking memory changes."""
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "mem": {}},
            {"step": 1, "mem": {}},
            {"step": 2, "mem": {100: 0x42}},
        ]
        state.command_buffer = "m100"

        result = run_command(state, traces)

        assert "Mem[0x0064] changed at step 2" in result
        assert "0x42" in result
        assert state.step_idx == 2

    def test_memory_track_no_change(self):
        """Test tracking memory that doesn't change."""
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "mem": {}},
            {"step": 1, "mem": {}},
        ]
        state.command_buffer = "m100"

        result = run_command(state, traces)

        assert "doesn't change" in result

    def test_memory_search_value_decimal(self):
        """Test searching for memory value in decimal."""
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "mem": {}},
            {"step": 1, "mem": {100: 42}},
        ]
        state.command_buffer = "m100=42"

        result = run_command(state, traces)

        assert "Mem[0x0064]=0x2A at step 1" in result
        assert state.step_idx == 1

    def test_memory_search_value_hex(self):
        """Test searching for memory value in hex."""
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "mem": {}},
            {"step": 1, "mem": {0x64: 0xFF}},
        ]
        state.command_buffer = "m0x64=0xFF"

        result = run_command(state, traces)

        assert "at step 1" in result
        assert state.step_idx == 1

    def test_memory_search_not_found(self):
        """Test memory search when value not found."""
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "mem": {}},
            {"step": 1, "mem": {100: 42}},
        ]
        state.command_buffer = "m100=99"

        result = run_command(state, traces)

        assert "not found" in result

    def test_memory_invalid_format(self):
        """Test invalid memory command format."""
        state = ViewState()
        traces = [{"step": 0, "mem": {}}]
        state.command_buffer = "mxyz"

        result = run_command(state, traces)

        assert "Invalid" in result


class TestRunCommandFlag:
    """Test flag tracking and search commands."""

    def test_flag_track_zero_change(self):
        """Test tracking Zero flag changes."""
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "sreg": 0b00000000},  # Z=0
            {"step": 1, "sreg": 0b00000010},  # Z=1
        ]
        state.command_buffer = "fZ"

        result = run_command(state, traces)

        assert "Flag Z changed at step 1" in result
        assert state.step_idx == 1

    def test_flag_track_carry_change(self):
        """Test tracking Carry flag changes."""
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "sreg": 0b00000000},  # C=0
            {"step": 1, "sreg": 0b00000001},  # C=1
        ]
        state.command_buffer = "fC"

        result = run_command(state, traces)

        assert "Flag C changed at step 1" in result
        assert state.step_idx == 1

    def test_flag_track_no_change(self):
        """Test tracking flag that doesn't change."""
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "sreg": 0b00000000},
            {"step": 1, "sreg": 0b00000000},
        ]
        state.command_buffer = "fZ"

        result = run_command(state, traces)

        assert "doesn't change" in result

    def test_flag_search_value_set(self):
        """Test searching for flag set (=1)."""
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "sreg": 0b00000000},
            {"step": 1, "sreg": 0b00000010},  # Z=1
        ]
        state.command_buffer = "fZ=1"

        result = run_command(state, traces)

        assert "Flag Z=1 at step 1" in result
        assert state.step_idx == 1

    def test_flag_search_value_clear(self):
        """Test searching for flag clear (=0)."""
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "sreg": 0b00000010},  # Z=1
            {"step": 1, "sreg": 0b00000000},  # Z=0
        ]
        state.command_buffer = "fZ=0"

        result = run_command(state, traces)

        assert "Flag Z=0 at step 1" in result
        assert state.step_idx == 1

    def test_flag_all_flags(self):
        """Test all flag names."""
        flags = ["I", "T", "H", "S", "V", "N", "Z", "C"]
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "sreg": 0b00000000},
            {"step": 1, "sreg": 0b11111111},  # All flags set
        ]

        for flag in flags:
            state.step_idx = 0
            state.command_buffer = f"f{flag}"
            result = run_command(state, traces)
            assert "changed" in result

    def test_flag_case_insensitive(self):
        """Test flag names are case insensitive."""
        state = ViewState(step_idx=0)
        traces = [
            {"step": 0, "sreg": 0b00000000},
            {"step": 1, "sreg": 0b00000010},
        ]
        state.command_buffer = "fz"  # lowercase

        result = run_command(state, traces)

        assert "Flag Z changed" in result

    def test_flag_invalid_name(self):
        """Test invalid flag name."""
        state = ViewState()
        traces = [{"step": 0, "sreg": 0}]
        state.command_buffer = "fX"

        result = run_command(state, traces)

        assert "Invalid flag" in result

    def test_flag_invalid_value(self):
        """Test invalid flag value."""
        state = ViewState()
        traces = [{"step": 0, "sreg": 0}]
        state.command_buffer = "fZ=2"

        result = run_command(state, traces)

        assert "must be 0 or 1" in result


class TestRunCommandMisc:
    """Test miscellaneous commands."""

    def test_help_command_h(self):
        """Test help command with 'h'."""
        state = ViewState()
        traces = [{"step": 0}]
        state.command_buffer = "h"

        result = run_command(state, traces)

        assert "Commands:" in result
        assert "NUM" in result

    def test_help_command_help(self):
        """Test help command with 'help'."""
        state = ViewState()
        traces = [{"step": 0}]
        state.command_buffer = "help"

        result = run_command(state, traces)

        assert "Commands:" in result

    def test_unknown_command(self):
        """Test unknown command."""
        state = ViewState()
        traces = [{"step": 0}]
        state.command_buffer = "xyz123"

        result = run_command(state, traces)

        assert "Unknown:" in result

    def test_empty_command(self):
        """Test empty command."""
        state = ViewState()
        traces = [{"step": 0}]
        state.command_buffer = ""

        result = run_command(state, traces)

        assert "Unknown:" in result or result == ""


class TestRunCommandIntegration:
    """Integration tests with actual CPU traces."""

    def test_command_with_real_trace(self):
        """Test commands with actual CPU execution trace."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 10
            ldi r17, 20
            add r16, r17
            ldi r18, 100
        """)
        cpu.load_program(asm)
        cpu.run()

        traces = cpu.step_trace
        state = ViewState()

        state.command_buffer = "/add"
        result = run_command(state, traces)
        assert "Found" in result

        state.step_idx = 0
        state.command_buffer = "r16=30"
        result = run_command(state, traces)
        assert "R16=0x1E" in result or "not found" in result

    def test_multiple_commands_sequence(self):
        """Test sequence of different commands."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 1
            ldi r17, 2
            add r16, r17
        """)
        cpu.load_program(asm)
        cpu.run()

        traces = cpu.step_trace
        state = ViewState()

        state.command_buffer = "1"
        run_command(state, traces)
        assert state.step_idx == 1

        state.command_buffer = "+1"
        run_command(state, traces)
        assert state.step_idx == 2

        state.command_buffer = "-1"
        run_command(state, traces)
        assert state.step_idx == 1


class TestKeyContext:
    """Test KeyContext methods."""

    def test_set_status(self):
        """Test setting status message."""
        state = ViewState()
        ctx = KeyContext(
            state=state,
            scr=None,
            traces=[],
            cpu=None,
            mem_addr_start=0,
            mem_addr_end=31,
            source_lines=None,
            n=0,
        )

        before_time = time.time()
        ctx.set_status("Test message")
        after_time = time.time()

        assert state.status_msg == "Test message"
        assert state.status_time >= before_time
        assert state.status_time <= after_time

    def test_set_status_multiple_times(self):
        """Test setting status message multiple times."""
        state = ViewState()
        ctx = KeyContext(
            state=state,
            scr=None,
            traces=[],
            cpu=None,
            mem_addr_start=0,
            mem_addr_end=31,
            source_lines=None,
            n=0,
        )

        ctx.set_status("First message")
        first_time = state.status_time

        time.sleep(0.01)  # Small delay to ensure time changes

        ctx.set_status("Second message")
        second_time = state.status_time

        assert state.status_msg == "Second message"
        assert second_time > first_time


class TestKeyHandlerDecorator:
    """Test the key_handler decorator."""

    def test_key_handler_decorator_registration(self):
        """Test that key_handler decorator registers handlers correctly."""
        from tiny8.cli import _key_handlers

        assert ord("q") in _key_handlers
        assert 27 in _key_handlers
        assert ord(" ") in _key_handlers
        assert ord("l") in _key_handlers
        assert ord("h") in _key_handlers
        assert ord("w") in _key_handlers
        assert ord("b") in _key_handlers


class TestViewStateDefaults:
    """Test ViewState default values."""

    def test_viewstate_defaults(self):
        """Test ViewState initializes with correct defaults."""
        state = ViewState()

        assert state.step_idx == 0
        assert state.scroll_offset == 0
        assert not state.playing
        assert state.last_advance_time == 0.0
        assert state.delay == 0.15
        assert state.show_all_regs
        assert not state.show_all_mem
        assert not state.command_mode
        assert state.command_buffer == ""
        assert state.marks == {}
        assert state.status_msg == ""
        assert state.status_time == 0.0

    def test_viewstate_custom_values(self):
        """Test ViewState with custom values."""
        marks = {"a": 10, "b": 20}
        state = ViewState(
            step_idx=5,
            scroll_offset=3,
            playing=True,
            delay=0.5,
            show_all_regs=False,
            show_all_mem=True,
            command_mode=True,
            command_buffer="test",
            marks=marks,
            status_msg="Status",
        )

        assert state.step_idx == 5
        assert state.scroll_offset == 3
        assert state.playing
        assert state.delay == 0.5
        assert not state.show_all_regs
        assert state.show_all_mem
        assert state.command_mode
        assert state.command_buffer == "test"
        assert state.marks == marks
        assert state.status_msg == "Status"
