"""Tests for modern Textual CLI and widgets."""

import asyncio
import pytest
from textual.widgets import Input

from tiny8 import CPU, assemble
from tiny8.tui import (
    BtopRegistersWidget,
    CVariablesWidget,
    CallStackWidget,
    CheckpointManager,
    CodeViewWidget,
    InstructionDetailWidget,
    LazyStatusWidget,
    MemoryMatrixWidget,
    MemoryWidget,
    RegistersWidget,
    SregWidget,
    StackWidget,
    TelemetryWidget,
    Tiny8App,
    TUIHelpScreen,
    CacheProgressModalScreen,
    InstructionDetailModalScreen,
    VimEditorScreen,
    VimTextArea,
    eval_condition,
    extract_call_frames,
    run_cli,
)


def create_tested_cpu() -> CPU:
    asm_src = """
    LDI R16, 42
    PUSH R16
    MOV R0, R16
    INC R16
    """
    asm = assemble(asm_src)
    cpu = CPU()
    cpu.load_program(asm)
    cpu.run(max_steps=10, show_progress=False)
    return cpu


def test_sreg_widget_rendering():
    widget = SregWidget()
    widget.sreg = 0b00000001
    rendered = widget.render().plain
    assert "C" in rendered
    assert "0x01" in rendered


def test_btop_registers_widget_rendering():
    widget = BtopRegistersWidget()
    widget.regs = [0] * 32
    widget.regs[0] = 5
    widget.regs[16] = 42
    widget.regs[31] = 255
    widget.prev_regs = [0] * 32
    widget.prev_regs[16] = 10
    rendered = widget.render().plain
    assert "REGISTERS (R00..R31)" in rendered
    assert "R00" in rendered
    assert "R15" in rendered
    assert "R16" in rendered
    assert "R31" in rendered
    assert "0x2A" in rendered
    assert "0xFF" in rendered


def test_registers_widget_rendering():
    widget = RegistersWidget()
    widget.regs = [0] * 32
    widget.regs[16] = 42
    rendered = widget.render().plain
    assert "REGISTERS" in rendered
    assert "R16:2A" in rendered


def test_memory_widget_rendering():
    widget = MemoryWidget()
    widget.start_addr = 0x60
    widget.mem = {0x60: 65, 0x61: 66}
    rendered = widget.render().plain
    assert "MEMORY DUMP" in rendered
    assert "j/k: scroll" in rendered
    assert "0x0060:" in rendered
    assert "4142" in rendered


def test_memory_widget_grayscale_and_hex_toggles():
    widget = MemoryWidget()
    widget.start_addr = 0x60
    widget.mem = {0x60: 255, 0x61: 0}

    # Default Viridis + Hex
    assert widget.color_mode == "viridis"
    assert widget.show_hex is True
    assert "FF.." in widget.render().plain

    # Switch to Grayscale + Pixel
    widget.color_mode = "grayscale"
    widget.show_hex = False
    assert widget.get_heatmap_bg(255, "grayscale") == "#FFFFFF"
    assert widget.get_heatmap_bg(0, "grayscale") == "#000000"
    rendered_pixel = widget.render().plain
    assert "Grayscale" in rendered_pixel
    assert "PIXEL" in rendered_pixel
    assert "FF.." not in rendered_pixel


def test_stack_widget_rendering():
    widget = StackWidget()
    widget.ram_size = 2048
    widget.sp = 2046  # 1 entry pushed
    widget.mem = {2047: 42}
    rendered = widget.render().plain
    assert "CALL STACK" in rendered
    assert "0x07FE" in rendered
    assert "42" in rendered


def test_instruction_detail_widget_rendering():
    widget = InstructionDetailWidget()
    widget.current_instr = "ADD R16, R17"
    widget.pc = 0x0005
    widget.sp = 0x07FE
    widget.source_line = 12
    widget.source_text = "add r16, r17"
    rendered = widget.render().plain
    assert "INSTRUCTION INSPECTOR" in rendered
    assert "ADD R16, R17" in rendered
    assert "Add without Carry" in rendered
    assert "0x0005" in rendered
    assert "Line 13" in rendered


