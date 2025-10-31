"""A simplified AVR-like 8-bit CPU simulator.

This module provides a lightweight CPU model inspired by the ATmega family.
The :class:`CPU` class is the primary export and implements a small, extensible instruction-dispatch model.
The implementation favors readability over step-accurate emulation. Add
instruction handlers by defining methods named ``op_<mnemonic>`` on ``CPU``.
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .assembler import AsmResult

from .memory import Memory
from .utils import ProgressBar

# SREG flag bit positions and short descriptions.
SREG_I = 7  # Global Interrupt Enable
SREG_T = 6  # Bit copy storage (temporary)
SREG_H = 5  # Half Carry
SREG_S = 4  # Sign (N ^ V)
SREG_V = 3  # Two's complement overflow
SREG_N = 2  # Negative
SREG_Z = 1  # Zero
SREG_C = 0  # Carry


class CPU:
    """In-memory 8-bit AVR-like CPU model.

    The CPU implements a compact instruction-dispatch model. Handlers are
    methods named ``op_<mnemonic>`` and are invoked by :meth:`step` for the
    currently-loaded program.

    Attributes:
        regs (list[int]): 32 8-bit general purpose registers (R0..R31).
        pc (int): Program counter (index into ``program``).
        sp (int): Stack pointer (index into RAM in the associated
            :class:`tiny8.memory.Memory`).
        sreg (int): Status register bits stored in a single integer (I, T,
            H, S, V, N, Z, C).
        step_count (int): Instruction execution counter.
        reg_trace (list[tuple[int, int, int]]): Per-step register change
            trace entries of the form ``(step, reg, new_value)``.
        mem_trace (list[tuple[int, int, int]]): Per-step memory change
            trace entries of the form ``(step, addr, new_value)``.
        step_trace (list[dict]): Full per-step snapshots useful for
            visualization and debugging.

    Note:
        This implementation simplifies many AVR specifics (flag semantics,
        exact step counts, IO mapping) in favor of clarity. Extend or
        replace individual ``op_`` handlers to increase fidelity.
    """

    def __init__(self, memory: Optional[Memory] = None):
        self.mem = memory or Memory()
        self.regs: list[int] = [0] * 32
        self.pc: int = 0
        self.sp: int = self.mem.ram_size - 1
        self.sreg: int = 0
        self.step_count: int = 0
        self.interrupts: dict[int, bool] = {}
        self.reg_trace: list[tuple[int, int, int]] = []
        self.mem_trace: list[tuple[int, int, int]] = []
        self.step_trace: list[dict] = []
        self.program: list[tuple[str, tuple]] = []
        self.labels: dict[str, int] = {}
        self.pc_to_line: dict[int, int] = {}
        self.source_lines: list[str] = []
        self.running = False

    def set_flag(self, bit: int, value: bool) -> None:
        """Set or clear a specific SREG flag bit.

        Args:
            bit: Integer bit index (0..7) representing the flag position.
            value: True to set the bit, False to clear it.
        """
        if value:
            self.sreg |= 1 << bit
        else:
            self.sreg &= ~(1 << bit)

    def get_flag(self, bit: int) -> bool:
        """Return the boolean value of a specific SREG flag bit.

        Args:
            bit: Integer bit index (0..7).

        Returns:
            True if the bit is set, False otherwise.
        """
        return bool((self.sreg >> bit) & 1)

    # --- AVR-like flag helpers (Z, C, N, V, S, H) ---
    def _set_flags_add(self, a: int, b: int, carry_in: int, result: int) -> None:
        """Set flags for ADD/ADC (AVR semantics).

        Args:
            a: First operand (0..255).
            b: Second operand (0..255).
            carry_in: Carry input (0 or 1).
            result: Integer sum result.
        """
        r = result & 0xFF
        c = (result >> 8) & 1
        h = (((a & 0x0F) + (b & 0x0F) + carry_in) >> 4) & 1
        n = (r >> 7) & 1
        v = 1 if (((~(a ^ b) & 0xFF) & (a ^ r) & 0x80) != 0) else 0
        s = n ^ v
        z = 1 if r == 0 else 0

        self.set_flag(SREG_C, bool(c))
        self.set_flag(SREG_H, bool(h))
        self.set_flag(SREG_N, bool(n))
        self.set_flag(SREG_V, bool(v))
        self.set_flag(SREG_S, bool(s))
        self.set_flag(SREG_Z, bool(z))

    def _set_flags_sub(self, a: int, b: int, borrow_in: int, result: int) -> None:
        """Set flags for SUB/CP/CPI (AVR semantics).

        Args:
            a: Minuend (0..255).
            b: Subtrahend (0..255).
            borrow_in: Borrow input (0 or 1).
            result: Signed difference (a - b - borrow_in).
        """
        r = result & 0xFF
        c = 1 if (a - b - borrow_in) < 0 else 0
        h = 1 if ((a & 0x0F) - (b & 0x0F) - borrow_in) < 0 else 0
        n = (r >> 7) & 1
        v = 1 if ((((a ^ b) & (a ^ r)) & 0x80) != 0) else 0
        s = n ^ v
        z = 1 if r == 0 else 0

        self.set_flag(SREG_C, bool(c))
        self.set_flag(SREG_H, bool(h))
        self.set_flag(SREG_N, bool(n))
        self.set_flag(SREG_V, bool(v))
        self.set_flag(SREG_S, bool(s))
        self.set_flag(SREG_Z, bool(z))

    def _set_flags_logical(self, result: int) -> None:
        """Set flags for logical operations (AND, OR, EOR) per AVR semantics.

        Args:
            result: Operation result.

        Note:
            Logical ops clear C and V, set N and Z, S = N ^ V, and clear H.
        """
        r = result & 0xFF
        n = (r >> 7) & 1
        z = 1 if r == 0 else 0
        s = n  # v is 0, so s = n ^ 0 = n

        self.set_flag(SREG_C, False)
        self.set_flag(SREG_V, False)
        self.set_flag(SREG_N, bool(n))
        self.set_flag(SREG_S, bool(s))
        self.set_flag(SREG_Z, bool(z))
        self.set_flag(SREG_H, False)

    def _set_flags_inc(self, old: int, new: int) -> None:
        """Set flags for INC (affects V, N, Z, S). Does not affect C or H.

        Args:
            old: Value before increment.
            new: Value after increment.
        """
        n = (new >> 7) & 1
        v = 1 if old == 0x7F else 0
        z = 1 if new == 0 else 0
        s = n ^ v
        self.set_flag(SREG_N, bool(n))
        self.set_flag(SREG_V, bool(v))
        self.set_flag(SREG_S, bool(s))
        self.set_flag(SREG_Z, bool(z))

    def _set_flags_add16(self, a: int, b: int, carry_in: int, result: int) -> None:
        """Set flags for 16-bit add (ADIW semantics approximation).

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

        self.set_flag(SREG_C, bool(c))
        self.set_flag(SREG_N, bool(n))
        self.set_flag(SREG_V, bool(v))
        self.set_flag(SREG_S, bool(s))
        self.set_flag(SREG_Z, bool(z))
        self.set_flag(SREG_H, False)

    def _set_flags_sub16(self, a: int, b: int, borrow_in: int, result: int) -> None:
        """Set flags for 16-bit subtraction (SBIW semantics approximation).

        Args:
            a: Minuend (0..0xFFFF).
            b: Subtrahend (0..0xFFFF).
            borrow_in: Borrow input (0 or 1).
            result: Integer difference a - b - borrow_in.
        """
        r = result & 0xFFFF
        c = 1 if (a - b - borrow_in) < 0 else 0
        n = (r >> 15) & 1
        v = 1 if ((((a ^ b) & (a ^ r)) & 0x8000) != 0) else 0
        s = n ^ v
        z = 1 if r == 0 else 0

        self.set_flag(SREG_C, bool(c))
        self.set_flag(SREG_N, bool(n))
        self.set_flag(SREG_V, bool(v))
        self.set_flag(SREG_S, bool(s))
        self.set_flag(SREG_Z, bool(z))
        self.set_flag(SREG_H, False)

    def _set_flags_dec(self, old: int, new: int) -> None:
        """Set flags for DEC (affects V, N, Z, S). Does not affect C or H.

        Args:
            old: Value before decrement.
            new: Value after decrement.
        """
        n = (new >> 7) & 1
        v = 1 if old == 0x80 else 0
        z = 1 if new == 0 else 0
        s = n ^ v
        self.set_flag(SREG_N, bool(n))
        self.set_flag(SREG_V, bool(v))
        self.set_flag(SREG_S, bool(s))
        self.set_flag(SREG_Z, bool(z))

    # Register access
    def read_reg(self, r: int) -> int:
        """Return the 8-bit value from register ``r``.

        Args:
            r: Register index (0..31).

        Returns:
            The 8-bit value (0..255) stored in the register.
        """
        return self.regs[r] & 0xFF

    def write_reg(self, r: int, val: int) -> None:
        """Write an 8-bit value to register ``r`` and record the change.

        Args:
            r: Register index (0..31).
            val: Value to write; will be truncated to 8 bits.

        Note:
            A trace entry is appended only when the register value actually
            changes to avoid noisy traces.
        """
        newv = val & 0xFF
        if self.regs[r] != newv:
            self.regs[r] = newv
            self.reg_trace.append((self.step_count, r, newv))

    # Memory access wrappers
    def read_ram(self, addr: int) -> int:
        """Read a byte from RAM at the given address.

        Args:
            addr: RAM address to read.

        Returns:
            Byte value stored at ``addr`` (0..255).
        """
        return self.mem.read_ram(addr)

    def write_ram(self, addr: int, val: int) -> None:
        """Write an 8-bit value to RAM at ``addr`` and record the trace.

        Args:
            addr: RAM address to write.
            val: Value to write; will be truncated to 8 bits.

        Note:
            The underlying :class:`Memory` object stores the value; a
            ``(step, addr, val)`` tuple is appended to ``mem_trace`` for
            visualizers/tests.
        """
        self.mem.write_ram(addr, val, self.step_count)
        self.mem_trace.append((self.step_count, addr, val & 0xFF))

    # Program loading
    def load_program(
        self,
        program: "list[tuple[str, tuple]] | AsmResult",
        labels: Optional[dict[str, int]] = None,
        pc_to_line: Optional[dict[int, int]] = None,
        source_lines: Optional[list[str]] = None,
    ):
        """Load an assembled program into the CPU.

        Args:
            program: Either a list of ``(mnemonic, operands)`` tuples or an
                AsmResult object. If AsmResult, other params are ignored.
            labels: Mapping of label strings to instruction indices (ignored if
                program is AsmResult).
            pc_to_line: Optional mapping from PC to source line number for tracing
                (ignored if program is AsmResult).
            source_lines: Optional original assembly source lines for display
                (ignored if program is AsmResult).

        Note:
            After loading the program, the program counter is reset to zero.
        """
        # Check if program is an AsmResult
        if hasattr(program, "program") and hasattr(program, "labels"):
            # It's an AsmResult
            asm = program
            self.program = asm.program
            self.labels = asm.labels
            self.pc_to_line = asm.pc_to_line
            self.source_lines = asm.source_lines
        else:
            # Legacy tuple-based format
            self.program = program
            self.labels = labels or {}
            self.pc_to_line = pc_to_line or {}
            self.source_lines = source_lines or []
        self.pc = 0

    # Instruction execution
    def step(self) -> bool:
        """Execute a single instruction at the current program counter.

        Performs one fetch-decode-execute step. A pre-step snapshot of
        registers and non-zero RAM is recorded, the instruction handler
        (``op_<mnemonic>``) is invoked, and a post-step trace entry is
        appended to ``step_trace``.

        Returns:
            True if an instruction was executed; False if the PC is out of
            range and execution should stop.
        """

        if self.pc < 0 or self.pc >= len(self.program):
            self.running = False
            return False

        instr, operands = self.program[self.pc]

        # Build textual form of the instruction for tracing (uppercase mnemonic
        # and register names like R0..R31). Operands decoded for display only.
        def fmt_op(o):
            if isinstance(o, tuple) and len(o) == 2 and o[0] == "reg":
                return f"R{o[1]}"
            return str(o)

        try:
            ops_text = ", ".join(fmt_op(o) for o in operands)
        except Exception:
            ops_text = ""
        instr_text = f"{instr.upper()} {ops_text}".strip()

        # record pre-step snapshot
        regs_snapshot = list(self.regs)
        # memory snapshot: capture all non-zero RAM addresses (helps visualization of higher addresses)
        mem_snapshot = {}
        for i in range(0, self.mem.ram_size):
            v = self.read_ram(i)
            if v != 0:
                mem_snapshot[i] = v

        # Convert register operand markers back to raw ints for handlers, and
        # call the appropriate handler (handlers are named op_<mnemonic> and
        # expect plain ints/strings as originally implemented).
        handler = getattr(self, f"op_{instr.lower()}", None)
        if handler is None:
            raise NotImplementedError(f"Instruction {instr} not implemented")

        # decode operands for handler call
        decoded_ops = []
        for o in operands:
            if isinstance(o, tuple) and len(o) == 2 and o[0] == "reg":
                decoded_ops.append(int(o[1]))
            else:
                decoded_ops.append(o)

        handler(*tuple(decoded_ops))

        # record step trace after execution (post-state)
        self.step_count += 1
        source_line = self.pc_to_line.get(self.pc, -1)
        self.step_trace.append(
            {
                "step": self.step_count,
                "pc": self.pc,
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
        """Run instructions until program end or ``max_steps`` is reached.

        Args:
            max_steps: Maximum number of instruction steps to execute
                (default 100000).
            show_progress: If True, display a progress bar during execution
                (default True).

        Note:
            This repeatedly calls :meth:`step` until it returns False or the
            maximum step count is reached.
        """
        self.running = True
        steps = 0

        if show_progress:
            pb = ProgressBar(total=max_steps, desc="CPU execution")

        try:
            while self.running and steps < max_steps:
                ok = self.step()
                if not ok:
                    break
                steps += 1

                if show_progress:
                    pb.update(1)
        finally:
            if show_progress:
                pb.close()

    def op_nop(self):
        """No-operation: does nothing for one step."""
        pass

    def op_ldi(self, reg_idx: int, imm: int):
        """Load an immediate value into a register.

        Args:
            reg_idx: Destination register index.
            imm: Immediate value to load.

        Note:
            The AVR LDI instruction is normally restricted to R16..R31; this
            simplified implementation accepts any register index.
        """
        self.write_reg(reg_idx, imm)

    def op_mov(self, rd: int, rr: int):
        """Copy the value from register ``rr`` into ``rd``.

        Args:
            rd: Destination register index.
            rr: Source register index.
        """
        self.write_reg(rd, self.read_reg(rr))

    def op_add(self, rd: int, rr: int):
        """Add register ``rr`` to ``rd`` (Rd := Rd + Rr) and update flags.

        Args:
            rd: Destination register index.
            rr: Source register index.

        Note:
            Sets C, H, N, V, S, Z per AVR semantics.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        res = a + b
        self.write_reg(rd, res & 0xFF)
        self._set_flags_add(a, b, 0, res)

    def op_and(self, rd: int, rr: int):
        """Logical AND (Rd := Rd & Rr) — updates N, Z, V=0, C=0, H=0, S.

        Args:
            rd: Destination register index.
            rr: Source register index.
        """
        res = self.read_reg(rd) & self.read_reg(rr)
        self.write_reg(rd, res)
        self._set_flags_logical(res)

    def op_or(self, rd: int, rr: int):
        """Logical OR (Rd := Rd | Rr) — updates N, Z, V=0, C=0, H=0, S.

        Args:
            rd: Destination register index.
            rr: Source register index.
        """
        res = self.read_reg(rd) | self.read_reg(rr)
        self.write_reg(rd, res)
        self._set_flags_logical(res)

    def op_eor(self, rd: int, rr: int):
        """Exclusive OR (Rd := Rd ^ Rr) — updates N, Z, V=0, C=0, H=0, S.

        Args:
            rd: Destination register index.
            rr: Source register index.
        """
        res = self.read_reg(rd) ^ self.read_reg(rr)
        self.write_reg(rd, res)
        self._set_flags_logical(res)

    def op_sub(self, rd: int, rr: int):
        """Subtract (Rd := Rd - Rr) and set flags C,H,N,V,S,Z.

        Args:
            rd: Destination register index.
            rr: Source register index.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        res_full = a - b
        self.write_reg(rd, res_full & 0xFF)
        self._set_flags_sub(a, b, 0, res_full)

    def op_inc(self, rd: int):
        """Increment (Rd := Rd + 1) — updates V,N,S,Z; does not change C/H.

        Args:
            rd: Destination register index.
        """
        old = self.read_reg(rd)
        new = (old + 1) & 0xFF
        self.write_reg(rd, new)
        self._set_flags_inc(old, new)

    def op_dec(self, rd: int):
        """Decrement (Rd := Rd - 1) — updates V,N,S,Z; does not change C/H.

        Args:
            rd: Destination register index.
        """
        old = self.read_reg(rd)
        new = (old - 1) & 0xFF
        self.write_reg(rd, new)
        self._set_flags_dec(old, new)

    def op_mul(self, rd: int, rr: int):
        """Multiply 8x8 -> 16: store low in Rd, high in Rd+1.

        Args:
            rd: Destination register index for low byte.
            rr: Source register index.

        Note:
            Updates Z and C flags. Z set if product == 0; C set if high != 0.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        prod = a * b
        low = prod & 0xFF
        high = (prod >> 8) & 0xFF
        self.write_reg(rd, low)
        if rd + 1 < 32:
            self.write_reg(rd + 1, high)
        self.set_flag(SREG_Z, prod == 0)
        self.set_flag(SREG_C, high != 0)
        self.set_flag(SREG_H, False)

    def op_adc(self, rd: int, rr: int):
        """Add with carry (Rd := Rd + Rr + C) and update flags.

        Args:
            rd: Destination register index.
            rr: Source register index.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        carry_in = 1 if self.get_flag(SREG_C) else 0
        res = a + b + carry_in
        self.write_reg(rd, res & 0xFF)
        self._set_flags_add(a, b, carry_in, res)

    def op_clr(self, rd: int):
        """Clear register (Rd := 0). Behaves like EOR Rd,Rd for flags.

        Args:
            rd: Destination register index.
        """
        self.write_reg(rd, 0)
        self.set_flag(SREG_N, False)
        self.set_flag(SREG_V, False)
        self.set_flag(SREG_S, False)
        self.set_flag(SREG_Z, True)
        self.set_flag(SREG_C, False)
        self.set_flag(SREG_H, False)

    def op_ser(self, rd: int):
        """Set register all ones (Rd := 0xFF). Update flags conservatively.

        Args:
            rd: Destination register index.
        """
        self.write_reg(rd, 0xFF)
        self.set_flag(SREG_N, True)
        self.set_flag(SREG_V, False)
        self.set_flag(SREG_S, True)
        self.set_flag(SREG_Z, False)
        self.set_flag(SREG_C, False)
        self.set_flag(SREG_H, False)

    def op_div(self, rd: int, rr: int):
        """Unsigned divide convenience instruction: quotient -> Rd, remainder -> Rd+1.

        Args:
            rd: Destination register index for quotient.
            rr: Divisor register index.

        Note:
            If divisor is zero, sets C and Z flags to indicate error.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        if b == 0:
            self.write_reg(rd, 0)
            self.set_flag(SREG_C, True)
            self.set_flag(SREG_Z, True)
            return
        q = a // b
        r = a % b
        self.write_reg(rd, q)
        if rd + 1 < 32:
            self.write_reg(rd + 1, r)
        self.set_flag(SREG_Z, q == 0)
        self.set_flag(SREG_C, False)
        self.set_flag(SREG_H, False)
        self.set_flag(SREG_V, False)

    def op_in(self, rd: int, port: int):
        """Read from I/O port into register.

        Args:
            rd: Destination register index.
            port: Port address to read from.
        """
        val = self.read_ram(port)
        self.write_reg(rd, val)

    def op_out(self, port: int, rr: int):
        """Write register value to I/O port.

        Args:
            port: Port address to write to.
            rr: Source register index.
        """
        val = self.read_reg(rr)
        self.write_ram(port, val)

    def op_jmp(self, label: str | int):
        """Jump to a given label or numeric address by updating the program counter.

        Args:
            label: The jump target. If a string, it is treated as a symbolic label
                and looked up in self.labels. If an int, it is used directly as the
                numeric address.

        Note:
            Sets PC to target - 1 because the instruction dispatcher will
            increment PC after the current instruction completes.
        """
        if isinstance(label, str):
            if label not in self.labels:
                raise KeyError(f"Label {label} not found")
            self.pc = self.labels[label] - 1
        else:
            self.pc = int(label) - 1

    def op_cpi(self, rd: int, imm: int):
        """Compare register with immediate (sets flags but doesn't modify register).

        Args:
            rd: Register index to compare.
            imm: Immediate value to compare against.
        """
        a = self.read_reg(rd)
        b = imm & 0xFF
        res = a - b
        self._set_flags_sub(a, b, 0, res)

    def op_cp(self, rd: int, rr: int):
        """Compare two registers (sets flags but doesn't modify registers).

        Args:
            rd: First register index.
            rr: Second register index.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        res = a - b
        self._set_flags_sub(a, b, 0, res)

    def op_lsl(self, rd: int):
        """Logical shift left (Rd := Rd << 1).

        Args:
            rd: Destination register index.
        """
        v = self.read_reg(rd)
        carry = (v >> 7) & 1
        nv = (v << 1) & 0xFF
        self.write_reg(rd, nv)
        self.set_flag(SREG_C, bool(carry))
        n = (nv >> 7) & 1
        vflag = n ^ carry
        self.set_flag(SREG_N, bool(n))
        self.set_flag(SREG_V, bool(vflag))
        self.set_flag(SREG_S, bool(n ^ vflag))
        self.set_flag(SREG_Z, nv == 0)
        self.set_flag(SREG_H, False)

    def op_lsr(self, rd: int):
        """Logical shift right (Rd := Rd >> 1).

        Args:
            rd: Destination register index.
        """
        v = self.read_reg(rd)
        carry = v & 1
        nv = (v >> 1) & 0xFF
        self.write_reg(rd, nv)
        self.set_flag(SREG_C, bool(carry))
        self.set_flag(SREG_N, False)
        self.set_flag(SREG_V, bool(carry))
        self.set_flag(SREG_S, bool(carry))
        self.set_flag(SREG_Z, nv == 0)
        self.set_flag(SREG_H, False)

    def op_rol(self, rd: int):
        """Rotate left through carry.

        Args:
            rd: Destination register index.
        """
        v = self.read_reg(rd)
        carry_in = 1 if self.get_flag(SREG_C) else 0
        carry_out = (v >> 7) & 1
        nv = ((v << 1) & 0xFF) | carry_in
        self.write_reg(rd, nv)
        self.set_flag(SREG_C, bool(carry_out))
        self.set_flag(SREG_N, bool((nv >> 7) & 1))
        self.set_flag(SREG_Z, nv == 0)
        self.set_flag(SREG_V, False)
        self.set_flag(SREG_S, bool((nv >> 7) & 1))
        self.set_flag(SREG_H, False)

    def op_ror(self, rd: int):
        """Rotate right through carry.

        Args:
            rd: Destination register index.
        """
        v = self.read_reg(rd)
        carry_in = 1 if self.get_flag(SREG_C) else 0
        carry_out = v & 1
        nv = (v >> 1) | (carry_in << 7)
        self.write_reg(rd, nv)
        self.set_flag(SREG_C, bool(carry_out))
        self.set_flag(SREG_N, bool((nv >> 7) & 1))
        self.set_flag(SREG_Z, nv == 0)
        self.set_flag(SREG_V, False)
        self.set_flag(SREG_S, bool((nv >> 7) & 1))
        self.set_flag(SREG_H, False)

    def op_com(self, rd: int):
        """One's complement: Rd := ~Rd. Updates N,V,S,Z,C per AVR-ish semantics.

        Args:
            rd: Destination register index.
        """
        v = self.read_reg(rd)
        nv = (~v) & 0xFF
        self.write_reg(rd, nv)
        n = (nv >> 7) & 1
        self.set_flag(SREG_N, bool(n))
        self.set_flag(SREG_V, False)
        self.set_flag(SREG_S, bool(n))
        self.set_flag(SREG_Z, nv == 0)
        self.set_flag(SREG_C, True)
        self.set_flag(SREG_H, False)

    def op_neg(self, rd: int):
        """Two's complement (negate): Rd := 0 - Rd. Flags as subtraction from 0.

        Args:
            rd: Destination register index.
        """
        a = self.read_reg(rd)
        res_full = 0 - a
        self.write_reg(rd, res_full & 0xFF)
        self._set_flags_sub(0, a, 0, res_full)

    def op_swap(self, rd: int):
        """Swap nibbles in register: Rd[7:4] <-> Rd[3:0]. Does not affect SREG.

        Args:
            rd: Destination register index.
        """
        v = self.read_reg(rd)
        nv = ((v & 0x0F) << 4) | ((v >> 4) & 0x0F)
        self.write_reg(rd, nv)

    def op_tst(self, rd: int):
        """Test: perform AND Rd,Rd and update flags but do not store result.

        Args:
            rd: Register index to test.
        """
        v = self.read_reg(rd)
        res = v & v
        self._set_flags_logical(res)

    def op_andi(self, rd: int, imm: int):
        """Logical AND with immediate (Rd := Rd & K).

        Args:
            rd: Destination register index.
            imm: Immediate value.
        """
        res = self.read_reg(rd) & (imm & 0xFF)
        self.write_reg(rd, res)
        self._set_flags_logical(res)

    def op_ori(self, rd: int, imm: int):
        """Logical OR with immediate (Rd := Rd | K).

        Args:
            rd: Destination register index.
            imm: Immediate value.
        """
        res = self.read_reg(rd) | (imm & 0xFF)
        self.write_reg(rd, res)
        self._set_flags_logical(res)

    def op_eori(self, rd: int, imm: int):
        """Logical EOR with immediate (Rd := Rd ^ K).

        Args:
            rd: Destination register index.
            imm: Immediate value.
        """
        res = self.read_reg(rd) ^ (imm & 0xFF)
        self.write_reg(rd, res)
        self._set_flags_logical(res)

    def op_subi(self, rd: int, imm: int):
        """Subtract immediate (Rd := Rd - K).

        Args:
            rd: Destination register index.
            imm: Immediate value.
        """
        a = self.read_reg(rd)
        b = imm & 0xFF
        res_full = a - b
        self.write_reg(rd, res_full & 0xFF)
        self._set_flags_sub(a, b, 0, res_full)

    def op_sbc(self, rd: int, rr: int):
        """Subtract with carry (Rd := Rd - Rr - C).

        Args:
            rd: Destination register index.
            rr: Source register index.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        borrow_in = 1 if self.get_flag(SREG_C) else 0
        res_full = a - b - borrow_in
        self.write_reg(rd, res_full & 0xFF)
        self._set_flags_sub(a, b, borrow_in, res_full)

    def op_sbci(self, rd: int, imm: int):
        """Subtract immediate with carry: Rd := Rd - K - C.

        Args:
            rd: Destination register index.
            imm: Immediate value.
        """
        a = self.read_reg(rd)
        b = imm & 0xFF
        borrow_in = 1 if self.get_flag(SREG_C) else 0
        res_full = a - b - borrow_in
        self.write_reg(rd, res_full & 0xFF)
        self._set_flags_sub(a, b, borrow_in, res_full)

    def op_sei(self):
        """Set Global Interrupt Enable (I bit)."""
        self.set_flag(SREG_I, True)

    def op_cli(self):
        """Clear Global Interrupt Enable (I bit)."""
        self.set_flag(SREG_I, False)

    def op_cpse(self, rd: int, rr: int):
        """Compare and Skip if Equal: compare Rd,Rr; if equal, skip next instruction.

        Args:
            rd: First register index.
            rr: Second register index.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        self._set_flags_sub(a, b, 0, a - b)
        if a == b:
            self.pc += 1

    def op_sbrs(self, rd: int, bit: int):
        """Skip next if bit in register is set.

        Args:
            rd: Register index.
            bit: Bit position to test.
        """
        v = self.read_reg(rd)
        if ((v >> (bit & 7)) & 1) == 1:
            self.pc += 1

    def op_sbrc(self, rd: int, bit: int):
        """Skip next if bit in register is clear.

        Args:
            rd: Register index.
            bit: Bit position to test.
        """
        v = self.read_reg(rd)
        if ((v >> (bit & 7)) & 1) == 0:
            self.pc += 1

    def op_sbis(self, io_addr: int, bit: int):
        """Skip if bit in IO/RAM-mapped address is set.

        Args:
            io_addr: I/O or RAM address.
            bit: Bit position to test.
        """
        v = self.read_ram(io_addr)
        if ((v >> (bit & 7)) & 1) == 1:
            self.pc += 1

    def op_sbic(self, io_addr: int, bit: int):
        """Skip if bit in IO/RAM-mapped address is clear.

        Args:
            io_addr: I/O or RAM address.
            bit: Bit position to test.
        """
        v = self.read_ram(io_addr)
        if ((v >> (bit & 7)) & 1) == 0:
            self.pc += 1

    def op_sbiw(self, rd_word_low: int, imm_word: int):
        """Subtract immediate from word register pair (Rd:Rd+1) — simplified.

        Args:
            rd_word_low: Low register of the pair (even register index).
            imm_word: 16-bit immediate to subtract.
        """
        lo = self.read_reg(rd_word_low)
        hi = self.read_reg(rd_word_low + 1) if (rd_word_low + 1) < 32 else 0
        word = (hi << 8) | lo
        new = (word - (imm_word & 0xFFFF)) & 0xFFFF
        new_lo = new & 0xFF
        new_hi = (new >> 8) & 0xFF
        self.write_reg(rd_word_low, new_lo)
        if rd_word_low + 1 < 32:
            self.write_reg(rd_word_low + 1, new_hi)
        self._set_flags_sub16(word, imm_word & 0xFFFF, 0, word - (imm_word & 0xFFFF))

    def op_adiw(self, rd_word_low: int, imm_word: int):
        """Add immediate to word register pair (Rd:Rd+1) - simplified.

        Args:
            rd_word_low: Low register of the pair (even register index).
            imm_word: 16-bit immediate to add.
        """
        lo = self.read_reg(rd_word_low)
        hi = self.read_reg(rd_word_low + 1) if (rd_word_low + 1) < 32 else 0
        word = (hi << 8) | lo
        new = (word + (imm_word & 0xFFFF)) & 0xFFFF
        new_lo = new & 0xFF
        new_hi = (new >> 8) & 0xFF
        self.write_reg(rd_word_low, new_lo)
        if rd_word_low + 1 < 32:
            self.write_reg(rd_word_low + 1, new_hi)
        self._set_flags_add16(word, imm_word & 0xFFFF, 0, word + (imm_word & 0xFFFF))

    def op_rjmp(self, label: str):
        """Relative jump — label may be an int or string label.

        Args:
            label: Jump target (label name or relative offset).
        """
        if isinstance(label, int):
            self.pc = self.pc + int(label)
        else:
            self.op_jmp(label)

    def op_rcall(self, label: str):
        """Relative call — push return address and jump relatively or to label.

        Args:
            label: Call target (label name or relative offset).
        """
        ret = self.pc + 1
        self.write_ram(self.sp, (ret >> 8) & 0xFF)
        self.sp -= 1
        self.write_ram(self.sp, ret & 0xFF)
        self.sp -= 1
        if isinstance(label, int):
            target = self.pc + int(label)
            self.pc = int(target) - 1
        else:
            self.op_jmp(label)

    def op_sbi(self, io_addr: int, bit: int):
        """Set a bit in an I/O/memory-mapped address (use RAM area).

        Args:
            io_addr: I/O or RAM address to modify.
            bit: Bit index to set (0..7).
        """
        # set bit in I/O location (use RAM address space)
        val = self.read_ram(io_addr)
        nval = val | (1 << (bit & 7))
        self.write_ram(io_addr, nval)

    def op_cbi(self, io_addr: int, bit: int):
        """Clear a bit in an I/O/memory-mapped address (use RAM area).

        Args:
            io_addr: I/O or RAM address to modify.
            bit: Bit index to clear (0..7).
        """
        val = self.read_ram(io_addr)
        nval = val & ~(1 << (bit & 7))
        self.write_ram(io_addr, nval)

    def op_ld(self, rd: int, addr_reg: int):
        """Load from RAM at address contained in register ``addr_reg`` into
        ``rd``.

        Args:
            rd: Destination register index.
            addr_reg: Register index containing the RAM address to load from.
        """
        addr = self.read_reg(addr_reg)
        val = self.read_ram(addr)
        self.write_reg(rd, val)

    def op_st(self, addr_reg: int, rr: int):
        """Store register ``rr`` into RAM at address contained in register
        ``addr_reg``.

        Args:
            addr_reg: Register index containing the RAM address to write to.
            rr: Source register index to store.
        """
        addr = self.read_reg(addr_reg)
        val = self.read_reg(rr)
        self.write_ram(addr, val)

    def op_brne(self, label: str):
        """Branch to label if Zero flag is not set (BRNE).

        Args:
            label: Destination label to jump to if Z flag is not set.
        """
        z = self.get_flag(SREG_Z)
        if not z:
            self.op_jmp(label)

    def op_breq(self, label: str):
        """Branch to label if Zero flag is set (BREQ).

        Args:
            label: Destination label to jump to if Z flag is set.
        """
        z = self.get_flag(SREG_Z)
        if z:
            self.op_jmp(label)

    def op_brcs(self, label: str):
        """Branch to a label if the carry flag is set.

        Args:
            label (str): Destination label to jump to if the carry flag is set.
        """
        c = self.get_flag(SREG_C)
        if c:
            self.op_jmp(label)

    def op_brcc(self, label: str):
        """Branch to a label if the carry flag is clear.

        Args:
            label (str): Destination label to jump to if the carry flag is clear.
        """
        c = self.get_flag(SREG_C)
        if not c:
            self.op_jmp(label)

    def op_brge(self, label: str | int):
        """Branch if Greater or Equal (Signed).

        Args:
            label: Destination label or address to jump to if the condition is met.
        """
        s = self.get_flag(SREG_S)
        if not s:
            self.op_jmp(label)

    def op_brlt(self, label: str | int):
        """Branch if Less Than (Signed).

        Args:
            label: Destination label or address to jump to if the condition is met.
        """
        s = self.get_flag(SREG_S)
        if s:
            self.op_jmp(label)

    def op_brmi(self, label: str | int):
        """Branch if Minus (Negative flag set).

        Args:
            label: Destination label or address to jump to if the condition is met.
        """
        n = self.get_flag(SREG_N)
        if n:
            self.op_jmp(label)

    def op_brpl(self, label: str | int):
        """Branch if Plus (Negative flag clear).

        Args:
            label: Destination label or address to jump to if the condition is met.
        """
        n = self.get_flag(SREG_N)
        if not n:
            self.op_jmp(label)

    def op_push(self, rr: int):
        """Push a register value onto the stack.

        Args:
            rr: Source register index to push.

        Note:
            The value of register ``rr`` is written to RAM at the current
            stack pointer, and the stack pointer is then decremented.
        """
        val = self.read_reg(rr)
        self.write_ram(self.sp, val)
        self.sp -= 1

    def op_pop(self, rd: int):
        """Pop a value from the stack into a register.

        Args:
            rd: Destination register index to receive the popped value.

        Note:
            The stack pointer is incremented, the byte at the new stack pointer
            is read from RAM, and the value is written into register ``rd``.
        """
        self.sp += 1
        val = self.read_ram(self.sp)
        self.write_reg(rd, val)

    def op_call(self, label: str):
        """Call a subroutine by pushing the return address and jumping to label.

        Args:
            label: Label to call.

        Note:
            The return address (pc+1) is pushed as two bytes (high then low) onto
            the stack, decrementing the stack pointer after each write.
        """
        ret = self.pc + 1
        self.write_ram(self.sp, (ret >> 8) & 0xFF)
        self.sp -= 1
        self.write_ram(self.sp, ret & 0xFF)
        self.sp -= 1
        self.op_jmp(label)

    def op_ret(self):
        """Return from subroutine by popping the return address and setting PC.

        Note:
            Two bytes are popped from the stack (low then high) to reconstruct the
            return address, which is then loaded into the program counter.
        """
        self.sp += 1
        low = self.read_ram(self.sp)
        self.sp += 1
        high = self.read_ram(self.sp)
        ret = (high << 8) | low
        self.pc = ret - 1

    def op_reti(self):
        """Return from interrupt: pop return address and set I flag."""
        self.sp += 1
        low = self.read_ram(self.sp)
        self.sp += 1
        high = self.read_ram(self.sp)
        ret = (high << 8) | low
        self.set_flag(SREG_I, True)
        self.pc = ret - 1

    def trigger_interrupt(self, vector_addr: int):
        """Trigger an interrupt vector if it is enabled.

        Args:
            vector_addr: Interrupt vector address to jump to.

        Note:
            If the interrupt vector is enabled in ``self.interrupts``, the current
            PC+1 is pushed onto the stack (high then low byte) and control jumps
            to ``vector_addr``.
        """
        if not self.interrupts.get(vector_addr, False):
            return
        ret = self.pc + 1
        self.write_ram(self.sp, (ret >> 8) & 0xFF)
        self.sp -= 1
        self.write_ram(self.sp, ret & 0xFF)
        self.sp -= 1
        self.pc = vector_addr - 1
