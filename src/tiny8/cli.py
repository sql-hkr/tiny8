"""Terminal based visualizer for tiny8 CPU step traces.

Provides a simple UI to inspect SREG, registers and a memory range
for a selected step from ``cpu.step_trace``. Interactive keyboard controls
allow play/pause and single-stepping.

Controls:
    .. code-block:: text

        Space - toggle play/pause
        l or > - next step
        k or < - previous step
        w - jump forward 10 steps
        b - jump back 10 steps
        0 - jump to first step
        $ - jump to last step
        q or ESC - quit

Usage:
    .. code-block:: python

        from tiny8.cli_visualizer import run_cli
        run_cli(cpu, mem_addr_start=0, mem_addr_end=127)
"""

from __future__ import annotations

import argparse
import curses
import math
import time


def _format_byte(b: int) -> str:
    return f"{b:02X}"


def run_cli(cpu, mem_addr_start: int = 0, mem_addr_end: int = 31, delay: float = 0.15):
    """Run the curses-based CLI visualizer for the given CPU.

    Args:
        cpu: CPU instance with a populated `step_trace` list.
        mem_addr_start: start address for memory display.
        mem_addr_end: end address for memory display.
        delay: seconds between automatic steps when playing.
    """

    traces = getattr(cpu, "step_trace", None)
    if not traces:
        raise RuntimeError(
            "cpu.step_trace is empty — run the CPU to populate step_trace first"
        )

    n_steps = len(traces)

    def draw_step(stdscr, idx: int):
        stdscr.erase()
        entry = traces[idx]

        pc = entry.get("pc", getattr(cpu, "pc", 0))
        sp = entry.get("sp", getattr(cpu, "sp", 0))
        instr = entry.get("instr", "")

        # Header
        header = f"Step {idx:{len(str(n_steps - 1))}}/{n_steps - 1}  PC:0x{pc:04X}  SP:0x{sp:04X}"
        if instr:
            header += f" RUN: {instr}"
        stdscr.addstr(0, 0, header)

        # SREG
        s = entry.get("sreg", 0)
        # flag_names = "I T H S V N Z C".split()
        bits = [(s >> b) & 1 for b in reversed(range(8))]
        sstr = " ".join(str(bit) for bit in bits)
        stdscr.addstr(2, 0, f"SREG: {sstr}  0x{s:02X}")

        # Registers (compact grid)
        regs = entry.get("regs", [])
        reg_count = 32
        reg_cols = min(8, int(math.ceil(math.sqrt(reg_count))))
        reg_rows = int(math.ceil(reg_count / reg_cols))

        stdscr.addstr(4, 0, "Registers:")
        for r in range(reg_rows):
            row_vals = []
            row_addr = r * reg_cols
            for c in range(reg_cols):
                i = row_addr + c
                if i >= reg_count:
                    break
                val = regs[i] if i < len(regs) else 0
                row_vals.append(_format_byte(val))
            # show register row reference (like memory rows) using hex index
            stdscr.addstr(5 + r, 2, f"0x{row_addr:02X}: " + " ".join(row_vals))

        # Memory (compact grid)
        memsnap = entry.get("mem", {})
        mem_count = max(0, mem_addr_end - mem_addr_start + 1)
        mem_cols = min(32, int(math.ceil(math.sqrt(mem_count)))) if mem_count > 0 else 1
        mem_rows = int(math.ceil(mem_count / mem_cols)) if mem_count > 0 else 1

        mem_top = 6 + reg_rows
        stdscr.addstr(mem_top, 0, f"Memory {hex(mem_addr_start)}..{hex(mem_addr_end)}:")
        for r in range(mem_rows):
            row_addr = mem_addr_start + r * mem_cols
            row_vals = []
            for c in range(mem_cols):
                a = row_addr + c
                if a > mem_addr_end:
                    break
                if a in memsnap:
                    val = memsnap[a]
                else:
                    try:
                        val = cpu.read_ram(a)
                    except Exception:
                        val = 0
                row_vals.append(_format_byte(val))
            stdscr.addstr(
                mem_top + 1 + r, 2, f"0x{row_addr:04X}: " + " ".join(row_vals)
            )

        # Footer
        footer_y = mem_top + 2 + mem_rows
        stdscr.addstr(
            footer_y,
            0,
            "Controls: space: play/pause  l: next  h: back  w: +10  b: -10\n"
            + " " * 10
            + "0: start  $: end  q: quit",
        )
        stdscr.refresh()

    def _curses_main(stdscr):
        curses.curs_set(0)
        stdscr.nodelay(True)
        idx = 0
        playing = False

        draw_step(stdscr, idx)

        while True:
            ch = stdscr.getch()
            if ch != -1:
                # handle keys
                if ch in (ord("q"), 27):
                    break
                elif ch == ord(" "):
                    playing = not playing
                elif ch in (ord("l"), curses.KEY_RIGHT):
                    idx = min(n_steps - 1, idx + 1)
                    draw_step(stdscr, idx)
                elif ch in (ord("h"), curses.KEY_LEFT):
                    idx = max(0, idx - 1)
                    draw_step(stdscr, idx)
                elif ch == ord("w"):
                    idx = min(n_steps - 1, idx + 10)
                    draw_step(stdscr, idx)
                elif ch == ord("b"):
                    idx = max(0, idx - 10)
                    draw_step(stdscr, idx)
                elif ch == ord("0"):
                    idx = 0
                    draw_step(stdscr, idx)
                elif ch == ord("$"):
                    idx = n_steps - 1
                    draw_step(stdscr, idx)

            if playing:
                time.sleep(delay)
                if idx < n_steps - 1:
                    idx += 1
                    draw_step(stdscr, idx)
                else:
                    playing = False
            else:
                time.sleep(0.05)

    curses.wrapper(_curses_main)


