"""A simplified AVR-like 8-bit CPU simulator.

This module provides a lightweight CPU model inspired by the ATmega family.
The :class:`CPU` class is the primary export and implements a small, extensible instruction-dispatch model.

Example:
    from tiny8.cpu import CPU
    from tiny8.memory import Memory

    cpu = CPU(Memory())
    # load a simple program (assumed assembled elsewhere)
    cpu.load_program([("ldi", (0, 10)), ("ldi", (1, 20)), ("add", (0, 1))], {})
    cpu.run()
    print(cpu.regs[0])  # usually 30

The implementation favors readability over cycle-accurate emulation. Add
instruction handlers by defining methods named ``op_<mnemonic>`` on
``CPU``.
"""

from typing import Dict, List, Optional, Tuple

from .memory import Memory

# SREG flag bit positions and short descriptions.
#
# Canonical AVR SREG layout (bit indices):
# 7: I  - Global Interrupt Enable
# 6: T  - Bit copy storage
# 5: H  - Half Carry (BC/ADC nibble carry)
# 4: S  - Sign (N ^ V)
# 3: V  - Two's complement overflow
# 2: N  - Negative (MSB of result)
# 1: Z  - Zero flag
# 0: C  - Carry flag

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
        regs (List[int]): 32 8-bit general purpose registers (R0..R31).
        pc (int): Program counter (index into ``program``).
        sp (int): Stack pointer (index into RAM in the associated
            :class:`tiny8.memory.Memory`).
        sreg (int): Status register bits stored in a single integer (I, T,
            H, S, V, N, Z, C).
        cycle (int): Instruction execution counter.
        reg_trace (List[Tuple[int, int, int]]): Per-cycle register change
            trace entries of the form ``(cycle, reg, new_value)``.
        mem_trace (List[Tuple[int, int, int]]): Per-cycle memory change
            trace entries of the form ``(cycle, addr, new_value)``.
        step_trace (List[dict]): Full per-step snapshots useful for
            visualization and debugging.

    Note:
        This implementation simplifies many AVR specifics (flag semantics,
        exact cycle counts, IO mapping) in favor of clarity. Extend or
        replace individual ``op_`` handlers to increase fidelity.
    """

    def __init__(self, memory: Optional[Memory] = None):
        self.mem = memory or Memory()
        # 32 general purpose 8-bit registers R0-R31
        self.regs: List[int] = [0] * 32
        # Program Counter (word-addressable for AVR) - we use byte addressing for simplicity
        self.pc: int = 0
        # Stack Pointer - point into RAM
        self.sp: int = self.mem.ram_size - 1
        # Status register (SREG) flags: I T H S V N Z C - store as bits in an int
        self.sreg: int = 0
        # Cycle counter
        self.cycle: int = 0
        # Simple interrupt vector table (addr->enabled)
        self.interrupts: Dict[int, bool] = {}
        # Execution trace of register/memory changes per cycle
        self.reg_trace: List[Tuple[int, int, int]] = []  # (cycle, reg, newval)
        self.mem_trace: List[Tuple[int, int, int]] = []  # (cycle, addr, newval)
        # Full step trace: list of dicts with cycle, pc, instr_text, regs snapshot, optional mem snapshot
        self.step_trace: List[dict] = []
        # Program area - list of instructions as tuples: (mnemonic, *operands)
        self.program: List[Tuple[str, Tuple]] = []
        # Labels -> pc
        self.labels: Dict[str, int] = {}
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
    def load_program(self, program: List[Tuple[str, Tuple]], labels: Dict[str, int]):
        """Load an assembled program into the CPU.

        Args:
            program: List of ``(mnemonic, operands)`` tuples returned by the
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
        """Add register ``rr`` to ``rd``, store low byte in ``rd``, and set
        flags.

        Args:
            rd: Destination register index.
            rr: Source register index.

        Note:
            Sets a simplified carry flag in bit 0 and the zero flag when the
            result is zero.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        res = a + b
        self.write_reg(rd, res)
        carry = (res & 0x100) != 0
        res8 = res & 0xFF
        self.set_flag(SREG_C, carry)  # C as bit0 simplification
        # set Z flag if zero
        self.set_flag(SREG_Z, res8 == 0)

    def op_and(self, rd: int, rr: int):
        """Bitwise AND: ``rd`` <- ``rd`` & ``rr``.

        Args:
            rd: Destination register index.
            rr: Source register index.
        """
        res = self.read_reg(rd) & self.read_reg(rr)
        self.write_reg(rd, res)

    def op_or(self, rd: int, rr: int):
        """Bitwise OR: ``rd`` <- ``rd`` | ``rr``.

        Args:
            rd: Destination register index.
            rr: Source register index.
        """
        res = self.read_reg(rd) | self.read_reg(rr)
        self.write_reg(rd, res)

    def op_eor(self, rd: int, rr: int):
        """Bitwise XOR (EOR): ``rd`` <- ``rd`` ^ ``rr``.

        Args:
            rd: Destination register index.
            rr: Source register index.
        """
        res = self.read_reg(rd) ^ self.read_reg(rr)
        self.write_reg(rd, res)

    def op_sub(self, rd: int, rr: int):
        """Subtract ``rr`` from ``rd``, store low byte in ``rd`` and set Z
        flag.

        Args:
            rd: Destination register index.
            rr: Source register index.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        res = (a - b) & 0x1FF
        res8 = res & 0xFF
        self.write_reg(rd, res8)
        # set Z flag if result is zero
        self.set_flag(SREG_Z, res8 == 0)

    def op_inc(self, rd: int):
        """Increment register ``rd`` by 1 (8-bit wrap-around).

        Args:
            rd: Register index to increment.
        """
        v = (self.read_reg(rd) + 1) & 0xFF
        self.write_reg(rd, v)

    def op_dec(self, rd: int):
        """Decrement register ``rd`` by 1 (8-bit wrap-around).

        Args:
            rd: Register index to decrement.
        """
        v = (self.read_reg(rd) - 1) & 0xFF
        self.write_reg(rd, v)

    def op_mul(self, rd: int, rr: int):
        """Multiply ``rd`` by ``rr``; store low byte in ``rd`` and high
        byte in ``rd+1``.

        Args:
            rd: Destination register index (multiplicand).
            rr: Source register index (multiplier).

        Note:
            This simplified MUL writes the 16-bit product across two
            registers when possible: low byte to ``rd`` and high byte to
            ``rd+1``.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        prod = a * b
        # store lower 8 in rd, upper 8 in rd+1 if exists
        self.write_reg(rd, prod & 0xFF)
        if rd + 1 < 32:
            self.write_reg(rd + 1, (prod >> 8) & 0xFF)

    def op_adc(self, rd: int, rr: int):
        """Add register ``rr`` plus carry to ``rd`` (ADC).

        Args:
            rd: Destination register index.
            rr: Source register index.

        Note:
            Carry input is read from the SREG carry bit.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        carry_in = 1 if self.get_flag(SREG_C) else 0
        res = a + b + carry_in
        carry = (res & 0x100) != 0
        res8 = res & 0xFF
        self.write_reg(rd, res8)
        self.set_flag(SREG_C, carry)
        self.set_flag(SREG_Z, res8 == 0)

    def op_clr(self, rd: int):
        """Clear register ``rd`` to zero.

        Args:
            rd: Register index to clear.
        """
        self.write_reg(rd, 0)

    def op_ser(self, rd: int):
        """Set all bits in register ``rd`` (write 0xFF).

        Args:
            rd: Register index to set to 0xFF.
        """
        self.write_reg(rd, 0xFF)

    def op_div(self, rd: int, rr: int):
        """Divide ``rd`` by ``rr`` storing quotient in ``rd`` and remainder
        in ``rd+1``.

        Args:
            rd: Dividend register (also destination for quotient).
            rr: Divisor register.

        Note:
            If divisor is zero, ``rd`` is set to 0 and the carry flag is set.
        """
        a = self.read_reg(rd)
        b = self.read_reg(rr)
        if b == 0:
            # set zero reg to 0 and set a flag
            self.write_reg(rd, 0)
            self.set_flag(SREG_C, True)
            return
        q = a // b
        r = a % b
        self.write_reg(rd, q)
        if rd + 1 < 32:
            self.write_reg(rd + 1, r)

    def op_in(self, rd: int, port: int):
        """Read from IO/memory-mapped ``port`` into register ``rd``.

        Args:
            rd: Destination register index.
            port: IO/memory-mapped port (treated as RAM address here).

        Note:
            This implementation reads from RAM for simplicity.
        """
        val = self.read_ram(port)
        self.write_reg(rd, val)

    def op_out(self, port: int, rr: int):
        """Write register ``rr`` to IO/memory-mapped ``port`` (stored in
        RAM).

        Args:
            port: IO/memory-mapped port (treated as RAM address here).
            rr: Source register index to write.
        """
        val = self.read_reg(rr)
        self.write_ram(port, val)

    def op_jmp(self, label: str):
        """Jump to a label or numeric PC value.

        Args:
            label: Label string or numeric program counter value.

        Note:
            The assembler provides label -> index mappings in ``self.labels``.
            The stored PC is decremented by one because :meth:`step` will
            increment it after the instruction executes.
        """
        if isinstance(label, str):
            if label not in self.labels:
                raise KeyError(f"Label {label} not found")
            self.pc = (
                self.labels[label] - 1
            )  # -1 because PC will be incremented after step
        else:
            self.pc = int(label) - 1

    def op_cpi(self, rd: int, imm: int):
        """Compare register ``rd`` with immediate and set Z flag if equal.

        Args:
            rd: Register index to compare.
            imm: Immediate value to compare with.
        """
        # compare with immediate: set Z flag if equal
        v = self.read_reg(rd)
        z = v == (imm & 0xFF)
        self.set_flag(SREG_Z, z)

    def op_cp(self, rd: int, rr: int):
        """Compare ``rd`` with ``rr`` and set Z and C flags.

        Args:
            rd: First operand register index.
            rr: Second operand register index.

        Note:
            This is a simplified unsigned compare: C bit indicates ``rd`` >
            ``rr``.
        """
        v = self.read_reg(rd)
        w = self.read_reg(rr)
        # set Z flag if equal
        # set C flag (bit 0) if rd > rr for unsigned compare (we treat C as 'greater')
        self.set_flag(SREG_Z, v == w)
        self.set_flag(SREG_C, v > w)

    def op_lsl(self, rd: int):
        """Logical shift left: shift bits left by one; MSB becomes carry.

        Args:
            rd: Register index to shift.
        """
        v = self.read_reg(rd)
        carry = (v >> 7) & 1
        nv = (v << 1) & 0xFF
        self.write_reg(rd, nv)
        self.set_flag(SREG_C, bool(carry))

    def op_lsr(self, rd: int):
        """Logical shift right: LSB becomes carry, MSB filled with zero.

        Args:
            rd: Register index to shift.
        """
        v = self.read_reg(rd)
        carry = v & 1
        nv = (v >> 1) & 0xFF
        self.write_reg(rd, nv)
        self.set_flag(SREG_C, bool(carry))

    def op_rol(self, rd: int):
        """Rotate left through carry: MSB moves to carry, carry is shifted
        in.

        Args:
            rd: Register index to rotate.
        """
        v = self.read_reg(rd)
        carry_in = 1 if self.get_flag(SREG_C) else 0
        carry_out = (v >> 7) & 1
        nv = ((v << 1) & 0xFF) | carry_in
        self.write_reg(rd, nv)
        self.set_flag(SREG_C, bool(carry_out))

    def op_ror(self, rd: int):
        """Rotate right through carry: LSB moves to carry, carry is
        shifted in.

        Args:
            rd: Register index to rotate.
        """
        v = self.read_reg(rd)
        carry_in = 1 if self.get_flag(SREG_C) else 0
        carry_out = v & 1
        nv = (v >> 1) | (carry_in << 7)
        self.write_reg(rd, nv)
        self.set_flag(SREG_C, bool(carry_out))

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
