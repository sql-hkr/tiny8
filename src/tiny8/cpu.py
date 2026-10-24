"""Simplified AVR-like 8-bit CPU simulator."""

from collections import deque
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .assembler import AsmResult

from .memory import Memory
from .utils import ProgressBar

SREG_I = 7
SREG_T = 6
SREG_H = 5
SREG_S = 4
SREG_V = 3
SREG_N = 2
SREG_Z = 1
SREG_C = 0


def _make_invoker(handler, decoded_ops: tuple):
    """Create a specialized zero-overhead callable for instruction execution."""
    if handler is None:
        return None
    n = len(decoded_ops)
    if n == 2:
        a, b = decoded_ops[0], decoded_ops[1]

        def inv2() -> None:
            handler(a, b)

        return inv2
    if n == 1:
        a = decoded_ops[0]

        def inv1() -> None:
            handler(a)

        return inv1
    if n == 0:
        return handler

    def inv_n() -> None:
        handler(*decoded_ops)

    return inv_n


class CPU:
    """Lightweight 8-bit AVR CPU emulator compliant with Microchip DS40002198A.

    Args:
        memory: Optional Memory instance. Defaults to a new Memory instance.

    Attributes:
        mem: Attached Memory instance.
        regs: List of 32 8-bit general purpose registers (R0..R31).
        pc: Current program counter address.
        sp: Stack pointer pointing to current top of stack in RAM.
        sreg: Status register integer containing I, T, H, S, V, N, Z, C flags.
        step_count: Number of instructions executed so far.
        interrupts: Mapping of interrupt vector addresses to enabled flags.
        reg_trace: Change history of registers as (step, reg_idx, new_val) tuples.
        mem_trace: Change history of RAM as (step, addr, new_val) tuples.
        step_trace: Full per-step snapshots for tracing and visualization.
        program: List of instruction tuples in (mnemonic, operands) format.
        labels: Mapping of symbolic labels to program counter addresses.
        pc_to_line: Mapping of program counter to source line numbers.
        source_lines: Original assembly source text lines.
        running: Flag indicating whether execution loop is active.
    """

    __slots__ = (
        "mem",
        "max_trace_steps",
        "max_trace_history",
        "trace_enabled",
        "regs",
        "pc",
        "sp",
        "sreg",
        "step_count",
        "interrupts",
        "reg_trace",
        "mem_trace",
        "step_trace",
        "program",
        "labels",
        "pc_to_line",
        "source_lines",
        "running",
        "_predecoded",
    )

    def __init__(
        self,
        memory: Memory | None = None,
        max_trace_steps: int = 1000,
        max_trace_history: int = 2000,
        trace_enabled: bool = True,
    ) -> None:
        self.mem = memory or Memory()
        self.max_trace_steps = max_trace_steps
        self.max_trace_history = max_trace_history
        self.trace_enabled = trace_enabled
        self.regs: list[int] = [0] * 32
        self.pc: int = 0
        self.sp: int = self.mem.ram_size - 1
        self.sreg: int = 0
        self.step_count: int = 0
        self.interrupts: dict[int, bool] = {}
        self.reg_trace: deque[tuple[int, int, int]] = deque(maxlen=max_trace_history)
        self.mem_trace: deque[tuple[int, int, int]] = deque(maxlen=max_trace_history)
        self.step_trace: deque[dict] = deque(maxlen=max_trace_steps)
        self.program: list[tuple[str, tuple]] = []
        self.labels: dict[str, int] = {}
        self.pc_to_line: dict[int, int] = {}
        self.source_lines: list[str] = []
        self.running: bool = False
        self._predecoded: list[tuple] = []

    def clear_traces(self) -> None:
        """Clear execution traces and history to free memory."""
        self.step_trace.clear()
        self.reg_trace.clear()
        self.mem_trace.clear()
        self.mem.clear_changes()

    def snapshot(self) -> dict[str, Any]:
        """Capture complete CPU and memory execution state snapshot."""
        return {
            "step": self.step_count,
            "pc": self.pc,
            "sp": self.sp,
            "sreg": self.sreg,
            "regs": list(self.regs),
            "mem": dict(self.mem.nonzero_ram),
            "running": self.running,
        }

    def restore_snapshot(self, snap: dict[str, Any]) -> None:
        """Restore CPU and memory execution state from a snapshot."""
        self.step_count = snap["step"]
        self.pc = snap["pc"]
        self.sp = snap["sp"]
        self.sreg = snap["sreg"]
        self.regs = list(snap["regs"])
        self.running = snap.get("running", True)
        self.mem.restore_ram(snap["mem"])

    def set_flag(self, bit: int, value: bool) -> None:
        """Set or clear a status register flag bit.

        Args:
            bit: SREG bit index (0..7).
            value: True to set flag, False to clear.
        """
        if value:
            self.sreg |= 1 << bit
        else:
            self.sreg &= ~(1 << bit)

    def get_flag(self, bit: int) -> bool:
        """Return boolean status of a specific SREG bit.

        Args:
            bit: SREG bit index (0..7).

        Returns:
            True if bit is set, False otherwise.
        """
        return bool((self.sreg >> bit) & 1)

    def _set_flags_add(self, a: int, b: int, carry_in: int, result: int) -> None:
        """Set SREG flags for addition operations (ADD, ADC).

        Args:
            a: First operand (0..255).
            b: Second operand (0..255).
            carry_in: Carry-in bit (0 or 1).
            result: Sum result before 8-bit truncation.
        """
        r = result & 0xFF
        c = (result >> 8) & 1
        h = (((a & 0x0F) + (b & 0x0F) + carry_in) >> 4) & 1
        n = (r >> 7) & 1
        v = 1 if ((~(a ^ b) & (a ^ r)) & 0x80) else 0
        s = n ^ v
        z = 1 if r == 0 else 0
        self.sreg = (
            (self.sreg & 0xC0)
            | (h << 5)
            | (s << 4)
            | (v << 3)
            | (n << 2)
            | (z << 1)
            | c
        )

    def _set_flags_sub(self, a: int, b: int, borrow_in: int, result: int) -> None:
        """Set SREG flags for subtraction operations (SUB, SBC, CP, CPI).

        Args:
            a: Minuend (0..255).
            b: Subtrahend (0..255).
            borrow_in: Borrow-in bit (0 or 1).
            result: Difference result before 8-bit truncation.
        """
        r = result & 0xFF
        c = 1 if (a - b - borrow_in) < 0 else 0
        h = 1 if ((a & 0x0F) - (b & 0x0F) - borrow_in) < 0 else 0
        n = (r >> 7) & 1
        v = 1 if (((a ^ b) & (a ^ r)) & 0x80) else 0
        s = n ^ v
        z = 1 if r == 0 else 0
        self.sreg = (
            (self.sreg & 0xC0)
            | (h << 5)
            | (s << 4)
            | (v << 3)
            | (n << 2)
            | (z << 1)
            | c
        )

    def _set_flags_logical(self, result: int) -> None:
        """Set SREG flags for logical operations (AND, OR, EOR).

        Status Register (SREG) per AVR Instruction Set Manual DS40002198A:
            S: N ⊕ V (For signed tests)
            V: 0 (Cleared)
            N: R7 (Set if MSB of result is set; cleared otherwise)
            Z: Set if result is $00; cleared otherwise
            H, C, T, I: Unaffected (-)

        Args:
            result: Operation result.
        """
        r = result & 0xFF
        n = (r >> 7) & 1
        z = 1 if r == 0 else 0
        self.sreg = (self.sreg & 0xE1) | (n << 4) | (n << 2) | (z << 1)

    def _set_flags_inc(self, old: int, new: int) -> None:
        """Set SREG flags for increment operation (INC).

        Args:
            old: Register value before increment.
            new: Register value after increment.
        """
        n = (new >> 7) & 1
        v = 1 if old == 0x7F else 0
        s = n ^ v
        z = 1 if new == 0 else 0
        self.sreg = (self.sreg & 0xE1) | (s << 4) | (v << 3) | (n << 2) | (z << 1)

    def _set_flags_add16(self, a: int, b: int, carry_in: int, result: int) -> None:
        """Set SREG flags for 16-bit addition (ADIW).

        Args:
            a: First operand (0..0xFFFF).
            b: Second operand (0..0xFFFF).
            carry_in: Carry input (0 or 1).
            result: Full integer sum.
        """
        r = result & 0xFFFF
        c = (result >> 16) & 1
        n = (r >> 15) & 1
        v = 1 if (((~(a ^ b) & 0xFFFF) & (a ^ r) & 0x8000) != 0) else 0
        s = n ^ v
        z = 1 if r == 0 else 0
        self.sreg = (self.sreg & 0xE0) | (s << 4) | (v << 3) | (n << 2) | (z << 1) | c

    def _set_flags_sub16(self, a: int, b: int, borrow_in: int, result: int) -> None:
        """Set SREG flags for 16-bit subtraction (SBIW).

        Args:
            a: Minuend (0..0xFFFF).
            b: Subtrahend (0..0xFFFF).
            borrow_in: Borrow input (0 or 1).
            result: Integer difference.
        """
        r = result & 0xFFFF
        c = 1 if (a - b - borrow_in) < 0 else 0
        n = (r >> 15) & 1
        v = 1 if (((a ^ b) & (a ^ r)) & 0x8000) != 0 else 0
        s = n ^ v
        z = 1 if r == 0 else 0
        self.sreg = (self.sreg & 0xE0) | (s << 4) | (v << 3) | (n << 2) | (z << 1) | c

    def _set_flags_dec(self, old: int, new: int) -> None:
        """Set SREG flags for decrement operation (DEC).

        Args:
            old: Register value before decrement.
            new: Register value after decrement.
        """
        n = (new >> 7) & 1
        v = 1 if old == 0x80 else 0
        s = n ^ v
        z = 1 if new == 0 else 0
        self.sreg = (self.sreg & 0xE1) | (s << 4) | (v << 3) | (n << 2) | (z << 1)

    def read_reg(self, r: int) -> int:
        """Return 8-bit value from register r.

        Args:
            r: Register index (0..31).

        Returns:
            8-bit unsigned integer value.
        """
        return self.regs[r]

    def write_reg(self, r: int, val: int) -> None:
        """Write 8-bit value to register r and trace changes.

        Args:
            r: Register index (0..31).
            val: Integer value to store (masked to 8-bit).
        """
        newv = val & 0xFF
        if self.trace_enabled:
            if self.regs[r] != newv:
                self.regs[r] = newv
                self.reg_trace.append((self.step_count, r, newv))
        else:
            self.regs[r] = newv

    def read_ram(self, addr: int) -> int:
        """Read byte from RAM address.

        Args:
            addr: Memory address.

        Returns:
            Byte value stored at address.
        """
        return self.mem.read_ram(addr)

    def write_ram(self, addr: int, val: int) -> None:
        """Write byte to RAM address and record memory trace.

        Args:
            addr: Target RAM address.
            val: Byte value to write.
        """
        self.mem.write_ram(addr, val, self.step_count)
        if self.trace_enabled:
            self.mem_trace.append((self.step_count, addr, val & 0xFF))

    def load_program(
        self,
        program: "list[tuple[str, tuple]] | AsmResult",
        labels: dict[str, int] | None = None,
        pc_to_line: dict[int, int] | None = None,
        source_lines: list[str] | None = None,
    ) -> None:
        """Load assembled program instructions into CPU.

        Args:
            program: AsmResult object or list of (mnemonic, operands) tuples.
            labels: Label mapping if program is a raw list.
            pc_to_line: PC to line mapping if program is a raw list.
            source_lines: Source text lines if program is a raw list.
        """
        if hasattr(program, "program") and hasattr(program, "labels"):
            self.program = program.program
            self.labels = program.labels
            self.pc_to_line = program.pc_to_line
            self.source_lines = program.source_lines
        else:
            self.program = program
            self.labels = labels or {}
            self.pc_to_line = pc_to_line or {}
            self.source_lines = source_lines or []
        self.pc = 0
        self._build_predecoded()

    def _build_predecoded(self) -> None:
        """Pre-decode program instructions for maximum execution throughput."""
        self._predecoded = []
        for instr, operands in self.program:
            handler = getattr(self, f"op_{instr.lower()}", None)
            decoded_ops = []
            for o in operands:
                if isinstance(o, tuple) and len(o) == 2 and o[0] == "reg":
                    decoded_ops.append(int(o[1]))
                else:
                    decoded_ops.append(o)

            def fmt_op(o) -> str:
                if isinstance(o, tuple) and len(o) == 2 and o[0] == "reg":
                    return f"R{o[1]}"
                return str(o)

            try:
                ops_text = ", ".join(fmt_op(o) for o in operands)
            except Exception:
                ops_text = ""
            instr_text = f"{instr.upper()} {ops_text}".strip()

            ops_tuple = tuple(decoded_ops)
            invoker = _make_invoker(handler, ops_tuple)
            self._predecoded.append((handler, ops_tuple, instr_text, invoker))

    def step(self, record_trace: bool | None = None) -> bool:
        """Execute next single instruction at current program counter.

        Args:
            record_trace: Optional override to enable or disable trace recording for this step.

        Returns:
            True if instruction executed successfully, False if PC is out of range.

        Raises:
            NotImplementedError: If instruction mnemonic has no handler.
        """
        if not (0 <= self.pc < len(self.program)):
            self.running = False
            return False

        pre_exec_pc = self.pc
        if not self._predecoded or len(self._predecoded) != len(self.program):
            self._build_predecoded()

        handler, decoded_ops, instr_text, invoker = self._predecoded[pre_exec_pc]
        if invoker is None:
            instr, _ = self.program[pre_exec_pc]
            raise NotImplementedError(f"Instruction {instr} not implemented")

        should_trace = self.trace_enabled if record_trace is None else record_trace

        if should_trace:
            regs_snapshot = list(self.regs)
            mem_snapshot = dict(self.mem.nonzero_ram)

        invoker()

        self.step_count += 1
        if should_trace:
            source_line = self.pc_to_line.get(pre_exec_pc, -1)
            self.step_trace.append(
                {
                    "step": self.step_count,
                    "pc": pre_exec_pc,
                    "instr": instr_text,
                    "regs": regs_snapshot,
                    "mem": mem_snapshot,
                    "sreg": self.sreg,
                    "sp": self.sp,
                    "source_line": source_line,
                }
            )
        self.pc += 1
        return True

    def run(self, max_steps: int = 100000, show_progress: bool = True) -> None:
        """Run instructions until completion or max_steps limit is reached.

        Args:
            max_steps: Maximum instruction step executions allowed.
            show_progress: Whether to show progress bar in terminal.
        """
        self.running = True

        if not show_progress and not self.trace_enabled:
            # Fast-path execution for batch and headless runs
            if not self._predecoded or len(self._predecoded) != len(self.program):
                self._build_predecoded()
            predec = self._predecoded
            prog_len = len(predec)
            steps = 0
            while self.running and steps < max_steps:
                curr_pc = self.pc
                if not (0 <= curr_pc < prog_len):
                    self.running = False
                    break
                item = predec[curr_pc]
                invoker = item[3]
                if invoker is None:
                    instr, _ = self.program[curr_pc]
                    raise NotImplementedError(f"Instruction {instr} not implemented")
                invoker()
                self.step_count += 1
                self.pc += 1
                steps += 1
            return

        steps = 0
        pb = (
            ProgressBar(total=max_steps, desc="CPU execution")
            if show_progress
            else None
        )

        try:
            while self.running and steps < max_steps:
                if not self.step():
                    break
                steps += 1
                if pb:
                    pb.update(1)
        finally:
            if pb:
                pb.close()

    def op_nop(self) -> None:
        """No Operation (NOP).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: No operation.
            Status Register (SREG): None.
        """

    def op_ldi(self, reg_idx: int, imm: int) -> None:
        """Load Immediate (LDI).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd <- K (16 <= d <= 31, 0 <= K <= 255)
            Status Register (SREG): None.

        Args:
            reg_idx: Destination register index (16..31).
            imm: Immediate byte value.
        """
        self.write_reg(reg_idx, imm)

    def op_mov(self, rd: int, rr: int) -> None:
        """Copy Register (MOV).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd <- Rr (0 <= d, r <= 31)
            Status Register (SREG): None.

        Args:
            rd: Destination register index.
            rr: Source register index.
        """
        self.write_reg(rd, self.read_reg(rr))

    def op_add(self, rd: int, rr: int) -> None:
        """Add without Carry (ADD).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd <- Rd + Rr
            Status Register (SREG): H, S, V, N, Z, C

        Args:
            rd: Destination register index.
            rr: Source register index.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        res = a + b
        self.write_reg(rd, res & 0xFF)
        self._set_flags_add(a, b, 0, res)

    def op_and(self, rd: int, rr: int) -> None:
        """Logical AND (AND).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd <- Rd • Rr
            Status Register (SREG): S, V=0, N, Z (H, C unaffected)

        Args:
            rd: Destination register index.
            rr: Source register index.
        """
        res = self.read_reg(rd) & self.read_reg(rr)
        self.write_reg(rd, res)
        self._set_flags_logical(res)

    def op_or(self, rd: int, rr: int) -> None:
        """Logical OR (OR).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd <- Rd v Rr
            Status Register (SREG): S, V=0, N, Z (H, C unaffected)

        Args:
            rd: Destination register index.
            rr: Source register index.
        """
        res = self.read_reg(rd) | self.read_reg(rr)
        self.write_reg(rd, res)
        self._set_flags_logical(res)

    def op_eor(self, rd: int, rr: int) -> None:
        """Exclusive OR (EOR).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd <- Rd ⊕ Rr
            Status Register (SREG): S, V=0, N, Z (H, C unaffected)

        Args:
            rd: Destination register index.
            rr: Source register index.
        """
        res = self.read_reg(rd) ^ self.read_reg(rr)
        self.write_reg(rd, res)
        self._set_flags_logical(res)

    def op_sub(self, rd: int, rr: int) -> None:
        """Subtract without Carry (SUB).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd <- Rd - Rr
            Status Register (SREG): H, S, V, N, Z, C

        Args:
            rd: Destination register index.
            rr: Source register index.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        res_full = a - b
        self.write_reg(rd, res_full & 0xFF)
        self._set_flags_sub(a, b, 0, res_full)

    def op_inc(self, rd: int) -> None:
        """Increment (INC).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd <- Rd + 1
            Status Register (SREG): S, V, N, Z (C unaffected)

        Args:
            rd: Destination register index.
        """
        old = self.read_reg(rd)
        new = (old + 1) & 0xFF
        self.write_reg(rd, new)
        self._set_flags_inc(old, new)

    def op_dec(self, rd: int) -> None:
        """Decrement (DEC).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd <- Rd - 1
            Status Register (SREG): S, V, N, Z (C unaffected)

        Args:
            rd: Destination register index.
        """
        old = self.read_reg(rd)
        new = (old - 1) & 0xFF
        self.write_reg(rd, new)
        self._set_flags_dec(old, new)

    def op_mul(self, rd: int, rr: int) -> None:
        """Multiply Unsigned (MUL).

        AVR Instruction Set Manual DS40002198A:
        R1:R0 <- Rd * Rr (unsigned).
        SREG C: Set if bit 15 of result is set; cleared otherwise.
        SREG Z: Set if result is $0000; cleared otherwise.

        Args:
            rd: Multiplicand register index (0..31).
            rr: Multiplier register index (0..31).
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        prod = a * b
        self.write_reg(0, prod & 0xFF)
        self.write_reg(1, (prod >> 8) & 0xFF)
        self.set_flag(SREG_Z, (prod & 0xFFFF) == 0)
        self.set_flag(SREG_C, bool((prod >> 15) & 1))

    def op_muls(self, rd: int, rr: int) -> None:
        """Multiply Signed (MULS).

        AVR Instruction Set Manual DS40002198A:
        R1:R0 <- Rd * Rr (signed).
        SREG C: Set if bit 15 of result is set; cleared otherwise.
        SREG Z: Set if result is $0000; cleared otherwise.

        Args:
            rd: Multiplicand signed register index (0..31).
            rr: Multiplier signed register index (0..31).
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        sa = a - 256 if a >= 128 else a
        sb = b - 256 if b >= 128 else b
        prod = sa * sb
        prod_u16 = prod & 0xFFFF
        self.write_reg(0, prod_u16 & 0xFF)
        self.write_reg(1, (prod_u16 >> 8) & 0xFF)
        self.set_flag(SREG_Z, prod_u16 == 0)
        self.set_flag(SREG_C, bool((prod_u16 >> 15) & 1))

    def op_mulsu(self, rd: int, rr: int) -> None:
        """Multiply Signed with Unsigned (MULSU).

        AVR Instruction Set Manual DS40002198A:
        R1:R0 <- Rd * Rr (Rd signed, Rr unsigned).
        SREG C: Set if bit 15 of result is set; cleared otherwise.
        SREG Z: Set if result is $0000; cleared otherwise.

        Args:
            rd: Multiplicand signed register index (0..31).
            rr: Multiplier unsigned register index (0..31).
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        sa = a - 256 if a >= 128 else a
        prod = sa * b
        prod_u16 = prod & 0xFFFF
        self.write_reg(0, prod_u16 & 0xFF)
        self.write_reg(1, (prod_u16 >> 8) & 0xFF)
        self.set_flag(SREG_Z, prod_u16 == 0)
        self.set_flag(SREG_C, bool((prod_u16 >> 15) & 1))

    def op_adc(self, rd: int, rr: int) -> None:
        """Add with Carry (ADC).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd <- Rd + Rr + C
            Status Register (SREG): H, S, V, N, Z, C

        Args:
            rd: Destination register index.
            rr: Source register index.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        carry_in = int(self.get_flag(SREG_C))
        res = a + b + carry_in
        self.write_reg(rd, res & 0xFF)
        self._set_flags_add(a, b, carry_in, res)

    def op_clr(self, rd: int) -> None:
        """Clear Register: Rd <- Rd ⊕ Rd = $00 (EOR Rd, Rd).

        Status Register (SREG) per AVR Manual DS40002198A:
            S: 0, V: 0, N: 0, Z: 1; H, C, T, I unaffected.
            Alternative name to the EOR Rd, Rd instruction.

        Args:
            rd: Destination register index.
        """
        self.op_eor(rd, rd)

    def op_ser(self, rd: int) -> None:
        """Set Register: Rd <- $FF (LDI Rd, $FF).

        Status Register (SREG) per AVR Manual DS40002198A:
            None affected. Alternative name to the LDI Rd, $FF instruction.

        Args:
            rd: Destination register index.
        """
        self.write_reg(rd, 0xFF)

    def op_in(self, rd: int, port: int) -> None:
        """Load an I/O Location to Register (IN).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd <- P
            Status Register (SREG): None.

        Args:
            rd: Destination register index.
            port: Port/memory address to read from.
        """
        self.write_reg(rd, self.read_ram(port))

    def op_out(self, port: int, rr: int) -> None:
        """Store Register to an I/O Location (OUT).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: P <- Rr
            Status Register (SREG): None.

        Args:
            port: Port/memory address to write to.
            rr: Source register index.
        """
        self.write_ram(port, self.read_reg(rr))

    def op_jmp(self, label: str | int) -> None:
        """Jump (JMP).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: PC <- k
            Status Register (SREG): None.

        Args:
            label: Target label name or instruction address.

        Raises:
            KeyError: If target label string is not found.
        """
        if isinstance(label, int):
            self.pc = label - 1
        else:
            target = self.labels.get(label)
            if target is not None:
                self.pc = target - 1
            else:
                try:
                    self.pc = int(label) - 1
                except (ValueError, TypeError):
                    raise KeyError(f"Label {label} not found")

    def op_cpi(self, rd: int, imm: int) -> None:
        """Compare with Immediate (CPI).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd - K (16 <= d <= 31, 0 <= K <= 255)
            Status Register (SREG): H, S, V, N, Z, C

        Args:
            rd: Register index to compare (16..31).
            imm: Immediate byte value.
        """
        a = self.read_reg(rd)
        b = imm & 0xFF
        self._set_flags_sub(a, b, 0, a - b)

    def op_cp(self, rd: int, rr: int) -> None:
        """Compare (CP).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd - Rr
            Status Register (SREG): H, S, V, N, Z, C

        Args:
            rd: First register index.
            rr: Second register index.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        self._set_flags_sub(a, b, 0, a - b)

    def op_lsl(self, rd: int) -> None:
        """Logical Shift Left: C <- Rd7, Rd(n+1) <- Rd(n), Rd0 <- 0.

        Status Register (SREG) per AVR Manual DS40002198A:
            H: Rd3, S: N ⊕ V, V: N ⊕ C, N: R7, Z: Set if result is $00, C: Rd7
            Alternative name to the ADD Rd, Rd instruction.

        Args:
            rd: Destination register index.
        """
        self.op_add(rd, rd)

    def op_lsr(self, rd: int) -> None:
        """Logical Shift Right: 0 -> Rd7 -> ... -> Rd0 -> C.

        Status Register (SREG) per AVR Manual DS40002198A:
            S: N ⊕ V, V: C, N: 0, Z: Set if result is $00, C: Rd0
            H, T, I unaffected (-).

        Args:
            rd: Destination register index.
        """
        v = self.read_reg(rd)
        carry = v & 1
        nv = (v >> 1) & 0xFF
        self.write_reg(rd, nv)
        c = carry
        vflag = c
        s = c
        z = 1 if nv == 0 else 0
        self.sreg = (self.sreg & 0xE0) | (s << 4) | (vflag << 3) | (z << 1) | c

    def op_asr(self, rd: int) -> None:
        """Arithmetic Shift Right: Rd7 -> Rd7 -> ... -> Rd0 -> C.

        Status Register (SREG) per AVR Manual DS40002198A:
            S: N ⊕ V, V: N ⊕ C, N: R7, Z: Set if result is $00, C: Rd0
            H, T, I unaffected (-).

        Args:
            rd: Destination register index.
        """
        v = self.read_reg(rd)
        carry = v & 1
        sign = v & 0x80
        nv = (v >> 1) | sign
        self.write_reg(rd, nv)
        n = (nv >> 7) & 1
        c = carry
        vflag = n ^ c
        s = n ^ vflag
        z = 1 if nv == 0 else 0
        self.sreg = (
            (self.sreg & 0xE0) | (s << 4) | (vflag << 3) | (n << 2) | (z << 1) | c
        )

    def op_rol(self, rd: int) -> None:
        """Rotate Left Through Carry: C <- Rd7, Rd(n+1) <- Rd(n), Rd0 <- C.

        Status Register (SREG) per AVR Manual DS40002198A:
            H: Rd3, S: N ⊕ V, V: N ⊕ C, N: R7, Z: Set if result is $00, C: Rd7
            Alternative name to the ADC Rd, Rd instruction.

        Args:
            rd: Destination register index.
        """
        self.op_adc(rd, rd)

    def op_ror(self, rd: int) -> None:
        """Rotate Right Through Carry: Rd7 <- C, Rd(n) <- Rd(n+1), C <- Rd0.

        Status Register (SREG) per AVR Manual DS40002198A:
            S: N ⊕ V, V: N ⊕ C, N: R7, Z: Set if result is $00, C: Rd0
            H, T, I unaffected (-).

        Args:
            rd: Destination register index.
        """
        v = self.read_reg(rd)
        carry_in = int(self.get_flag(SREG_C))
        carry_out = v & 1
        nv = (v >> 1) | (carry_in << 7)
        self.write_reg(rd, nv)
        n = (nv >> 7) & 1
        c = carry_out
        vflag = n ^ c
        s = n ^ vflag
        z = 1 if nv == 0 else 0
        self.sreg = (
            (self.sreg & 0xE0) | (s << 4) | (vflag << 3) | (n << 2) | (z << 1) | c
        )

    def op_com(self, rd: int) -> None:
        """One's Complement: Rd <- $FF - Rd.

        Status Register (SREG) per AVR Manual DS40002198A:
            S: N ⊕ V, V: 0, N: R7, Z: Set if result is $00, C: 1
            H, T, I unaffected (-).

        Args:
            rd: Destination register index.
        """
        v = self.read_reg(rd)
        nv = (~v) & 0xFF
        self.write_reg(rd, nv)
        n = (nv >> 7) & 1
        z = 1 if nv == 0 else 0
        self.sreg = (self.sreg & 0xE0) | (n << 4) | (n << 2) | (z << 1) | 1

    def op_neg(self, rd: int) -> None:
        """Two's Complement: Rd <- $00 - Rd.

        Status Register (SREG) per AVR Manual DS40002198A:
            H: R3 + ~Rd3, S: N ⊕ V, V: Rd == $80, N: R7, Z: Set if result is $00, C: Rd != $00

        Args:
            rd: Destination register index.
        """
        a = self.read_reg(rd)
        res_full = 0 - a
        self.write_reg(rd, res_full & 0xFF)
        self._set_flags_sub(0, a, 0, res_full)

    def op_swap(self, rd: int) -> None:
        """Swap Nibbles: Rd(7..4) <-> Rd(3..0).

        Status Register (SREG) per AVR Manual DS40002198A:
            None affected.

        Args:
            rd: Destination register index.
        """
        v = self.read_reg(rd)
        self.write_reg(rd, ((v & 0x0F) << 4) | ((v >> 4) & 0x0F))

    def op_tst(self, rd: int) -> None:
        """Test for Zero or Minus: Rd & Rd.

        Status Register (SREG) per AVR Manual DS40002198A:
            S: N ⊕ V, V: 0, N: R7, Z: Set if Rd is $00
            Alternative name to the AND Rd, Rd instruction.

        Args:
            rd: Register index to test.
        """
        self.op_and(rd, rd)

    def op_andi(self, rd: int, imm: int) -> None:
        """Logical AND with Immediate (ANDI).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd <- Rd • K (16 <= d <= 31, 0 <= K <= 255)
            Status Register (SREG): S, V=0, N, Z (H, C unaffected)

        Args:
            rd: Destination register index (16..31).
            imm: Immediate value.
        """
        res = self.read_reg(rd) & (imm & 0xFF)
        self.write_reg(rd, res)
        self._set_flags_logical(res)

    def op_ori(self, rd: int, imm: int) -> None:
        """Logical OR with Immediate (ORI).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd <- Rd v K (16 <= d <= 31, 0 <= K <= 255)
            Status Register (SREG): S, V=0, N, Z (H, C unaffected)

        Args:
            rd: Destination register index (16..31).
            imm: Immediate value.
        """
        res = self.read_reg(rd) | (imm & 0xFF)
        self.write_reg(rd, res)
        self._set_flags_logical(res)

    def op_subi(self, rd: int, imm: int) -> None:
        """Subtract Immediate (SUBI).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd <- Rd - K (16 <= d <= 31, 0 <= K <= 255)
            Status Register (SREG): H, S, V, N, Z, C

        Args:
            rd: Destination register index (16..31).
            imm: Immediate value.
        """
        a = self.read_reg(rd)
        b = imm & 0xFF
        res_full = a - b
        self.write_reg(rd, res_full & 0xFF)
        self._set_flags_sub(a, b, 0, res_full)

    def op_sbc(self, rd: int, rr: int) -> None:
        """Subtract with Carry (SBC).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd <- Rd - Rr - C
            Status Register (SREG): H, S, V, N, Z, C

        Args:
            rd: Destination register index.
            rr: Source register index.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        borrow_in = int(self.get_flag(SREG_C))
        res_full = a - b - borrow_in
        self.write_reg(rd, res_full & 0xFF)
        self._set_flags_sub(a, b, borrow_in, res_full)

    def op_sbci(self, rd: int, imm: int) -> None:
        """Subtract Immediate with Carry (SBCI).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd <- Rd - K - C (16 <= d <= 31, 0 <= K <= 255)
            Status Register (SREG): H, S, V, N, Z, C

        Args:
            rd: Destination register index (16..31).
            imm: Immediate value.
        """
        a = self.read_reg(rd)
        b = imm & 0xFF
        borrow_in = int(self.get_flag(SREG_C))
        res_full = a - b - borrow_in
        self.write_reg(rd, res_full & 0xFF)
        self._set_flags_sub(a, b, borrow_in, res_full)

    def op_sei(self) -> None:
        """Set Global Interrupt Flag (SEI).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: I <- 1
            Status Register (SREG): I
        """
        self.set_flag(SREG_I, True)

    def op_cli(self) -> None:
        """Clear Global Interrupt Flag (CLI).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: I <- 0
            Status Register (SREG): I
        """
        self.set_flag(SREG_I, False)

    def op_cpse(self, rd: int, rr: int) -> None:
        """Compare Skip if Equal (CPSE).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: If Rd = Rr then PC <- PC + 2 (or 3)
            Status Register (SREG): None (all flags unaffected)

        Args:
            rd: First register index.
            rr: Second register index.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        if a == b:
            self.pc += 1

    def op_sbrs(self, rd: int, bit: int) -> None:
        """Skip if Bit in Register is Set (SBRS).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: If Rd(b) = 1 then PC <- PC + 2 (or 3)
            Status Register (SREG): None.

        Args:
            rd: Register index.
            bit: Bit index (0..7).
        """
        if ((self.read_reg(rd) >> (bit & 7)) & 1) == 1:
            self.pc += 1

    def op_sbrc(self, rd: int, bit: int) -> None:
        """Skip if Bit in Register is Cleared (SBRC).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: If Rd(b) = 0 then PC <- PC + 2 (or 3)
            Status Register (SREG): None.

        Args:
            rd: Register index.
            bit: Bit index (0..7).
        """
        if ((self.read_reg(rd) >> (bit & 7)) & 1) == 0:
            self.pc += 1

    def op_sbis(self, io_addr: int, bit: int) -> None:
        """Skip if Bit in I/O Register is Set (SBIS).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: If P(b) = 1 then PC <- PC + 2 (or 3)
            Status Register (SREG): None.

        Args:
            io_addr: I/O or RAM address.
            bit: Bit index (0..7).
        """
        if ((self.read_ram(io_addr) >> (bit & 7)) & 1) == 1:
            self.pc += 1

    def op_sbic(self, io_addr: int, bit: int) -> None:
        """Skip if Bit in I/O Register is Cleared (SBIC).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: If P(b) = 0 then PC <- PC + 2 (or 3)
            Status Register (SREG): None.

        Args:
            io_addr: I/O or RAM address.
            bit: Bit index (0..7).
        """
        if ((self.read_ram(io_addr) >> (bit & 7)) & 1) == 0:
            self.pc += 1

    def op_sbiw(self, rd_word_low: int, imm_word: int) -> None:
        """Subtract Immediate from Word (SBIW).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd+1:Rd <- Rd+1:Rd - K (d in {24, 26, 28, 30}, 0 <= K <= 63)
            Status Register (SREG): S, V, N, Z, C

        Args:
            rd_word_low: Low register index of register pair (e.g. 24, 26, 28, 30).
            imm_word: Immediate value to subtract.
        """
        lo = self.read_reg(rd_word_low)
        hi = self.read_reg(rd_word_low + 1) if (rd_word_low + 1) < 32 else 0
        word = (hi << 8) | lo
        new = (word - (imm_word & 0xFFFF)) & 0xFFFF
        self.write_reg(rd_word_low, new & 0xFF)
        if rd_word_low + 1 < 32:
            self.write_reg(rd_word_low + 1, (new >> 8) & 0xFF)
        self._set_flags_sub16(word, imm_word & 0xFFFF, 0, word - (imm_word & 0xFFFF))

    def op_adiw(self, rd_word_low: int, imm_word: int) -> None:
        """Add Immediate to Word (ADIW).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd+1:Rd <- Rd+1:Rd + K (d in {24, 26, 28, 30}, 0 <= K <= 63)
            Status Register (SREG): S, V, N, Z, C

        Args:
            rd_word_low: Low register index of register pair (e.g. 24, 26, 28, 30).
            imm_word: Immediate value to add.
        """
        lo = self.read_reg(rd_word_low)
        hi = self.read_reg(rd_word_low + 1) if (rd_word_low + 1) < 32 else 0
        word = (hi << 8) | lo
        new = (word + (imm_word & 0xFFFF)) & 0xFFFF
        self.write_reg(rd_word_low, new & 0xFF)
        if rd_word_low + 1 < 32:
            self.write_reg(rd_word_low + 1, (new >> 8) & 0xFF)
        self._set_flags_add16(word, imm_word & 0xFFFF, 0, word + (imm_word & 0xFFFF))

    def op_rjmp(self, label: str | int) -> None:
        """Relative Jump (RJMP).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: PC <- PC + k + 1
            Status Register (SREG): None.

        Args:
            label: Jump target offset or symbolic label.
        """
        if isinstance(label, int):
            self.pc += label
        else:
            self.op_jmp(label)

    def op_rcall(self, label: str | int) -> None:
        """Relative Call to Subroutine (RCALL).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: PC <- PC + k + 1, STACK <- PC + 1
            Status Register (SREG): None.

        Args:
            label: Call target offset or symbolic label.
        """
        ret = self.pc + 1
        self.write_ram(self.sp, (ret >> 8) & 0xFF)
        self.sp -= 1
        self.write_ram(self.sp, ret & 0xFF)
        self.sp -= 1
        if isinstance(label, int):
            self.pc = self.pc + label - 1
        else:
            self.op_jmp(label)

    def op_sbi(self, io_addr: int, bit: int) -> None:
        """Set Bit in I/O Register (SBI).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: I/O(P, b) <- 1
            Status Register (SREG): None.

        Args:
            io_addr: Memory address.
            bit: Bit index (0..7).
        """
        self.write_ram(io_addr, self.read_ram(io_addr) | (1 << (bit & 7)))

    def op_cbi(self, io_addr: int, bit: int) -> None:
        """Clear Bit in I/O Register (CBI).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: I/O(P, b) <- 0
            Status Register (SREG): None.

        Args:
            io_addr: Memory address.
            bit: Bit index (0..7).
        """
        self.write_ram(io_addr, self.read_ram(io_addr) & ~(1 << (bit & 7)))

    def op_ld(self, rd: int, addr_reg: int) -> None:
        """Load Indirect from Data Space to Register (LD).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd <- (X / Y / Z)
            Status Register (SREG): None.

        Supports 16-bit pointer pairs (X=R27:R26, Y=R29:R28, Z=R31:R30) when high byte is set.

        Args:
            rd: Destination register index.
            addr_reg: Pointer register index.
        """
        high = self.read_reg(addr_reg + 1) if addr_reg in (26, 28, 30) else 0
        low = self.read_reg(addr_reg)
        addr = (high << 8) | low if high > 0 else low
        self.write_reg(rd, self.read_ram(addr))

    def op_st(self, addr_reg: int, rr: int) -> None:
        """Store Indirect from Register to Data Space (ST).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: (X / Y / Z) <- Rr
            Status Register (SREG): None.

        Supports 16-bit pointer pairs (X=R27:R26, Y=R29:R28, Z=R31:R30) when high byte is set.

        Args:
            addr_reg: Pointer register index.
            rr: Source register index.
        """
        high = self.read_reg(addr_reg + 1) if addr_reg in (26, 28, 30) else 0
        low = self.read_reg(addr_reg)
        addr = (high << 8) | low if high > 0 else low
        self.write_ram(addr, self.read_reg(rr))

    def op_lds(self, rd: int, addr: int) -> None:
        """Load Direct from Data Space (LDS).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: Rd <- (k)
            Status Register (SREG): None.

        Args:
            rd: Destination register index.
            addr: Memory address (0..ram_size-1).
        """
        self.write_reg(rd, self.read_ram(addr))

    def op_sts(self, addr: int, rr: int) -> None:
        """Store Direct to Data Space (STS).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: (k) <- Rr
            Status Register (SREG): None.

        Args:
            addr: Memory address (0..ram_size-1).
            rr: Source register index.
        """
        self.write_ram(addr, self.read_reg(rr))

    def op_brne(self, label: str | int) -> None:
        """Branch if Not Equal (BRNE).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: If Z = 0 then PC <- PC + k + 1
            Status Register (SREG): None.

        Args:
            label: Jump target label or numeric address.
        """
        if not (self.sreg & 0x02):
            self.op_jmp(label)

    def op_breq(self, label: str | int) -> None:
        """Branch if Equal (BREQ).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: If Z = 1 then PC <- PC + k + 1
            Status Register (SREG): None.

        Args:
            label: Jump target label or numeric address.
        """
        if self.sreg & 0x02:
            self.op_jmp(label)

    def op_brcs(self, label: str | int) -> None:
        """Branch if Carry Set (BRCS).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: If C = 1 then PC <- PC + k + 1
            Status Register (SREG): None.

        Args:
            label: Jump target label or numeric address.
        """
        if self.sreg & 0x01:
            self.op_jmp(label)

    def op_brcc(self, label: str | int) -> None:
        """Branch if Carry Cleared (BRCC).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: If C = 0 then PC <- PC + k + 1
            Status Register (SREG): None.

        Args:
            label: Jump target label or numeric address.
        """
        if not (self.sreg & 0x01):
            self.op_jmp(label)

    def op_brlo(self, label: str | int) -> None:
        """Branch if Lower Unsigned (BRLO).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: If C = 1 then PC <- PC + k + 1 (alias for BRCS)
            Status Register (SREG): None.

        Args:
            label: Jump target label or numeric address.
        """
        if self.sreg & 0x01:
            self.op_jmp(label)

    def op_brsh(self, label: str | int) -> None:
        """Branch if Same or Higher Unsigned (BRSH).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: If C = 0 then PC <- PC + k + 1 (alias for BRCC)
            Status Register (SREG): None.

        Args:
            label: Jump target label or numeric address.
        """
        if not (self.sreg & 0x01):
            self.op_jmp(label)

    def op_brge(self, label: str | int) -> None:
        """Branch if Greater or Equal Signed (BRGE).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: If S = 0 (N ⊕ V = 0) then PC <- PC + k + 1
            Status Register (SREG): None.

        Args:
            label: Jump target label or numeric address.
        """
        if not (self.sreg & 0x10):
            self.op_jmp(label)

    def op_brlt(self, label: str | int) -> None:
        """Branch if Less Than Signed (BRLT).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: If S = 1 (N ⊕ V = 1) then PC <- PC + k + 1
            Status Register (SREG): None.

        Args:
            label: Jump target label or numeric address.
        """
        if self.sreg & 0x10:
            self.op_jmp(label)

    def op_brmi(self, label: str | int) -> None:
        """Branch if Minus (BRMI).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: If N = 1 then PC <- PC + k + 1
            Status Register (SREG): None.

        Args:
            label: Jump target label or numeric address.
        """
        if self.sreg & 0x04:
            self.op_jmp(label)

    def op_brpl(self, label: str | int) -> None:
        """Branch if Plus (BRPL).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: If N = 0 then PC <- PC + k + 1
            Status Register (SREG): None.

        Args:
            label: Jump target label or numeric address.
        """
        if not (self.sreg & 0x04):
            self.op_jmp(label)

    def op_push(self, rr: int) -> None:
        """Push Register on Stack (PUSH).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: STACK <- Rr, SP <- SP - 1
            Status Register (SREG): None.

        Args:
            rr: Source register index.
        """
        self.write_ram(self.sp, self.read_reg(rr))
        self.sp -= 1

    def op_pop(self, rd: int) -> None:
        """Pop Register from Stack (POP).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: SP <- SP + 1, Rd <- STACK
            Status Register (SREG): None.

        Args:
            rd: Destination register index.
        """
        self.sp += 1
        self.write_reg(rd, self.read_ram(self.sp))

    def op_call(self, label: str | int) -> None:
        """Long Call to Subroutine (CALL).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: STACK <- PC + 1, PC <- k
            Status Register (SREG): None.

        Args:
            label: Subroutine target label or address.
        """
        ret = self.pc + 1
        self.write_ram(self.sp, (ret >> 8) & 0xFF)
        self.sp -= 1
        self.write_ram(self.sp, ret & 0xFF)
        self.sp -= 1
        self.op_jmp(label)

    def op_ret(self) -> None:
        """Return from Subroutine (RET).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: PC <- STACK
            Status Register (SREG): None.
        """
        self.sp += 1
        low = self.read_ram(self.sp)
        self.sp += 1
        high = self.read_ram(self.sp)
        self.pc = ((high << 8) | low) - 1

    def op_reti(self) -> None:
        """Return from Interrupt (RETI).

        Per AVR Instruction Set Manual DS40002198A:
            Operation: PC <- STACK, I <- 1
            Status Register (SREG): I
        """
        self.sp += 1
        low = self.read_ram(self.sp)
        self.sp += 1
        high = self.read_ram(self.sp)
        self.set_flag(SREG_I, True)
        self.pc = ((high << 8) | low) - 1

    def trigger_interrupt(self, vector_addr: int) -> None:
        """Trigger an interrupt if enabled in vector configuration.

        Args:
            vector_addr: Vector entry address in RAM.
        """
        if not self.interrupts.get(vector_addr, False):
            return
        ret = self.pc + 1
        self.write_ram(self.sp, (ret >> 8) & 0xFF)
        self.sp -= 1
        self.write_ram(self.sp, ret & 0xFF)
        self.sp -= 1
        self.pc = vector_addr - 1
