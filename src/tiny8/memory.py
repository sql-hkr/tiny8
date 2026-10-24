"""Memory model for tiny8 providing RAM and ROM with change tracking."""

from collections import deque


class Memory:
    """Byte-addressable RAM/ROM memory subsystem.

    Maintains separate RAM and ROM buffers as 8-bit unsigned bytes (0-255)
    and logs modifications for tracing and visualization.

    Args:
        ram_size: Number of bytes in RAM. Defaults to 65536.
        rom_size: Number of bytes in ROM. Defaults to 2048.

    Attributes:
        ram_size: Size of RAM in bytes.
        rom_size: Size of ROM in bytes.
        ram: Bytearray representing RAM contents.
        rom: Bytearray representing ROM contents.
        ram_changes: Log of RAM writes as (addr, old_val, new_val, step) tuples.
        rom_changes: Log of ROM writes as (addr, old_val, new_val, step) tuples.
    """

    __slots__ = (
        "ram_size",
        "rom_size",
        "max_changes",
        "track_changes",
        "ram",
        "rom",
        "nonzero_ram",
        "ram_changes",
        "rom_changes",
    )

    def __init__(
        self,
        ram_size: int = 65536,
        rom_size: int = 2048,
        max_changes: int = 2000,
        track_changes: bool = True,
    ) -> None:
        self.ram_size = ram_size
        self.rom_size = rom_size
        self.max_changes = max_changes
        self.track_changes = track_changes
        self.ram = bytearray(ram_size)
        self.rom = bytearray(rom_size)
        self.nonzero_ram: dict[int, int] = {}
        self.ram_changes: deque[tuple[int, int, int, int]] = deque(maxlen=max_changes)
        self.rom_changes: deque[tuple[int, int, int, int]] = deque(maxlen=max_changes)

    def read_ram(self, addr: int) -> int:
        """Read a byte from RAM.

        Args:
            addr: Memory address in the range [0, ram_size).

        Returns:
            The byte value stored at the address.

        Raises:
            IndexError: If addr is outside valid RAM boundaries.
        """
        if not (0 <= addr < self.ram_size):
            raise IndexError("RAM address out of range")
        return self.ram[addr]

    def write_ram(self, addr: int, value: int, step: int = 0) -> None:
        """Write a byte to RAM and log change if value changed.

        Args:
            addr: Memory address in the range [0, ram_size).
            value: Byte value to store (masked to 8-bit).
            step: Step index associated with this write. Defaults to 0.

        Raises:
            IndexError: If addr is outside valid RAM boundaries.
        """
        if not (0 <= addr < self.ram_size):
            raise IndexError("RAM address out of range")
        old = self.ram[addr]
        new = value & 0xFF
        if old == new:
            return
        self.ram[addr] = new
        if self.track_changes:
            self.ram_changes.append((addr, old, new, step))
        if new != 0:
            self.nonzero_ram[addr] = new
        elif old != 0:
            self.nonzero_ram.pop(addr, None)

    def clear_changes(self) -> None:
        """Clear memory modification history to free memory."""
        self.ram_changes.clear()
        self.rom_changes.clear()

    def restore_ram(self, mem_dict: dict[int, int]) -> None:
        """Restore RAM contents from a dictionary of non-zero entries."""
        for addr in list(self.nonzero_ram.keys()):
            self.ram[addr] = 0
        self.nonzero_ram = dict(mem_dict)
        for addr, val in self.nonzero_ram.items():
            if 0 <= addr < self.ram_size:
                self.ram[addr] = val & 0xFF

    def load_rom(self, data: list[int]) -> None:
        """Load byte sequence into ROM and record changes.

        Args:
            data: Sequence of byte values to load into ROM.

        Raises:
            ValueError: If data length exceeds configured rom_size.
        """
        if len(data) > self.rom_size:
            raise ValueError("ROM image too large")
        if self.track_changes:
            for i, v in enumerate(data):
                old = self.rom[i]
                new = v & 0xFF
                self.rom[i] = new
                if old != new:
                    self.rom_changes.append((i, old, new, 0))
        else:
            for i, v in enumerate(data):
                self.rom[i] = v & 0xFF

    def read_rom(self, addr: int) -> int:
        """Read a byte from ROM.

        Args:
            addr: ROM address in the range [0, rom_size).

        Returns:
            The byte value stored at the address.

        Raises:
            IndexError: If addr is outside valid ROM boundaries.
        """
        if not (0 <= addr < self.rom_size):
            raise IndexError("ROM address out of range")
        return self.rom[addr]

    def snapshot_ram(self) -> list[int]:
        """Return a shallow copy of RAM contents.

        Returns:
            List of integers representing current RAM.
        """
        return list(self.ram)

    def snapshot_rom(self) -> list[int]:
        """Return a shallow copy of ROM contents.

        Returns:
            List of integers representing current ROM.
        """
        return list(self.rom)