def test_telemetry_widget_rendering():
    widget = TelemetryWidget()
    widget.total_steps = 10
    widget.current_step = 5
    widget.instr_counts = {"ADD": 3, "LDI": 2}
    rendered = widget.render().plain
    assert "EXECUTION TELEMETRY" in rendered
    assert "5/10" in rendered
    assert "ADD" in rendered


def test_code_view_widget_rendering():
    widget = CodeViewWidget()
    widget.program = [("LDI", (("reg", 16), 10)), ("ADD", (("reg", 16), ("reg", 0)))]
    widget.current_pc = 0
    widget.breakpoints = {1}
    rendered_text = widget.render()
    rendered = rendered_text.plain
    assert "PROGRAM EXECUTION" in rendered
    assert "LDI" in rendered
    assert "●" in rendered
    # Non-current line (ADD) should be styled white (#FFFFFF)
    spans = [
        span
        for span in rendered_text.spans
        if str(span.style) == "#ffffff" or str(span.style) == "#FFFFFF"
    ]
    assert len(spans) > 0


def test_lazy_status_widget_rendering():
    widget = LazyStatusWidget()
    widget.mode = "NORMAL"
    widget.filename = "factorial.c"
    widget.current_step = 5
    widget.total_steps = 20
    widget.current_pc = 0x000E
    widget.current_sp = 0x07FE
    widget.current_instr = "ADD R16, R17"
    rendered = widget.render().plain
    assert "NORMAL" in rendered
    assert "factorial.c" in rendered
    assert "Step: 5" in rendered
    assert "0x000E" in rendered
    assert "ADD R16, R17" in rendered
    assert "h: help" in rendered


def test_tiny8_app_navigation_and_features():
    async def _test():
        cpu = create_tested_cpu()
        app = Tiny8App(cpu=cpu)
        async with app.run_test() as pilot:
            assert app.current_idx == 0

            # Step forward
            await pilot.press("n")
            assert app.current_idx == 1

            # Step backward
            await pilot.press("p")
            assert app.current_idx == 0

            # Toggle breakpoint
            await pilot.press("b")
            assert len(app.breakpoints) == 1
            await pilot.press("b")
            assert len(app.breakpoints) == 0

            # Set breakpoint at PC=2 and continue
            app.breakpoints.add(2)
            await pilot.press("c")
            assert app.current_idx == 2

            # Memory scroll
            initial_mem = app.mem_start
            await pilot.press("j")
            assert app.mem_start == initial_mem + 32
            await pilot.press("k")
            assert app.mem_start == initial_mem
            await pilot.press("J")
            assert app.mem_start == initial_mem + 128
            await pilot.press("K")
            assert app.mem_start == initial_mem

            # Toggle play/pause
            await pilot.press("space")
            assert app.playing is True
            await pilot.press("space")
            assert app.playing is False

            # Reset
            app.current_idx = 2
            await pilot.press("r")
            assert app.current_idx == 0

            # Open reference modal with 'i'
            await pilot.press("i")
            assert len(app.screen_stack) == 2
            await pilot.press("escape")
            assert len(app.screen_stack) == 1

            # Open reference modal with 'h'
            await pilot.press("h")
            assert len(app.screen_stack) == 2
            await pilot.press("escape")
            assert len(app.screen_stack) == 1

            # Command bar open and cancel
            await pilot.press("colon")
            cmd_bar = app.query_one("#command-bar")
            assert cmd_bar.styles.display == "block"
            await pilot.press("escape")
            assert cmd_bar.styles.display == "none"

            # Command bar execution with ':'
            await pilot.press(":")
            assert cmd_bar.styles.display == "block"
            inp = app.query_one("#cmd-input")
            assert inp.has_focus
            await pilot.press("g", "o", "t", "o", " ", "2")
            await pilot.press("enter")
            assert cmd_bar.styles.display == "none"
            assert app.current_idx == 2

            # Command bar breakpoint command
            await pilot.press(":")
            await pilot.press("b", " ", "1")
            await pilot.press("enter")
            assert 1 in app.breakpoints

    asyncio.run(_test())


def test_run_cli_empty_trace_raises():
    cpu = CPU()
    with pytest.raises(RuntimeError):
        run_cli(cpu)


