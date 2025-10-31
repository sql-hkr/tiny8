"""Terminal-based visualizer for tiny8 CPU step traces.

Simplified and enhanced CLI with Vim-style controls, marks, search, and more.
"""

from __future__ import annotations

import argparse
import curses
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# Key handler registry
_key_handlers: dict[int | str, Callable] = {}


def key_handler(*keys: int | str):
    """Decorator to register a function as a handler for specific key(s).

    Args:
        *keys: One or more keys (as int or string) to bind to this handler.

    Example:
        @key_handler(ord('q'), 27)  # q and ESC
        def quit_handler(state, ...):
            return True  # Signal to exit
    """

    def decorator(func: Callable) -> Callable:
        for key in keys:
            _key_handlers[key] = func
        return func

    return decorator


@dataclass
class ViewState:
    """State container for the CLI visualizer.

    Attributes:
        step_idx: Current step index in trace.
        scroll_offset: Vertical scroll offset for memory view.
        playing: Whether auto-play is active.
        last_advance_time: Timestamp of last auto-advance.
        delay: Delay between auto-advance steps in seconds.
        show_all_regs: Show all 32 registers vs only changed.
        show_all_mem: Show non-zero memory vs all memory.
        command_mode: Whether in command input mode.
        command_buffer: Current command being typed.
        marks: Dictionary of named position marks.
        status_msg: Current status message to display.
        status_time: Timestamp when status message was set.
    """

    step_idx: int = 0
    scroll_offset: int = 0
    playing: bool = False
    last_advance_time: float = 0.0
    delay: float = 0.15
    show_all_regs: bool = True
    show_all_mem: bool = False
    command_mode: bool = False
    command_buffer: str = ""
    marks: dict[str, int] = field(default_factory=dict)
    status_msg: str = ""
    status_time: float = 0.0


@dataclass
class KeyContext:
    """Context passed to key handlers."""

    state: ViewState
    scr: Any
    traces: list
    cpu: Any
    mem_addr_start: int
    mem_addr_end: int
    source_lines: list[str] | None
    n: int  # total steps

    def redraw(self) -> int:
        """Redraw screen and return height."""
        return draw_step(
            self.scr,
            self.state,
            self.traces,
            self.cpu,
            self.mem_addr_start,
            self.mem_addr_end,
            self.source_lines,
        )

    def set_status(self, msg: str) -> None:
        """Set status message."""
        self.state.status_msg = msg
        self.state.status_time = time.time()


def format_byte(value: int) -> str:
    """Format byte value as two-digit hex string.

    Args:
        value: Byte value to format (0-255).

    Returns:
        Two-character uppercase hex string.
    """
    return f"{value:02X}"


def safe_add(
    scr, y: int, x: int, text: str, attr: int = 0, max_x: int | None = None
) -> None:
    """Safely add text to screen, handling boundary conditions.

    Args:
        scr: Curses screen object.
        y: Y coordinate (row).
        x: X coordinate (column).
        text: Text to display.
        attr: Display attributes (e.g., curses.A_BOLD).
        max_x: Maximum x coordinate, or None to use screen width.
    """
    if max_x is None:
        _, max_x = scr.getmaxyx()
    if y < 0 or y >= scr.getmaxyx()[0]:
        return
    # Truncate text to fit within screen bounds
    text = text[: max_x - x - 1] if x < max_x else ""
    try:
        scr.addstr(y, x, text, attr)
    except curses.error:
        pass


