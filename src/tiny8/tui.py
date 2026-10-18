"""Modern Textual-based interactive debugger and dashboard for Tiny8.

Provides an OLED black themed TUI with real-time registers, memory, SREG flags,
gradient heatmap bars, stack explorer, breakpoints, and telemetry.
"""

from __future__ import annotations

import argparse
import bisect
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Header,
    Input,
    Label,
    ProgressBar,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from .assembler import assemble, assemble_file
from .compiler import (
    compile_c_file,
    compile_c_file_with_symbols,
    compile_c_with_symbols,
)
from .cpu import CPU

PLAYBACK_RATES: list[int] = [1, 5, 20, 100, 500, 2000, 5000, 10000, 50000]


class CheckpointManager:
    """Manages sparse snapshots and loop detection for time-travel.

    Stores complete CPU state snapshots every `interval` steps (default 100),
    enabling instant seeking and reverse playback without heavy RAM overhead.
    """

    def __init__(
        self,
        cpu: CPU,
        interval: int = 100,
        max_snapshots: int = 50000,
    ) -> None:
        self.cpu = cpu
        self.interval = interval
        self.max_snapshots = max_snapshots
        self.snapshots: dict[int, dict[str, Any]] = {}
        self.checkpoint_steps: list[int] = []
        self._history_signatures: dict[tuple[int, int, tuple[int, ...]], int] = {}
        self.infinite_loop_detected: bool = False
        self.loop_reason: str = ""

        # Initial step 0 snapshot
        self.record(0)

    def record(self, step: int) -> None:
        """Store a CPU snapshot at the given step."""
        if step not in self.snapshots and len(self.snapshots) < self.max_snapshots:
            self.snapshots[step] = self.cpu.snapshot()
            if not self.checkpoint_steps or step > self.checkpoint_steps[-1]:
                self.checkpoint_steps.append(step)
            else:
                idx = bisect.bisect_right(self.checkpoint_steps, step)
                self.checkpoint_steps.insert(idx, step)

    def record_if_interval(self, step: int) -> None:
        """Record snapshot if step is a multiple of interval."""
        if step % self.interval == 0:
            self.record(step)

    def restore_exact_step(self, target_step: int) -> bool:
        """Restore CPU to exact target_step using the closest preceding snapshot."""
        if target_step < 0 or not self.checkpoint_steps:
            return False

        # If target_step is beyond currently recorded checkpoints, dynamically extend cache
        if target_step > self.checkpoint_steps[-1] and not self.infinite_loop_detected:
            latest_step = self.checkpoint_steps[-1]
            self.cpu.restore_snapshot(self.snapshots[latest_step])
            self.cpu.running = 0 <= self.cpu.pc < len(self.cpu.program)
            old_trace = self.cpu.trace_enabled
            self.cpu.trace_enabled = False
            try:
                while self.cpu.running and self.cpu.step_count < target_step:
                    if self.detect_loop():
                        self.cpu.running = False
                        break
                    if not self.cpu.step(record_trace=False):
                        self.cpu.running = False
                        break
                    if self.cpu.step_count % self.interval == 0:
                        self.record(self.cpu.step_count)
                if self.cpu.step_count not in self.snapshots:
                    self.record(self.cpu.step_count)
            finally:
                self.cpu.trace_enabled = old_trace

        # Find closest checkpoint <= target_step
        idx = bisect.bisect_right(self.checkpoint_steps, target_step) - 1
        if idx < 0:
            base_step = self.checkpoint_steps[0]
        else:
            base_step = self.checkpoint_steps[idx]

        self.cpu.restore_snapshot(self.snapshots[base_step])
        self.cpu.running = 0 <= self.cpu.pc < len(self.cpu.program)
        self.infinite_loop_detected = False
        self.loop_reason = ""
        if self.detect_loop():
            self.cpu.running = False
        self.cpu.step_trace.clear()

        # Step forward remaining steps (at most self.interval - 1 steps)
        steps_to_advance = max(0, target_step - base_step) if self.cpu.running else 0
        for _ in range(steps_to_advance):
            if self.detect_loop():
                self.cpu.running = False
                break
            if not self.cpu.step():
                self.cpu.running = False
                break

        # Ensure step_trace has at least the current step representation
        if not self.cpu.step_trace:
            cur_instr = ""
            if 0 <= self.cpu.pc < len(self.cpu.program):
                instr, ops = self.cpu.program[self.cpu.pc]
                cur_instr = (
                    f"{instr} " + ", ".join(str(o) for o in ops) if ops else instr
                )
            self.cpu.step_trace.append(
                {
                    "step": self.cpu.step_count,
                    "pc": self.cpu.pc,
                    "instr": cur_instr,
                    "regs": list(self.cpu.regs),
                    "mem": dict(self.cpu.mem.nonzero_ram),
                    "sreg": self.cpu.sreg,
                    "sp": self.cpu.sp,
                    "source_line": self.cpu.pc_to_line.get(self.cpu.pc, -1),
                }
            )
        return True

    def invalidate_after(self, step: int) -> None:
        """Invalidate checkpoints after modified step on memory/register edit."""
        to_remove = [s for s in self.checkpoint_steps if s > step]
        for s in to_remove:
            self.snapshots.pop(s, None)
            self.checkpoint_steps.remove(s)
        self._history_signatures.clear()
        self.infinite_loop_detected = False
        self.loop_reason = ""

    def detect_loop(self, window_size: int = 256) -> bool:
        """Detect infinite loop (e.g. self-jump HALT or cycling registers/PC)."""
        cur_pc = self.cpu.pc
        if 0 <= cur_pc < len(self.cpu.program):
            instr, operands = self.cpu.program[cur_pc]
            if instr in ("RJMP", "JMP") and operands:
                op = operands[0]
                target_pc: int | None = None
                if isinstance(op, str):
                    target_pc = self.cpu.labels.get(op)
                elif isinstance(op, int):
                    if instr == "RJMP":
                        if op in (-1, 0):
                            target_pc = cur_pc
                        else:
                            target_pc = cur_pc + 1 + op
                    else:
                        target_pc = op
                if target_pc == cur_pc:
                    self.infinite_loop_detected = True
                    self.loop_reason = f"HALT spin loop detected at PC=0x{cur_pc:04X} (step {self.cpu.step_count})"
                    return True
            elif instr in ("HLT", "BREAK"):
                self.infinite_loop_detected = True
                self.loop_reason = f"HALT instruction encountered at PC=0x{cur_pc:04X}"
                return True

        sig = (cur_pc, self.cpu.sreg, tuple(self.cpu.regs))
        if sig in self._history_signatures:
            prev_step = self._history_signatures[sig]
            diff = self.cpu.step_count - prev_step
            if 0 < diff <= window_size:
                self.infinite_loop_detected = True
                self.loop_reason = f"Cycle loop detected: repeats every {diff} steps at PC=0x{cur_pc:04X}"
                return True
        self._history_signatures[sig] = self.cpu.step_count
        if len(self._history_signatures) > 3000:
            self._history_signatures.clear()
        return False

    def precompute(
        self,
        max_steps: int | None = None,
        check_loops: bool = True,
        progress_callback: Callable[[int, int | None], None] | None = None,
    ) -> int:
        """Precompute execution checkpoints until an infinite loop or halt is detected."""
        if not self.cpu.program or not (0 <= self.cpu.pc < len(self.cpu.program)):
            return 0
        old_trace = self.cpu.trace_enabled
        self.cpu.trace_enabled = False
        try:
            self.cpu.running = True
            computed = 0
            limit = max_steps if max_steps is not None else 10_000_000
            while self.cpu.running and computed < limit:
                if check_loops and self.detect_loop():
                    self.cpu.running = False
                    break
                if not self.cpu.step(record_trace=False):
                    break
                computed += 1
                if self.cpu.step_count % self.interval == 0:
                    self.record(self.cpu.step_count)
                if progress_callback and (computed % 10000 == 0):
                    progress_callback(computed, max_steps)
            if self.cpu.step_count not in self.snapshots:
                self.record(self.cpu.step_count)
            if progress_callback:
                progress_callback(computed, max_steps)
            return computed
        finally:
            self.cpu.trace_enabled = old_trace


INSTRUCTION_DOCS: dict[str, dict[str, str]] = {
    "NOP": {
        "name": "No Operation",
        "syntax": "NOP",
        "desc": "Performs no operation. The CPU performs a single cycle nop.",
        "flags": "None",
    },
    "LDI": {
        "name": "Load Immediate",
        "syntax": "LDI Rd, K",
        "desc": "Loads an 8-bit constant directly into register Rd (16 <= d <= 31, 0 <= K <= 255).",
        "flags": "None",
    },
    "MOV": {
        "name": "Copy Register",
        "syntax": "MOV Rd, Rr",
        "desc": "Makes a copy of one register into another (Rd <- Rr). The source register Rr is unchanged.",
        "flags": "None",
    },
    "ADD": {
        "name": "Add without Carry",
        "syntax": "ADD Rd, Rr",
        "desc": "Adds two registers without the C Flag and places the result in the destination register Rd (Rd <- Rd + Rr).",
        "flags": "H, S, V, N, Z, C",
    },
    "ADC": {
        "name": "Add with Carry",
        "syntax": "ADC Rd, Rr",
        "desc": "Adds two registers and the contents of the C Flag and places the result in Rd (Rd <- Rd + Rr + C).",
        "flags": "H, S, V, N, Z, C",
    },
    "SUB": {
        "name": "Subtract without Carry",
        "syntax": "SUB Rd, Rr",
        "desc": "Subtracts two registers and places the result in the destination register Rd (Rd <- Rd - Rr).",
        "flags": "H, S, V, N, Z, C",
    },
    "SUBI": {
        "name": "Subtract Immediate",
        "syntax": "SUBI Rd, K",
        "desc": "Subtracts a constant from a register and places the result in Rd (Rd <- Rd - K, 16 <= d <= 31).",
        "flags": "H, S, V, N, Z, C",
    },
    "SBC": {
        "name": "Subtract with Carry",
        "syntax": "SBC Rd, Rr",
        "desc": "Subtracts two registers and subtracts the C Flag and places the result in Rd (Rd <- Rd - Rr - C).",
        "flags": "H, S, V, N, Z, C",
    },
    "SBCI": {
        "name": "Subtract Immediate with Carry",
        "syntax": "SBCI Rd, K",
        "desc": "Subtracts a constant and the C Flag from Rd (Rd <- Rd - K - C, 16 <= d <= 31).",
        "flags": "H, S, V, N, Z, C",
    },
    "AND": {
        "name": "Logical AND",
        "syntax": "AND Rd, Rr",
        "desc": "Performs the logical AND between two registers and places the result in Rd (Rd <- Rd & Rr).",
        "flags": "S, V=0, N, Z",
    },
    "ANDI": {
        "name": "Logical AND with Immediate",
        "syntax": "ANDI Rd, K",
        "desc": "Performs the logical AND between register Rd and a constant (Rd <- Rd & K, 16 <= d <= 31).",
        "flags": "S, V=0, N, Z",
    },
    "OR": {
        "name": "Logical OR",
        "syntax": "OR Rd, Rr",
        "desc": "Performs the logical OR between two registers and places the result in Rd (Rd <- Rd | Rr).",
        "flags": "S, V=0, N, Z",
    },
    "ORI": {
        "name": "Logical OR with Immediate",
        "syntax": "ORI Rd, K",
        "desc": "Performs the logical OR between register Rd and a constant (Rd <- Rd | K, 16 <= d <= 31).",
        "flags": "S, V=0, N, Z",
    },
    "EOR": {
        "name": "Exclusive OR",
        "syntax": "EOR Rd, Rr",
        "desc": "Performs the logical Exclusive OR between two registers and places the result in Rd (Rd <- Rd ^ Rr).",
        "flags": "S, V=0, N, Z",
    },
    "COM": {
        "name": "One's Complement",
        "syntax": "COM Rd",
        "desc": "Performs a One's Complement of register Rd (Rd <- $FF - Rd).",
        "flags": "S, V=0, N, Z, C=1",
    },
    "NEG": {
        "name": "Two's Complement",
        "syntax": "NEG Rd",
        "desc": "Replaces the contents of register Rd with its two's complement (Rd <- $00 - Rd).",
        "flags": "H, S, V, N, Z, C",
    },
    "INC": {
        "name": "Increment",
        "syntax": "INC Rd",
        "desc": "Adds one to the contents of register Rd (Rd <- Rd + 1). The C Flag is not affected.",
        "flags": "S, V, N, Z",
    },
    "DEC": {
        "name": "Decrement",
        "syntax": "DEC Rd",
        "desc": "Subtracts one from the contents of register Rd (Rd <- Rd - 1). The C Flag is not affected.",
        "flags": "S, V, N, Z",
    },
    "MUL": {
        "name": "Multiply Unsigned",
        "syntax": "MUL Rd, Rr",
        "desc": "Performs 8x8 -> 16-bit unsigned multiplication: R1:R0 <- Rd * Rr (R0 = low byte, R1 = high byte).",
        "flags": "Z, C",
    },
    "MULS": {
        "name": "Multiply Signed",
        "syntax": "MULS Rd, Rr",
        "desc": "Performs 8x8 -> 16-bit signed multiplication: R1:R0 <- Rd * Rr (signed).",
        "flags": "Z, C",
    },
    "MULSU": {
        "name": "Multiply Signed with Unsigned",
        "syntax": "MULSU Rd, Rr",
        "desc": "Performs 8x8 -> 16-bit signed-with-unsigned multiplication: R1:R0 <- Rd * Rr (Rd signed, Rr unsigned).",
        "flags": "Z, C",
    },
    "CP": {
        "name": "Compare",
        "syntax": "CP Rd, Rr",
        "desc": "Compares two registers (Rd - Rr) without altering contents and sets SREG flags.",
        "flags": "H, S, V, N, Z, C",
    },
    "CPI": {
        "name": "Compare with Immediate",
        "syntax": "CPI Rd, K",
        "desc": "Compares register Rd with constant K (Rd - K, 16 <= d <= 31) and sets SREG flags.",
        "flags": "H, S, V, N, Z, C",
    },
    "CPSE": {
        "name": "Compare and Skip if Equal",
        "syntax": "CPSE Rd, Rr",
        "desc": "Compares two registers and skips the next instruction if Rd == Rr.",
        "flags": "None",
    },
    "JMP": {
        "name": "Jump",
        "syntax": "JMP k",
        "desc": "Unconditional jump to the entire program space (PC <- k).",
        "flags": "None",
    },
    "RJMP": {
        "name": "Relative Jump",
        "syntax": "RJMP k",
        "desc": "Relative jump to an address within PC - 2K + 1 and PC + 2K (words).",
        "flags": "None",
    },
    "CALL": {
        "name": "Long Call to a Subroutine",
        "syntax": "CALL k",
        "desc": "Calls a subroutine in the entire program space, pushing return address onto the stack.",
        "flags": "None",
    },
    "RCALL": {
        "name": "Relative Call to a Subroutine",
        "syntax": "RCALL k",
        "desc": "Relative call to a subroutine within PC - 2K + 1 and PC + 2K, pushing return address.",
        "flags": "None",
    },
    "RET": {
        "name": "Return from Subroutine",
        "syntax": "RET",
        "desc": "Returns from subroutine by popping return address from the stack into PC.",
        "flags": "None",
    },
    "RETI": {
        "name": "Return from Interrupt",
        "syntax": "RETI",
        "desc": "Returns from interrupt by popping return address from stack and setting Global Interrupt Flag (I <- 1).",
        "flags": "I=1",
    },
    "BREQ": {
        "name": "Branch if Equal",
        "syntax": "BREQ k",
        "desc": "Conditional relative branch: Tests Zero Flag (Z) and branches if Z is set (Z == 1).",
        "flags": "None",
    },
    "BRNE": {
        "name": "Branch if Not Equal",
        "syntax": "BRNE k",
        "desc": "Conditional relative branch: Tests Zero Flag (Z) and branches if Z is cleared (Z == 0).",
        "flags": "None",
    },
    "BRCS": {
        "name": "Branch if Carry Set",
        "syntax": "BRCS k",
        "desc": "Conditional relative branch: Tests Carry Flag (C) and branches if C is set (C == 1).",
        "flags": "None",
    },
    "BRCC": {
        "name": "Branch if Carry Cleared",
        "syntax": "BRCC k",
        "desc": "Conditional relative branch: Tests Carry Flag (C) and branches if C is cleared (C == 0).",
        "flags": "None",
    },
    "BRLO": {
        "name": "Branch if Lower (Unsigned)",
        "syntax": "BRLO k",
        "desc": "Conditional relative branch: Tests Carry Flag (C) and branches if C is set (same as BRCS).",
        "flags": "None",
    },
    "BRSH": {
        "name": "Branch if Same or Higher (Unsigned)",
        "syntax": "BRSH k",
        "desc": "Conditional relative branch: Tests Carry Flag (C) and branches if C is cleared (same as BRCC).",
        "flags": "None",
    },
    "BRGE": {
        "name": "Branch if Greater or Equal (Signed)",
        "syntax": "BRGE k",
        "desc": "Conditional relative branch: Tests Sign Flag (S) and branches if S is cleared (S == 0).",
        "flags": "None",
    },
    "BRLT": {
        "name": "Branch if Less Than (Signed)",
        "syntax": "BRLT k",
        "desc": "Conditional relative branch: Tests Sign Flag (S) and branches if S is set (S == 1).",
        "flags": "None",
    },
    "BRMI": {
        "name": "Branch if Minus",
        "syntax": "BRMI k",
        "desc": "Conditional relative branch: Tests Negative Flag (N) and branches if N is set (N == 1).",
        "flags": "None",
    },
    "BRPL": {
        "name": "Branch if Plus",
        "syntax": "BRPL k",
        "desc": "Conditional relative branch: Tests Negative Flag (N) and branches if N is cleared (N == 0).",
        "flags": "None",
    },
    "PUSH": {
        "name": "Push Register on Stack",
        "syntax": "PUSH Rr",
        "desc": "Stores the contents of register Rr on the stack. The Stack Pointer is post-decremented.",
        "flags": "None",
    },
    "POP": {
        "name": "Pop Register from Stack",
        "syntax": "POP Rd",
        "desc": "Loads register Rd with the contents of the stack. The Stack Pointer is pre-incremented.",
        "flags": "None",
    },
    "LD": {
        "name": "Load Indirect from Data Space to Register",
        "syntax": "LD Rd, X / Y / Z",
        "desc": "Loads one byte indirect from the data space to register Rd using pointer register.",
        "flags": "None",
    },
    "ST": {
        "name": "Store Indirect from Register to Data Space",
        "syntax": "ST X / Y / Z, Rr",
        "desc": "Stores one byte indirect from register Rr to data space using pointer register.",
        "flags": "None",
    },
    "LDS": {
        "name": "Load Direct from Data Space",
        "syntax": "LDS Rd, k",
        "desc": "Loads one byte from the data space to register Rd (Rd <- (k)).",
        "flags": "None",
    },
    "STS": {
        "name": "Store Direct to Data Space",
        "syntax": "STS k, Rr",
        "desc": "Stores one byte from register Rr to the data space ((k) <- Rr).",
        "flags": "None",
    },
    "LSL": {
        "name": "Logical Shift Left",
        "syntax": "LSL Rd",
        "desc": "Shifts all bits in Rd left: C <- Rd7, Rd(n+1) <- Rd(n), Rd0 <- 0 (Alternative to ADD Rd, Rd).",
        "flags": "H, S, V, N, Z, C",
    },
    "LSR": {
        "name": "Logical Shift Right",
        "syntax": "LSR Rd",
        "desc": "Shifts all bits in Rd right: 0 -> Rd7 -> ... -> Rd0 -> C.",
        "flags": "S, V, N=0, Z, C",
    },
    "ASR": {
        "name": "Arithmetic Shift Right",
        "syntax": "ASR Rd",
        "desc": "Shifts all bits in Rd right, preserving sign bit: Rd7 -> Rd7 -> ... -> Rd0 -> C.",
        "flags": "S, V, N, Z, C",
    },
    "ROL": {
        "name": "Rotate Left Through Carry",
        "syntax": "ROL Rd",
        "desc": "Shifts all bits in Rd left through C Flag (Alternative to ADC Rd, Rd).",
        "flags": "H, S, V, N, Z, C",
    },
    "ROR": {
        "name": "Rotate Right Through Carry",
        "syntax": "ROR Rd",
        "desc": "Shifts all bits in Rd right through C Flag: Rd7 <- C, Rd(n) <- Rd(n+1), C <- Rd0.",
        "flags": "S, V, N, Z, C",
    },
    "SWAP": {
        "name": "Swap Nibbles",
        "syntax": "SWAP Rd",
        "desc": "Swaps high and low nibbles in a register: Rd(7..4) <-> Rd(3..0).",
        "flags": "None",
    },
    "TST": {
        "name": "Test for Zero or Minus",
        "syntax": "TST Rd",
        "desc": "Tests if a number is negative or zero: Rd & Rd (Alternative to AND Rd, Rd).",
        "flags": "S, V=0, N, Z",
    },
    "CLR": {
        "name": "Clear Register",
        "syntax": "CLR Rd",
        "desc": "Clears a register: Rd <- Rd ^ Rd = $00 (Alternative to EOR Rd, Rd).",
        "flags": "S=0, V=0, N=0, Z=1",
    },
    "SER": {
        "name": "Set Register",
        "syntax": "SER Rd",
        "desc": "Loads $FF directly into register Rd (16 <= d <= 31; Alternative to LDI Rd, $FF).",
        "flags": "None",
    },
    "ADIW": {
        "name": "Add Immediate to Word",
        "syntax": "ADIW Rd+1:Rd, K",
        "desc": "Adds an immediate value (0-63) to a register pair (R25:R24, R27:R26, R29:R28, R31:R30).",
        "flags": "S, V, N, Z, C",
    },
    "SBIW": {
        "name": "Subtract Immediate from Word",
        "syntax": "SBIW Rd+1:Rd, K",
        "desc": "Subtracts an immediate value (0-63) from a register pair (R25:R24, R27:R26, R29:R28, R31:R30).",
        "flags": "S, V, N, Z, C",
    },
    "SBI": {
        "name": "Set Bit in I/O Register",
        "syntax": "SBI A, b",
        "desc": "Sets a specified bit in an I/O register (0 <= A <= 31, 0 <= b <= 7).",
        "flags": "None",
    },
    "CBI": {
        "name": "Clear Bit in I/O Register",
        "syntax": "CBI A, b",
        "desc": "Clears a specified bit in an I/O register (0 <= A <= 31, 0 <= b <= 7).",
        "flags": "None",
    },
    "IN": {
        "name": "Load an I/O Location to Register",
        "syntax": "IN Rd, A",
        "desc": "Loads data from the I/O Space (Ports, Timers, Configuration Registers) into register Rd.",
        "flags": "None",
    },
    "OUT": {
        "name": "Store Register to an I/O Location",
        "syntax": "OUT A, Rr",
        "desc": "Stores data from register Rr to the I/O Space (Ports, Timers, Configuration Registers).",
        "flags": "None",
    },
    "SEI": {
        "name": "Set Global Interrupt Flag",
        "syntax": "SEI",
        "desc": "Sets the Global Interrupt Flag (I) in SREG. Interrupts will be enabled.",
        "flags": "I=1",
    },
    "CLI": {
        "name": "Clear Global Interrupt Flag",
        "syntax": "CLI",
        "desc": "Clears the Global Interrupt Flag (I) in SREG. Interrupts will be disabled.",
        "flags": "I=0",
    },
    "SBRS": {
        "name": "Skip if Bit in Register is Set",
        "syntax": "SBRS Rr, b",
        "desc": "Tests a bit in a register and skips the next instruction if the bit is set (0 <= b <= 7).",
        "flags": "None",
    },
    "SBRC": {
        "name": "Skip if Bit in Register is Cleared",
        "syntax": "SBRC Rr, b",
        "desc": "Tests a bit in a register and skips the next instruction if the bit is cleared (0 <= b <= 7).",
        "flags": "None",
    },
    "SBIS": {
        "name": "Skip if Bit in I/O Register is Set",
        "syntax": "SBIS A, b",
        "desc": "Tests a bit in an I/O register and skips the next instruction if the bit is set.",
        "flags": "None",
    },
    "SBIC": {
        "name": "Skip if Bit in I/O Register is Cleared",
        "syntax": "SBIC A, b",
        "desc": "Tests a bit in an I/O register and skips the next instruction if the bit is cleared.",
        "flags": "None",
    },
}