def test_vim_editor_workflow(tmp_path):
    from pathlib import Path

    async def _test():
        test_file = str(tmp_path / "prog.c")
        app = Tiny8App(file_path=test_file, start_in_editor=True)
        async with app.run_test() as pilot:
            assert len(app.screen_stack) == 2
            editor_screen = app.screen_stack[-1]
            assert isinstance(editor_screen, VimEditorScreen)

            editor = editor_screen.query_one("#vim-editor", VimTextArea)
            assert editor.mode == "NORMAL"

            # Press 'i' to enter INSERT mode
            await pilot.press("i")
            assert editor.mode == "INSERT"

            # Press Escape to return to NORMAL mode
            await pilot.press("escape")
            assert editor.mode == "NORMAL"

            # Write C program
            editor.text = "int main() { return 77; }"
            await pilot.pause()

            # Execute :w command to save
            editor_screen.handle_vim_command("w")
            assert Path(test_file).exists()
            assert "77" in Path(test_file).read_text(encoding="utf-8")

            # Execute :run command to compile, execute, and switch to debugger
            editor_screen.handle_vim_command("run")
            await pilot.pause()
            assert len(app.screen_stack) == 1
            assert app.num_traces > 0
            assert app.cpu.regs[16] == 77

            # Press 'e' in debugger to reopen editor
            await pilot.press("e")
            assert len(app.screen_stack) == 2
            editor_screen2 = app.screen_stack[-1]
            assert isinstance(editor_screen2, VimEditorScreen)

            # Exit editor with :q
            editor_screen2.handle_vim_command("q")
            await pilot.pause()
            assert len(app.screen_stack) == 1

    asyncio.run(_test())


def test_eval_condition():
    regs = [0] * 32
    regs[0] = 5
    regs[16] = 42
    mem = {0x60: 100, 0x61: 0}

    assert eval_condition("R0 == 5", regs, mem) is True
    assert eval_condition("R0 != 5", regs, mem) is False
    assert eval_condition("R16 > 40", regs, mem) is True
    assert eval_condition("R16 < 40", regs, mem) is False
    assert eval_condition("mem[0x60] == 100", regs, mem) is True
    assert eval_condition("mem[0x60] >= 100", regs, mem) is True
    assert eval_condition("mem[0x61] == 0", regs, mem) is True
    assert eval_condition("R0", regs, mem) is True
    assert eval_condition("R1", regs, mem) is False
    assert eval_condition("invalid_expr", regs, mem) is False


def test_extract_call_frames():
    traces = [
        {"instr": "LDI R16, 1", "pc": 0, "sp": 2047},
        {"instr": "RCALL my_func", "pc": 1, "sp": 2047},
        {"instr": "ADD R16, R16", "pc": 5, "sp": 2045},
        {"instr": "RET", "pc": 6, "sp": 2045},
    ]

    frames_at_1 = extract_call_frames(traces, 1)
    assert len(frames_at_1) == 1
    assert frames_at_1[0]["func"] == "my_func"

    frames_at_3 = extract_call_frames(traces, 3)
    assert len(frames_at_3) == 0


def test_c_variables_widget():
    w = CVariablesWidget()
    assert "(No C variable symbols loaded)" in w.render().plain

    w.var_symbols = {
        "x": {"addr": 0x60, "type": "int"},
        "y": {"addr": 0x61, "type": "int"},
    }
    w.mem = {0x60: 42, 0x61: 0}
    w.prev_mem = {0x60: 10, 0x61: 0}
    rendered = w.render().plain
    assert "C VARIABLES" in rendered
    assert "x" in rendered
    assert "0x0060" in rendered
    assert "0x2A" in rendered
    assert "UPDATED" in rendered
    assert "ZERO" in rendered


def test_call_stack_widget():
    w = CallStackWidget()
    w.current_pc = 0x0010
    assert "main() at PC:0x0010" in w.render().plain

    w.frames = [{"func": "calc", "pc": 0x0004, "sp": 0x07FE}]
    rendered = w.render().plain
    assert "calc()" in rendered
    assert "PC:0x0004" in rendered


def test_memory_matrix_widget():
    w = MemoryMatrixWidget()
    w.base_addr = 0x60
    w.mem = {0x60: 10}
    w.write_counts = {0x60: 2}
    w.read_counts = {0x61: 1}
    rendered = w.render().plain
    assert "2D RAM ACCESS ACTIVITY MATRIX" in rendered
    assert "0x0060:" in rendered


