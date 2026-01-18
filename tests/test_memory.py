"""Memory subsystem tests.

Tests for RAM, ROM operations, memory snapshots, and edge cases.
"""

from pathlib import Path
import pytest

from tiny8 import CPU, assemble, compile_c_file_with_symbols
from tiny8.memory import Memory
from tiny8.tui import Tiny8App


class TestMemoryBasicOperations:
    """Test basic memory read/write operations."""

    def test_load_rom_oversized(self):
        """Test loading oversized ROM."""
        mem = Memory(rom_size=10)
        program = list(range(20))  # Larger than rom_size
        with pytest.raises(ValueError, match="ROM image too large"):
            mem.load_rom(program)

    def test_ram_out_of_bounds_read(self):
        """Test RAM out of bounds read."""
        mem = Memory(ram_size=10)
        with pytest.raises(IndexError):
            mem.read_ram(100)

    def test_ram_out_of_bounds_write(self):
        """Test RAM out of bounds write."""
        mem = Memory(ram_size=10)
        with pytest.raises(IndexError):
            mem.write_ram(100, 42)

    def test_rom_out_of_bounds_read(self):
        """Test ROM out of bounds read."""
        mem = Memory(rom_size=10)
        with pytest.raises(IndexError):
            mem.read_rom(100)

    def test_write_ram_preserves_mask(self):
        """Test that write_ram preserves 8-bit mask."""
        mem = Memory(ram_size=10)
        mem.write_ram(5, 256)  # Overflow
        assert mem.read_ram(5) == 0  # 256 & 0xFF = 0

    def test_load_rom_preserves_mask(self):
        """Test that load_rom preserves 8-bit mask."""
        mem = Memory(rom_size=10)
        mem.load_rom([256, 257, 258])
        assert mem.read_rom(0) == 0  # 256 & 0xFF
        assert mem.read_rom(1) == 1  # 257 & 0xFF
        assert mem.read_rom(2) == 2  # 258 & 0xFF


class TestMemoryChangeTracking:
    """Test memory change tracking."""

    def test_write_ram_change_tracking(self):
        """Test that RAM changes are tracked."""
        mem = Memory(ram_size=10)
        mem.write_ram(5, 42, step=1)
        assert len(mem.ram_changes) == 1
        assert mem.ram_changes[0] == (5, 0, 42, 1)

    def test_load_rom_empty(self):
        """Test loading empty ROM."""
        mem = Memory(rom_size=10)
        mem.load_rom([])
        assert mem.read_rom(0) == 0

    def test_load_rom_changes_tracking(self):
        """Test that ROM changes are tracked."""
        mem = Memory(rom_size=10)
        mem.load_rom([1, 2, 3])
        assert len(mem.rom_changes) >= 3


class TestMemorySnapshots:
    """Test memory snapshot methods."""

    def test_snapshot_ram(self):
        """Test RAM snapshot."""
        mem = Memory(ram_size=10)
        mem.write_ram(5, 42)
        snapshot = mem.snapshot_ram()
        assert snapshot[5] == 42
        assert len(snapshot) == 10
        snapshot[5] = 99
        assert mem.read_ram(5) == 42

    def test_snapshot_rom(self):
        """Test ROM snapshot."""
        mem = Memory(rom_size=10)
        mem.load_rom([1, 2, 3])
        snapshot = mem.snapshot_rom()
        assert snapshot[0] == 1
        assert snapshot[1] == 2
        assert len(snapshot) == 10
        snapshot[0] = 99
        assert mem.read_rom(0) == 1

    def test_restore_ram_and_untracked_rom(self):
        """Test restore_ram and load_rom when track_changes is False."""
        mem = Memory(ram_size=20, rom_size=20, track_changes=False)
        mem.load_rom([10, 20, 30])
        assert mem.read_rom(0) == 10
        assert mem.read_rom(1) == 20
        assert len(mem.rom_changes) == 0

        # Write initial non-zero
        mem.write_ram(3, 100)
        assert mem.read_ram(3) == 100

        # Restore from dict with different keys and in-range values
        mem.restore_ram({5: 250, 7: 15})
        assert mem.read_ram(3) == 0
        assert mem.read_ram(5) == 250
        assert mem.read_ram(7) == 15


class TestMemoryOptimizationAndTraceBounds:
    """Test memory optimization, bounded trace history, and trace lifecycle."""

    def test_cpu_trace_bounded_during_long_run(self):
        """Verify that step_trace, reg_trace, and mem_trace do not grow unboundedly."""
        asm_src = """
        loop:
            ldi r16, 1
            ldi r17, 2
            add r16, r17
            rjmp loop
        """
        asm = assemble(asm_src)
        cpu = CPU(max_trace_steps=50, max_trace_history=100)
        cpu.load_program(asm)
        cpu.run(max_steps=5000, show_progress=False)

        assert cpu.step_count == 5000
        assert len(cpu.step_trace) <= 50
        assert len(cpu.reg_trace) <= 100
        assert len(cpu.mem_trace) <= 100
        assert len(cpu.mem.ram_changes) <= cpu.mem.max_changes

    def test_cpu_tracing_disabled_skips_trace_allocations(self):
        """Verify that disabling tracing produces no trace entries."""
        asm_src = """
        loop:
            ldi r16, 42
            sts 0x0100, r16
            rjmp loop
        """
        asm = assemble(asm_src)
        cpu = CPU()
        cpu.load_program(asm)
        cpu.trace_enabled = False
        cpu.mem.track_changes = False

        for _ in range(500):
            cpu.step(record_trace=False)

        assert cpu.step_count == 500
        assert len(cpu.step_trace) == 0
        assert len(cpu.reg_trace) == 0
        assert len(cpu.mem_trace) == 0
        assert len(cpu.mem.ram_changes) == 0

    def test_simulation_memory_bounded(self):
        """Simulate execution and verify memory and traces remain strictly bounded."""
        factorial_c = Path(__file__).parent.parent / "examples" / "factorial.c"
        asm_code, symbols = compile_c_file_with_symbols(str(factorial_c))
        asm = assemble(asm_code)

        cpu = CPU()
        cpu.load_program(asm)
        cpu.source_lines = factorial_c.read_text(encoding="utf-8").splitlines()
        cpu.pc_to_line = asm.pc_to_line
        cpu.run(max_steps=1000, show_progress=False)

        app = Tiny8App(
            cpu=cpu, file_path=str(factorial_c), max_steps=1000, var_symbols=symbols
        )

        for _ in range(20):
            cpu.run(max_steps=3000, show_progress=False)

        assert len(app.traces) <= 1000
        assert len(cpu.step_trace) <= cpu.max_trace_steps
        assert len(cpu.reg_trace) <= cpu.max_trace_history
        assert len(cpu.mem_trace) <= cpu.max_trace_history

    def test_clear_traces(self):
        """Verify clear_traces empties all trace lists and change logs."""
        cpu = CPU()
        cpu.write_reg(16, 42)
        cpu.write_ram(0x50, 99)
        cpu.step_trace.append({"step": 1})

        assert len(cpu.reg_trace) > 0
        assert len(cpu.mem_trace) > 0
        assert len(cpu.mem.ram_changes) > 0
        assert len(cpu.step_trace) > 0

        cpu.clear_traces()
        assert len(cpu.reg_trace) == 0
        assert len(cpu.mem_trace) == 0
        assert len(cpu.mem.ram_changes) == 0
        assert len(cpu.step_trace) == 0