def interpolate_color(t: float) -> str:
    """Interpolate RGB color matching authentic Viridis style.

    Args:
        t: Float value from 0.0 to 1.0.

    Returns:
        Hex RGB color string (e.g. '#FDE725').
    """
    t = max(0.0, min(1.0, t))
    points = [
        (0.00, (68, 1, 84)),  # #440154 Deep Purple
        (0.15, (71, 45, 123)),  # #472D7B Purple
        (0.30, (49, 104, 142)),  # #31688E Blue
        (0.45, (33, 145, 140)),  # #21918C Teal
        (0.60, (53, 183, 121)),  # #35B779 Green
        (0.75, (109, 205, 89)),  # #6DCD59 Light Green
        (0.90, (180, 222, 44)),  # #B4DE2C Yellow-Green
        (1.00, (253, 231, 37)),  # #FDE725 Bright Yellow
    ]
    for i in range(len(points) - 1):
        t0, c0 = points[i]
        t1, c1 = points[i + 1]
        if t0 <= t <= t1:
            ratio = (t - t0) / (t1 - t0) if (t1 - t0) > 0 else 0.0
            r = int(c0[0] + ratio * (c1[0] - c0[0]))
            g = int(c0[1] + ratio * (c1[1] - c0[1]))
            b = int(c0[2] + ratio * (c1[2] - c0[2]))
            return f"#{r:02X}{g:02X}{b:02X}"
    return "#FDE725"


def get_widget_available_lines(
    widget: Static, overhead: int = 8, min_lines: int = 4
) -> int:
    """Calculate visible content lines available for widget based on terminal/screen height."""
    try:
        if widget.screen and widget.screen.size.height > 0:
            return max(min_lines, widget.screen.size.height - overhead)
    except Exception:
        pass
    try:
        if getattr(widget, "app", None) and widget.app.size.height > 0:
            return max(min_lines, widget.app.size.height - overhead)
    except Exception:
        pass
    try:
        if widget.size.height > 0:
            return max(min_lines, widget.size.height)
    except Exception:
        pass
    try:
        return max(min_lines, shutil.get_terminal_size((120, 36)).lines - overhead)
    except Exception:
        return 24


def render_btop_bar(val: int, max_val: int = 255, width: int = 18) -> Text:
    """Render horizontal gradient heatmap bar with trailing dot fill.

    Args:
        val: Current numerical value.
        max_val: Upper scale limit.
        width: Character width of bar.

    Returns:
        Rich Text object containing gradient blocks and shade dots.
    """
    ratio = min(1.0, max(0.0, val / max_val)) if max_val > 0 else 0.0
    filled_blocks = int(ratio * width)

    t = Text()
    for col in range(width):
        col_ratio = (col + 1) / width
        color = interpolate_color(col_ratio)
        if col < filled_blocks:
            t.append("█", style=color)
        else:
            t.append("░", style="#1A1A1A on #000000")
    return t


class SregWidget(Static):
    """Badge-style display for SREG condition flags."""

    sreg: reactive[int] = reactive(0)

    FLAGS = [
        ("I", 7),
        ("T", 6),
        ("H", 5),
        ("S", 4),
        ("V", 3),
        ("N", 2),
        ("Z", 1),
        ("C", 0),
    ]

    def render(self) -> Text:
        res = Text()
        res.append(" SREG: ", style="bold #00D2FF")
        for name, bit in self.FLAGS:
            is_set = (self.sreg >> bit) & 1
            if is_set:
                res.append(f" {name} ", style="bold black on #00FF87")
            else:
                res.append(f" {name} ", style="dim #444444 on #111111")
            res.append(" ")
        res.append(f"(0x{self.sreg:02X})", style="bold #FFAA00")
        return res


class BtopRegistersWidget(Static):
    """Register bars with graphical gradient heatmaps in a 2-column layout."""

    regs: reactive[list[int]] = reactive(lambda: [0] * 32)
    prev_regs: reactive[list[int]] = reactive(lambda: [0] * 32)
    start_r: reactive[int] = reactive(0)
    visible_count: reactive[int] = reactive(32)

    def render(self) -> Text:
        t = Text()
        t.append(
            " REGISTERS (R00..R31)\n",
            style="bold #00D2FF",
        )
        bar_w = 10
        for row in range(16):
            # Left column: R00..R15
            r_l = row
            val_l = self.regs[r_l] if r_l < len(self.regs) else 0
            pval_l = self.prev_regs[r_l] if r_l < len(self.prev_regs) else 0
            chg_l = val_l != pval_l
            style_l = (
                "bold #FFAA00"
                if chg_l
                else ("bold #00FF87" if val_l > 0 else "dim #666666")
            )
            t.append(f" R{r_l:02d} ", style=style_l)
            t.append_text(render_btop_bar(val_l, max_val=255, width=bar_w))
            t.append(f" 0x{val_l:02X}", style=style_l)
            t.append(f"({val_l:>3})", style="#CCCCCC" if val_l > 0 else "dim #444444")
            t.append("◀" if chg_l else " ", style="bold #FFAA00")

            t.append(" │ ", style="dim #333333")

            # Right column: R16..R31
            r_r = row + 16
            val_r = self.regs[r_r] if r_r < len(self.regs) else 0
            pval_r = self.prev_regs[r_r] if r_r < len(self.prev_regs) else 0
            chg_r = val_r != pval_r
            style_r = (
                "bold #FFAA00"
                if chg_r
                else ("bold #00FF87" if val_r > 0 else "dim #666666")
            )
            t.append(f"R{r_r:02d} ", style=style_r)
            t.append_text(render_btop_bar(val_r, max_val=255, width=bar_w))
            t.append(f" 0x{val_r:02X}", style=style_r)
            t.append(f"({val_r:>3})", style="#CCCCCC" if val_r > 0 else "dim #444444")
            t.append("◀" if chg_r else " ", style="bold #FFAA00")
            t.append("\n")
        return t


class RegistersWidget(Static):
    """Grid displaying 32 8-bit general purpose registers."""

    regs: reactive[list[int]] = reactive(lambda: [0] * 32)
    prev_regs: reactive[list[int]] = reactive(lambda: [0] * 32)

    def render(self) -> Text:
        t = Text()
        t.append(" REGISTERS (R0..R31)\n", style="bold #00D2FF")
        for row in range(4):
            for col in range(8):
                idx = row * 8 + col
                val = self.regs[idx] if idx < len(self.regs) else 0
                pval = self.prev_regs[idx] if idx < len(self.prev_regs) else 0
                is_changed = val != pval

                r_label = f"R{idx:02d}:"
                hex_val = f"{val:02X}"
                if is_changed:
                    t.append(f"{r_label}", style="dim #888888")
                    t.append(f"{hex_val} ", style="bold black on #FFAA00")
                elif val != 0:
                    t.append(f"{r_label}", style="dim #888888")
                    t.append(f"{hex_val} ", style="bold #00FF87")
                else:
                    t.append(f"{r_label}", style="dim #333333")
                    t.append(f"{hex_val} ", style="dim #555555")
            t.append("\n")
        return t