def test_advanced_debugger_features():
    cpu = create_tested_cpu()

    async def _test():
        app = Tiny8App(cpu=cpu)
        async with app.run_test():
            # 1. Conditional Breakpoint
            app.on_input_submitted(
                Input.Submitted(app.query_one("#cmd-input", Input), "b 3 if R16 == 43")
            )
            assert 3 in app.breakpoints
            assert app.conditional_breakpoints.get(3) == "R16 == 43"

            # 2. Watchpoints
            app.on_input_submitted(
                Input.Submitted(app.query_one("#cmd-input", Input), "watch R0")
            )
            assert "R0" in app.watchpoints

            # 3. Bookmarks
            app.on_input_submitted(
                Input.Submitted(app.query_one("#cmd-input", Input), "mark loop_start")
            )
            assert "loop_start" in app.bookmarks

            # Jump via bookmark
            app.current_idx = 0
            app.on_input_submitted(
                Input.Submitted(app.query_one("#cmd-input", Input), "'loop_start")
            )
            assert app.current_idx == app.bookmarks["loop_start"]

            # 4. State Rewriting (:set, :poke)
            app.on_input_submitted(
                Input.Submitted(app.query_one("#cmd-input", Input), "set R5 77")
            )
            assert app.traces[app.current_idx]["regs"][5] == 77

            app.on_input_submitted(
                Input.Submitted(app.query_one("#cmd-input", Input), "poke 0x70 99")
            )
            assert app.traces[app.current_idx]["mem"][0x70] == 99

            # 5. REPL (:exec)
            prev_traces_count = len(app.traces)
            app.on_input_submitted(
                Input.Submitted(app.query_one("#cmd-input", Input), "exec LDI R17, 88")
            )
            assert len(app.traces) == prev_traces_count + 1
            assert app.traces[app.current_idx]["regs"][17] == 88

            # 6. Reverse Continue (Shift+C / action_reverse_continue)
            app.current_idx = len(app.traces) - 1
            app.action_reverse_continue()
            assert app.current_idx <= len(app.traces) - 2

            # 7. Clear breakpoints (:bc)
            app.on_input_submitted(
                Input.Submitted(app.query_one("#cmd-input", Input), "bc")
            )
            assert len(app.breakpoints) == 0
            assert len(app.conditional_breakpoints) == 0

            # 8. Unwatch (:unwatch)
            app.on_input_submitted(
                Input.Submitted(app.query_one("#cmd-input", Input), "unwatch")
            )
            assert len(app.watchpoints) == 0

            # 9. Grayscale & Hex Mode Toggles
            assert app.color_mode == "viridis"
            assert app.show_hex is True
            app.action_toggle_grayscale()
            assert app.color_mode == "grayscale"
            app.action_toggle_hex()
            assert app.show_hex is False
            app.action_cycle_mode()
            assert app.color_mode == "grayscale"
            assert app.show_hex is True

            # Via command bar
            app.on_input_submitted(
                Input.Submitted(app.query_one("#cmd-input", Input), "viridis")
            )
            assert app.color_mode == "viridis"
            app.on_input_submitted(
                Input.Submitted(app.query_one("#cmd-input", Input), "pixel")
            )
            assert app.show_hex is False

    asyncio.run(_test())


def test_help_and_instruction_detail_screens():
    async def _test():
        cpu = create_tested_cpu()
        app = Tiny8App(cpu=cpu)
        async with app.run_test() as pilot:
            # Press 'h' -> should open TUIHelpScreen
            await pilot.press("h")
            assert isinstance(app.screen, TUIHelpScreen)
            await pilot.press("escape")
            assert not isinstance(app.screen, TUIHelpScreen)

            # Press 'question_mark' -> should open TUIHelpScreen
            await pilot.press("question_mark")
            assert isinstance(app.screen, TUIHelpScreen)
            await pilot.press("escape")
            assert not isinstance(app.screen, TUIHelpScreen)

            # Press 'i' -> should open InstructionDetailModalScreen for current instruction
            await pilot.press("i")
            assert isinstance(app.screen, InstructionDetailModalScreen)
            # Check current instruction details
            assert app.screen.instr != ""
            assert "0x" in hex(app.screen.pc)
            await pilot.press("escape")
            assert not isinstance(app.screen, InstructionDetailModalScreen)

    asyncio.run(_test())


