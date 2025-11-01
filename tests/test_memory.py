"""Memory subsystem tests.

Tests for RAM, ROM operations, memory snapshots, and edge cases.
"""

import pytest

from tiny8.memory import Memory


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