class MemoryWidget(Static):
    """32x32 Memory Dump with rich heatmap background coloring for direct visual rendering."""

    mem: reactive[dict[int, int]] = reactive(dict)
    prev_mem: reactive[dict[int, int]] = reactive(dict)
    start_addr: reactive[int] = reactive(0x0200)
    width: int = 32
    height: int = 32
    color_mode: reactive[str] = reactive("viridis")
    show_hex: reactive[bool] = reactive(True)

    @staticmethod
    def get_heatmap_bg(val: int, color_mode: str = "viridis") -> str:
        """Calculate rich heat color background for byte value 0..255."""
        if color_mode == "grayscale":
            if val <= 0:
                return "#000000"
            v = max(0, min(255, val))
            return f"#{v:02X}{v:02X}{v:02X}"
        # Viridis mode
        if val <= 0:
            return "#0D0818"
        return interpolate_color(val / 255.0)

    def render(self) -> Text:
        t = Text()
        avail_rows = get_widget_available_lines(self, overhead=8, min_lines=4)
        rows_to_show = max(4, avail_rows - 1)
        end_addr = min(0xFFFF, self.start_addr + self.width * rows_to_show - 1)
        palette_lbl = "Viridis" if self.color_mode == "viridis" else "Grayscale"
        display_lbl = "HEX" if self.show_hex else "PIXEL"
        t.append(
            f" MEMORY DUMP (0x{self.start_addr:04X}..0x{end_addr:04X}) "
            f"[{self.width}x{rows_to_show} | {palette_lbl} | {display_lbl} | g: gray/viridis, x: hex/pixel, j/k: scroll, J/K: fast]\n",
            style="bold #00D2FF",
        )
        for r in range(rows_to_show):
            row_addr = self.start_addr + r * self.width
            if row_addr > 0xFFFF:
                break
            t.append(f"0x{row_addr:04X}: ", style="bold #666666")
            for col in range(self.width):
                addr = row_addr + col
                if addr > 0xFFFF:
                    break
                val = self.mem.get(addr, 0)

                if val == 0:
                    if self.color_mode == "grayscale":
                        if self.show_hex:
                            t.append("..", style="dim #444444 on #000000")
                        else:
                            t.append("  ", style="on #000000")
                    else:
                        if self.show_hex:
                            t.append("..", style="dim #472D7B on #0D0818")
                        else:
                            t.append("  ", style="on #0D0818")
                else:
                    bg = self.get_heatmap_bg(val, self.color_mode)
                    if self.show_hex:
                        if self.color_mode == "grayscale":
                            fg = "#000000" if val >= 128 else "#FFFFFF"
                        else:
                            fg = "#000000" if val >= 140 else "#FFFFFF"
                        t.append(f"{val:02X}", style=f"bold {fg} on {bg}")
                    else:
                        t.append("  ", style=f"on {bg}")

            t.append("\n")
        return t


class StackWidget(Static):
    """Call stack and stack pointer inspector."""

    sp: reactive[int] = reactive(0xFFFF)
    mem: reactive[dict[int, int]] = reactive(dict)
    ram_size: reactive[int] = reactive(65536)

    def render(self) -> Text:
        t = Text()
        t.append(f" CALL STACK (SP: 0x{self.sp:04X})\n", style="bold #00D2FF")

        max_entries = 5
        base_sp = self.ram_size - 1
        depth = base_sp - self.sp

        if depth <= 0:
            t.append(
                "  (Stack is currently empty - SP at top of RAM)\n", style="dim #555555"
            )
            return t

        for i in range(min(max_entries, depth)):
            addr = self.sp + 1 + i
            val = self.mem.get(addr, 0)
            tag = "TOS (Top of Stack)" if i == 0 else f"TOS+{i}"
            t.append(f"  0x{addr:04X}: ", style="dim #888888")
            t.append(f"0x{val:02X} ", style="bold #00FF87")
            t.append(f"({val:>3}) ", style="#CCCCCC")
            t.append(f"[{tag}]\n", style="dim #FFAA00")

        if depth > max_entries:
            t.append(
                f"  ... and {depth - max_entries} more stack entries\n",
                style="dim #666666",
            )
        return t


class InstructionDetailWidget(Static):
    """Deep-dive inspector displaying current instruction details, syntax, and effects."""

    current_instr: reactive[str] = reactive("")
    pc: reactive[int] = reactive(0)
    sp: reactive[int] = reactive(0)
    source_line: reactive[int] = reactive(-1)
    source_text: reactive[str] = reactive("")

    def render(self) -> Text:
        t = Text()
        t.append(" INSTRUCTION INSPECTOR & REFERENCE\n", style="bold #00D2FF")

        if not self.current_instr:
            t.append("  (No instruction executed yet)\n", style="dim #555555")
            return t

        parts = self.current_instr.split()
        mnemonic = parts[0].upper() if parts else ""
        doc = INSTRUCTION_DOCS.get(mnemonic, {})

        name = doc.get("name", "Custom / Label")
        syntax = doc.get("syntax", self.current_instr)
        desc = doc.get("desc", "Executes CPU instruction step.")
        flags = doc.get("flags", "None")

        t.append("  Current: ", style="dim #888888")
        t.append(f"{self.current_instr:<16} ", style="bold #FFFFFF")
        t.append("PC: ", style="dim #888888")
        t.append(f"0x{self.pc:04X} ", style="bold #00FF87")
        t.append("SP: ", style="dim #888888")
        t.append(f"0x{self.sp:04X}\n", style="bold #FFAA00")

        t.append("  Name:    ", style="dim #888888")
        t.append(f"{name} ", style="bold #00D2FF")
        t.append(f"({syntax})\n", style="dim #AAAAAA")

        t.append("  Action:  ", style="dim #888888")
        t.append(f"{desc}\n", style="#CCCCCC")

        t.append("  Flags:   ", style="dim #888888")
        t.append(f"{flags}", style="bold #FFAA00")

        if self.source_line >= 0 and self.source_text:
            t.append("\n  Source:  ", style="dim #888888")
            t.append(f"Line {self.source_line + 1}: ", style="bold #00FF87")
            t.append(f"{self.source_text}", style="italic #AAAAAA")

        return t


class TelemetryWidget(Static):
    """Real-time execution metrics and instruction distribution dashboard."""

    total_steps: reactive[int] = reactive(0)
    current_step: reactive[int] = reactive(0)
    instr_counts: reactive[dict[str, int]] = reactive(dict)

    def render(self) -> Text:
        t = Text()
        t.append(" EXECUTION TELEMETRY\n", style="bold #00D2FF")
        t.append(
            f"  Step Progress: {self.current_step}/{self.total_steps}\n",
            style="#dddddd",
        )

        top_instr = Counter(self.instr_counts).most_common(5)
        if top_instr:
            t.append("  Top Instructions:\n", style="dim #888888")
            max_c = max(c for _, c in top_instr) if top_instr else 1
            for name, count in top_instr:
                bar_len = int((count / max_c) * 14)
                bar = "█" * bar_len
                t.append(f"    {name:<5}: ", style="bold #FFAA00")
                t.append(f"{bar:<14} ", style="#00FF87")
                t.append(f"{count:>4}\n", style="dim #777777")
        return t