def test_vim_editor_quit_command():
    async def _test():
        cpu = create_tested_cpu()
        app = Tiny8App(cpu=cpu)
        async with app.run_test() as pilot:
            # Open Vim editor with 'e'
            await pilot.press("e")
            assert isinstance(app.screen, VimEditorScreen)

            # Type :q and submit
            await pilot.press("colon")
            await pilot.press("q")
            await pilot.press("enter")

            # Must return to debugger screen, and CLI app must NOT exit
            assert not isinstance(app.screen, VimEditorScreen)
            assert app.is_running is True

    asyncio.run(_test())


def test_statusline_step_count_exceeds_999():
    """Verify statusline current_step accurately displays step numbers beyond 999."""

    async def _test():
        from tiny8.assembler import assemble
        from tiny8.tui import LazyStatusWidget

        # Infinite counter loop:
        # loop: INC R16, RJMP loop
        asm = assemble("loop:\n    INC R16\n    RJMP loop")
        cpu = CPU()
        cpu.load_program(asm)
        # Execute 1500 steps so deque maxlen (1000) is exceeded
        cpu.run(max_steps=1500, show_progress=False)
        assert cpu.step_count == 1500

        app = Tiny8App(cpu=cpu)
        app.current_idx = app.num_traces - 1
        async with app.run_test():
            lazy_status = app.query_one("#lazy-status", LazyStatusWidget)
            # Must reflect actual step count (1500), not ring buffer index 999
            assert lazy_status.current_step == 1500
            rendered = lazy_status.render().plain
            assert "Step: 1500" in rendered
            assert "h: help" in rendered

    asyncio.run(_test())


def test_playback_speed_and_adaptive_batching():
    """Verify playback speed acceleration down to 30ms visual limit and automatic batch scaling."""

    async def _test():
        cpu = create_tested_cpu()
        app = Tiny8App(cpu=cpu)
        async with app.run_test() as pilot:
            # Initial defaults
            assert app.speed_ms == 100
            assert app.playback_rate_idx == 0
            assert app.batch_size == 1

            # Press '+' repeatedly to accelerate visually down to 30ms:
            # 100 -> 80 -> 60 -> 40 -> 30 (4 steps)
            for _ in range(4):
                await pilot.press("+")
            assert app.speed_ms == 30
            assert app.playback_rate_idx == 0
            assert app.batch_size == 1

            # Once at visual threshold (30ms), pressing '+' automatically transitions to batch processing:
            # 1 -> 5 -> 20 -> 100
            await pilot.press("+")
            assert app.speed_ms == 30
            assert app.playback_rate_idx == 1
            assert app.batch_size == 5

            await pilot.press("+")
            assert app.playback_rate_idx == 2
            assert app.batch_size == 20

            # Press '-' -> batch decreases back to 5, then 1
            await pilot.press("-")
            assert app.playback_rate_idx == 1
            assert app.batch_size == 5

            await pilot.press("-")
            assert app.playback_rate_idx == 0
            assert app.batch_size == 1

            # Press '-' again -> visual interval increases: 30 -> 50ms
            await pilot.press("-")
            assert app.speed_ms == 50

            # Test command bar :speed 25
            await pilot.press(":")
            await pilot.press("s", "p", "e", "e", "d", " ", "2", "5")
            await pilot.press("enter")
            assert app.speed_ms == 25

            # Test command bar :batch 10000
            await pilot.press(":")
            await pilot.press("b", "a", "t", "c", "h", " ", "1", "0", "0", "0", "0")
            await pilot.press("enter")
            assert app.batch_size == 10000

            # Test command bar :turbo
            await pilot.press(":")
            await pilot.press("t", "u", "r", "b", "o")
            await pilot.press("enter")
            assert app.speed_ms == 30
            assert app.batch_size == 50000

            # Test command bar :normal
            await pilot.press(":")
            await pilot.press("n", "o", "r", "m", "a", "l")
            await pilot.press("enter")
            assert app.speed_ms == 100
            assert app.batch_size == 1

    asyncio.run(_test())


