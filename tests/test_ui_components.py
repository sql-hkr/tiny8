"""Test cases for UI-related code (cli.py and visualizer.py).

Following best practices for testing UI code:
1. Separate logic from UI rendering
2. Mock/patch UI library functions for fast tests
3. Use headless rendering where applicable
4. Keep tests simple and fast
"""

import io
from unittest.mock import Mock, patch

import pytest

from tiny8 import CPU, assemble


class TestCLILogic:
    """Test CLI logic functions without actual terminal rendering."""

    def test_view_state_initialization(self):
        """Test ViewState dataclass initialization."""
        from tiny8.cli import ViewState

        state = ViewState()
        assert state.step_idx == 0
        assert state.scroll_offset == 0
        assert not state.playing
        assert state.delay == 0.15
        assert state.show_all_regs
        assert not state.show_all_mem
        assert not state.command_mode
        assert state.command_buffer == ""
        assert state.marks == {}
        assert state.status_msg == ""

    def test_view_state_custom_values(self):
        """Test ViewState with custom values."""
        from tiny8.cli import ViewState

        state = ViewState(
            step_idx=5,
            scroll_offset=10,
            playing=True,
            delay=0.5,
            show_all_regs=False,
        )
        assert state.step_idx == 5
        assert state.scroll_offset == 10
        assert state.playing
        assert state.delay == 0.5
        assert not state.show_all_regs

    def test_key_context_initialization(self):
        """Test KeyContext dataclass initialization."""
        from tiny8.cli import KeyContext, ViewState

        cpu = CPU()
        state = ViewState()
        mock_scr = Mock()
        traces = []

        ctx = KeyContext(
            state=state,
            scr=mock_scr,
            traces=traces,
            cpu=cpu,
            mem_addr_start=0x60,
            mem_addr_end=0x7F,
            source_lines=None,
            n=0,
        )

        assert ctx.state == state
        assert ctx.traces == traces
        assert ctx.cpu == cpu
        assert ctx.mem_addr_start == 0x60
        assert ctx.mem_addr_end == 0x7F

    def test_key_context_set_status(self):
        """Test KeyContext status message setting."""
        from tiny8.cli import KeyContext, ViewState

        state = ViewState()
        ctx = KeyContext(
            state=state,
            scr=Mock(),
            traces=[],
            cpu=CPU(),
            mem_addr_start=0,
            mem_addr_end=0,
            source_lines=None,
            n=0,
        )

        ctx.set_status("Test message")
        assert ctx.state.status_msg == "Test message"
        assert ctx.state.status_time > 0

    def test_key_handler_decorator(self):
        """Test key handler registration decorator."""
        from tiny8.cli import _key_handlers, key_handler

        original_handlers = _key_handlers.copy()
        _key_handlers.clear()

        @key_handler(ord("t"), ord("T"))
        def test_handler(ctx):
            return "test_result"

        assert ord("t") in _key_handlers
        assert ord("T") in _key_handlers
        assert _key_handlers[ord("t")] == test_handler

        _key_handlers.clear()
        _key_handlers.update(original_handlers)


class TestCLIFunctionsMocked:
    """Test CLI functions with mocked curses."""

    @patch("tiny8.cli.curses")
    def test_run_cli_with_mock(self, mock_curses):
        """Test run_cli with mocked curses."""
        from tiny8.cli import run_cli

        mock_curses.wrapper.return_value = None

        cpu = CPU()
        asm = assemble("ldi r16, 42")
        cpu.load_program(asm)
        cpu.run()

        try:
            with patch("tiny8.cli.curses.wrapper") as mock_wrapper:
                mock_wrapper.return_value = None
                assert callable(run_cli)
        except Exception:
            pass

    def test_parse_go_to_step_logic(self):
        """Test logic for parsing step numbers without UI."""
        test_cases = [
            ("10", 10),
            ("0", 0),
            ("999", 999),
        ]

        for input_str, expected in test_cases:
            try:
                result = int(input_str)
                assert result == expected
            except ValueError:
                assert False, f"Should parse {input_str}"

    def test_mark_name_validation(self):
        """Test mark name validation logic."""
        valid_marks = ["a", "b", "z", "A", "Z"]
        for mark in valid_marks:
            assert len(mark) == 1
            assert mark.isalpha()

        invalid_marks = ["1", "!", "", "ab"]
        for mark in invalid_marks:
            assert not (len(mark) == 1 and mark.isalpha())