class CodeViewWidget(Static):
    """Assembly and source line inspection with execution pointer and breakpoints."""

    program: reactive[list[tuple[str, tuple]]] = reactive(list)
    current_pc: reactive[int] = reactive(0)
    source_lines: reactive[list[str]] = reactive(list)
    pc_to_line: reactive[dict[int, int]] = reactive(dict)
    breakpoints: reactive[set[int]] = reactive(set)

    def render(self) -> Text:
        t = Text()
        t.append(" PROGRAM EXECUTION [b: toggle breakpoint]\n", style="bold #00D2FF")

        window = 7
        start = max(0, self.current_pc - window // 2)
        end = min(len(self.program), start + window)

        for pc in range(start, end):
            is_current = pc == self.current_pc
            has_bp = pc in self.breakpoints
            instr, ops = self.program[pc]
            ops_str = ", ".join(
                f"R{op[1]}" if isinstance(op, tuple) and op[0] == "reg" else str(op)
                for op in ops
            )
            line_str = f"0x{pc:04X}: {instr:<5} {ops_str}"

            bp_marker = "● " if has_bp else "  "
            bp_style = "bold #FF0055" if has_bp else "dim #444444"

            t.append(bp_marker, style=bp_style)
            if is_current:
                t.append(f"▶ {line_str:<28}\n", style="bold black on #00D2FF")
            else:
                t.append(f"  {line_str:<28}\n", style="#FFFFFF")
        return t


def eval_condition(expr: str, regs: list[int], mem: dict[int, int]) -> bool:
    """Safely evaluate debugger watch and conditional breakpoint expressions."""
    expr = expr.strip()
    match = re.match(r"^(.*?)\s*(==|!=|<=|>=|<|>)\s*(.*?)$", expr)
    if not match:
        r_m = re.match(r"^[rR](\d+)$", expr)
        if r_m:
            idx = int(r_m.group(1))
            return bool(regs[idx]) if 0 <= idx < len(regs) else False
        return False

    left_str, op, right_str = match.groups()

    def resolve(val_str: str) -> int:
        val_str = val_str.strip()
        r_m = re.match(r"^[rR](\d+)$", val_str)
        if r_m:
            r_idx = int(r_m.group(1))
            return regs[r_idx] if 0 <= r_idx < len(regs) else 0
        m_m = re.match(r"^mem\[(0x[0-9a-fA-F]+|\d+)\]$", val_str)
        if m_m:
            addr = (
                int(m_m.group(1), 16)
                if m_m.group(1).startswith("0x")
                else int(m_m.group(1))
            )
            return mem.get(addr, 0)
        return int(val_str, 16) if val_str.startswith("0x") else int(val_str)

    try:
        left = resolve(left_str)
        right = resolve(right_str)
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == "<=":
            return left <= right
        if op == ">=":
            return left >= right
        if op == "<":
            return left < right
        if op == ">":
            return left > right
    except Exception:
        return False
    return False


def extract_call_frames(
    traces: list[dict[str, Any]], current_idx: int
) -> list[dict[str, Any]]:
    """Reconstruct active function call frames up to current trace index."""
    frames: list[dict[str, Any]] = []
    for i in range(min(current_idx + 1, len(traces))):
        instr = traces[i].get("instr", "")
        parts = instr.split()
        if not parts:
            continue
        op = parts[0].upper()
        if op in ("RCALL", "CALL") and len(parts) > 1:
            target = parts[1]
            frames.append(
                {
                    "func": target,
                    "pc": traces[i].get("pc", 0),
                    "sp": traces[i].get("sp", 0),
                    "step": i,
                }
            )
        elif op == "RET":
            if frames:
                frames.pop()
    return frames


class CVariablesWidget(Static):
    """Live C variable table showing symbol names, addresses, and runtime values."""

    var_symbols: reactive[dict[str, dict[str, Any]]] = reactive(dict)
    mem: reactive[dict[int, int]] = reactive(dict)
    prev_mem: reactive[dict[int, int]] = reactive(dict)

    def render(self) -> Text:
        t = Text()
        t.append(" C VARIABLES (LIVE SYMBOL TABLE)\n", style="bold #00D2FF")
        if not self.var_symbols:
            t.append("  (No C variable symbols loaded)\n", style="dim #666666")
            t.append(
                "  Compile or run C code ('tiny8 <file.c>') to inspect variables\n",
                style="dim #444444",
            )
            return t

        t.append(
            f"  {'VARIABLE':<12} {'TYPE':<6} {'ADDR':<8} {'HEX':<6} {'DEC':<6} {'STATUS'}\n",
            style="bold #888888",
        )
        t.append(
            f"  {'-' * 12} {'-' * 6} {'-' * 8} {'-' * 6} {'-' * 6} {'-' * 8}\n",
            style="dim #444444",
        )

        for name, meta in sorted(
            self.var_symbols.items(), key=lambda x: x[1].get("addr", 0)
        ):
            addr = meta.get("addr", 0)
            vtype = meta.get("type", "int")
            val = self.mem.get(addr, 0)
            pval = self.prev_mem.get(addr, 0)
            is_chg = val != pval

            name_style = "bold #FFAA00" if is_chg else "bold #FFFFFF"
            val_style = (
                "bold black on #FFAA00"
                if is_chg
                else ("bold #00FF87" if val > 0 else "dim #555555")
            )

            t.append(f"  {name:<12} ", style=name_style)
            t.append(f"{vtype:<6} ", style="#00D2FF")
            t.append(f"0x{addr:04X}   ", style="dim #AAAAAA")
            t.append(f"0x{val:02X}   ", style=val_style)
            t.append(f"{val:>3}    ", style="#CCCCCC" if val > 0 else "dim #555555")
            if is_chg:
                t.append("UPDATED ◀\n", style="bold #FFAA00")
            elif val > 0:
                t.append("ACTIVE\n", style="dim #00FF87")
            else:
                t.append("ZERO\n", style="dim #444444")
        return t


class CallStackWidget(Static):
    """Dynamic function backtrace reconstructed from execution calls and returns."""

    frames: reactive[list[dict[str, Any]]] = reactive(list)
    current_pc: reactive[int] = reactive(0)

    def render(self) -> Text:
        t = Text()
        t.append(" FUNCTION CALL STACK (BACKTRACE)\n", style="bold #00D2FF")
        if not self.frames:
            t.append(
                f"  #0  main() at PC:0x{self.current_pc:04X} (active frame)\n",
                style="bold #00FF87",
            )
            return t

        for i, frame in enumerate(reversed(self.frames)):
            depth = len(self.frames) - i
            fname = frame.get("func", "function")
            call_pc = frame.get("pc", 0)
            call_sp = frame.get("sp", 0)
            is_top = i == 0
            prefix = "▶ " if is_top else "  "
            style = "bold #00FF87" if is_top else "#CCCCCC"
            t.append(f"{prefix}#{depth}  {fname}() ", style=style)
            t.append(
                f"[called from PC:0x{call_pc:04X}, SP:0x{call_sp:04X}]\n",
                style="dim #888888",
            )

        t.append("   #0  main() (root entry)\n", style="dim #666666")
        return t


class MemoryMatrixWidget(Static):
    """2D RAM access heatmap showing read and write activity across addresses."""

    mem: reactive[dict[int, int]] = reactive(dict)
    read_counts: reactive[dict[int, int]] = reactive(dict)
    write_counts: reactive[dict[int, int]] = reactive(dict)
    base_addr: reactive[int] = reactive(0x60)

    def render(self) -> Text:
        t = Text()
        end_matrix_addr = min(0xFFFF, self.base_addr + 127)
        t.append(
            f" 2D RAM ACCESS ACTIVITY MATRIX (0x{self.base_addr:04X}..0x{end_matrix_addr:04X})\n",
            style="bold #00D2FF",
        )
        t.append(
            "  Legend: [.] Untouched  [R] Read  [W] Write  [X] Read+Write (Hot)\n\n",
            style="dim #888888",
        )

        t.append("         ", style="")
        for c in range(16):
            t.append(f" {c:X} ", style="dim #00D2FF")
        t.append("\n")

        for row in range(8):
            row_start = self.base_addr + row * 16
            if row_start > 0xFFFF:
                break
            t.append(f"  0x{row_start:04X}: ", style="bold #666666")
            for col in range(16):
                addr = row_start + col
                if addr > 0xFFFF:
                    break
                rc = self.read_counts.get(addr, 0)
                wc = self.write_counts.get(addr, 0)
                val = self.mem.get(addr, 0)

                if rc > 0 and wc > 0:
                    t.append(" X ", style="bold black on #00D2FF")
                elif wc > 0:
                    t.append(" W ", style="bold black on #FFAA00")
                elif rc > 0:
                    t.append(" R ", style="bold black on #00FF87")
                elif val > 0:
                    t.append(" · ", style="bold #555555")
                else:
                    t.append(" . ", style="dim #222222")
            t.append("\n")
        return t


class CacheProgressModalScreen(ModalScreen):
    """Sleek modal dialog displaying a progress bar while precomputing cache checkpoints."""

    CSS = """
    CacheProgressModalScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }
    #cache-dialog {
        width: 76;
        height: auto;
        background: #000000;
        border: solid #00D2FF;
        padding: 1 2;
    }
    #cache-title {
        text-align: center;
        color: #00D2FF;
        text-style: bold;
        margin-bottom: 1;
    }
    #cache-status {
        text-align: center;
        color: #FFFFFF;
        text-style: bold;
        margin-bottom: 1;
    }
    #cache-detail {
        text-align: center;
        color: #888888;
    }
    ProgressBar {
        margin: 1 0;
    }
    ProgressBar > .progress--bar {
        color: #00FF87;
        background: #1a1a1a;
    }
    ProgressBar > .progress--percentage {
        color: #FFAA00;
        text-style: bold;
    }
    """

    def __init__(self, max_steps: int | None = None) -> None:
        super().__init__()
        self.target_steps = max_steps

    def compose(self) -> ComposeResult:
        """Compose modal progress bar widgets."""
        with Vertical(id="cache-dialog"):
            yield Label("PRECOMPUTING CACHE CHECKPOINTS", id="cache-title")
            yield Label("Initializing CPU cache checkpoints...", id="cache-status")
            yield ProgressBar(
                id="cache-bar",
                total=self.target_steps,
                show_eta=bool(self.target_steps),
            )
            yield Label(
                "Sparse CPU state snapshots cached for instant time-travel",
                id="cache-detail",
            )

    def update_progress(self, current: int, total: int | None) -> None:
        try:
            bar = self.query_one("#cache-bar", ProgressBar)
            lbl = self.query_one("#cache-status", Label)
            if total is not None and total > 0:
                bar.total = total
                bar.update(progress=current)
                pct = (current / max(1, total)) * 100
                lbl.update(
                    f"Caching execution: {current:,} / {total:,} steps ({pct:.1f}%)"
                )
            else:
                bar.total = None
                bar.update(progress=current)
                lbl.update(
                    f"Caching execution until infinite loop: {current:,} steps..."
                )
        except Exception:
            pass


class TUIHelpScreen(ModalScreen):
    """Full-screen modal displaying TUI application usage, keyboard shortcuts, and guides."""

    CSS = """
    TUIHelpScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }
    #help-dialog {
        width: 85%;
        height: 85%;
        background: #000000;
        border: solid #00D2FF;
        padding: 1 2;
    }
    #help-title {
        text-align: center;
        color: #00D2FF;
        text-style: bold;
        margin-bottom: 1;
    }
    #help-scroll {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose help screen dialog widgets."""
        with Vertical(id="help-dialog"):
            yield Label("TINY8 TUI APPLICATION USAGE & KEYBOARD GUIDE", id="help-title")
            with VerticalScroll(id="help-scroll"):
                t_text = Text()

                t_text.append(
                    "EXECUTION & TIME-TRAVEL CONTROLS\n", style="bold #00D2FF"
                )
                t_text.append("  n              ", style="bold #FFAA00")
                t_text.append("Step forward 1 instruction (+1 step)\n", style="#FFFFFF")
                t_text.append("  p              ", style="bold #FFAA00")
                t_text.append(
                    "Step backward 1 instruction (-1 step, Time-Travel debug)\n",
                    style="#FFFFFF",
                )
                t_text.append("  Space          ", style="bold #FFAA00")
                t_text.append(
                    "Play / pause automatic continuous execution\n",
                    style="#FFFFFF",
                )
                t_text.append("  c              ", style="bold #FFAA00")
                t_text.append(
                    "Continue forward until next breakpoint or program completion\n",
                    style="#FFFFFF",
                )
                t_text.append("  C (Shift+c)    ", style="bold #FFAA00")
                t_text.append(
                    "Reverse continue backward until previous breakpoint or start\n",
                    style="#FFFFFF",
                )
                t_text.append("  b              ", style="bold #FFAA00")
                t_text.append(
                    "Toggle breakpoint at current PC position\n", style="#FFFFFF"
                )
                t_text.append("  + / -          ", style="bold #FFAA00")
                t_text.append(
                    "Increase / decrease automatic playback execution speed\n",
                    style="#FFFFFF",
                )
                t_text.append("  r              ", style="bold #FFAA00")
                t_text.append(
                    "Reset execution back to Step 0 (start)\n", style="#FFFFFF"
                )
                t_text.append("  q              ", style="bold #FFAA00")
                t_text.append("Quit Tiny8 application\n\n", style="#FFFFFF")

                t_text.append("INSPECTION & HELP MODALS\n", style="bold #00FF87")
                t_text.append("  h  or  ?       ", style="bold #FFAA00")
                t_text.append(
                    "Open this TUI Application Usage & Keyboard Guide\n",
                    style="#FFFFFF",
                )
                t_text.append("  i              ", style="bold #FFAA00")
                t_text.append(
                    "Inspect details of currently selected/executing instruction\n",
                    style="#FFFFFF",
                )
                t_text.append("  j / k          ", style="bold #FFAA00")
                t_text.append(
                    "Scroll memory view down / up (J / K for fast scroll)\n",
                    style="#FFFFFF",
                )
                t_text.append("  g              ", style="bold #FFAA00")
                t_text.append(
                    "Toggle Grayscale / Viridis color palette\n", style="#FFFFFF"
                )
                t_text.append("  x              ", style="bold #FFAA00")
                t_text.append(
                    "Toggle Hexadecimal digits (02X) / Graphic Pixel blocks\n",
                    style="#FFFFFF",
                )
                t_text.append("  m              ", style="bold #FFAA00")
                t_text.append(
                    "Cycle view modes (Viridis+Hex -> Viridis+Pixel -> Grayscale+Pixel -> Grayscale+Hex)\n\n",
                    style="#FFFFFF",
                )

                t_text.append("BUILT-IN VIM MODAL EDITOR\n", style="bold #FFAA00")
                t_text.append("  e              ", style="bold #FFAA00")
                t_text.append(
                    "Launch full-screen Vim-style modal editor anytime\n",
                    style="#FFFFFF",
                )
                t_text.append("  NORMAL Mode    ", style="bold #00D2FF")
                t_text.append(
                    "h/j/k/l movement, w/b word jump, 0/$ line bounds, gg/G top/bottom\n",
                    style="#CCCCCC",
                )
                t_text.append("                 ", style="bold #00D2FF")
                t_text.append(
                    "x delete char, dd delete line, yy copy line, p paste, u undo, Ctrl+r redo\n",
                    style="#CCCCCC",
                )
                t_text.append("  INSERT Mode    ", style="bold #00D2FF")
                t_text.append(
                    "Type 'i' / 'a' / 'o' to edit code, press <Esc> to return to normal mode\n",
                    style="#CCCCCC",
                )
                t_text.append("  COMMAND Mode   ", style="bold #00D2FF")
                t_text.append("Type ':' in normal mode:\n", style="#CCCCCC")
                t_text.append(
                    "                 :w [path]     Save code\n", style="dim #FFFFFF"
                )
                t_text.append(
                    "                 :wq / :x      Save and return to debugger\n",
                    style="dim #FFFFFF",
                )
                t_text.append(
                    "                 :run          Compile / assemble and restart debugging\n",
                    style="dim #FFFFFF",
                )
                t_text.append(
                    "                 :q / :q!      Exit editor\n\n",
                    style="dim #FFFFFF",
                )

                t_text.append("COMMAND BAR (:) SHORTCUTS\n", style="bold #FF007F")
                t_text.append(
                    "  Press ':' anytime from the debugger to enter commands:\n",
                    style="#CCCCCC",
                )
                t_text.append("  :goto <step>       ", style="bold #FFAA00")
                t_text.append("Jump directly to specific step index\n", style="#FFFFFF")
                t_text.append("  :b <pc> [if expr]  ", style="bold #FFAA00")
                t_text.append(
                    "Set breakpoint at PC with optional condition (e.g. :b 0x0010 if R16 > 10)\n",
                    style="#FFFFFF",
                )
                t_text.append("  :watch <target>    ", style="bold #FFAA00")
                t_text.append(
                    "Set watchpoint on register/memory (e.g. :watch R16 or :watch 0x0100)\n",
                    style="#FFFFFF",
                )
                t_text.append("  :set <reg/addr> <val>", style="bold #FFAA00")
                t_text.append(
                    "Dynamically edit register or memory value (e.g. :set R16 42, :set 0x0100 255)\n",
                    style="#FFFFFF",
                )
                t_text.append("  :mem <addr/name>   ", style="bold #FFAA00")
                t_text.append(
                    "Jump memory dump to address 0x0000..0xFFFF or alias (e.g. :mem 0x0600, :mem 0xFFFF, :mem vram, :mem stack)\n",
                    style="#FFFFFF",
                )
                t_text.append("  :exec <asm>        ", style="bold #FFAA00")
                t_text.append(
                    "Dynamically execute an assembly instruction immediately (e.g. :exec LDI R16, 5)\n",
                    style="#FFFFFF",
                )
                t_text.append("  :tab <name>        ", style="bold #FFAA00")
                t_text.append(
                    "Switch active tab (memory, cvars, callstack)\n",
                    style="#FFFFFF",
                )
                t_text.append("  :rc                ", style="bold #FFAA00")
                t_text.append("Run reverse continue\n", style="#FFFFFF")
                t_text.append("  :h / :help / :?    ", style="bold #FFAA00")
                t_text.append("Open this help guide\n", style="#FFFFFF")
                t_text.append("  :i / :info / :instr", style="bold #FFAA00")
                t_text.append(
                    "Open current instruction detail modal\n\n", style="#FFFFFF"
                )

                t_text.append("PANELS & TABS OVERVIEW\n", style="bold #00FF87")
                t_text.append(
                    "  • Code View:       Source code disassembly with current execution pointer and breakpoints\n",
                    style="#CCCCCC",
                )
                t_text.append(
                    "  • Inspector:       Real-time breakdown of current instruction, operands, PC, SP\n",
                    style="#CCCCCC",
                )
                t_text.append(
                    "  • SREG Timeline:   Condition flags timeline history (Carry, Zero, Negative, etc.)\n",
                    style="#CCCCCC",
                )
                t_text.append(
                    "  • Registers:       General-purpose registers R0..R31 with change highlight bars\n",
                    style="#CCCCCC",
                )
                t_text.append(
                    "  • Memory:          32x32 Memory dump covering full 0x0000..0xFFFF RAM (including 0x0200..0x05FF VRAM)\n",
                    style="#CCCCCC",
                )
                t_text.append(
                    "  • C Variables:     Variable symbols table tracking types, memory addresses, values\n",
                    style="#CCCCCC",
                )
                t_text.append(
                    "  • Call Stack:      Reconstructed active function stack frames and return addresses\n",
                    style="#CCCCCC",
                )

                yield Static(t_text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()

    def key_escape(self) -> None:
        self.dismiss()

    def key_enter(self) -> None:
        self.dismiss()

    def key_h(self) -> None:
        self.dismiss()

    def key_question_mark(self) -> None:
        self.dismiss()


class InstructionDetailModalScreen(ModalScreen):
    """Full-screen modal displaying in-depth specifications for the currently selected instruction."""

    CSS = """
    InstructionDetailModalScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }
    #detail-modal-dialog {
        width: 85%;
        height: 85%;
        background: #000000;
        border: solid #00FF87;
        padding: 1 2;
    }
    #detail-modal-title {
        text-align: center;
        color: #00FF87;
        text-style: bold;
        margin-bottom: 1;
    }
    #detail-modal-scroll {
        height: 1fr;
    }
    #detail-close-btn {
        margin-top: 1;
        dock: bottom;
    }
    """

    def __init__(
        self,
        instr: str = "",
        pc: int = 0,
        sp: int = 0,
        source_line: int = -1,
        sreg: int = 0,
    ) -> None:
        super().__init__()
        self.instr = instr
        self.pc = pc
        self.sp = sp
        self.source_line = source_line
        self.sreg = sreg

    def compose(self) -> ComposeResult:
        """Compose instruction detail modal widgets."""
        with Vertical(id="detail-modal-dialog"):
            yield Label(
                "CURRENT INSTRUCTION SPECIFICATION & DETAILS",
                id="detail-modal-title",
            )
            with VerticalScroll(id="detail-modal-scroll"):
                t = Text()

                parts = self.instr.strip().split() if self.instr else []
                mnemonic = parts[0].upper() if parts else ""
                doc = INSTRUCTION_DOCS.get(mnemonic, {})

                t.append(
                    "┌─ SELECTED INSTRUCTION EXECUTION CONTEXT ─────────────────────────────┐\n",
                    style="bold #00D2FF",
                )
                t.append("│ Instruction : ", style="bold #00D2FF")
                t.append(
                    f"{self.instr if self.instr else '(None)':<24} ",
                    style="bold #FFAA00",
                )
                t.append("PC : ", style="bold #00D2FF")
                t.append(f"0x{self.pc:04X}  ", style="bold #00FF87")
                t.append("SP : ", style="bold #00D2FF")
                t.append(f"0x{self.sp:04X} │\n", style="bold #FFAA00")

                line_str = f"Line {self.source_line}" if self.source_line > 0 else "N/A"
                sreg_bits = f"0b{self.sreg:08b} (0x{self.sreg:02X})"
                t.append("│ Source Line : ", style="bold #00D2FF")
                t.append(f"{line_str:<24} ", style="#FFFFFF")
                t.append("SREG: ", style="bold #00D2FF")
                t.append(f"{sreg_bits:<20} │\n", style="dim #00FF87")
                t.append(
                    "└─────────────────────────────────────────────────────────────────────┘\n\n",
                    style="bold #00D2FF",
                )

                if doc:
                    name = doc.get("name", mnemonic)
                    syntax = doc.get("syntax", self.instr)
                    desc = doc.get("desc", "Executes CPU instruction step.")
                    flags = doc.get("flags", "None")

                    t.append("ARCHITECTURAL SPECIFICATION\n", style="bold #00FF87")
                    t.append("  Mnemonic       : ", style="bold #FFAA00")
                    t.append(f"{mnemonic}\n", style="bold #FFFFFF")
                    t.append("  Instruction    : ", style="bold #FFAA00")
                    t.append(f"{name}\n", style="bold #FFFFFF")
                    t.append("  Syntax Pattern : ", style="bold #FFAA00")
                    t.append(f"{syntax}\n", style="bold #00D2FF")
                    t.append("  Operation      : ", style="bold #FFAA00")
                    t.append(f"{desc}\n", style="#CCCCCC")
                    t.append("  Flags Affected : ", style="bold #FFAA00")
                    t.append(
                        f"{flags}\n\n",
                        style="bold #FF5555" if flags != "None" else "dim #888888",
                    )

                    t.append("SREG STATUS REGISTER BREAKDOWN\n", style="bold #FFAA00")
                    flag_names = [
                        (
                            "C",
                            "Carry",
                            0,
                            "Set if arithmetic operation generated a carry out of bit 7",
                        ),
                        ("Z", "Zero", 1, "Set if arithmetic/logic result is zero"),
                        (
                            "N",
                            "Negative",
                            2,
                            "Set if MSB (bit 7) of result is set (signed negative)",
                        ),
                        (
                            "V",
                            "Overflow",
                            3,
                            "Set if two's complement signed overflow occurred",
                        ),
                        (
                            "S",
                            "Sign (N ⊕ V)",
                            4,
                            "Exclusive-OR of Negative and Overflow flags",
                        ),
                        (
                            "H",
                            "Half Carry",
                            5,
                            "Set if carry occurred from bit 3 to bit 4 (BCD arithmetic)",
                        ),
                        (
                            "T",
                            "Bit Copy",
                            6,
                            "Temporary storage bit for BST and BLD instructions",
                        ),
                        (
                            "I",
                            "Interrupt",
                            7,
                            "Global Interrupt Enable bit (SEI / CLI)",
                        ),
                    ]
                    for code, fl_name, bit_idx, fl_desc in flag_names:
                        is_active = bool(self.sreg & (1 << bit_idx))
                        status_str = "[ACTIVE]" if is_active else "[CLEAR]"
                        status_style = "bold #00FF87" if is_active else "dim #555555"
                        is_affected = code in flags
                        t.append(
                            f"  [{code}] {fl_name:<11} {status_str} (Bit {bit_idx}) ",
                            style=status_style,
                        )
                        if is_affected:
                            t.append(
                                "(Affected by this instruction)\n", style="bold #FFAA00"
                            )
                        else:
                            t.append("\n")
                        t.append(f"      {fl_desc}\n", style="dim #AAAAAA")
                    t.append("\n")
                else:
                    t.append(
                        "  (No built-in documentation found for this instruction/label)\n\n",
                        style="dim #888888",
                    )

                t.append(
                    "ALL TINY8 INSTRUCTIONS QUICK REFERENCE\n", style="bold #00D2FF"
                )
                for mn, d in sorted(INSTRUCTION_DOCS.items()):
                    prefix = "▶ " if mn == mnemonic else "  "
                    hl_style = "bold #00FF87" if mn == mnemonic else "bold #FFAA00"
                    t.append(f"{prefix}{mn:<6} ", style=hl_style)
                    t.append(f"[{d['syntax']}]", style="bold #00D2FF")
                    t.append(f" - {d['name']}: {d['desc']}\n", style="#CCCCCC")

                yield Static(t)
            yield Button(
                "Close (Esc / Enter)", id="detail-close-btn", variant="primary"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()

    def key_escape(self) -> None:
        self.dismiss()

    def key_enter(self) -> None:
        self.dismiss()


class InstructionReferenceScreen(ModalScreen):
    """Full-screen reference modal showing all instruction details."""

    CSS = """
    InstructionReferenceScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }
    #modal-dialog {
        width: 80%;
        height: 80%;
        background: #000000;
        border: solid #00D2FF;
        padding: 1 2;
    }
    #modal-title {
        text-align: center;
        color: #00D2FF;
        text-style: bold;
        margin-bottom: 1;
    }
    #modal-scroll {
        height: 1fr;
    }
    #close-btn {
        margin-top: 1;
        dock: bottom;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose instruction reference modal widgets."""
        with Vertical(id="modal-dialog"):
            yield Label("TINY8 INSTRUCTION SET REFERENCE", id="modal-title")
            with VerticalScroll(id="modal-scroll"):
                t = Text()
                for mnemonic, doc in sorted(INSTRUCTION_DOCS.items()):
                    t.append(f"{mnemonic:<6} ", style="bold #FFAA00")
                    t.append(f"[{doc['syntax']}]", style="bold #00FF87")
                    t.append(f" - {doc['name']}\n", style="bold #FFFFFF")
                    t.append(f"       Operation: {doc['desc']}\n", style="#CCCCCC")
                    t.append(
                        f"       Flags:     {doc['flags']}\n\n", style="dim #00D2FF"
                    )
                yield Static(t)
            yield Button("Close (Esc / Enter)", id="close-btn", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()

    def key_escape(self) -> None:
        self.dismiss()

    def key_enter(self) -> None:
        self.dismiss()


DEFAULT_C_TEMPLATE = """int main() {
    int a = 10;
    int b = 20;
    int sum = a + b;
    return sum;
}
"""

DEFAULT_ASM_TEMPLATE = """; Tiny8 Assembly Program
LDI R16, 10
LDI R17, 20
ADD R16, R17
"""


class LazyStatusWidget(Static):
    """Bottom statusline with mode badge, file stats, and help hint."""

    mode: reactive[str] = reactive("NORMAL")
    filename: reactive[str] = reactive("tiny8")
    current_step: reactive[int] = reactive(0)
    total_steps: reactive[int] = reactive(0)
    current_pc: reactive[int] = reactive(0)
    current_sp: reactive[int] = reactive(0)
    current_instr: reactive[str] = reactive("")
    sub_info: reactive[str] = reactive("")
    hint: reactive[str] = reactive("h: help")

    def render(self) -> Text:
        right_hints = self.hint if self.hint else "h: help"
        right_t = Text()
        tokens = right_hints.split("  ")
        for i, token in enumerate(tokens):
            if i > 0:
                right_t.append("  ")
            parts = token.split(" ", 1)
            if len(parts) == 2:
                key_part, label_part = parts
                right_t.append(key_part, style="bold #00D2FF")
                right_t.append(" ")
                right_t.append(label_part, style="#AAAAAA")
            else:
                right_t.append(token, style="dim #888888")

        screen_width = self.size.width if self.size.width > 0 else 120
        right_len = len(right_t.plain)

        status_t = Text()
        if "PLAY" in self.mode or self.mode in ("RUNNING", "INSERT"):
            status_t.append(f" {self.mode} ", style="bold black on #00FF87")
        elif "REV" in self.mode:
            status_t.append(f" {self.mode} ", style="bold black on #00D2FF")
        elif self.mode == "COMMAND":
            status_t.append(f" {self.mode} ", style="bold black on #00D2FF")
        elif self.mode == "BREAKPOINT":
            status_t.append(f" {self.mode} ", style="bold black on #FF0055")
        else:
            status_t.append(f" {self.mode} ", style="bold black on #FABD2F")

        status_t.append(" ")
        status_t.append(f"{self.filename}", style="bold #FFFFFF")

        if self.sub_info:
            status_t.append(" | ", style="dim #555555")
            status_t.append(f"{self.sub_info}", style="#CCCCCC")
        else:
            status_t.append(" | ", style="dim #555555")
            status_t.append(f"Step: {self.current_step}", style="bold #00D2FF")
            status_t.append(" | ", style="dim #555555")
            status_t.append(f"PC: 0x{self.current_pc:04X}", style="bold #00FF87")
            status_t.append(" | ", style="dim #555555")
            status_t.append(f"SP: 0x{self.current_sp:04X}", style="bold #FFAA00")

            if self.current_instr:
                status_t.append(" | ", style="dim #555555")
                status_t.append(f"{self.current_instr}", style="#E6EDF3")

        cur_len = len(status_t.plain)
        pad = max(2, screen_width - cur_len - right_len - 1)
        status_t.append(" " * pad)
        status_t.append_text(right_t)
        return status_t


class VimTextArea(TextArea):
    """TextArea enhanced with Vim modal navigation and editing."""

    mode: reactive[str] = reactive("NORMAL")
    pending_key: str = ""
    yanked_text: str = ""
    is_modified: reactive[bool] = reactive(False)

    def on_key(self, event: events.Key) -> None:
        if self.mode == "INSERT":
            if event.key == "escape":
                self.mode = "NORMAL"
                event.prevent_default()
                event.stop()
                if hasattr(self.screen, "update_editor_status"):
                    self.screen.update_editor_status()
            else:
                self.is_modified = True
                if hasattr(self.screen, "update_editor_status"):
                    self.screen.update_editor_status()
            return

        if self.mode == "NORMAL":
            key = event.character or event.key

            if self.pending_key:
                prefix = self.pending_key
                self.pending_key = ""
                if prefix == "d" and key == "d":
                    self.action_delete_line()
                    self.is_modified = True
                    event.prevent_default()
                    event.stop()
                    if hasattr(self.screen, "update_editor_status"):
                        self.screen.update_editor_status()
                    return
                elif prefix == "y" and key == "y":
                    row, _ = self.cursor_location
                    if row < len(self.document.lines):
                        self.yanked_text = self.document.get_line(row)
                    event.prevent_default()
                    event.stop()
                    return
                elif prefix == "g" and key == "g":
                    self.move_cursor((0, 0))
                    event.prevent_default()
                    event.stop()
                    if hasattr(self.screen, "update_editor_status"):
                        self.screen.update_editor_status()
                    return

            if event.key == "escape":
                self.pending_key = ""
                event.prevent_default()
                event.stop()
                return

            if key in ("h", "left"):
                self.action_cursor_left()
                event.prevent_default()
                event.stop()
            elif key in ("j", "down"):
                self.action_cursor_down()
                event.prevent_default()
                event.stop()
            elif key in ("k", "up"):
                self.action_cursor_up()
                event.prevent_default()
                event.stop()
            elif key in ("l", "right"):
                self.action_cursor_right()
                event.prevent_default()
                event.stop()
            elif key == "w":
                self.action_cursor_word_right()
                event.prevent_default()
                event.stop()
            elif key == "b":
                self.action_cursor_word_left()
                event.prevent_default()
                event.stop()
            elif key == "0":
                self.action_cursor_line_start()
                event.prevent_default()
                event.stop()
            elif key == "$":
                self.action_cursor_line_end()
                event.prevent_default()
                event.stop()
            elif key == "G":
                last_line = max(0, len(self.document.lines) - 1)
                self.move_cursor((last_line, 0))
                event.prevent_default()
                event.stop()
            elif key in ("g", "d", "y"):
                self.pending_key = key
                event.prevent_default()
                event.stop()
            elif key == "i":
                self.mode = "INSERT"
                event.prevent_default()
                event.stop()
            elif key == "a":
                self.action_cursor_right()
                self.mode = "INSERT"
                event.prevent_default()
                event.stop()
            elif key == "I":
                self.action_cursor_line_start()
                self.mode = "INSERT"
                event.prevent_default()
                event.stop()
            elif key == "A":
                self.action_cursor_line_end()
                self.mode = "INSERT"
                event.prevent_default()
                event.stop()
            elif key == "o":
                self.action_cursor_line_end()
                self.insert("\n")
                self.mode = "INSERT"
                self.is_modified = True
                event.prevent_default()
                event.stop()
            elif key == "O":
                self.action_cursor_line_start()
                self.insert("\n")
                self.action_cursor_up()
                self.mode = "INSERT"
                self.is_modified = True
                event.prevent_default()
                event.stop()
            elif key == "x":
                self.action_delete_right()
                self.is_modified = True
                event.prevent_default()
                event.stop()
            elif key == "p":
                if self.yanked_text:
                    self.action_cursor_line_end()
                    self.insert("\n" + self.yanked_text)
                    self.is_modified = True
                event.prevent_default()
                event.stop()
            elif key == "u":
                self.action_undo()
                event.prevent_default()
                event.stop()
            elif event.key == "ctrl+r":
                self.action_redo()
                event.prevent_default()
                event.stop()
            elif key in (":", "colon"):
                if hasattr(self.screen, "action_open_vim_command"):
                    self.screen.action_open_vim_command()
                event.prevent_default()
                event.stop()
            else:
                event.prevent_default()
                event.stop()

            if hasattr(self.screen, "update_editor_status"):
                self.screen.update_editor_status()


class VimEditorScreen(Screen):
    """Full-screen modal Vim editor for creating and modifying C and ASM files."""

    CSS = """
    VimEditorScreen {
        background: #000000;
        color: #E6EDF3;
    }
    #editor-header {
        height: 1;
        dock: top;
        background: #050505;
        border-bottom: solid #222222;
        padding: 0 1;
    }
    #vim-editor {
        height: 1fr;
        background: #000000;
        border: none;
    }
    #vim-status {
        dock: bottom;
        height: 1;
        background: #000000;
        color: #E6EDF3;
        padding: 0;
        margin: 0 1;
    }
    #vim-cmd-bar {
        dock: bottom;
        height: 3;
        background: #000000;
        border-top: solid #00D2FF;
        display: none;
        padding: 0 1;
        margin: 0;
    }
    #vim-cmd-prefix {
        color: #00D2FF;
        text-style: bold;
        width: 2;
        height: 1;
        padding: 0;
        margin: 0;
    }
    #vim-cmd-input {
        background: #000000;
        color: #00FF87;
        border: none;
        height: 1;
        padding: 0;
        margin: 0;
        width: 1fr;
    }
    """

    BINDINGS = [
        Binding("escape", "handle_escape", "Normal Mode / Cancel"),
        Binding("f5", "execute_run", "Run (Compile & Debug)", priority=True),
    ]

    def __init__(self, file_path: str = "main.c", initial_code: str = "") -> None:
        super().__init__()
        self.file_path = file_path
        self.initial_code = initial_code
        self.message = ""

    def compose(self) -> ComposeResult:
        """Compose widgets for the Vim editor screen."""
        with Container(id="editor-header"):
            yield Label(
                "[bold #00D2FF]TINY8 VIM EDITOR[/] | [bold #FFAA00]:w[/] Save  "
                "[bold #00FF87]:run[/] Debug  [bold #00D2FF]:q[/] Quit  [dim]'h'[/] Help"
            )
        yield VimTextArea(
            text=self.initial_code,
            theme="vscode_dark",
            show_line_numbers=True,
            id="vim-editor",
        )
        with Horizontal(id="vim-cmd-bar"):
            yield Label(":", id="vim-cmd-prefix")
            yield Input(placeholder="w, q, wq, run, e <file>", id="vim-cmd-input")
        yield LazyStatusWidget(id="vim-status")

    def on_mount(self) -> None:
        text_area = self.query_one("#vim-editor", VimTextArea)
        text_area.focus()
        self.update_editor_status()

    def update_editor_status(self) -> None:
        try:
            editor = self.query_one("#vim-editor", VimTextArea)
            status = self.query_one("#vim-status", LazyStatusWidget)
            status.mode = editor.mode
            fname = Path(self.file_path).name
            mod_tag = " [+]" if editor.is_modified else ""
            status.filename = f"{fname}{mod_tag}"
            row, col = editor.cursor_location
            total_lines = len(editor.document.lines)
            ftype = "C Source" if fname.endswith(".c") else "Assembly"
            status.sub_info = (
                f"[{ftype}] | Line {row + 1}, Col {col + 1} | {total_lines} lines"
            )
            if self.message:
                status.sub_info = f"{status.sub_info} | {self.message}"
            if editor.mode == "INSERT":
                status.hint = "<Esc> Normal"
            else:
                status.hint = ":run Debug  :w Save  :q Quit  h Help"
        except Exception:
            pass

    def action_open_vim_command(self) -> None:
        self.query_one("#vim-status").styles.display = "none"
        cmd_bar = self.query_one("#vim-cmd-bar")
        cmd_bar.styles.display = "block"
        cmd_input = self.query_one("#vim-cmd-input", Input)
        cmd_input.value = ""
        cmd_input.focus()

    def action_handle_escape(self) -> None:
        cmd_bar = self.query_one("#vim-cmd-bar")
        if cmd_bar.styles.display != "none":
            cmd_bar.styles.display = "none"
            self.query_one("#vim-status").styles.display = "block"
            self.query_one("#vim-editor").focus()
            return
        editor = self.query_one("#vim-editor", VimTextArea)
        if editor.mode == "INSERT":
            editor.mode = "NORMAL"
            self.update_editor_status()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "vim-cmd-input":
            event.stop()
            self.handle_vim_command(event.value.strip())

    def handle_vim_command(self, raw_cmd: str) -> None:
        cmd_bar = self.query_one("#vim-cmd-bar")
        cmd_bar.styles.display = "none"
        self.query_one("#vim-status").styles.display = "block"
        editor = self.query_one("#vim-editor", VimTextArea)
        editor.focus()

        cmd = raw_cmd.lstrip(":")
        if not cmd:
            return

        parts = cmd.split()
        sub = parts[0].lower()

        if sub in ("w", "write"):
            target_file = parts[1] if len(parts) > 1 else self.file_path
            self.save_file(target_file)
        elif sub in ("q", "quit", "q!", "quit!"):
            if editor.is_modified and not (cmd.endswith("!") or sub.endswith("!")):
                self.message = (
                    "[bold #FF0055]No write since last change (add ! to override)[/]"
                )
                self.update_editor_status()
                return
            if len(self.app.screen_stack) > 1:
                self.app.pop_screen()
            else:
                self.app.exit()
        elif sub in ("wq", "x"):
            self.save_file(self.file_path)
            self.action_execute_run()
        elif sub in ("run", "r", "make"):
            self.action_execute_run()
        elif sub in ("e", "edit") and len(parts) > 1:
            self.load_target_file(parts[1])
        elif sub == "new":
            new_name = parts[1] if len(parts) > 1 else "untitled.c"
            self.file_path = new_name
            editor.text = ""
            editor.is_modified = False
            self.message = f"[New File] {new_name}"
            self.update_editor_status()
        elif sub in ("h", "help", "?"):
            self.app.push_screen(TUIHelpScreen())

    def save_file(self, target_path: str) -> bool:
        editor = self.query_one("#vim-editor", VimTextArea)
        try:
            Path(target_path).write_text(editor.text, encoding="utf-8")
            self.file_path = target_path
            editor.is_modified = False
            lines = len(editor.document.lines)
            self.message = f'[bold #00FF87]"{target_path}" {lines}L written[/]'
            self.update_editor_status()
            return True
        except Exception as e:
            self.message = f"[bold #FF0055]Error saving: {e}[/]"
            self.update_editor_status()
            return False

    def load_target_file(self, target_path: str) -> None:
        editor = self.query_one("#vim-editor", VimTextArea)
        p = Path(target_path)
        if p.exists():
            editor.text = p.read_text(encoding="utf-8")
            self.message = f'"{target_path}" loaded'
        else:
            editor.text = ""
            self.message = f'[New File] "{target_path}"'
        self.file_path = target_path
        editor.is_modified = False
        self.update_editor_status()

    def action_execute_run(self) -> None:
        editor = self.query_one("#vim-editor", VimTextArea)
        self.save_file(self.file_path)
        code = editor.text

        try:
            if self.file_path.endswith(".c"):
                asm_src, symbols = compile_c_with_symbols(code)
                asm = assemble(asm_src)
                src_lines = code.splitlines()
                if hasattr(self.app, "var_symbols"):
                    self.app.var_symbols = symbols
            else:
                asm = assemble(code)
                src_lines = code.splitlines()
                if hasattr(self.app, "var_symbols"):
                    self.app.var_symbols = {}

            cpu = CPU()
            cpu.load_program(asm)
            cpu.source_lines = src_lines
            cpu.pc_to_line = asm.pc_to_line
            max_steps = getattr(self.app, "max_steps", None)

            # Precompute checkpoint cache before execution starts
            mgr = CheckpointManager(cpu, interval=100)
            computed = mgr.precompute(max_steps=max_steps)

            init_steps = min(1000, computed)
            mgr.restore_exact_step(0)
            cpu.run(max_steps=init_steps, show_progress=False)

            self.app.cpu = cpu
            self.app.checkpoint_manager = mgr
            self.app.execution_mode = "cache"
            self.app.traces = list(cpu.step_trace)
            self.app.num_traces = len(cpu.step_trace)
            self.app.current_idx = 0
            self.app.file_path = self.file_path
            self.app.title_text = Path(self.file_path).name

            code_w = self.app.query_one("#code-view", CodeViewWidget)
            code_w.program = cpu.program
            code_w.source_lines = cpu.source_lines
            code_w.pc_to_line = cpu.pc_to_line
            self.app.update_views()

            if len(self.app.screen_stack) > 1:
                self.app.pop_screen()
        except Exception as err:
            self.message = f"[bold #FF0055]Build error: {err}[/]"
            self.update_editor_status()


class Tiny8App(App):
    """Textual application with OLED black background and advanced debugger features."""

    TITLE = "Tiny8"

    CSS = """
    Screen {
        background: #000000;
        color: #E6EDF3;
    }
    Header {
        background: #000000;
        color: #00D2FF;
        text-style: bold;
        border-bottom: solid #222222;
    }
    #sreg-view {
        height: auto;
        padding: 0;
        margin: 1 0;
        width: 1fr;
    }
    #main-container {
        layout: horizontal;
        height: 1fr;
        margin: 0 1;
    }
    #left-panel {
        width: 1fr;
        height: 1fr;
        border: solid #222222;
        background: #000000;
        margin-right: 1;
        padding: 1;
        overflow-y: auto;
    }
    #right-panel {
        width: 1fr;
        height: 1fr;
        border: solid #222222;
        background: #000000;
        padding: 1;
        overflow-y: auto;
    }
    #lazy-status {
        dock: bottom;
        height: 1;
        background: #000000;
        color: #E6EDF3;
        padding: 0;
        margin: 0 1;
    }
    #command-bar {
        dock: bottom;
        height: 3;
        background: #000000;
        border-top: solid #00D2FF;
        display: none;
        padding: 0 1;
        margin: 0;
    }
    #cmd-prefix {
        color: #00D2FF;
        text-style: bold;
        width: 2;
        height: 1;
        padding: 0;
        margin: 0;
    }
    #cmd-input {
        background: #000000;
        color: #00FF87;
        border: none;
        height: 1;
        padding: 0;
        margin: 0;
        width: 1fr;
    }
    TabbedContent {
        height: 1fr;
    }
    TabPane {
        padding: 0;
        background: #000000;
    }
    Static {
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_play", "Play Forward"),
        Binding("shift+space", "toggle_reverse_play", "Play Reverse"),
        Binding("backspace", "toggle_reverse_play", "Play Reverse"),
        Binding("n", "step_forward", "Step +1"),
        Binding("p", "step_backward", "Step -1"),
        Binding("c", "continue_run", "Continue (to Breakpoint)"),
        Binding("shift+c", "reverse_continue", "Rev Continue"),
        Binding("C", "reverse_continue", "Rev Continue"),
        Binding("b", "toggle_breakpoint", "Toggle Breakpoint"),
        Binding("j", "scroll_down", "Scroll Down"),
        Binding("k", "scroll_up", "Scroll Up"),
        Binding("shift+j", "scroll_page_down", "Page Down", show=False),
        Binding("J", "scroll_page_down", "Page Down", show=False),
        Binding("shift+k", "scroll_page_up", "Page Up", show=False),
        Binding("K", "scroll_page_up", "Page Up", show=False),
        Binding("pagedown", "scroll_page_down", "Page Down", show=False),
        Binding("pageup", "scroll_page_up", "Page Up", show=False),
        Binding("colon", "open_command", "Command (:)"),
        Binding(":", "open_command", "Command (:)"),
        Binding("shift+semicolon", "open_command", "Command (:)"),
        Binding("e", "open_editor", "Vim Editor"),
        Binding("r", "reset", "Reset"),
        Binding("h", "show_help", "Help"),
        Binding("question_mark", "show_help", "Help"),
        Binding("?", "show_help", "Help"),
        Binding("i", "show_instruction_detail", "Instruction Detail"),
        Binding("escape", "cancel_command", "Cancel Command"),
        Binding("+", "faster", "Speed +"),
        Binding("-", "slower", "Speed -"),
        Binding("g", "toggle_grayscale", "Grayscale/Viridis"),
        Binding("x", "toggle_hex", "Hex/Pixel"),
        Binding("m", "cycle_mode", "Cycle View Mode"),
        Binding("q", "quit", "Quit"),
    ]

    current_idx: reactive[int] = reactive(0)
    playing: reactive[bool] = reactive(False)
    play_direction: reactive[int] = reactive(1)
    playback_rate_idx: reactive[int] = reactive(0)
    speed_ms: reactive[int] = reactive(100)
    batch_size: reactive[int] = reactive(1)
    execution_mode: reactive[str] = reactive("cache")
    breakpoints: reactive[set[int]] = reactive(set)
    mem_start: reactive[int] = reactive(0x60)
    reg_start: reactive[int] = reactive(0)
    color_mode: reactive[str] = reactive("viridis")
    show_hex: reactive[bool] = reactive(True)

    def __init__(
        self,
        cpu: CPU | None = None,
        title_text: str = "Tiny8 Debugger",
        file_path: str = "main.c",
        start_in_editor: bool = False,
        max_steps: int | None = None,
        var_symbols: dict[str, dict[str, Any]] | None = None,
        checkpoint_manager: CheckpointManager | None = None,
        execution_mode: str = "cache",
        precompute_cache: bool = True,
        show_cache_progress: bool = False,
    ) -> None:
        super().__init__()
        self.file_path = file_path
        self.start_in_editor = start_in_editor
        self.max_steps = max_steps
        self.show_cache_progress = show_cache_progress
        self.precompute_cache = precompute_cache
        self.var_symbols: dict[str, dict[str, Any]] = var_symbols or {}
        self.conditional_breakpoints: dict[int, str] = {}
        self.watchpoints: set[str] = set()
        self.bookmarks: dict[str, int] = {}
        self.execution_mode = execution_mode
        if cpu is not None:
            self.cpu = cpu
            self.traces = list(cpu.step_trace)[-1000:]
        else:
            self.cpu = CPU()
            self.traces = []
        self.num_traces = len(self.traces)

        if checkpoint_manager is not None:
            self.checkpoint_manager = checkpoint_manager
        else:
            self.checkpoint_manager = CheckpointManager(self.cpu, interval=100)
            if (
                precompute_cache
                and self.cpu.program
                and not self.start_in_editor
                and not show_cache_progress
            ):
                if self.cpu.step_count == 0:
                    computed = self.checkpoint_manager.precompute(
                        max_steps=self.max_steps
                    )
                    self.checkpoint_manager.restore_exact_step(0)
                    init_steps = min(
                        1000,
                        self.max_steps if self.max_steps is not None else computed,
                    )
                    self.cpu.run(max_steps=init_steps, show_progress=False)
                    self.traces = list(self.cpu.step_trace)
                    self.num_traces = len(self.traces)
                elif self.cpu.step_trace:
                    for tr in self.cpu.step_trace:
                        st = tr.get("step", 0)
                        if st % self.checkpoint_manager.interval == 0:
                            if st not in self.checkpoint_manager.snapshots:
                                self.checkpoint_manager.snapshots[st] = {
                                    "step": st,
                                    "pc": tr.get("pc", 0),
                                    "sp": tr.get("sp", self.cpu.mem.ram_size - 1),
                                    "sreg": tr.get("sreg", 0),
                                    "regs": list(tr.get("regs", [0] * 32)),
                                    "mem": dict(tr.get("mem", {})),
                                    "running": True,
                                }
                                if st not in self.checkpoint_manager.checkpoint_steps:
                                    idx = bisect.bisect_right(
                                        self.checkpoint_manager.checkpoint_steps, st
                                    )
                                    self.checkpoint_manager.checkpoint_steps.insert(
                                        idx, st
                                    )

        self.title_text = Path(file_path).name if file_path else title_text
        self.timer: Any = None
        if self.file_path and any(
            k in self.file_path.lower()
            for k in ("diffusion", "mnist", "heatmap", "vram")
        ):
            self.mem_start = 0x0200

    def on_key(self, event: events.Key) -> None:
        if len(self.screen_stack) > 1:
            return
        cmd_bar = self.query_one("#command-bar")
        if cmd_bar.styles.display != "none":
            return
        if (
            event.key in (":", "colon", "shift+colon", "shift+semicolon")
            or event.character == ":"
        ):
            self.action_open_command()
            event.prevent_default()
            event.stop()
            return

    def compose(self) -> ComposeResult:
        """Compose the root application layout and widgets."""
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            with Vertical(id="left-panel"):
                yield CodeViewWidget(id="code-view")
                yield InstructionDetailWidget(id="detail-view")
                yield SregWidget(id="sreg-view")
                yield BtopRegistersWidget(id="btop-regs-view")
            with Vertical(id="right-panel"):
                with TabbedContent():
                    with TabPane("Memory", id="tab-btop"):
                        yield MemoryWidget(id="mem-view")
                    with TabPane("C Variables", id="tab-cvars"):
                        yield CVariablesWidget(id="cvars-view")
                    with TabPane("Call Stack", id="tab-callstack"):
                        yield CallStackWidget(id="callstack-view")
        with Horizontal(id="command-bar"):
            yield Label(":", id="cmd-prefix")
            yield Input(
                placeholder="goto <step/mark>, b <pc> [if expr], watch <var>, rc, set R0 5, exec <asm>",
                id="cmd-input",
            )
        yield LazyStatusWidget(id="lazy-status")

    def on_mount(self) -> None:
        code_widget = self.query_one("#code-view", CodeViewWidget)
        code_widget.program = self.cpu.program
        code_widget.source_lines = self.cpu.source_lines
        code_widget.pc_to_line = self.cpu.pc_to_line
        self.update_views()
        if self.start_in_editor:
            self.action_open_editor()
        elif (
            self.show_cache_progress
            and self.cpu.program
            and len(self.checkpoint_manager.checkpoint_steps) <= 1
        ):
            self._start_cache_precompute_with_progress()

    def _start_cache_precompute_with_progress(self) -> None:
        """Launch visual progress modal and run cache precomputation in background worker thread."""
        modal = CacheProgressModalScreen(max_steps=self.max_steps)
        self.push_screen(modal)
        self.run_worker(self._worker_precompute_cache, thread=True)

    def _worker_precompute_cache(self) -> None:
        def on_prog(cur: int, tot: int | None) -> None:
            self.call_from_thread(self._on_cache_progress_update, cur, tot)

        computed = self.checkpoint_manager.precompute(
            max_steps=self.max_steps, progress_callback=on_prog
        )
        self.checkpoint_manager.restore_exact_step(0)
        init_steps = min(
            1000, self.max_steps if self.max_steps is not None else computed
        )
        self.cpu.run(max_steps=init_steps, show_progress=False)
        self.traces = list(self.cpu.step_trace)
        self.num_traces = len(self.traces)
        self.current_idx = 0
        self.call_from_thread(self._on_cache_precompute_done, computed)

    def _on_cache_progress_update(self, current: int, total: int | None) -> None:
        if isinstance(self.screen, CacheProgressModalScreen):
            self.screen.update_progress(current, total)

    def _on_cache_precompute_done(self, computed: int) -> None:
        if isinstance(self.screen, CacheProgressModalScreen):
            self.screen.dismiss()
        self.update_views()
        loop_msg = (
            f" ({self.checkpoint_manager.loop_reason})"
            if self.checkpoint_manager.infinite_loop_detected
            else ""
        )
        self.notify(
            f"Cache precomputation completed: {computed:,} steps cached{loop_msg}",
            timeout=3.0,
        )

    def action_open_editor(self) -> None:
        """Open full-screen Vim editor for source code."""
        code = ""
        p = Path(self.file_path)
        if p.exists():
            code = p.read_text(encoding="utf-8")
        elif self.cpu.source_lines:
            code = "\n".join(self.cpu.source_lines)
        else:
            code = (
                DEFAULT_C_TEMPLATE
                if self.file_path.endswith(".c")
                else DEFAULT_ASM_TEMPLATE
            )
        self.push_screen(VimEditorScreen(file_path=self.file_path, initial_code=code))

    def update_views(self) -> None:
        if (
            not getattr(self, "_screen_stack", None)
            or not self.traces
            or not (0 <= self.current_idx < self.num_traces)
        ):
            return

        entry = self.traces[self.current_idx]
        prev = self.traces[self.current_idx - 1] if self.current_idx > 0 else None

        sreg_widget = self.query_one("#sreg-view", SregWidget)
        sreg_widget.sreg = entry.get("sreg", 0)

        btop_regs = self.query_one("#btop-regs-view", BtopRegistersWidget)
        btop_regs.prev_regs = (
            prev.get("regs", entry.get("regs", [0] * 32))
            if prev
            else entry.get("regs", [0] * 32)
        )
        btop_regs.regs = entry.get("regs", [0] * 32)
        btop_regs.start_r = self.reg_start

        try:
            regs_widget = self.query_one("#regs-view", RegistersWidget)
            regs_widget.prev_regs = (
                prev.get("regs", entry.get("regs", [0] * 32))
                if prev
                else entry.get("regs", [0] * 32)
            )
            regs_widget.regs = entry.get("regs", [0] * 32)
        except Exception:
            pass

        mem_widget = self.query_one("#mem-view", MemoryWidget)
        mem_widget.prev_mem = (
            prev.get("mem", entry.get("mem", {})) if prev else entry.get("mem", {})
        )
        mem_widget.mem = entry.get("mem", {})
        mem_widget.start_addr = self.mem_start
        mem_widget.color_mode = getattr(self, "color_mode", "viridis")
        mem_widget.show_hex = getattr(self, "show_hex", True)

        try:
            cvars_widget = self.query_one("#cvars-view", CVariablesWidget)
            cvars_widget.var_symbols = getattr(self, "var_symbols", {})
            cvars_widget.mem = entry.get("mem", {})
            cvars_widget.prev_mem = (
                prev.get("mem", entry.get("mem", {})) if prev else entry.get("mem", {})
            )
        except Exception:
            pass

        try:
            callstack_widget = self.query_one("#callstack-view", CallStackWidget)
            callstack_widget.frames = extract_call_frames(self.traces, self.current_idx)
            callstack_widget.current_pc = entry.get("pc", 0)
        except Exception:
            pass

        try:
            matrix_widget = self.query_one("#matrix-view", MemoryMatrixWidget)
            matrix_widget.mem = entry.get("mem", {})
            matrix_widget.base_addr = self.mem_start
            wc: Counter[int] = Counter()
            rc: Counter[int] = Counter()
            start_i = max(0, self.current_idx - 200)
            for i in range(start_i, self.current_idx + 1):
                cur_e = self.traces[i]
                prv_e = self.traces[i - 1] if i > 0 else None
                c_m = cur_e.get("mem", {})
                p_m = prv_e.get("mem", {}) if prv_e else {}
                for a, v in c_m.items():
                    if p_m.get(a) != v:
                        wc[a] += 1
                instr = cur_e.get("instr", "")
                if instr:
                    op = instr.split()[0].upper()
                    if op in ("LD", "LDS", "LDD", "POP", "RET"):
                        rc[cur_e.get("sp", 0)] += 1
            matrix_widget.write_counts = dict(wc)
            matrix_widget.read_counts = dict(rc)
        except Exception:
            pass

        try:
            stack_w = self.query_one("#stack-view-grid", StackWidget)
            stack_w.sp = entry.get("sp", self.cpu.mem.ram_size - 1)
            stack_w.mem = entry.get("mem", {})
            stack_w.ram_size = self.cpu.mem.ram_size
        except Exception:
            pass

        code_widget = self.query_one("#code-view", CodeViewWidget)
        code_widget.current_pc = entry.get("pc", 0)
        code_widget.breakpoints = set(self.breakpoints)

        detail_widget = self.query_one("#detail-view", InstructionDetailWidget)
        detail_widget.current_instr = entry.get("instr", "")
        detail_widget.pc = entry.get("pc", 0)
        detail_widget.sp = entry.get("sp", 0)
        source_line_idx = entry.get("source_line", -1)
        detail_widget.source_line = source_line_idx
        if 0 <= source_line_idx < len(self.cpu.source_lines) and self.cpu.source_lines:
            detail_widget.source_text = self.cpu.source_lines[source_line_idx].strip()
        else:
            detail_widget.source_text = ""

        # Determine actual execution step number and total count from trace entry or CPU state
        actual_step = (
            entry.get("step", self.cpu.step_count if self.cpu else self.current_idx + 1)
            if entry
            else (self.cpu.step_count if self.cpu else self.current_idx)
        )
        total_steps = max(self.cpu.step_count if self.cpu else 0, self.num_traces)

        try:
            telemetry_widget = self.query_one("#telemetry-view", TelemetryWidget)
            telemetry_widget.total_steps = total_steps
            telemetry_widget.current_step = actual_step
            counts: Counter[str] = Counter()
            for i in range(self.current_idx + 1):
                instr_str = self.traces[i].get("instr", "")
                if instr_str:
                    counts[instr_str.split()[0]] += 1
            telemetry_widget.instr_counts = dict(counts)
        except Exception:
            pass

        try:
            lazy_status = self.query_one("#lazy-status", LazyStatusWidget)
            if self.current_idx in self.breakpoints:
                lazy_status.mode = "BREAKPOINT"
            elif self.playing:
                rate = (
                    PLAYBACK_RATES[self.playback_rate_idx] if self.speed_ms <= 30 else 1
                )
                tag = f"x{rate:,}" if self.speed_ms <= 30 else f"{self.speed_ms}ms"
                if self.play_direction == 1:
                    lazy_status.mode = f"PLAY ▶ {tag}"
                else:
                    lazy_status.mode = f"REV ◀ {tag}"
            else:
                tag = "CACHE" if self.execution_mode == "cache" else "LIVE"
                lazy_status.mode = f"NORMAL ({tag})"
            lazy_status.filename = self.title_text
            lazy_status.current_step = actual_step
            lazy_status.total_steps = total_steps
            lazy_status.current_pc = entry.get("pc", 0)
            lazy_status.current_sp = entry.get("sp", 0)
            lazy_status.current_instr = entry.get("instr", "")
        except Exception:
            pass

    def action_step_forward(self) -> None:
        if self.current_idx < self.num_traces - 1:
            self.current_idx += 1
            self.update_views()
        elif self.cpu and self.cpu.running:
            self.cpu.step()
            self.traces = list(self.cpu.step_trace)
            self.num_traces = len(self.traces)
            self.current_idx = max(0, self.num_traces - 1)
            self.update_views()

    def action_step_backward(self) -> None:
        if self.current_idx > 0:
            self.current_idx -= 1
            self.update_views()

    def action_toggle_breakpoint(self) -> None:
        """Toggle breakpoint on current PC."""
        if not self.traces or not (0 <= self.current_idx < self.num_traces):
            return
        cur_pc = self.traces[self.current_idx].get("pc", 0)
        if cur_pc in self.breakpoints:
            self.breakpoints.remove(cur_pc)
            self.conditional_breakpoints.pop(cur_pc, None)
        else:
            self.breakpoints.add(cur_pc)
        self.update_views()

    def _is_breakpoint_hit(self, step_idx: int) -> bool:
        if not (0 <= step_idx < self.num_traces):
            return False
        entry = self.traces[step_idx]
        pc = entry.get("pc", 0)
        if pc in self.breakpoints:
            cond = self.conditional_breakpoints.get(pc)
            if not cond:
                return True
            regs = entry.get("regs", [0] * 32)
            mem = entry.get("mem", {})
            return eval_condition(cond, regs, mem)
        return False

    def _check_watchpoints_triggered(self, step_idx: int) -> bool:
        if not self.watchpoints or step_idx <= 0 or step_idx >= self.num_traces:
            return False
        cur = self.traces[step_idx]
        prev = self.traces[step_idx - 1]
        regs = cur.get("regs", [0] * 32)
        prev_regs = prev.get("regs", [0] * 32)
        mem = cur.get("mem", {})
        prev_mem = prev.get("mem", {})
        for wp in self.watchpoints:
            m_r = re.match(r"^[rR](\d+)$", wp.strip())
            if m_r:
                ridx = int(m_r.group(1))
                if 0 <= ridx < len(regs) and regs[ridx] != prev_regs[ridx]:
                    return True
                continue
            m_m = re.match(r"^(?:mem\[)?(0x[0-9a-fA-F]+|\d+)\]?$", wp.strip())
            if m_m:
                addr = (
                    int(m_m.group(1), 16)
                    if m_m.group(1).startswith("0x")
                    else int(m_m.group(1))
                )
                if mem.get(addr, 0) != prev_mem.get(addr, 0):
                    return True
                continue
            if eval_condition(wp, regs, mem):
                if not eval_condition(wp, prev_regs, prev_mem):
                    return True
        return False

    def action_continue_run(self) -> None:
        """Run forward until next breakpoint, watchpoint, or program completion."""
        next_step = self.current_idx + 1
        while next_step < self.num_traces:
            if self._is_breakpoint_hit(next_step) or self._check_watchpoints_triggered(
                next_step
            ):
                self.current_idx = next_step
                self.update_views()
                return
            next_step += 1
        self.current_idx = self.num_traces - 1
        self.update_views()

    def action_reverse_continue(self) -> None:
        """Run backward until previous breakpoint, watchpoint, or program start."""
        prev_step = self.current_idx - 1
        while prev_step >= 0:
            if self._is_breakpoint_hit(prev_step) or self._check_watchpoints_triggered(
                prev_step
            ):
                self.current_idx = prev_step
                self.update_views()
                return
            prev_step -= 1
        self.current_idx = 0
        self.update_views()

    def action_exec_instruction(self, instr_str: str) -> None:
        """Execute an assembly instruction dynamically in REPL mode."""
        try:
            asm_res = assemble(instr_str)
            if not asm_res.program:
                return
            cur = self.traces[self.current_idx]
            self.cpu.regs = list(cur.get("regs", [0] * 32))
            self.cpu.sreg = cur.get("sreg", 0)
            self.cpu.sp = cur.get("sp", self.cpu.mem.ram_size - 1)
            for a, v in cur.get("mem", {}).items():
                self.cpu.mem.ram[a] = v
            self.cpu.load_program(asm_res)
            self.cpu.running = True
            self.cpu.step()
            if self.cpu.step_trace:
                self.cpu.step_trace.pop()

            new_entry = {
                "step": self.num_traces + 1,
                "pc": cur.get("pc", 0),
                "instr": f"[REPL] {instr_str}",
                "regs": list(self.cpu.regs),
                "mem": {i: v for i, v in enumerate(self.cpu.mem.ram) if v != 0},
                "sreg": self.cpu.sreg,
                "sp": self.cpu.sp,
                "source_line": -1,
            }
            self.traces.insert(self.current_idx + 1, new_entry)
            self.num_traces = len(self.traces)
            self.current_idx += 1
            self.update_views()
        except Exception:
            pass

    def watch_mem_start(self, new_val: int) -> None:
        """Update only the memory widget when mem_start changes."""
        try:
            mem_widget = self.query_one("#mem-view", MemoryWidget)
            mem_widget.start_addr = new_val
        except Exception:
            pass
        try:
            matrix_widget = self.query_one("#matrix-view", MemoryMatrixWidget)
            matrix_widget.base_addr = new_val
        except Exception:
            pass

    def action_scroll_down(self) -> None:
        """Scroll memory down (1 row = 32 bytes)."""
        self.mem_start = min(0xFFE0, self.mem_start + 32)

    def action_scroll_up(self) -> None:
        """Scroll memory up (1 row = 32 bytes)."""
        self.mem_start = max(0x0000, self.mem_start - 32)

    def action_scroll_page_down(self) -> None:
        """Fast scroll memory down (4 rows = 128 bytes)."""
        self.mem_start = min(0xFFE0, self.mem_start + 128)

    def action_scroll_page_up(self) -> None:
        """Fast scroll memory up (4 rows = 128 bytes)."""
        self.mem_start = max(0x0000, self.mem_start - 128)

    def action_open_command(self) -> None:
        """Open command bar input."""
        cmd_bar = self.query_one("#command-bar")
        cmd_bar.styles.display = "block"
        self.query_one("#lazy-status").styles.display = "none"
        cmd_input = self.query_one("#cmd-input", Input)
        cmd_input.value = ""
        cmd_input.focus()

    def action_cancel_command(self) -> None:
        """Cancel and close command input or dismiss modal dialog."""
        if len(self.screen_stack) > 1:
            self.pop_screen()
            return
        cmd_bar = self.query_one("#command-bar")
        if cmd_bar.styles.display != "none":
            cmd_bar.styles.display = "none"
            self.query_one("#lazy-status").styles.display = "block"
            self.set_focus(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Process entered command."""
        if event.input.id != "cmd-input":
            return
        event.stop()
        cmd_bar = self.query_one("#command-bar")
        cmd_bar.styles.display = "none"
        self.query_one("#lazy-status").styles.display = "block"
        self.set_focus(None)
        raw_cmd = event.value.strip().lstrip(":")

        if not raw_cmd:
            return

        if raw_cmd.startswith("'"):
            mark_name = raw_cmd[1:].strip()
            if mark_name in self.bookmarks:
                self.current_idx = self.bookmarks[mark_name]
                self.update_views()
            return

        parts = raw_cmd.split()
        sub = parts[0].lower()

        if sub.isdigit():
            step_target = int(sub)
            if 0 <= step_target < self.num_traces:
                self.current_idx = step_target
                self.update_views()
            else:
                found = False
                for idx, tr in enumerate(self.traces):
                    if tr.get("step") == step_target:
                        self.current_idx = idx
                        self.update_views()
                        found = True
                        break
                if (
                    not found
                    and self.execution_mode == "cache"
                    and self.checkpoint_manager.checkpoint_steps
                ):
                    if self.checkpoint_manager.restore_exact_step(step_target):
                        self.traces = list(self.cpu.step_trace)
                        self.num_traces = len(self.traces)
                        self.current_idx = max(0, self.num_traces - 1)
                        self.update_views()
        elif sub in ("goto", "step", "s") and len(parts) > 1:
            target = parts[1]
            if target in self.bookmarks:
                self.current_idx = self.bookmarks[target]
                self.update_views()
            elif target.isdigit():
                step_target = int(target)
                if 0 <= step_target < self.num_traces:
                    self.current_idx = step_target
                    self.update_views()
                else:
                    found = False
                    for idx, tr in enumerate(self.traces):
                        if tr.get("step") == step_target:
                            self.current_idx = idx
                            self.update_views()
                            found = True
                            break
                    if (
                        not found
                        and self.execution_mode == "cache"
                        and self.checkpoint_manager.checkpoint_steps
                    ):
                        if self.checkpoint_manager.restore_exact_step(step_target):
                            self.traces = list(self.cpu.step_trace)
                            self.num_traces = len(self.traces)
                            self.current_idx = max(0, self.num_traces - 1)
                            self.update_views()
        elif sub in ("b", "break", "bp"):
            if len(parts) > 1:
                cmd_rest = " ".join(parts[1:])
                if " if " in cmd_rest:
                    pc_part, cond = cmd_rest.split(" if ", 1)
                    try:
                        target_pc = (
                            int(pc_part.strip(), 16)
                            if pc_part.strip().startswith("0x")
                            else int(pc_part.strip())
                        )
                        self.breakpoints.add(target_pc)
                        self.conditional_breakpoints[target_pc] = cond.strip()
                        self.update_views()
                    except ValueError:
                        pass
                else:
                    try:
                        target_pc = (
                            int(parts[1], 16)
                            if parts[1].startswith("0x")
                            else int(parts[1])
                        )
                        if target_pc in self.breakpoints:
                            self.breakpoints.remove(target_pc)
                            self.conditional_breakpoints.pop(target_pc, None)
                        else:
                            self.breakpoints.add(target_pc)
                        self.update_views()
                    except ValueError:
                        pass
            else:
                self.action_toggle_breakpoint()
        elif sub in ("bc", "clear", "unbreak"):
            self.breakpoints.clear()
            self.conditional_breakpoints.clear()
            self.update_views()
        elif sub in ("w", "watch") and len(parts) > 1:
            wp_expr = " ".join(parts[1:]).strip()
            self.watchpoints.add(wp_expr)
        elif sub in ("unwatch", "uw"):
            if len(parts) > 1:
                wp_expr = " ".join(parts[1:]).strip()
                self.watchpoints.discard(wp_expr)
            else:
                self.watchpoints.clear()
        elif sub in ("mark", "bookmark") and len(parts) > 1:
            mark_name = parts[1].strip()
            self.bookmarks[mark_name] = self.current_idx
        elif sub in ("rc", "rev", "reverse"):
            self.action_reverse_continue()
        elif sub in ("set", "poke") and len(parts) > 2:
            reg_match = re.match(r"^[rR](\d+)$", parts[1])
            if reg_match:
                try:
                    ridx = int(reg_match.group(1))
                    val = (
                        int(parts[2], 16)
                        if parts[2].startswith(("0x", "0X"))
                        else int(parts[2])
                    )
                    if 0 <= ridx < 32:
                        cur_step = (
                            self.traces[self.current_idx].get(
                                "step", self.cpu.step_count
                            )
                            if self.traces and 0 <= self.current_idx < self.num_traces
                            else self.cpu.step_count
                        )
                        if self.traces and (0 <= self.current_idx < self.num_traces):
                            self.traces[self.current_idx]["regs"][ridx] = val & 0xFF
                        if ridx < len(self.cpu.regs):
                            self.cpu.regs[ridx] = val & 0xFF
                        self.checkpoint_manager.invalidate_after(cur_step)
                        self.notify(
                            f"R{ridx} set to {val}. Checkpoint cache invalidated after step {cur_step}.",
                            timeout=1.5,
                        )
                        self.update_views()
                except ValueError:
                    pass
            else:
                try:
                    addr = (
                        int(parts[1], 16)
                        if parts[1].startswith(("0x", "0X"))
                        else int(parts[1])
                    )
                    val = (
                        int(parts[2], 16)
                        if parts[2].startswith(("0x", "0X"))
                        else int(parts[2])
                    )
                    if 0 <= addr < self.cpu.mem.ram_size:
                        cur_step = (
                            self.traces[self.current_idx].get(
                                "step", self.cpu.step_count
                            )
                            if self.traces and 0 <= self.current_idx < self.num_traces
                            else self.cpu.step_count
                        )
                        if self.traces and (0 <= self.current_idx < self.num_traces):
                            self.traces[self.current_idx]["mem"][addr] = val & 0xFF
                        self.cpu.mem.ram[addr] = val & 0xFF
                        self.cpu.mem.nonzero_ram[addr] = val & 0xFF
                        self.checkpoint_manager.invalidate_after(cur_step)
                        self.notify(
                            f"Memory 0x{addr:04X} set to {val}. Checkpoint cache invalidated after step {cur_step}.",
                            timeout=1.5,
                        )
                        self.update_views()
                except ValueError:
                    pass
        elif sub == "exec" and len(parts) > 1:
            instr_str = " ".join(parts[1:])
            self.action_exec_instruction(instr_str)
        elif sub in ("c", "cont", "continue", "run"):
            self.action_continue_run()
        elif sub in ("m", "mem", "memory") and len(parts) > 1:
            target = parts[1].lower()
            addr = None
            if target in ("regs", "reg", "r"):
                addr = 0x0000
            elif target in ("io", "ports"):
                addr = 0x0020
            elif target in ("sram", "ram"):
                addr = 0x0060
            elif target in ("vram", "video", "heatmap"):
                addr = 0x0200
            elif target in ("ext", "extended", "data", "heap"):
                addr = 0x0600
            elif target in ("sp", "stack", "top"):
                addr = self.cpu.sp
            else:
                try:
                    if target.startswith(("0x", "0X")):
                        addr = int(target, 16)
                    else:
                        try:
                            addr = int(target)
                        except ValueError:
                            addr = int(target, 16)
                except ValueError:
                    addr = None

            if addr is not None:
                self.mem_start = max(0, min(0xFFE0, addr & ~0x1F))
                self.update_views()
        elif sub in ("find", "search", "/") and len(parts) > 1:
            term = parts[1].lower()
            for i in range(self.current_idx + 1, self.num_traces):
                instr = self.traces[i].get("instr", "").lower()
                if term in instr:
                    self.current_idx = i
                    self.update_views()
                    break
        elif sub in ("play", "forward"):
            self.action_toggle_play()
        elif sub in ("revplay", "reverse_play", "rev"):
            self.action_toggle_reverse_play()
        elif sub in ("mode", "toggle") and len(parts) > 1:
            m = parts[1].lower()
            if m in ("cache", "cached"):
                self.execution_mode = "cache"
                self.notify("Execution Mode: CACHE (Checkpoints enabled)", timeout=1.5)
            elif m in ("live", "direct", "realtime"):
                self.execution_mode = "live"
                self.notify("Execution Mode: LIVE (Direct step)", timeout=1.5)
            else:
                self.action_cycle_mode()
            self.update_views()
        elif sub in ("cache",):
            self.execution_mode = "cache"
            self.notify("Execution Mode: CACHE", timeout=1.5)
            self.update_views()
        elif sub in ("live",):
            self.execution_mode = "live"
            self.notify("Execution Mode: LIVE", timeout=1.5)
            self.update_views()
        elif sub in ("precompute", "pcomp"):
            limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            msg = (
                f"Precomputing cache up to {limit:,} steps..."
                if limit
                else "Precomputing cache until infinite loop..."
            )
            self.notify(msg, timeout=1.5)
            done = self.checkpoint_manager.precompute(max_steps=limit)
            self.traces = list(self.cpu.step_trace)
            self.num_traces = len(self.traces)
            self.current_idx = max(0, self.num_traces - 1)
            reason = (
                f" ({self.checkpoint_manager.loop_reason})"
                if self.checkpoint_manager.infinite_loop_detected
                else ""
            )
            self.notify(
                f"Precomputed {done:,} steps{reason}. Total checkpoints: {len(self.checkpoint_manager.checkpoint_steps)}",
                timeout=2.5,
            )
            self.update_views()
        elif sub in ("gray", "grayscale", "grey"):
            self.action_toggle_grayscale()
        elif sub in ("viridis", "color", "colour"):
            self.color_mode = "viridis"
            self.update_views()
        elif sub in ("hex", "hexadecimal"):
            self.show_hex = True
            self.update_views()
        elif sub in ("pixel", "block", "graphic", "img", "image"):
            self.show_hex = False
            self.update_views()
        elif sub in ("mode", "toggle"):
            self.action_cycle_mode()
        elif sub in ("speed", "spd") and len(parts) > 1:
            if parts[1].isdigit():
                self.speed_ms = max(1, min(1000, int(parts[1])))
                if self.playing and self.timer:
                    self.timer.stop()
                    self.timer = self.set_interval(
                        self.speed_ms / 1000.0, self._auto_step
                    )
                self.notify(
                    f"Speed set to {self.speed_ms}ms (batch: {self.batch_size})",
                    timeout=1.5,
                )
        elif sub in ("batch", "bth") and len(parts) > 1:
            if parts[1].isdigit():
                self.batch_size = max(1, min(200000, int(parts[1])))
                self.notify(
                    f"Batch size set to {self.batch_size} (speed: {self.speed_ms}ms)",
                    timeout=1.5,
                )
        elif sub in ("turbo", "fast", "max"):
            self.speed_ms = 30
            self.playback_rate_idx = len(PLAYBACK_RATES) - 1
            self.batch_size = PLAYBACK_RATES[self.playback_rate_idx]
            self.notify(
                f"TURBO mode enabled: {self.batch_size:,} steps/tick (~33 fps)",
                timeout=1.5,
            )
            self.update_views()
        elif sub in ("normal", "std", "default"):
            self.speed_ms = 100
            self.playback_rate_idx = 0
            self.batch_size = 1
            self.notify(
                "Standard speed enabled: 100ms interval (1 step/tick)", timeout=1.5
            )
            self.update_views()
        elif sub in ("e", "edit", "vim"):
            if len(parts) > 1:
                self.file_path = parts[1]
            self.action_open_editor()
        elif sub in ("r", "reset"):
            self.action_reset()
        elif sub in ("h", "help", "?"):
            self.action_show_help()
        elif sub in ("i", "info", "instr", "detail"):
            self.action_show_instruction_detail()
        elif sub in ("ref", "reference"):
            self.action_show_reference()
        elif sub in ("q", "quit", "exit"):
            self.exit()

    def action_reset(self) -> None:
        self.current_idx = 0
        self.playing = False
        if self.timer:
            self.timer.stop()
        self.update_views()

    def action_toggle_grayscale(self) -> None:
        """Toggle between Viridis and Grayscale color palette."""
        self.color_mode = "grayscale" if self.color_mode == "viridis" else "viridis"
        self.update_views()

    def action_toggle_hex(self) -> None:
        """Toggle between Hexadecimal digits (02X) and Graphic Pixel blocks."""
        self.show_hex = not self.show_hex
        self.update_views()

    def action_cycle_mode(self) -> None:
        """Cycle view modes (Viridis+Hex -> Viridis+Pixel -> Grayscale+Pixel -> Grayscale+Hex)."""
        if self.color_mode == "viridis" and self.show_hex:
            self.show_hex = False
        elif self.color_mode == "viridis" and not self.show_hex:
            self.color_mode = "grayscale"
        elif self.color_mode == "grayscale" and not self.show_hex:
            self.show_hex = True
        else:
            self.color_mode = "viridis"
            self.show_hex = True
        self.update_views()

    def action_show_help(self) -> None:
        """Show full TUI application usage and keyboard guide."""
        self.push_screen(TUIHelpScreen())

    def action_show_instruction_detail(self) -> None:
        """Show in-depth specification and effects for the currently selected instruction."""
        instr_str = ""
        pc = 0
        sp = 0
        source_line = -1
        sreg = 0
        if self.traces and 0 <= self.current_idx < self.num_traces:
            entry = self.traces[self.current_idx]
            instr_str = entry.get("instr", "")
            pc = entry.get("pc", 0)
            sp = entry.get("sp", 0)
            source_line = entry.get("source_line", -1)
            sreg = entry.get("sreg", 0)
        elif self.cpu:
            pc = self.cpu.pc
            sp = self.cpu.sp
            sreg = self.cpu.sreg
            source_line = self.cpu.pc_to_line.get(pc, -1)
            if 0 <= pc < len(self.cpu.program):
                instr, ops = self.cpu.program[pc]
                ops_str = ", ".join(
                    f"R{o[1]}"
                    if isinstance(o, tuple) and len(o) == 2 and o[0] == "reg"
                    else str(o)
                    for o in ops
                )
                instr_str = f"{instr} {ops_str}".strip()

        self.push_screen(
            InstructionDetailModalScreen(
                instr=instr_str, pc=pc, sp=sp, source_line=source_line, sreg=sreg
            )
        )

    def action_show_reference(self) -> None:
        """Show full instruction set reference modal."""
        self.push_screen(InstructionReferenceScreen())

    def action_toggle_play(self) -> None:
        """Toggle forward automatic playback."""
        if self.playing and self.play_direction == 1:
            self.playing = False
            if self.timer:
                self.timer.stop()
        else:
            self.play_direction = 1
            self.playing = True
            if self.timer:
                self.timer.stop()
            interval = max(0.025, self.speed_ms / 1000.0)
            self.timer = self.set_interval(interval, self._auto_step)
        self.update_views()

    def action_toggle_reverse_play(self) -> None:
        """Toggle reverse automatic playback (time-travel replay)."""
        if self.playing and self.play_direction == -1:
            self.playing = False
            if self.timer:
                self.timer.stop()
        else:
            self.play_direction = -1
            self.playing = True
            if self.timer:
                self.timer.stop()
            interval = max(0.025, self.speed_ms / 1000.0)
            self.timer = self.set_interval(interval, self._auto_step)
        self.update_views()

    def _auto_step(self) -> None:
        if not self.cpu:
            self.playing = False
            if self.timer:
                self.timer.stop()
            return

        batch = (
            PLAYBACK_RATES[self.playback_rate_idx]
            if self.speed_ms <= 30
            else self.batch_size
        )
        cur_step = (
            self.traces[self.current_idx].get("step", self.cpu.step_count)
            if (self.traces and 0 <= self.current_idx < len(self.traces))
            else self.cpu.step_count
        )

        if self.play_direction == 1:
            # Forward playback in Cache mode using precomputed checkpoints
            if (
                self.execution_mode == "cache"
                and self.checkpoint_manager.checkpoint_steps
            ):
                target_step = cur_step + batch
                self.checkpoint_manager.restore_exact_step(target_step)
                self.traces = list(self.cpu.step_trace)
                self.num_traces = len(self.traces)
                self.current_idx = max(0, self.num_traces - 1)
                if (
                    not self.cpu.running
                    or self.checkpoint_manager.infinite_loop_detected
                    or self._is_breakpoint_hit(self.current_idx)
                    or self._check_watchpoints_triggered(self.current_idx)
                ):
                    self.playing = False
                    if self.timer:
                        self.timer.stop()
                    if self.checkpoint_manager.infinite_loop_detected:
                        self.notify(
                            f"Auto-stopped: {self.checkpoint_manager.loop_reason}",
                            timeout=3.0,
                        )
                self.update_views()
                return

            if self.current_idx < self.num_traces - 1:
                adv = min(batch, self.num_traces - 1 - self.current_idx)
                self.current_idx += adv
                if self._is_breakpoint_hit(
                    self.current_idx
                ) or self._check_watchpoints_triggered(self.current_idx):
                    self.playing = False
                    if self.timer:
                        self.timer.stop()
                self.update_views()
            elif self.cpu.running:
                # Live mode or computing beyond cached checkpoints
                old_trace = self.cpu.trace_enabled
                is_large_batch = batch > 20
                if is_large_batch:
                    self.cpu.trace_enabled = False
                try:
                    for i in range(batch):
                        if not self.cpu.running:
                            break
                        if (
                            self.execution_mode == "cache"
                            and i % 16 == 0
                            and self.checkpoint_manager.detect_loop()
                        ):
                            self.cpu.running = False
                            self.notify(
                                f"Auto-stopped: {self.checkpoint_manager.loop_reason}",
                                timeout=3.0,
                            )
                            break
                        record_this = not is_large_batch or (i == batch - 1)
                        if not self.cpu.step(record_trace=record_this):
                            break
                        if self.execution_mode == "cache":
                            self.checkpoint_manager.record_if_interval(
                                self.cpu.step_count
                            )
                        if self.cpu.pc in self.breakpoints:
                            break
                finally:
                    self.cpu.trace_enabled = old_trace

                self.traces = list(self.cpu.step_trace)
                self.num_traces = len(self.traces)
                self.current_idx = max(0, self.num_traces - 1)
                if (
                    not self.cpu.running
                    or self._is_breakpoint_hit(self.current_idx)
                    or self._check_watchpoints_triggered(self.current_idx)
                ):
                    self.playing = False
                    if self.timer:
                        self.timer.stop()
                self.update_views()
            else:
                self.playing = False
                if self.timer:
                    self.timer.stop()
        else:
            # Reverse playback (Time-Travel replay)
            target_step = max(0, cur_step - batch)
            if target_step == cur_step or cur_step == 0:
                self.playing = False
                if self.timer:
                    self.timer.stop()
                self.notify("Reached start of execution (Step 0)", timeout=1.5)
                return

            if (
                self.execution_mode == "cache"
                and self.checkpoint_manager.checkpoint_steps
            ):
                self.checkpoint_manager.restore_exact_step(target_step)
                self.traces = list(self.cpu.step_trace)
                self.num_traces = len(self.traces)
                self.current_idx = max(0, self.num_traces - 1)
            else:
                if self.current_idx > 0:
                    self.current_idx = max(0, self.current_idx - batch)
                else:
                    self.playing = False
                    if self.timer:
                        self.timer.stop()
            if target_step == 0:
                self.playing = False
                if self.timer:
                    self.timer.stop()
            self.update_views()

    def action_faster(self) -> None:
        """Increase playback execution speed.

        Decreases timer interval down to visual limit (30ms / ~33 fps), then automatically
        transitions to adaptive batch processing scaling up to 50,000 steps per tick.
        """
        if self.speed_ms > 30:
            self.speed_ms = max(30, self.speed_ms - 20)
            msg = f"Visual Speed: {self.speed_ms}ms"
        else:
            if self.playback_rate_idx < len(PLAYBACK_RATES) - 1:
                self.playback_rate_idx += 1
            rate = PLAYBACK_RATES[self.playback_rate_idx]
            self.batch_size = rate
            msg = f"Adaptive Batch: {rate:,} steps/tick (~33 fps)"

        if self.playing and self.timer:
            self.timer.stop()
            interval = max(0.025, self.speed_ms / 1000.0)
            self.timer = self.set_interval(interval, self._auto_step)

        self.notify(msg, timeout=1.2)
        self.update_views()

    def action_slower(self) -> None:
        """Decrease playback execution speed.

        Scales down batch processing first, then transitions back to observable visual delay.
        """
        if self.playback_rate_idx > 0:
            self.playback_rate_idx -= 1
            rate = PLAYBACK_RATES[self.playback_rate_idx]
            self.batch_size = rate
            msg = f"Adaptive Batch: {rate:,} steps/tick (~33 fps)"
        else:
            self.speed_ms = min(500, self.speed_ms + 20)
            msg = f"Visual Speed: {self.speed_ms}ms"

        if self.playing and self.timer:
            self.timer.stop()
            interval = max(0.025, self.speed_ms / 1000.0)
            self.timer = self.set_interval(interval, self._auto_step)

        self.notify(msg, timeout=1.2)
        self.update_views()


def run_cli(
    cpu: CPU,
    mem_addr_start: int = 0x60,
    mem_addr_end: int = 0xDF,
    delay: float = 0.1,
    source_lines: list[str] | None = None,
    var_symbols: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Launch modern Textual TUI debugger with OLED black theme and gradient heatmaps.

    Args:
        cpu: CPU emulator with execution history.
        mem_addr_start: Start address for memory viewer.
        mem_addr_end: End address for memory viewer.
        delay: Playback interval in seconds.
        source_lines: Source assembly or C lines.
        var_symbols: C variable metadata symbols.
    """
    if not cpu.step_trace:
        raise RuntimeError("cpu.step_trace is empty")
    app = Tiny8App(cpu=cpu, var_symbols=var_symbols)
    app.run()


def main() -> None:
    """Entry point for tiny8 CLI supporting Assembly and C sources."""
    from tiny8 import __version__

    parser = argparse.ArgumentParser(
        prog="tiny8",
        description="Tiny8 modern CPU simulator, C compiler, Vim editor, and Textual debugger",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="assembly file (.asm) or C source file (.c) to run or edit (default: main.c in editor)",
    )
    parser.add_argument(
        "--edit",
        "-e",
        action="store_true",
        help="launch directly into Vim editor mode",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="maximum CPU execution steps (default: until infinite loop or halt)",
    )
    parser.add_argument(
        "--compile-only",
        "-c",
        action="store_true",
        help="compile C code and print generated Tiny8 assembly without running",
    )

    args = parser.parse_args()

    if args.file is None:
        app = Tiny8App(
            file_path="main.c", start_in_editor=True, max_steps=args.max_steps
        )
        app.run()
        return

    target_path = Path(args.file)
    if args.compile_only:
        if args.file.endswith(".c"):
            print(compile_c_file(args.file))
        else:
            print(target_path.read_text(encoding="utf-8"))
        return

    if not target_path.exists() or args.edit:
        app = Tiny8App(
            file_path=args.file, start_in_editor=True, max_steps=args.max_steps
        )
        app.run()
        return

    if args.file.endswith(".c"):
        asm_code, symbols = compile_c_file_with_symbols(args.file)
        asm = assemble(asm_code)
        src_lines = target_path.read_text(encoding="utf-8").splitlines()
    else:
        asm = assemble_file(args.file)
        src_lines = target_path.read_text(encoding="utf-8").splitlines()
        symbols = {}

    max_steps = args.max_steps

    cpu = CPU()
    cpu.load_program(asm)
    cpu.source_lines = src_lines
    cpu.pc_to_line = asm.pc_to_line

    checkpoint_mgr = CheckpointManager(cpu, interval=100)

    app = Tiny8App(
        cpu=cpu,
        file_path=args.file,
        max_steps=max_steps,
        var_symbols=symbols,
        checkpoint_manager=checkpoint_mgr,
        execution_mode="cache",
        precompute_cache=True,
        show_cache_progress=True,
    )
    app.current_idx = 0
    app.run()


if __name__ == "__main__":
    main()