def test_checkpoint_manager_snapshot_and_time_travel():
    """Verify 100-step sparse snapshots, exact step restoration, and cache invalidation."""
    asm_src = """
    LDI R16, 0
loop:
    INC R16
    CPI R16, 250
    BRNE loop
    """
    asm = assemble(asm_src)
    cpu = CPU()
    cpu.load_program(asm)

    mgr = CheckpointManager(cpu, interval=100)
    assert 0 in mgr.checkpoint_steps

    # Step through 250 instructions
    for _ in range(250):
        cpu.step()
        mgr.record_if_interval(cpu.step_count)

    assert 100 in mgr.checkpoint_steps
    assert 200 in mgr.checkpoint_steps
    assert len(mgr.checkpoint_steps) >= 3

    # Restore step 150 (nearest checkpoint is 100, then advance 50 steps)
    ok = mgr.restore_exact_step(150)
    assert ok is True
    assert cpu.step_count == 150

    # Test cache invalidation on memory/register edit
    mgr.invalidate_after(120)
    assert 200 not in mgr.checkpoint_steps
    assert 100 in mgr.checkpoint_steps
    assert 0 in mgr.checkpoint_steps


def test_checkpoint_manager_infinite_loop_detection():
    """Verify detection of HALT spin-loops and cycle loops."""
    # 1. HALT spin loop: RJMP 0 (jump to self)
    asm_spin = assemble("loop: RJMP loop")
    cpu_spin = CPU()
    cpu_spin.load_program(asm_spin)
    mgr_spin = CheckpointManager(cpu_spin)
    assert mgr_spin.detect_loop() is True
    assert "HALT" in mgr_spin.loop_reason

    # 2. Cycle loop: NOP; NOP; RJMP -2
    asm_cycle = assemble("loop: NOP\nNOP\nRJMP loop")
    cpu_cycle = CPU()
    cpu_cycle.load_program(asm_cycle)
    mgr_cycle = CheckpointManager(cpu_cycle)
    # Advance a few cycles
    detected = False
    for _ in range(30):
        cpu_cycle.step()
        if mgr_cycle.detect_loop(window_size=16):
            detected = True
            break
    assert detected is True
    assert "Cycle" in mgr_cycle.loop_reason


def test_reverse_playback_and_mode_switching():
    """Verify reverse playback toggle, mode switching, and precomputing."""

    async def _test():
        cpu = create_tested_cpu()
        app = Tiny8App(cpu=cpu)
        async with app.run_test() as pilot:
            # Default execution mode is cache
            assert app.execution_mode == "cache"

            # Switch mode via command
            await pilot.press(":")
            await pilot.press("m", "o", "d", "e", " ", "l", "i", "v", "e")
            await pilot.press("enter")
            assert app.execution_mode == "live"

            await pilot.press(":")
            await pilot.press("c", "a", "c", "h", "e")
            await pilot.press("enter")
            assert app.execution_mode == "cache"

            # Reverse playback toggle
            assert app.playing is False
            await pilot.press("shift+space")
            assert app.playing is True
            assert app.play_direction == -1
            await pilot.press("shift+space")
            assert app.playing is False

            # Precompute command
            await pilot.press(":")
            await pilot.press(
                "p", "r", "e", "c", "o", "m", "p", "u", "t", "e", " ", "5", "0"
            )
            await pilot.press("enter")
            assert len(app.checkpoint_manager.checkpoint_steps) >= 1

    asyncio.run(_test())


def test_default_cache_mode_and_precompute_before_execution():
    """Verify cache mode is default and cache data is created before execution starts."""
    asm_src = """
    LDI R16, 0
loop:
    INC R16
    CPI R16, 250
    BRNE loop
    """
    asm = assemble(asm_src)
    cpu = CPU()
    cpu.load_program(asm)

    app = Tiny8App(cpu=cpu, max_steps=500, precompute_cache=True)
    # Verify default mode is cache
    assert app.execution_mode == "cache"

    # Verify cache data was created before execution
    assert 0 in app.checkpoint_manager.checkpoint_steps
    assert 100 in app.checkpoint_manager.checkpoint_steps
    assert 200 in app.checkpoint_manager.checkpoint_steps
    assert len(app.checkpoint_manager.checkpoint_steps) >= 3

    # Verify app started at step 0
    assert app.current_idx == 0

    async def _test():
        async with app.run_test() as pilot:
            await pilot.press(":")
            await pilot.press("g", "o", "t", "o", " ", "2", "0", "0")
            await pilot.press("enter")
            assert app.current_idx == 200

            # Seek to step 300 via cache restore
            ok = app.checkpoint_manager.restore_exact_step(300)
            assert ok is True
            assert app.cpu.step_count == 300

    asyncio.run(_test())