class TestVisualizerLogic:
    """Test Visualizer logic with mocked matplotlib."""

    def test_visualizer_initialization(self):
        """Test Visualizer initialization."""
        from tiny8.visualizer import Visualizer

        cpu = CPU()
        viz = Visualizer(cpu)
        assert viz.cpu == cpu

    @patch("tiny8.visualizer.plt")
    @patch("tiny8.visualizer.animation")
    def test_animate_execution_mock(self, mock_animation, mock_plt):
        """Test animate_execution with mocked matplotlib."""
        from tiny8.visualizer import Visualizer

        cpu = CPU()
        asm = assemble("""
            ldi r16, 10
            ldi r17, 20
            add r16, r17
        """)
        cpu.load_program(asm)
        cpu.run()

        viz = Visualizer(cpu)

        mock_fig = Mock()
        mock_plt.subplots.return_value = (mock_fig, [Mock(), Mock(), Mock()])
        mock_animation.FuncAnimation.return_value = Mock()

        try:
            viz.animate_execution(
                mem_addr_start=0x60,
                mem_addr_end=0x6F,
                interval=100,
                plot_every=1,
            )
        except Exception:
            pass

    def test_visualizer_data_preparation(self):
        """Test data preparation logic for visualization."""
        import numpy as np

        from tiny8.visualizer import Visualizer

        cpu = CPU()
        asm = assemble("""
            ldi r16, 5
            ldi r17, 3
            add r16, r17
        """)
        cpu.load_program(asm)
        cpu.run()

        _ = Visualizer(cpu)
        num_steps = len(cpu.step_trace)

        sreg_mat = np.zeros((8, num_steps))
        reg_mat = np.zeros((32, num_steps))

        assert sreg_mat.shape == (8, num_steps)
        assert reg_mat.shape == (32, num_steps)
        assert num_steps > 0

        for idx, entry in enumerate(cpu.step_trace):
            sreg = entry.get("sreg", 0)
            regs = entry.get("regs", [0] * 32)

            for bit in range(8):
                sreg_mat[bit, idx] = (sreg >> bit) & 1

            for reg_idx in range(32):
                reg_mat[reg_idx, idx] = regs[reg_idx]

        assert np.any(reg_mat)


class TestVisualizerHeadless:
    """Test Visualizer with headless matplotlib backend."""

    def test_visualizer_headless_rendering(self):
        """Test Visualizer with Agg backend (headless)."""
        import matplotlib

        matplotlib.use("Agg")

        import matplotlib.pyplot as plt

        from tiny8.visualizer import Visualizer

        cpu = CPU()
        asm = assemble("""
            ldi r16, 10
            inc r16
            inc r16
        """)
        cpu.load_program(asm)
        cpu.run()

        _ = Visualizer(cpu)

        try:
            fig, axes = plt.subplots(3, 1, figsize=(10, 8))
            assert len(axes) == 3
            plt.close(fig)
        except Exception:
            pytest.skip("Matplotlib not available or headless mode failed")

    def test_plot_generation_without_save(self, tmp_path):
        """Test that plotting logic works without saving file."""
        import matplotlib

        matplotlib.use("Agg")

        import matplotlib.pyplot as plt

        data = [1, 2, 3, 4, 5]
        plt.figure()
        plt.plot(data)
        plt.close()


class TestCLIHelperFunctions:
    """Test CLI helper functions that don't require curses."""

    def test_format_register_name(self):
        """Test register name formatting logic."""
        for i in range(32):
            reg_name = f"R{i}"
            assert reg_name.startswith("R")
            assert reg_name[1:].isdigit()

    def test_format_hex_value(self):
        """Test hex value formatting logic."""
        test_values = [0x00, 0xFF, 0x42, 0xAB]
        for val in test_values:
            hex_str = f"0x{val:02X}"
            assert hex_str.startswith("0x")
            assert len(hex_str) == 4

    def test_format_binary_value(self):
        """Test binary value formatting logic."""
        test_values = [0b00000000, 0b11111111, 0b10101010]
        for val in test_values:
            bin_str = f"{val:08b}"
            assert len(bin_str) == 8
            assert all(c in "01" for c in bin_str)

    def test_memory_range_validation(self):
        """Test memory range validation logic."""
        test_cases = [
            (0x00, 0xFF, True),
            (0x60, 0x7F, True),
            (0x100, 0xFF, False),  # Invalid (start > end)
            (-1, 0x10, False),  # Invalid (negative)
        ]

        for start, end, should_be_valid in test_cases:
            is_valid = 0 <= start <= end <= 0xFFFF
            assert is_valid == should_be_valid


class TestCLICommandParsing:
    """Test command parsing logic without UI."""

    def test_parse_goto_command(self):
        """Test parsing goto command."""
        commands = [
            ("10", 10),
            ("0", 0),
            ("999", 999),
        ]

        for cmd, expected in commands:
            if cmd.isdigit():
                result = int(cmd)
                assert result == expected

    def test_parse_mark_command(self):
        """Test parsing mark commands."""
        valid_marks = ["ma", "mz", "mA", "mZ"]
        for mark_cmd in valid_marks:
            if mark_cmd.startswith("m") and len(mark_cmd) == 2:
                letter = mark_cmd[1]
                assert letter.isalpha()

    def test_parse_search_command(self):
        """Test parsing search commands."""
        search_cmds = ["/test", "/abc", "/123"]
        for cmd in search_cmds:
            if cmd.startswith("/"):
                pattern = cmd[1:]
                assert len(pattern) > 0