def draw_step(
    scr,
    state: ViewState,
    traces: list,
    cpu,
    mem_start: int,
    mem_end: int,
    source_lines: list[str] | None = None,
) -> int:
    """Draw the current execution step to screen.

    Displays header, SREG flags, assembly source code, registers, and memory for the current step.
    Highlights changes from previous step and the currently executing source line.

    Args:
        scr: Curses screen object.
        state: Current view state.
        traces: List of execution trace entries.
        cpu: CPU instance (unused, for consistency).
        mem_start: Start address for memory display.
        mem_end: End address for memory display.
        source_lines: Optional list of original assembly source lines for display.

    Returns:
        Total number of lines drawn (for scroll calculations).
    """
    max_y, max_x = scr.getmaxyx()
    scr.erase()

    idx, mem_scroll, n = state.step_idx, state.scroll_offset, len(traces)
    entry = traces[idx]
    prev = traces[idx - 1] if idx > 0 else None

    pc, sp = entry.get("pc", 0), entry.get("sp", 0)
    instr, sreg = entry.get("instr", ""), entry.get("sreg", 0)
    prev_sreg = prev.get("sreg", 0) if prev else 0
    regs, prev_regs = entry.get("regs", []), prev.get("regs", []) if prev else []
    mem, prev_mem = entry.get("mem", {}), prev.get("mem", {}) if prev else {}

    line = 0

    # Header (fixed) - White bold for high visibility
    safe_add(
        scr,
        line,
        0,
        f"Step {idx}/{n - 1}  PC:0x{pc:04X}  SP:0x{sp:04X}  {instr}",
        curses.color_pair(3) | curses.A_BOLD,
        max_x,
    )
    line += 2

    # Assembly Source Code (if available)
    if source_lines:
        source_line_num = entry.get("source_line", -1)
        safe_add(
            scr,
            line,
            0,
            "Assembly Source:",
            curses.color_pair(3) | curses.A_BOLD,
            max_x,
        )
        line += 1

        context_lines = 5
        start_line = max(0, source_line_num - context_lines)
        end_line = min(len(source_lines), source_line_num + context_lines + 1)

        lines_before = source_line_num - start_line
        lines_after = end_line - source_line_num - 1

        padding_before = max(0, context_lines - lines_before)
        padding_after = max(0, context_lines - lines_after)

        for _ in range(padding_before):
            safe_add(scr, line, 2, "", 0, max_x)
            line += 1

        for src_idx in range(start_line, end_line):
            if src_idx < len(source_lines):
                prefix = ">>>" if src_idx == source_line_num else "   "
                src_text = source_lines[src_idx].rstrip()
                display_text = f"{prefix} {src_idx + 1:3d}: {src_text}"
                if src_idx == source_line_num:
                    attr = curses.color_pair(1) | curses.A_BOLD
                else:
                    attr = 0
                safe_add(scr, line, 2, display_text, attr, max_x)
                line += 1

        for _ in range(padding_after):
            safe_add(scr, line, 2, "", 0, max_x)
            line += 1

        line += 1

    flags = ["I", "T", "H", "S", "V", "N", "Z", "C"]
    safe_add(scr, line, 0, "SREG: ", curses.color_pair(3) | curses.A_BOLD, max_x)
    x = 6
    for i, name in enumerate(flags):
        bit_pos = 7 - i
        bit, pbit = (sreg >> bit_pos) & 1, (prev_sreg >> bit_pos) & 1
        if bit != pbit and prev:
            # Changed flag: green background
            attr = curses.color_pair(1) | curses.A_BOLD
        elif bit == 1:
            # Set flag: green text to indicate active
            attr = curses.color_pair(2) | curses.A_BOLD
        else:
            # Cleared flag: normal text
            attr = 0
        safe_add(scr, line, x, f"{name}:{bit} ", attr, max_x)
        x += 4
    safe_add(scr, line, x + 2, f"0x{sreg:02X}", curses.color_pair(2), max_x)
    line += 2

    # Registers (fixed)
    safe_add(
        scr,
        line,
        0,
        f"Registers ({'all' if state.show_all_regs else 'changed'}):",
        curses.color_pair(3) | curses.A_BOLD,
        max_x,
    )
    line += 1

    if state.show_all_regs:
        for row in range(2):
            base = row * 16
            safe_add(
                scr,
                line,
                2,
                f"R{base:02d}-{base + 15:02d}: ",
                curses.color_pair(3),
                max_x,
            )
            for col in range(16):
                r = base + col
                if r >= 32:
                    break
                val = regs[r] if r < len(regs) else 0
                pval = prev_regs[r] if r < len(prev_regs) else 0
                if val != pval and prev:
                    # Changed register: green background
                    attr = curses.color_pair(1) | curses.A_BOLD
                elif val != 0:
                    # Non-zero register: green text
                    attr = curses.color_pair(2)
                else:
                    # Zero register: normal text
                    attr = 0
                safe_add(scr, line, 12 + col * 3, format_byte(val), attr, max_x)
            line += 1
    else:
        changed = [
            (
                r,
                prev_regs[r] if r < len(prev_regs) else 0,
                regs[r] if r < len(regs) else 0,
            )
            for r in range(32)
            if (regs[r] if r < len(regs) else 0)
            != (prev_regs[r] if r < len(prev_regs) else 0)
            and prev
        ]
        if changed:
            for r, old, new in changed:
                safe_add(
                    scr,
                    line,
                    2,
                    f"R{r:02d}: {format_byte(old)} → {format_byte(new)}",
                    curses.color_pair(1) | curses.A_BOLD,
                    max_x,
                )
                line += 1
        else:
            safe_add(scr, line, 2, "(no changes)", 0, max_x)
            line += 1
    line += 1

    # Memory header (fixed)
    safe_add(
        scr,
        line,
        0,
        f"Memory {hex(mem_start)}..{hex(mem_end)} ({'non-zero' if state.show_all_mem else 'all'}):",
        curses.color_pair(3) | curses.A_BOLD,
        max_x,
    )
    line += 1

    # Calculate memory viewport
    mem_start_line = line
    mem_available_lines = max_y - line - 1  # Reserve 1 line for status

    # Build memory lines
    mem_lines = []
    if state.show_all_mem:
        nz = [(a, v) for a, v in mem.items() if mem_start <= a <= mem_end]
        nz.sort()
        if nz:
            for addr, val in nz:
                pval = prev_mem.get(addr, 0)
                if val != pval and prev:
                    # Changed memory: green background
                    attr = curses.color_pair(1) | curses.A_BOLD
                else:
                    # Non-zero memory: green text
                    attr = curses.color_pair(2)
                ch = chr(val) if 32 <= val <= 126 else "."
                mem_lines.append((f"0x{addr:04X}: {format_byte(val)}  '{ch}'", attr))
        else:
            mem_lines.append(("(all zero)", 0))
    else:
        for row in range((mem_end - mem_start + 16) // 16):
            row_addr = mem_start + row * 16
            if row_addr > mem_end:
                break
            line_text = f"0x{row_addr:04X}: "
            ascii_parts = []
            highlights = []
            for col in range(16):
                addr = row_addr + col
                if addr > mem_end:
                    break
                val, pval = mem.get(addr, 0), prev_mem.get(addr, 0) if prev else 0
                if val != pval and prev:
                    highlights.append((12 + col * 3, format_byte(val)))
                ascii_parts.append(chr(val) if 32 <= val <= 126 else ".")
            mem_lines.append((line_text, 0, highlights, ascii_parts))

    # Render visible memory lines
    total_mem_lines = len(mem_lines)
    for i in range(mem_available_lines):
        mem_line_idx = mem_scroll + i
        if mem_line_idx >= total_mem_lines:
            break
        scr_line = mem_start_line + i
        if scr_line >= max_y - 1:
            break

        mem_line_data = mem_lines[mem_line_idx]
        if state.show_all_mem:
            text, attr = mem_line_data
            safe_add(scr, scr_line, 2, text, attr, max_x)
        else:
            line_text, attr, highlights, ascii_parts = mem_line_data
            safe_add(scr, scr_line, 2, line_text, curses.color_pair(3), max_x)
            # Draw hex bytes
            row_addr = mem_start + mem_line_idx * 16
            for col in range(16):
                addr = row_addr + col
                if addr > mem_end:
                    break
                val = mem.get(addr, 0)
                pval = prev_mem.get(addr, 0) if prev else 0
                if val != pval and prev:
                    # Changed memory: green background
                    attr = curses.color_pair(1) | curses.A_BOLD
                elif val != 0:
                    # Non-zero memory: green text
                    attr = curses.color_pair(2)
                else:
                    # Zero memory: normal text
                    attr = 0
                safe_add(scr, scr_line, 12 + col * 3, format_byte(val), attr, max_x)
            # Draw ASCII
            safe_add(scr, scr_line, 12 + 48, "  " + "".join(ascii_parts), 0, max_x)

    # Status/Command line
    status_line = max_y - 1
    scr.move(status_line, 0)
    scr.clrtoeol()

    if state.command_mode:
        # Command mode: white bold for visibility
        safe_add(
            scr,
            status_line,
            0,
            f":{state.command_buffer}",
            curses.color_pair(3) | curses.A_BOLD,
            max_x,
        )
    else:
        # Normal mode: show temporary status message or footer
        if state.status_msg and time.time() - state.status_time < 0.5:
            # Status messages in green
            safe_add(
                scr,
                status_line,
                0,
                state.status_msg,
                curses.color_pair(2) | curses.A_BOLD,
                max_x,
            )
        else:
            play = "[PLAY]" if state.playing else "[PAUSE]"
            info = f" Speed:{state.delay:.2f}s"
            if mem_scroll > 0:
                info += f" MemScroll:{mem_scroll}/{max(0, total_mem_lines - mem_available_lines)}"
            info += " | / for help | q to quit"
            # Play/pause in green when active, white otherwise
            play_attr = (
                curses.color_pair(2) | curses.A_BOLD
                if state.playing
                else curses.color_pair(3) | curses.A_BOLD
            )
            safe_add(scr, status_line, 0, play, play_attr, max_x)
            safe_add(scr, status_line, len(play), info, 0, max_x)

    scr.refresh()
    return total_mem_lines


def show_help(scr) -> None:
    """Display help screen with all available commands and controls.

    Shows comprehensive documentation of keyboard shortcuts, commands,
    and features. Waits for user keypress before returning.

    Args:
        scr: Curses screen object.
    """
    scr.clear()
    help_text = [
        "Tiny8 CLI - Help",
        "",
        "Navigation:  l/h: next/prev  w/b: ±10  0/$: first/last  j/k: scroll",
        "Playback:    Space: play/pause  [/]: slower/faster",
        "Display:     r: toggle regs  M: toggle mem  =: step info",
        "Marks:       ma: set mark  'a: goto mark",
        "",
        "Commands (press : to enter):",
        "  123       - Jump to step 123",
        "  +50, -20  - Relative jump forward/backward",
        "  /add      - Search forward for instruction containing 'add'",
        "  ?ldi      - Search backward for instruction",
        "  @100      - Jump to PC address (decimal or 0x hex)",
        "  r10       - Find next change to register R10",
        "  r10=42    - Find where R10 equals 42 (decimal or 0x hex)",
        "  m100      - Find next change to memory address 100",
        "  m100=0xFF - Find where memory[100] equals 0xFF",
        "  fZ        - Find next change to flag Z (I,T,H,S,V,N,Z,C)",
        "  fC=1      - Find where flag C equals 1",
        "  h, help   - Show command help",
        "",
        "Other:       /: this help  q: quit",
        "",
        "Press any key...",
    ]
    for i, line in enumerate(help_text):
        try:
            scr.addstr(i, 2, line)
        except Exception:
            pass
    scr.refresh()
    scr.nodelay(False)
    scr.getch()
    scr.nodelay(True)


def show_info(scr, entry: dict, idx: int) -> None:
    """Display detailed information about a specific step.

    Shows PC, SP, instruction, SREG, and all non-zero registers and memory
    for the given step. Waits for user keypress before returning.

    Args:
        scr: Curses screen object.
        entry: Trace entry dictionary containing step data.
        idx: Step index number.
    """
    scr.clear()
    lines = [
        f"Step {idx} Details",
        "",
        f"PC: 0x{entry.get('pc', 0):04X}  SP: 0x{entry.get('sp', 0):04X}",
        f"Instruction: {entry.get('instr', 'N/A')}",
        f"SREG: 0x{entry.get('sreg', 0):02X}",
        "",
        "Non-zero registers:",
    ]
    for i, v in enumerate(entry.get("regs", [])):
        if v:
            lines.append(f"  R{i:02d} = 0x{v:02X} ({v})")
    lines.append("")
    lines.append("Non-zero memory:")
    for a in sorted(entry.get("mem", {}).keys()):
        v = entry["mem"][a]
        ch = chr(v) if 32 <= v <= 126 else "."
        lines.append(f"  0x{a:04X} = 0x{v:02X} ({v}) '{ch}'")
    lines.append("")
    lines.append("Press any key...")

    for i, line in enumerate(lines):
        try:
            scr.addstr(i, 2, line)
        except Exception:
            pass
    scr.refresh()
    scr.nodelay(False)
    scr.getch()
    scr.nodelay(True)


def run_command(state: ViewState, traces: list[dict]) -> str:
    """Execute a command and return status message.

    Handles all command types including navigation, search, and tracking.
    Updates state.step_idx and state.scroll_offset as needed.

    Args:
        state: Current ViewState object to modify.
        traces: List of trace entry dictionaries.

    Returns:
        Status message string describing the result.

    Command Types:
        - Numeric (123): Jump to step 123
        - Relative (±50): Jump forward/backward 50 steps
        - Forward search (/add): Find instruction containing "add"
        - Backward search (?ldi): Search backward for "ldi"
        - PC jump (@100): Jump to PC address 0x64
        - Register track (r10): Find next change to R10
        - Register search (r10=42): Find where R10 equals 42
        - Memory track (m100): Find next change to memory[100]
        - Memory search (m100=0xFF): Find where memory[100] equals 0xFF
        - Flag track (fZ): Find next change to flag Z
        - Flag search (fC=1): Find where flag C equals 1
        - Help (h, help): Show command documentation
    """
    cmd = state.command_buffer.strip()
    n = len(traces)

    # Jump to absolute step number
    if cmd.isdigit():
        t = int(cmd)
        if 0 <= t < n:
            state.step_idx, state.scroll_offset = t, 0
            return f"→ step {t}"
        return f"Invalid: {t}"

    # Relative jump (+50, -20)
    if cmd and cmd[0] in "+-" and cmd[1:].isdigit():
        new_idx = state.step_idx + int(cmd)
        if 0 <= new_idx < n:
            state.step_idx, state.scroll_offset = new_idx, 0
            return f"→ step {new_idx}"
        return f"Invalid: {new_idx}"

    # Search forward for instruction (/add, /ldi r16)
    if cmd.startswith("/"):
        search = cmd[1:].lower().strip()
        if not search:
            return "Empty search"
        for i in range(state.step_idx + 1, n):
            instr = traces[i].get("instr", "").lower()
            if search in instr:
                state.step_idx, state.scroll_offset = i, 0
                return f"Found at step {i}: {traces[i].get('instr', '')}"
        return f"Not found: {search}"

    # Search backward (?add, ?ldi r16)
    if cmd.startswith("?"):
        search = cmd[1:].lower().strip()
        if not search:
            return "Empty search"
        for i in range(state.step_idx - 1, -1, -1):
            instr = traces[i].get("instr", "").lower()
            if search in instr:
                state.step_idx, state.scroll_offset = i, 0
                return f"Found at step {i}: {traces[i].get('instr', '')}"
        return f"Not found: {search}"

    # Jump to PC address (@100, @0x64)
    if cmd.startswith("@"):
        try:
            addr_str = cmd[1:].strip()
            target_pc = (
                int(addr_str, 16) if addr_str.startswith("0x") else int(addr_str)
            )
            for i in range(n):
                if traces[i].get("pc", -1) == target_pc:
                    state.step_idx, state.scroll_offset = i, 0
                    return f"→ step {i} (PC=0x{target_pc:04X})"
            return f"PC 0x{target_pc:04X} not found"
        except ValueError:
            return f"Invalid address: {cmd}"

    # Find register change (r10, r16=42)
    if cmd.startswith("r") and len(cmd) >= 2:
        try:
            parts = cmd[1:].split("=")
            reg_num = int(parts[0])
            if not (0 <= reg_num <= 31):
                return f"Invalid register: R{reg_num}"

            if len(parts) == 1:
                # Find next change to this register
                current_val = (
                    traces[state.step_idx].get("regs", [])[reg_num]
                    if reg_num < len(traces[state.step_idx].get("regs", []))
                    else 0
                )
                for i in range(state.step_idx + 1, n):
                    regs = traces[i].get("regs", [])
                    if reg_num < len(regs) and regs[reg_num] != current_val:
                        state.step_idx, state.scroll_offset = i, 0
                        return f"R{reg_num} changed at step {i}: 0x{regs[reg_num]:02X}"
                return f"R{reg_num} doesn't change"
            else:
                # Find where register equals value
                target_val = (
                    int(parts[1], 16) if parts[1].startswith("0x") else int(parts[1])
                )
                for i in range(state.step_idx + 1, n):
                    regs = traces[i].get("regs", [])
                    if reg_num < len(regs) and regs[reg_num] == target_val:
                        state.step_idx, state.scroll_offset = i, 0
                        return f"R{reg_num}=0x{target_val:02X} at step {i}"
                return f"R{reg_num}=0x{target_val:02X} not found"
        except (ValueError, IndexError):
            return f"Invalid: {cmd}"

    # Memory search (m100, m0x64=42)
    if cmd.startswith("m") and len(cmd) >= 2:
        try:
            parts = cmd[1:].split("=")
            addr = int(parts[0], 16) if parts[0].startswith("0x") else int(parts[0])

            if len(parts) == 1:
                # Find next change to this memory address
                current_val = traces[state.step_idx].get("mem", {}).get(addr, 0)
                for i in range(state.step_idx + 1, n):
                    mem = traces[i].get("mem", {})
                    new_val = mem.get(addr, 0)
                    if new_val != current_val:
                        state.step_idx, state.scroll_offset = i, 0
                        return f"Mem[0x{addr:04X}] changed at step {i}: 0x{new_val:02X}"
                return f"Mem[0x{addr:04X}] doesn't change"
            else:
                # Find where memory equals value
                target_val = (
                    int(parts[1], 16) if parts[1].startswith("0x") else int(parts[1])
                )
                for i in range(state.step_idx + 1, n):
                    mem = traces[i].get("mem", {})
                    if mem.get(addr, 0) == target_val:
                        state.step_idx, state.scroll_offset = i, 0
                        return f"Mem[0x{addr:04X}]=0x{target_val:02X} at step {i}"
                return f"Mem[0x{addr:04X}]=0x{target_val:02X} not found"
        except (ValueError, IndexError):
            return f"Invalid: {cmd}"

    # Flag search (fZ, fC=1)
    if cmd.startswith("f") and len(cmd) >= 2:
        flag_map = {"I": 7, "T": 6, "H": 5, "S": 4, "V": 3, "N": 2, "Z": 1, "C": 0}
        try:
            parts = cmd[1:].split("=")
            flag_name = parts[0].upper()
            if flag_name not in flag_map:
                return f"Invalid flag: {flag_name}"

            bit_pos = flag_map[flag_name]

            if len(parts) == 1:
                # Find next change to this flag
                current_sreg = traces[state.step_idx].get("sreg", 0)
                current_bit = (current_sreg >> bit_pos) & 1
                for i in range(state.step_idx + 1, n):
                    sreg = traces[i].get("sreg", 0)
                    bit = (sreg >> bit_pos) & 1
                    if bit != current_bit:
                        state.step_idx, state.scroll_offset = i, 0
                        return f"Flag {flag_name} changed at step {i}: {bit}"
                return f"Flag {flag_name} doesn't change"
            else:
                # Find where flag equals value
                target_val = int(parts[1])
                if target_val not in [0, 1]:
                    return "Flag value must be 0 or 1"
                for i in range(state.step_idx + 1, n):
                    sreg = traces[i].get("sreg", 0)
                    bit = (sreg >> bit_pos) & 1
                    if bit == target_val:
                        state.step_idx, state.scroll_offset = i, 0
                        return f"Flag {flag_name}={target_val} at step {i}"
                return f"Flag {flag_name}={target_val} not found"
        except (ValueError, KeyError):
            return f"Invalid: {cmd}"

    # Help command
    if cmd in ["h", "help"]:
        return "Commands: NUM, ±NUM, /instr, ?instr, @addr, rN[=val], mADDR[=val], fFLAG[=val]"

    return f"Unknown: {cmd}"


# Key handler functions using decorator pattern
@key_handler(ord("q"), 27)  # q and ESC
def handle_quit(ctx: KeyContext) -> bool:
    """Quit the visualizer."""
    return True  # Signal to exit


@key_handler(ord(" "))
def handle_play_pause(ctx: KeyContext) -> int:
    """Toggle play/pause."""
    ctx.state.playing = not ctx.state.playing
    if ctx.state.playing:
        ctx.state.last_advance_time = time.time()
    return ctx.redraw()


@key_handler(ord("l"), curses.KEY_RIGHT)
def handle_step_forward(ctx: KeyContext) -> int:
    """Step forward."""
    ctx.state.step_idx = min(ctx.n - 1, ctx.state.step_idx + 1)
    ctx.state.scroll_offset = 0
    return ctx.redraw()


@key_handler(ord("h"), curses.KEY_LEFT)
def handle_step_backward(ctx: KeyContext) -> int:
    """Step backward."""
    ctx.state.step_idx = max(0, ctx.state.step_idx - 1)
    ctx.state.scroll_offset = 0
    return ctx.redraw()


@key_handler(ord("w"))
def handle_jump_forward(ctx: KeyContext) -> int:
    """Jump forward 10 steps."""
    ctx.state.step_idx = min(ctx.n - 1, ctx.state.step_idx + 10)
    ctx.state.scroll_offset = 0
    return ctx.redraw()


@key_handler(ord("b"))
def handle_jump_backward(ctx: KeyContext) -> int:
    """Jump backward 10 steps."""
    ctx.state.step_idx = max(0, ctx.state.step_idx - 10)
    ctx.state.scroll_offset = 0
    return ctx.redraw()


@key_handler(ord("0"))
def handle_goto_first(ctx: KeyContext) -> int:
    """Go to first step."""
    ctx.state.step_idx = 0
    ctx.state.scroll_offset = 0
    return ctx.redraw()


@key_handler(ord("$"))
def handle_goto_last(ctx: KeyContext) -> int:
    """Go to last step."""
    ctx.state.step_idx = ctx.n - 1
    ctx.state.scroll_offset = 0
    return ctx.redraw()


@key_handler(ord("r"))
def handle_toggle_regs(ctx: KeyContext) -> int:
    """Toggle showing all registers."""
    ctx.state.show_all_regs = not ctx.state.show_all_regs
    return ctx.redraw()


@key_handler(ord("M"))
def handle_toggle_mem(ctx: KeyContext) -> int:
    """Toggle showing all memory."""
    ctx.state.show_all_mem = not ctx.state.show_all_mem
    return ctx.redraw()


@key_handler(ord("["))
def handle_slower(ctx: KeyContext) -> int:
    """Decrease playback speed."""
    ctx.state.delay = min(2.0, ctx.state.delay + 0.05)
    ctx.set_status(f"Speed: {ctx.state.delay:.2f}s")
    return ctx.redraw()


@key_handler(ord("]"))
def handle_faster(ctx: KeyContext) -> int:
    """Increase playback speed."""
    ctx.state.delay = max(0.05, ctx.state.delay - 0.05)
    ctx.set_status(f"Speed: {ctx.state.delay:.2f}s")
    return ctx.redraw()


@key_handler(ord("="))
def handle_show_info(ctx: KeyContext) -> int:
    """Show detailed step information."""
    show_info(ctx.scr, ctx.traces[ctx.state.step_idx], ctx.state.step_idx)
    return ctx.redraw()


@key_handler(ord("/"))
def handle_show_help(ctx: KeyContext) -> int:
    """Show help screen."""
    show_help(ctx.scr)
    return ctx.redraw()


@key_handler(ord("j"))
def handle_scroll_down(ctx: KeyContext, h: int) -> int:
    """Scroll memory view down."""
    ctx.state.scroll_offset = min(max(0, h - 1), ctx.state.scroll_offset + 1)
    return ctx.redraw()


@key_handler(ord("k"))
def handle_scroll_up(ctx: KeyContext, h: int) -> int:
    """Scroll memory view up."""
    ctx.state.scroll_offset = max(0, ctx.state.scroll_offset - 1)
    return ctx.redraw()


def run_cli(
    cpu,
    mem_addr_start: int = 0,
    mem_addr_end: int = 31,
    delay: float = 0.15,
    source_lines: list[str] | None = None,
) -> None:
    """Run interactive CLI visualizer in terminal.

    Displays CPU state, registers, memory, and assembly source in a curses-based interface
    with keyboard navigation and playback controls.

    Args:
        cpu: CPU instance with step_trace attribute containing execution history.
        mem_addr_start: Starting memory address to display (default: 0).
        mem_addr_end: Ending memory address to display (default: 31).
        delay: Initial playback delay in seconds (default: 0.15).
        source_lines: Optional list of original assembly source lines for display.

    Raises:
        RuntimeError: If cpu.step_trace is empty or missing.
    """
    traces = getattr(cpu, "step_trace", None)
    if not traces:
        raise RuntimeError("cpu.step_trace empty")

    n = len(traces)

    def main(scr):
        curses.curs_set(0)
        scr.nodelay(True)

        # Initialize color pairs for usability-focused design
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(
            1, curses.COLOR_BLACK, curses.COLOR_GREEN
        )  # Black on green (highlights)
        curses.init_pair(2, curses.COLOR_GREEN, -1)  # Green text (active/positive)
        curses.init_pair(3, curses.COLOR_WHITE, -1)  # White text (important info)

        state = ViewState(delay=delay)
        ctx = KeyContext(
            state=state,
            scr=scr,
            traces=traces,
            cpu=cpu,
            mem_addr_start=mem_addr_start,
            mem_addr_end=mem_addr_end,
            source_lines=source_lines,
            n=n,
        )
        h = ctx.redraw()

        while True:
            ch = scr.getch()

            if ch == curses.KEY_RESIZE:
                h = ctx.redraw()
                continue

            if ch != -1:
                # Handle command mode
                if state.command_mode:
                    if ch == 27:
                        state.command_mode, state.command_buffer = False, ""
                        h = ctx.redraw()
                    elif ch in (curses.KEY_ENTER, 10, 13):
                        state.status_msg = run_command(state, traces)
                        state.status_time = time.time()
                        state.command_mode, state.command_buffer = False, ""
                        h = ctx.redraw()
                    elif ch in (curses.KEY_BACKSPACE, 127, 8):
                        state.command_buffer = state.command_buffer[:-1]
                        my, mx = scr.getmaxyx()
                        safe_add(
                            scr, my - 1, 0, f":{state.command_buffer}" + " " * 20, 0, mx
                        )
                        scr.refresh()
                    elif 32 <= ch <= 126:
                        state.command_buffer += chr(ch)
                        my, mx = scr.getmaxyx()
                        safe_add(scr, my - 1, 0, f":{state.command_buffer}", 0, mx)
                        scr.refresh()
                    continue

                # Handle : for command mode
                if ch == ord(":"):
                    state.command_mode, state.command_buffer, state.playing = (
                        True,
                        "",
                        False,
                    )
                    h = ctx.redraw()
                    continue

                # Handle marks (m and ')
                if ch == ord("m"):
                    scr.nodelay(False)
                    mc = scr.getch()
                    scr.nodelay(True)
                    if 97 <= mc <= 122:
                        mn = chr(mc)
                        state.marks[mn] = state.step_idx
                        ctx.set_status(f"Mark '{mn}' set")
                        h = ctx.redraw()
                    continue

                if ch == ord("'"):
                    scr.nodelay(False)
                    mc = scr.getch()
                    scr.nodelay(True)
                    if 97 <= mc <= 122:
                        mn = chr(mc)
                        if mn in state.marks:
                            state.step_idx, state.scroll_offset = state.marks[mn], 0
                            ctx.set_status(f"→ mark '{mn}'")
                        else:
                            ctx.set_status(f"Mark '{mn}' not set")
                        h = ctx.redraw()
                    continue

                # Dispatch to registered key handlers
                handler = _key_handlers.get(ch)
                if handler:
                    # Handle scroll handlers that need h parameter
                    if ch in (ord("j"), ord("k")):
                        result = handler(ctx, h)
                    else:
                        result = handler(ctx)

                    if result is True:  # Quit signal
                        break
                    if isinstance(result, int):  # New height
                        h = result

            # Handle auto-play
            if state.playing:
                t = time.time()
                if t - state.last_advance_time >= state.delay:
                    if state.step_idx < n - 1:
                        state.step_idx += 1
                        h = ctx.redraw()
                        state.last_advance_time = t
                    else:
                        state.playing = False
                time.sleep(0.01)
            else:
                # Check if status message expired and needs redraw
                if state.status_msg:
                    elapsed = time.time() - state.status_time
                    if elapsed >= 0.5:
                        state.status_msg = ""
                        h = ctx.redraw()
                time.sleep(0.05)

    curses.wrapper(main)


def main() -> None:
    """Entry point for CLI command-line interface.

    Parses command-line arguments, assembles the input file, runs the CPU,
    and launches either CLI or animation mode visualization.

    The function supports two modes:
    - CLI mode: Interactive terminal-based step-through debugger
    - Animation mode: Generate video/GIF visualization of execution

    Command-line arguments are organized into groups for better clarity:
    - Execution options: Control CPU behavior (max-steps)
    - Memory display: Configure memory address range (supports hex notation)
    - CLI mode: Interactive playback settings
    - Animation mode: Video generation parameters
    """
    from tiny8 import CPU, __version__, assemble_file

    parser = argparse.ArgumentParser(
        prog="tiny8",
        description="Tiny8 8-bit CPU simulator with interactive CLI and visualization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s program.asm                          # Run in interactive CLI mode
  %(prog)s program.asm -m ani -o output.mp4     # Generate animation video
  %(prog)s program.asm --mem-start 0x100 --mem-end 0x11F  # Custom memory range
  %(prog)s program.asm -d 0.5                   # Slower playback (0.5s per step)

Interactive CLI Controls:
  l/h or arrows  - Navigate forward/backward
  w/b            - Jump ±10 steps
  0/$            - Jump to first/last step
  j/k            - Scroll memory view
  Space          - Play/pause execution
  [/]            - Adjust playback speed
  r              - Toggle register display
  M              - Toggle memory display mode
  :123           - Jump to step 123
  /add           - Search forward for instruction
  q              - Quit
        """,
    )

    # Version
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    # Required arguments
    parser.add_argument(
        "asm_file",
        metavar="FILE",
        help="path to Tiny8 assembly file to execute",
    )

    # Mode selection
    parser.add_argument(
        "--mode",
        "-m",
        choices=["cli", "ani"],
        default="cli",
        help="visualization mode: 'cli' for interactive terminal (default), 'ani' for animation video",
    )

    # Execution options
    exec_group = parser.add_argument_group("execution options")
    exec_group.add_argument(
        "--max-steps",
        type=int,
        default=15000,
        metavar="N",
        help="maximum number of CPU steps to execute (default: 15000)",
    )

    # Memory display options
    mem_group = parser.add_argument_group("memory display options")
    mem_group.add_argument(
        "--mem-start",
        "-ms",
        type=lambda x: int(x, 0),  # Support 0x hex notation
        default=0x00,
        metavar="ADDR",
        help="starting memory address to display (decimal or 0xHEX, default: 0x00)",
    )
    mem_group.add_argument(
        "--mem-end",
        "-me",
        type=lambda x: int(x, 0),  # Support 0x hex notation
        default=0xFF,
        metavar="ADDR",
        help="ending memory address to display (decimal or 0xHEX, default: 0xFF)",
    )

    # CLI mode options
    cli_group = parser.add_argument_group("CLI mode options")
    cli_group.add_argument(
        "--delay",
        "-d",
        type=float,
        default=0.15,
        metavar="SEC",
        help="initial playback delay between steps in seconds (default: 0.15)",
    )

    # Animation mode options
    ani_group = parser.add_argument_group("animation mode options")
    ani_group.add_argument(
        "--interval",
        "-i",
        type=int,
        default=1,
        metavar="MS",
        help="animation update interval in milliseconds (default: 1)",
    )
    ani_group.add_argument(
        "--fps",
        "-f",
        type=int,
        default=60,
        metavar="FPS",
        help="frames per second for animation output (default: 60)",
    )
    ani_group.add_argument(
        "--plot-every",
        "-pe",
        type=int,
        default=100,
        metavar="N",
        help="update plot every N steps for performance (default: 100)",
    )
    ani_group.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        help="output filename for animation (e.g., output.mp4, output.gif)",
    )

    args = parser.parse_args()

    asm = assemble_file(args.asm_file)
    cpu = CPU()
    cpu.load_program(asm)
    cpu.run(max_steps=args.max_steps)

    if args.mode == "cli":
        run_cli(cpu, args.mem_start, args.mem_end, args.delay, asm.source_lines)
    elif args.mode == "ani":
        from tiny8 import Visualizer

        viz = Visualizer(cpu)
        viz.animate_execution(
            interval=args.interval,
            mem_addr_start=args.mem_start,
            mem_addr_end=args.mem_end,
            plot_every=args.plot_every,
            filename=args.output,
            fps=args.fps,
        )


if __name__ == "__main__":
    main()