def test_goto_large_step_via_cache_and_dynamic_extension():
    """Verify :goto with large step jumps instantly via cache checkpoints and extends dynamically."""
    asm_src = """
    LDI R16, 0
loop:
    INC R16
    CPI R16, 250
    BRNE loop
    LDI R16, 0
    RJMP loop
    """
    asm = assemble(asm_src)
    cpu = CPU()
    cpu.load_program(asm)

    # CheckpointManager with initial precompute of 5000 steps
    mgr = CheckpointManager(cpu, interval=100)
    mgr.precompute(max_steps=5000)
    assert mgr.checkpoint_steps[-1] >= 5000

    # 1. Direct restore within precomputed checkpoints
    ok = mgr.restore_exact_step(4500)
    assert ok is True
    assert cpu.step_count == 4500

    # 2. Dynamic extension beyond initial checkpoints (e.g. step 20000)
    ok2 = mgr.restore_exact_step(20000)
    assert ok2 is True
    assert cpu.step_count == 20000
    assert 20000 in mgr.checkpoint_steps


def test_auto_step_infinite_loop_stops_playback_without_freezing():
    """Verify that playing into a HALT spin loop automatically stops playback and updates ProfilerWidget safely."""
    asm_src = """
    LDI R16, 3
loop:
    DEC R16
    BRNE loop
halt_loop:
    RJMP halt_loop
    """
    asm = assemble(asm_src)
    cpu = CPU()
    cpu.load_program(asm)

    mgr = CheckpointManager(cpu, interval=10)
    mgr.precompute(max_steps=500)

    app = Tiny8App(cpu=cpu, checkpoint_manager=mgr, execution_mode="cache")
    app.playback_rate_idx = 7  # x50,000
    app.speed_ms = 30
    app.playing = True
    app.play_direction = 1

    # Trigger _auto_step: it advances towards 50,000, hits halt_loop, and auto-stops
    app._auto_step()

    assert app.playing is False
    assert mgr.infinite_loop_detected is True
    assert "HALT spin loop" in mgr.loop_reason


def test_cache_progress_modal_and_visual_precompute():
    """Verify that CacheProgressModalScreen updates and Tiny8App with show_cache_progress precomputes on mount."""
    modal = CacheProgressModalScreen(max_steps=1000)
    assert modal.target_steps == 1000

    asm_src = """
    LDI R16, 0
loop:
    INC R16
    CPI R16, 50
    BRNE loop
    """
    asm = assemble(asm_src)
    cpu = CPU()
    cpu.load_program(asm)

    app = Tiny8App(
        cpu=cpu,
        max_steps=200,
        precompute_cache=True,
        show_cache_progress=True,
    )

    async def _test():
        async with app.run_test() as pilot:
            # Wait for background precomputation worker to complete
            for _ in range(50):
                await pilot.pause(0.05)
                if not isinstance(app.screen, CacheProgressModalScreen):
                    break
            # Checkpoints should be created
            assert len(app.checkpoint_manager.checkpoint_steps) >= 2
            assert app.current_idx == 0

    asyncio.run(_test())


def test_precompute_until_infinite_loop():
    """Verify that precompute runs until an infinite loop is entered when max_steps is None."""
    asm_src = """
    LDI R16, 0
loop:
    INC R16
    CPI R16, 120
    BRNE loop
halt_loop:
    RJMP halt_loop
    """
    asm = assemble(asm_src)
    cpu = CPU()
    cpu.load_program(asm)

    mgr = CheckpointManager(cpu, interval=50)
    # With max_steps=None, precompute should run until halt_loop is reached
    computed = mgr.precompute(max_steps=None)

    assert mgr.infinite_loop_detected is True
    assert "HALT spin loop" in mgr.loop_reason
    assert computed > 200
    assert mgr.checkpoint_steps[-1] == computed

    # Verify CacheProgressModalScreen handles None max_steps gracefully
    modal = CacheProgressModalScreen(max_steps=None)
    assert modal.target_steps is None
    modal.update_progress(150, None)


