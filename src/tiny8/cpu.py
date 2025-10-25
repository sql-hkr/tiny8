"""A simplified AVR-like 8-bit CPU simulator.

This module provides a lightweight CPU model inspired by the ATmega family.
The :class:`CPU` class is the primary export and implements a small, extensible instruction-dispatch model.
The implementation favors readability over cycle-accurate emulation. Add
instruction handlers by defining methods named ``op_<mnemonic>`` on ``CPU``.
"""

from typing import Optional

from .memory import Memory

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
        cycle (int): Instruction execution counter.
        reg_trace (list[tuple[int, int, int]]): Per-cycle register change
            trace entries of the form ``(cycle, reg, new_value)``.
        mem_trace (list[tuple[int, int, int]]): Per-cycle memory change
            trace entries of the form ``(cycle, addr, new_value)``.
        step_trace (list[dict]): Full per-step snapshots useful for
            visualization and debugging.

    Note:
        This implementation simplifies many AVR specifics (flag semantics,
        exact cycle counts, IO mapping) in favor of clarity. Extend or
        replace individual ``op_`` handlers to increase fidelity.
    """

    def __init__(self, memory: Optional[Memory] = None):
        self.mem = memory or Memory()
        # 32 general purpose 8-bit registers R0-R31
        self.regs: [int] = [0] * 32
        # Program Counter (word-addressable for AVR) - we use byte addressing for simplicity
        self.pc: int = 0
        # Stack Pointer - point into RAM
        self.sp: int = self.mem.ram_size - 1
        # Status register (SREG) flags: I T H S V N Z C - store as bits in an int
        self.sreg: int = 0
        # Cycle counter
        self.cycle: int = 0
        # Simple interrupt vector table (addr->enabled)
        self.interrupts: dict[int, bool] = {}
        # Execution trace of register/memory changes per cycle
        self.reg_trace: list[tuple[int, int, int]] = []  # (cycle, reg, newval)
        self.mem_trace: list[tuple[int, int, int]] = []  # (cycle, addr, newval)
        # Full step trace: list of dicts with cycle, pc, instr_text, regs snapshot, optional mem snapshot
        self.step_trace: list[dict] = []
        # Program area - list of instructions as tuples: (mnemonic, *operands)
        self.program: list[tuple[str, tuple]] = []
        # Labels -> pc
        self.labels: dict[str, int] = {}
        # Running state
        self.running = False

    # Helper SREG flags accessors
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

        a, b are 0..255 values, carry_in is 0/1, result is integer sum.
        """
        r = result & 0xFF
        # Carry (C): bit 8
        c = (result >> 8) & 1
        # Half carry (H): carry from bit3
        h = (((a & 0x0F) + (b & 0x0F) + carry_in) >> 4) & 1
        # Negative (N): bit7 of result
        n = (r >> 7) & 1
        # Two's complement overflow (V): when signs of a and b are same and sign of result differs
        # Use 8-bit masking to avoid Python's infinite-bit ~ behavior.
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

        Borrow_in is 0/1; result is signed difference (a - b - borrow_in).
        """
        r = result & 0xFF
        # Carry (C) indicates borrow in subtraction
        c = 1 if (a - b - borrow_in) < 0 else 0
        # Half-carry (H): borrow from bit4
        h = 1 if ((a & 0x0F) - (b & 0x0F) - borrow_in) < 0 else 0
        n = (r >> 7) & 1
        # Two's complement overflow (V): if signs of a and b differ and sign of result differs from sign of a
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

        Logical ops clear C and V, set N and Z, S = N ^ V, and clear H.
        """
        r = result & 0xFF
        n = (r >> 7) & 1
        z = 1 if r == 0 else 0
        v = 0
        c = 0
        s = n ^ v

        self.set_flag(SREG_C, bool(c))
        self.set_flag(SREG_V, bool(v))
        self.set_flag(SREG_N, bool(n))
        self.set_flag(SREG_S, bool(s))
        self.set_flag(SREG_Z, bool(z))
        self.set_flag(SREG_H, False)

    def _set_flags_inc(self, old: int, new: int) -> None:
        """Set flags for INC (affects V, N, Z, S). Does not affect C or H."""
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

        a, b are 0..0xFFFF, carry_in is 0/1, result is full integer sum.
        """
        r = result & 0xFFFF
        # Carry out of bit15
        c = (result >> 16) & 1
        # Negative (N) is bit15 of result
        n = (r >> 15) & 1
        # Two's complement overflow (V): when signs of a and b are same and sign of result differs
        v = 1 if (((~(a ^ b) & 0xFFFF) & (a ^ r) & 0x8000) != 0) else 0
        s = n ^ v
        z = 1 if r == 0 else 0

        self.set_flag(SREG_C, bool(c))
        self.set_flag(SREG_N, bool(n))
        self.set_flag(SREG_V, bool(v))
        self.set_flag(SREG_S, bool(s))
        self.set_flag(SREG_Z, bool(z))
        # H is undefined for word ops on AVR; clear conservatively
        self.set_flag(SREG_H, False)

    def _set_flags_sub16(self, a: int, b: int, borrow_in: int, result: int) -> None:
        """Set flags for 16-bit subtraction (SBIW semantics approximation).

        Borrow_in is 0/1; result is integer difference a - b - borrow_in.
        """
        r = result & 0xFFFF
        # Carry indicates borrow out of bit15
        c = 1 if (a - b - borrow_in) < 0 else 0
        n = (r >> 15) & 1
        # Two's complement overflow (V) for subtraction
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
        """Set flags for DEC (affects V, N, Z, S). Does not affect C or H."""
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
            self.reg_trace.append((self.cycle, r, newv))

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
            ``(cycle, addr, val)`` tuple is appended to ``mem_trace`` for
            visualizers/tests.
        """
        self.mem.write_ram(addr, val, self.cycle)
        self.mem_trace.append((self.cycle, addr, val & 0xFF))

    # Program loading
    def load_program(self, program: list[tuple[str, tuple]], labels: dict[str, int]):
        """Load an assembled program into the CPU.

        Args:
            program: list of ``(mnemonic, operands)`` tuples returned by the
                assembler.
            labels: Mapping of label strings to instruction indices.

        Note:
            After loading the program, the program counter is reset to zero.
        """
        self.program = program
        self.labels = labels
        self.pc = 0

    # Instruction execution
    def step(self) -> bool:
        """Execute a single instruction at the current program counter.

        Performs one fetch-decode-execute cycle. A pre-step snapshot of
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
        self.cycle += 1
        self.step_trace.append(
            {
                "cycle": self.cycle,
                "pc": self.pc,
                "instr": instr_text,
                "regs": regs_snapshot,
                "mem": mem_snapshot,
                "sreg": self.sreg,
                "sp": self.sp,
            }
        )
        self.pc += 1
        return True

    def run(self, max_cycles: int = 100000) -> None:
        """Run instructions until program end or ``max_cycles`` is reached.

        Args:
            max_cycles: Maximum number of instruction cycles to execute
                (default 100000).

        Note:
            This repeatedly calls :meth:`step` until it returns False or the
            maximum cycle count is reached.
        """
        self.running = True
        cycles = 0
        while self.running and cycles < max_cycles:
            ok = self.step()
            if not ok:
                break
            cycles += 1

    # Minimal instruction implementations
    def op_nop(self):
        """No-operation: does nothing for one cycle."""
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

        Sets C, H, N, V, S, Z per AVR semantics.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        res = a + b
        self.write_reg(rd, res & 0xFF)
        self._set_flags_add(a, b, 0, res)

    def op_and(self, rd: int, rr: int):
        """Logical AND (Rd := Rd & Rr) — updates N, Z, V=0, C=0, H=0, S."""
        res = self.read_reg(rd) & self.read_reg(rr)
        self.write_reg(rd, res)
        self._set_flags_logical(res)

    def op_or(self, rd: int, rr: int):
        """Logical OR (Rd := Rd | Rr) — updates N, Z, V=0, C=0, H=0, S."""
        res = self.read_reg(rd) | self.read_reg(rr)
        self.write_reg(rd, res)
        self._set_flags_logical(res)

    def op_eor(self, rd: int, rr: int):
        """Exclusive OR (Rd := Rd ^ Rr) — updates N, Z, V=0, C=0, H=0, S."""
        res = self.read_reg(rd) ^ self.read_reg(rr)
        self.write_reg(rd, res)
        self._set_flags_logical(res)

    def op_sub(self, rd: int, rr: int):
        """Subtract (Rd := Rd - Rr) and set flags C,H,N,V,S,Z."""
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        res_full = a - b
        self.write_reg(rd, res_full & 0xFF)
        self._set_flags_sub(a, b, 0, res_full)

    def op_inc(self, rd: int):
        """Increment (Rd := Rd + 1) — updates V,N,S,Z; does not change C/H."""
        old = self.read_reg(rd)
        new = (old + 1) & 0xFF
        self.write_reg(rd, new)
        self._set_flags_inc(old, new)

    def op_dec(self, rd: int):
        """Decrement (Rd := Rd - 1) — updates V,N,S,Z; does not change C/H."""
        old = self.read_reg(rd)
        new = (old - 1) & 0xFF
        self.write_reg(rd, new)
        self._set_flags_dec(old, new)

    def op_mul(self, rd: int, rr: int):
        """Multiply 8x8 -> 16: store low in Rd, high in Rd+1. Update Z and C conservatively."""
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        prod = a * b
        low = prod & 0xFF
        high = (prod >> 8) & 0xFF
        self.write_reg(rd, low)
        if rd + 1 < 32:
            self.write_reg(rd + 1, high)
        # Update flags: Z set if product == 0; C set if high != 0; H undefined -> clear
        self.set_flag(SREG_Z, prod == 0)
        self.set_flag(SREG_C, high != 0)
        self.set_flag(SREG_H, False)

    def op_adc(self, rd: int, rr: int):
        """Add with carry (Rd := Rd + Rr + C) and update flags."""
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        carry_in = 1 if self.get_flag(SREG_C) else 0
        res = a + b + carry_in
        self.write_reg(rd, res & 0xFF)
        self._set_flags_add(a, b, carry_in, res)

    def op_clr(self, rd: int):
        """Clear register (Rd := 0). Behaves like EOR Rd,Rd for flags."""
        self.write_reg(rd, 0)
        self.set_flag(SREG_N, False)
        self.set_flag(SREG_V, False)
        self.set_flag(SREG_S, False)
        self.set_flag(SREG_Z, True)
        self.set_flag(SREG_C, False)
        self.set_flag(SREG_H, False)

    def op_ser(self, rd: int):
        """Set register all ones (Rd := 0xFF). Update flags conservatively."""
        self.write_reg(rd, 0xFF)
        self.set_flag(SREG_N, True)
        self.set_flag(SREG_V, False)
        self.set_flag(SREG_S, True)
        self.set_flag(SREG_Z, False)
        self.set_flag(SREG_C, False)
        self.set_flag(SREG_H, False)

    def op_div(self, rd: int, rr: int):
        """Unsigned divide convenience instruction: quotient -> Rd, remainder -> Rd+1."""
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        if b == 0:
            self.write_reg(rd, 0)
            # indicate error
            self.set_flag(SREG_C, True)
            self.set_flag(SREG_Z, True)
            return
        q = a // b
        r = a % b
        self.write_reg(rd, q)
        if rd + 1 < 32:
            self.write_reg(rd + 1, r)
        # update flags: Z if quotient zero; clear others conservatively
        self.set_flag(SREG_Z, q == 0)
        self.set_flag(SREG_C, False)
        self.set_flag(SREG_H, False)
        self.set_flag(SREG_V, False)

    def op_in(self, rd: int, port: int):
        val = self.read_ram(port)
        self.write_reg(rd, val)

    def op_out(self, port: int, rr: int):
        val = self.read_reg(rr)
        self.write_ram(port, val)

    def op_jmp(self, label: str | int):
        """Jump to a given label or numeric address by updating the program counter.

        This operation sets the CPU's program counter (self.pc) to the target address minus one.
        The subtraction of one accounts for the fact that the instruction dispatcher will typically
        increment the program counter after the current instruction completes.

        Args:
            label (str | int): The jump target. If a string, it is treated as a symbolic label
                and looked up in self.labels to obtain its numeric address. If an int (or any
                value convertible to int), it is used directly as the numeric address.
        """

        if isinstance(label, str):
            if label not in self.labels:
                raise KeyError(f"Label {label} not found")
            self.pc = self.labels[label] - 1
        else:
            self.pc = int(label) - 1

    def op_cpi(self, rd: int, imm: int):
        a = self.read_reg(rd)
        b = imm & 0xFF
        res = a - b
        self._set_flags_sub(a, b, 0, res)

    def op_cp(self, rd: int, rr: int):
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        res = a - b
        self._set_flags_sub(a, b, 0, res)

    def op_lsl(self, rd: int):
        v = self.read_reg(rd)
        carry = (v >> 7) & 1
        nv = (v << 1) & 0xFF
        self.write_reg(rd, nv)
        # C from old MSB
        self.set_flag(SREG_C, bool(carry))
        n = (nv >> 7) & 1
        # V = N xor C per AVR for LSL
        vflag = 1 if (n ^ carry) else 0
        s = n ^ vflag
        self.set_flag(SREG_N, bool(n))
        self.set_flag(SREG_V, bool(vflag))
        self.set_flag(SREG_S, bool(s))
        self.set_flag(SREG_Z, nv == 0)
        self.set_flag(SREG_H, False)

    def op_lsr(self, rd: int):
        v = self.read_reg(rd)
        carry = v & 1
        nv = (v >> 1) & 0xFF
        self.write_reg(rd, nv)
        self.set_flag(SREG_C, bool(carry))
        # N becomes 0 after logical shift right
        self.set_flag(SREG_N, False)
        # V = N xor C -> 0 xor C
        self.set_flag(SREG_V, bool(carry))
        self.set_flag(SREG_S, bool(False ^ carry))
        self.set_flag(SREG_Z, nv == 0)
        self.set_flag(SREG_H, False)

    def op_rol(self, rd: int):
        v = self.read_reg(rd)
        carry_in = 1 if self.get_flag(SREG_C) else 0
        carry_out = (v >> 7) & 1
        nv = ((v << 1) & 0xFF) | carry_in
        self.write_reg(rd, nv)
        self.set_flag(SREG_C, bool(carry_out))
        self.set_flag(SREG_N, bool((nv >> 7) & 1))
        self.set_flag(SREG_Z, nv == 0)
        self.set_flag(SREG_V, False)
        self.set_flag(SREG_S, bool(((nv >> 7) & 1) ^ 0))
        self.set_flag(SREG_H, False)

    def op_ror(self, rd: int):
        v = self.read_reg(rd)
        carry_in = 1 if self.get_flag(SREG_C) else 0
        carry_out = v & 1
        nv = (v >> 1) | (carry_in << 7)
        self.write_reg(rd, nv)
        self.set_flag(SREG_C, bool(carry_out))
        self.set_flag(SREG_N, bool((nv >> 7) & 1))
        self.set_flag(SREG_Z, nv == 0)
        self.set_flag(SREG_V, False)
        self.set_flag(SREG_S, bool(((nv >> 7) & 1) ^ 0))
        self.set_flag(SREG_H, False)

    def op_com(self, rd: int):
        """One's complement: Rd := ~Rd. Updates N,V,S,Z,C per AVR-ish semantics."""
        v = self.read_reg(rd)
        nv = (~v) & 0xFF
        self.write_reg(rd, nv)
        n = (nv >> 7) & 1
        vflag = 0
        s = n ^ vflag
        z = 1 if nv == 0 else 0
        # COM sets Carry in AVR
        self.set_flag(SREG_N, bool(n))
        self.set_flag(SREG_V, bool(vflag))
        self.set_flag(SREG_S, bool(s))
        self.set_flag(SREG_Z, bool(z))
        self.set_flag(SREG_C, True)
        self.set_flag(SREG_H, False)

    def op_neg(self, rd: int):
        """Two's complement (negate): Rd := 0 - Rd. Flags as subtraction from 0."""
        a = self.read_reg(rd)
        res_full = 0 - a
        self.write_reg(rd, res_full & 0xFF)
        # use subtraction helper (0 - a)
        self._set_flags_sub(0, a, 0, res_full)

    def op_swap(self, rd: int):
        """Swap nibbles in register: Rd[7:4] <-> Rd[3:0]. Does not affect SREG."""
        v = self.read_reg(rd)
        nv = ((v & 0x0F) << 4) | ((v >> 4) & 0x0F)
        self.write_reg(rd, nv)

    def op_tst(self, rd: int):
        """Test: perform AND Rd,Rd and update flags but do not store result."""
        v = self.read_reg(rd)
        res = v & v
        # logical helper clears C/V/H and sets N/Z/S
        self._set_flags_logical(res)

    def op_andi(self, rd: int, imm: int):
        res = self.read_reg(rd) & (imm & 0xFF)
        self.write_reg(rd, res)
        self._set_flags_logical(res)

    def op_ori(self, rd: int, imm: int):
        res = self.read_reg(rd) | (imm & 0xFF)
        self.write_reg(rd, res)
        self._set_flags_logical(res)

    def op_eori(self, rd: int, imm: int):
        res = self.read_reg(rd) ^ (imm & 0xFF)
        self.write_reg(rd, res)
        self._set_flags_logical(res)

    def op_subi(self, rd: int, imm: int):
        a = self.read_reg(rd)
        b = imm & 0xFF
        res_full = a - b
        self.write_reg(rd, res_full & 0xFF)
        self._set_flags_sub(a, b, 0, res_full)

    def op_sbc(self, rd: int, rr: int):
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        borrow_in = 1 if self.get_flag(SREG_C) else 0
        res_full = a - b - borrow_in
        self.write_reg(rd, res_full & 0xFF)
        self._set_flags_sub(a, b, borrow_in, res_full)

    def op_sbci(self, rd: int, imm: int):
        """Subtract immediate with carry: Rd := Rd - K - C"""
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
        """Compare and Skip if Equal: compare Rd,Rr; if equal, skip next instruction."""
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        # set compare flags like CP
        self._set_flags_sub(a, b, 0, a - b)
        if a == b:
            # skip next instruction by advancing PC by one (step() will add one more)
            self.pc += 1

    def op_sbrs(self, rd: int, bit: int):
        """Skip next if bit in register is set."""
        v = self.read_reg(rd)
        if ((v >> (bit & 7)) & 1) == 1:
            self.pc += 1

    def op_sbrc(self, rd: int, bit: int):
        """Skip next if bit in register is clear."""
        v = self.read_reg(rd)
        if ((v >> (bit & 7)) & 1) == 0:
            self.pc += 1

    def op_sbis(self, io_addr: int, bit: int):
        """Skip if bit in IO/RAM-mapped address is set."""
        v = self.read_ram(io_addr)
        if ((v >> (bit & 7)) & 1) == 1:
            self.pc += 1

    def op_sbic(self, io_addr: int, bit: int):
        """Skip if bit in IO/RAM-mapped address is clear."""
        v = self.read_ram(io_addr)
        if ((v >> (bit & 7)) & 1) == 0:
            self.pc += 1

    def op_sbiw(self, rd_word_low: int, imm_word: int):
        """Subtract immediate from word register pair (Rd:Rd+1) — simplified.

        rd_word_low is the low register of the pair (even register index).
        imm_word is a 16-bit immediate to subtract.
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
        # precise flags for 16-bit subtraction
        self._set_flags_sub16(word, imm_word & 0xFFFF, 0, word - (imm_word & 0xFFFF))

    def op_adiw(self, rd_word_low: int, imm_word: int):
        """Add immediate to word register pair (Rd:Rd+1) - simplified.

        rd_word_low is the low register of the pair (even register index).
        imm_word is a 16-bit immediate to add.
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
        # precise flags for 16-bit addition
        self._set_flags_add16(word, imm_word & 0xFFFF, 0, word + (imm_word & 0xFFFF))

    def op_rjmp(self, label: str):
        """Relative jump — label may be an int or string label."""
        # reuse op_jmp behavior (op_jmp sets PC to label-1).
        # If label is a relative offset integer, set pc accordingly.
        if isinstance(label, int):
            self.pc = self.pc + int(label)
        else:
            self.op_jmp(label)

    def op_rcall(self, label: str):
        """Relative call — push return address and jump relatively or to label."""
        ret = self.pc + 1
        self.write_ram(self.sp, (ret >> 8) & 0xFF)
        self.sp -= 1
        self.write_ram(self.sp, ret & 0xFF)
        self.sp -= 1
        if isinstance(label, int):
            # For numeric relative offsets, behave like op_jmp which sets
            # pc = target - 1 (step() will increment after execution).
            # Calculate absolute target and adjust similarly.
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
        """BRGE - Branch if Greater or Equal (Signed)

        Args:
            label: Destination label or address to jump to if the condition is met.
        """

        s = self.get_flag(SREG_S)
        if not s:
            self.op_jmp(label)

    def op_brlt(self, label: str | int):
        """BRLT - Branch if Less Than (Signed).

        Args:
            label: Destination label or address to jump to if the condition is met.
        """

        s = self.get_flag(SREG_S)
        if s:
            self.op_jmp(label)

    def op_push(self, rr: int):
        """Push a register value onto the stack.

        The value of register ``rr`` is written to the RAM at the current
        stack pointer, and the stack pointer is then decremented.

        Args:
            rr (int): Source register index to push.
        """
        val = self.read_reg(rr)
        self.write_ram(self.sp, val)
        self.sp -= 1

    def op_pop(self, rd: int):
        """Pop a value from the stack into a register.

        The stack pointer is incremented, the byte at the new stack pointer
        is read from RAM, and the value is written into register ``rd``.

        Args:
            rd (int): Destination register index to receive the popped value.
        """
        self.sp += 1
        val = self.read_ram(self.sp)
        self.write_reg(rd, val)

    def op_call(self, label: str):
        """Call a subroutine by pushing the return address and jumping to label.

        The return address (pc+1) is pushed as two bytes (high then low) onto
        the stack, decrementing the stack pointer after each write. Control
        then jumps to ``label``.

        Args:
            label (str): Label to call.
        """
        # push return address (pc+1)
        ret = self.pc + 1
        self.write_ram(self.sp, (ret >> 8) & 0xFF)
        self.sp -= 1
        self.write_ram(self.sp, ret & 0xFF)
        self.sp -= 1
        self.op_jmp(label)

    def op_ret(self):
        """Return from subroutine by popping the return address and setting PC.

        Two bytes are popped from the stack (low then high) to reconstruct the
        return address, which is then loaded into the program counter
        (adjusted because step() will increment PC after execution).
        """
        # pop return address
        self.sp += 1
        low = self.read_ram(self.sp)
        self.sp += 1
        high = self.read_ram(self.sp)
        ret = (high << 8) | low
        self.pc = ret - 1

    def op_reti(self):
        """Return from interrupt: pop return address and set I flag."""
        # similar to ret, but also set Global Interrupt Enable
        self.sp += 1
        low = self.read_ram(self.sp)
        self.sp += 1
        high = self.read_ram(self.sp)
        ret = (high << 8) | low
        self.set_flag(SREG_I, True)
        self.pc = ret - 1

    # Interrupt handling (very simple)
    def trigger_interrupt(self, vector_addr: int):
        """Trigger an interrupt vector if it is enabled.

        If the interrupt vector is enabled in ``self.interrupts``, the current
        PC+1 is pushed onto the stack (high then low byte) and control jumps
        to ``vector_addr``.

        Args:
            vector_addr (int): Interrupt vector address to jump to.

        Returns:
            None
        """
        if not self.interrupts.get(vector_addr, False):
            return
        # push PC and jump to vector
        ret = self.pc + 1
        self.write_ram(self.sp, (ret >> 8) & 0xFF)
        self.sp -= 1
        self.write_ram(self.sp, ret & 0xFF)
        self.sp -= 1
        self.pc = vector_addr - 1