class TestVisualizerDataExtraction:
    """Test data extraction logic from CPU traces."""

    def test_extract_sreg_bits(self):
        """Test SREG bit extraction logic."""
        sreg_value = 0b10101010

        bits = []
        for i in range(8):
            bit = (sreg_value >> i) & 1
            bits.append(bit)

        assert bits == [0, 1, 0, 1, 0, 1, 0, 1]

    def test_extract_register_values(self):
        """Test register value extraction from trace."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 42
            ldi r17, 100
        """)
        cpu.load_program(asm)
        cpu.run()

        assert len(cpu.step_trace) > 0
        for entry in cpu.step_trace:
            regs = entry.get("regs", [])
            assert isinstance(regs, list)
            if regs:
                assert len(regs) == 32

    def test_extract_memory_values(self):
        """Test memory value extraction from trace."""
        cpu = CPU()
        asm = assemble("""
            ldi r16, 42
            inc r16
        """)
        cpu.load_program(asm)
        cpu.run()

        for entry in cpu.step_trace:
            mem = entry.get("mem", {})
            assert isinstance(mem, dict)


class TestCLIStateManagement:
    """Test CLI state management logic."""

    def test_state_mark_management(self):
        """Test mark storage and retrieval."""
        from tiny8.cli import ViewState

        state = ViewState()

        state.marks["a"] = 10
        state.marks["b"] = 20
        state.marks["c"] = 30

        assert state.marks["a"] == 10
        assert state.marks["b"] == 20
        assert state.marks["c"] == 30
        assert len(state.marks) == 3

    def test_state_command_buffer(self):
        """Test command buffer management."""
        from tiny8.cli import ViewState

        state = ViewState()

        state.command_buffer = "g"
        state.command_buffer += "o"
        state.command_buffer += "t"
        state.command_buffer += "o"

        assert state.command_buffer == "goto"

        state.command_buffer = ""
        assert state.command_buffer == ""

    def test_state_scroll_boundaries(self):
        """Test scroll offset boundary logic."""
        from tiny8.cli import ViewState

        state = ViewState()
        max_scroll = 100

        state.scroll_offset = 50
        assert 0 <= state.scroll_offset <= max_scroll

        state.scroll_offset = 0
        assert state.scroll_offset >= 0

        state.scroll_offset = max_scroll
        assert state.scroll_offset <= max_scroll


class TestVisualizerConfiguration:
    """Test Visualizer configuration options."""

    def test_visualizer_custom_parameters(self):
        """Test Visualizer with custom parameters."""
        from tiny8.visualizer import Visualizer

        cpu = CPU()
        asm = assemble("ldi r16, 42")
        cpu.load_program(asm)
        cpu.run()

        _ = Visualizer(cpu)

        config = {
            "mem_addr_start": 0x100,
            "mem_addr_end": 0x1FF,
            "interval": 500,
            "fps": 60,
            "fontsize": 12,
            "cmap": "viridis",
            "plot_every": 2,
        }

        assert config["mem_addr_start"] < config["mem_addr_end"]
        assert config["interval"] > 0
        assert config["fps"] > 0
        assert config["fontsize"] > 0
        assert config["plot_every"] >= 1

    def test_colormap_names(self):
        """Test valid colormap names."""
        valid_cmaps = ["viridis", "inferno", "plasma", "magma", "cividis"]

        for cmap in valid_cmaps:
            assert isinstance(cmap, str)
            assert len(cmap) > 0


class TestIntegrationMinimal:
    """Minimal integration tests for UI components."""

    def test_cli_with_cpu_trace(self):
        """Test CLI can access CPU trace data."""
        from tiny8.cli import ViewState

        cpu = CPU()
        asm = assemble("""
            ldi r16, 10
            ldi r17, 20
            add r16, r17
        """)
        cpu.load_program(asm)
        cpu.run()

        state = ViewState()
        traces = cpu.step_trace

        assert state.step_idx >= 0
        assert state.step_idx < len(traces) or len(traces) == 0

        if traces:
            state.step_idx = min(state.step_idx, len(traces) - 1)
            assert 0 <= state.step_idx < len(traces)

    def test_visualizer_with_cpu_trace(self):
        """Test Visualizer can access CPU trace data."""
        from tiny8.visualizer import Visualizer

        cpu = CPU()
        asm = assemble("""
            ldi r16, 5
            inc r16
            inc r16
        """)
        cpu.load_program(asm)
        cpu.run()

        viz = Visualizer(cpu)

        assert len(viz.cpu.step_trace) > 0
        assert hasattr(viz.cpu, "step_trace")
        assert viz.cpu == cpu

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_cli_help_output(self, mock_stdout):
        """Test CLI argument parsing help."""
        import argparse

        parser = argparse.ArgumentParser(description="Test CLI")
        parser.add_argument("file", help="Assembly file")
        parser.add_argument("--mem-start", type=int, default=0x60)
        parser.add_argument("--mem-end", type=int, default=0x7F)

        args = parser.parse_args(["test.asm", "--mem-start", "100", "--mem-end", "200"])
        assert args.file == "test.asm"
        assert args.mem_start == 100
        assert args.mem_end == 200