def test_app_layout_and_tab_structure():
    """Verify SREG placement in left panel, and removal of matrix, grid, and profiler tabs."""
    asm_src = """
    LDI R16, 0
loop:
    INC R16
    CPI R16, 20
    BRNE loop
    """
    asm = assemble(asm_src)
    cpu = CPU()
    cpu.load_program(asm)
    app = Tiny8App(cpu=cpu, max_steps=100)

    async def _test():
        async with app.run_test():
            # Verify SregWidget is inside left-panel above btop-regs-view
            left_children = [
                type(c).__name__ for c in app.query_one("#left-panel").children
            ]
            assert "SregWidget" in left_children
            assert "BtopRegistersWidget" in left_children
            sreg_idx = left_children.index("SregWidget")
            btop_idx = left_children.index("BtopRegistersWidget")
            assert sreg_idx < btop_idx

            # Verify top-bar is removed
            assert len(app.query("#top-bar")) == 0

            # Verify removed tabs: no tab-matrix, tab-grid, or tab-profiler
            assert len(app.query("#tab-matrix")) == 0
            assert len(app.query("#tab-grid")) == 0
            assert len(app.query("#tab-profiler")) == 0

    asyncio.run(_test())


def test_memory_widget_terminal_fitting():
    """Verify MemoryWidget adapts rows to terminal lines."""
    mem_w = MemoryWidget()
    mem_w.start_addr = 0x0200
    rendered_mem = mem_w.render().plain
    assert "MEMORY DUMP" in rendered_mem
    assert "HEATMAP" not in rendered_mem
    assert "0x0200:" in rendered_mem


def test_memory_widget_full_range_at_0xffff():
    """Verify MemoryWidget renders up to 0xFFFF correctly without out-of-bounds rows."""
    mem_w = MemoryWidget()
    mem_w.start_addr = 0xFFE0
    mem_w.mem = {0xFFFF: 0xAB, 0xFFE0: 0x12}
    rendered = mem_w.render().plain
    assert "0xFFE0:" in rendered
    assert "12" in rendered
    assert "AB" in rendered
    assert "0x10000:" not in rendered


def test_tui_memory_navigation_full_range():
    """Verify TUI can scroll and jump across full 0x0000..0xFFFF address space."""
    async def _test():
        cpu = CPU()
        asm = assemble("NOP\nNOP\n")
        cpu.load_program(asm)
        cpu.step(record_trace=True)

        app = Tiny8App(cpu=cpu, file_path="main.asm", precompute_cache=False)
        async with app.run_test(size=(120, 36)) as pilot:
            inp = app.query_one("#cmd-input", Input)

            # Jump to end of RAM via command
            app.on_input_submitted(Input.Submitted(inp, "mem 0xFFFF"))
            assert app.mem_start == 0xFFE0

            # Jump via alias
            app.on_input_submitted(Input.Submitted(inp, "mem vram"))
            assert app.mem_start == 0x0200

            app.on_input_submitted(Input.Submitted(inp, "mem stack"))
            assert app.mem_start == (cpu.sp & ~0x1F)

            app.on_input_submitted(Input.Submitted(inp, "mem sram"))
            assert app.mem_start == 0x0060

            app.on_input_submitted(Input.Submitted(inp, "mem 0x0600"))
            assert app.mem_start == 0x0600

            # Set memory byte at high address
            app.on_input_submitted(Input.Submitted(inp, "set 0xFFFF 0xEF"))
            assert cpu.mem.ram[0xFFFF] == 0xEF

            # Test scrolling bounds
            app.mem_start = 0xFFC0
            app.action_scroll_down()
            assert app.mem_start == 0xFFE0
            app.action_scroll_down()
            assert app.mem_start == 0xFFE0  # Capped at 0xFFE0 (0xFFFF row)

            app.mem_start = 0x0010
            app.action_scroll_up()
            assert app.mem_start == 0x0000
            app.action_scroll_up()
            assert app.mem_start == 0x0000  # Capped at 0x0000

    asyncio.run(_test())