def main():
    from tiny8 import CPU, assemble_file

    parser = argparse.ArgumentParser(description="Tiny8 CLI Visualizer")
    parser.add_argument(
        "asm_file",
        type=str,
        help="Path to the assembly file to simulate",
    )
    parser.add_argument(
        "--mode",
        "-m",
        type=str,
        default="cli",
        help="Mode to run the simulator in (default: cli)",
    )
    parser.add_argument(
        "--max_cycles", type=int, default=15000, help="Maximum CPU cycles to run"
    )
    parser.add_argument(
        "--mem-start",
        "-ms",
        type=int,
        default=100,
        help="Start address for memory display (default: 100)",
    )
    parser.add_argument(
        "--mem-end",
        "-me",
        type=int,
        default=131,
        help="End address for memory display (default: 131)",
    )
    parser.add_argument(
        "--delay",
        "-d",
        type=float,
        default=0.15,
        help="Delay in seconds between automatic steps when playing (default: 0.15)",
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=int,
        default=1,
        help="Interval in milliseconds between frames for animation mode (default: 1)",
    )
    parser.add_argument(
        "--fps",
        "-f",
        type=int,
        default=60,
        help="Frames per second for animation mode (default: 60)",
    )
    parser.add_argument(
        "--plot-every",
        "-pe",
        type=int,
        default=100,
        help="Plot every N steps in animation mode (default: 100)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output filename for animation mode (e.g., bubblesort.gif)",
    )
    args = parser.parse_args()
    prog, labels = assemble_file(args.asm_file)
    cpu = CPU()
    cpu.load_program(prog, labels)
    cpu.run(max_cycles=args.max_cycles)
    if args.mode == "cli":
        run_cli(cpu, mem_addr_start=args.mem_start, mem_addr_end=args.mem_end)
    elif args.mode == "ani":
        from tiny8 import Visualizer

        viz = Visualizer(cpu)
        viz.animate_combined(
            interval=args.interval,
            mem_addr_start=args.mem_start,
            mem_addr_end=args.mem_end,
            plot_every=args.plot_every,
            output_file=args.output,
            fps=args.fps,
        )
