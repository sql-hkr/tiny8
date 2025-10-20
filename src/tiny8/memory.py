"""Memory model for tiny8 - simple RAM and ROM with change tracking."""

from typing import List, Tuple


class Memory:
    """
    Memory class for a simple byte-addressable RAM/ROM model.

    This class provides a minimal memory subsystem with separate RAM and ROM
    regions, change-logging for writes/loads, and convenience snapshot
    methods. All stored values are maintained as 8-bit unsigned bytes
    (0-255).

    Args:
        ram_size: Number of bytes in RAM (default 2048).
        rom_size: Number of bytes in ROM (default 2048).

    Attributes:
        ram: Mutable list representing RAM contents (each element 0-255).
        rom: Mutable list representing ROM contents (each element 0-255).
        ram_changes: Change log for RAM writes. Each entry is a tuple
            (addr, old_value, new_value, cycle) appended only when a write
            changes the stored byte.
        rom_changes: Change log for ROM loads. Each entry is a tuple
            (addr, old_value, new_value, cycle) appended when load_rom
            changes bytes.

    Notes:
        - All write/load operations mask values with 0xFF so stored values are
          always in the range 0..255.
        - ram_changes and rom_changes record only actual changes (old != new).
        - read_* methods perform bounds checking and raise IndexError for
          invalid addresses.
        - load_rom accepts an iterable of integers and raises ValueError if
          the input is larger than the configured ROM size.
    """

    def __init__(self, ram_size: int = 2048, rom_size: int = 2048):
        self.ram_size = ram_size
        self.rom_size = rom_size
        self.ram = [0] * ram_size
        self.rom = [0] * rom_size
        # change logs: list of (addr, old, new, cycle)
        self.ram_changes: List[Tuple[int, int, int, int]] = []
        self.rom_changes: List[Tuple[int, int, int, int]] = []

    def read_ram(self, addr: int) -> int:
        """Read and return the value stored in RAM at the specified address.

        Args:
            addr: The RAM address to read. Must be within the valid range
                0 <= addr < self.ram_size.

        Returns:
            The integer value stored at the given RAM address.

        Raises:
            IndexError: If the provided addr is negative or not less than
                self.ram_size.
        """
        if addr < 0 or addr >= self.ram_size:
            raise IndexError("RAM address out of range")
        return self.ram[addr]

    def write_ram(self, addr: int, value: int, cycle: int = 0) -> None:
        """Write a byte to RAM at the specified address.

        Args:
            addr: Target RAM address. Must be in the range [0, self.ram_size).
            value: Value to write; only the low 8 bits are stored (value & 0xFF).
            cycle: Optional cycle/timestamp associated with this write; defaults
                to 0.

        Raises:
            IndexError: If addr is out of the valid RAM range.

        Notes:
            The provided value is masked to a single byte before storing. If
            the stored byte changes, a record (addr, old_value, new_value,
            cycle) is appended to self.ram_changes to track the modification.
        """
        if addr < 0 or addr >= self.ram_size:
            raise IndexError("RAM address out of range")
        old = self.ram[addr]
        self.ram[addr] = value & 0xFF
        if old != self.ram[addr]:
            self.ram_changes.append((addr, old, self.ram[addr], cycle))

    def load_rom(self, data: List[int]) -> None:
        """Load a ROM image into the emulator's ROM buffer.

        Args:
            data: Sequence of integer byte values (expected 0-255) comprising
                the ROM image. Values outside 0-255 will be truncated to 8
                bits.

        Raises:
            ValueError: If len(data) is greater than self.rom_size.

        Notes:
            Overwrites self.rom[i] for i in range(len(data)) with
            (data[i] & 0xFF). Appends (index, old_value, new_value, 0) to
            self.rom_changes for each address where the value actually changed.
        """
        if len(data) > self.rom_size:
            raise ValueError("ROM image too large")
        for i, v in enumerate(data):
            old = self.rom[i]
            self.rom[i] = v & 0xFF
            if old != self.rom[i]:
                self.rom_changes.append((i, old, self.rom[i], 0))

    def read_rom(self, addr: int) -> int:
        """Read a value from the ROM at the specified address.

        Args:
            addr: Zero-based address within ROM to read.

        Returns:
            The value stored at the given ROM address.

        Raises:
            IndexError: If ``addr`` is negative or greater than or equal to
                ``self.rom_size``.
        """
        if addr < 0 or addr >= self.rom_size:
            raise IndexError("ROM address out of range")
        return self.rom[addr]

    def snapshot_ram(self) -> List[int]:
        """Return a snapshot copy of the emulator's RAM.

        Returns:
            A new list containing the current contents of RAM. Each element
            represents a byte (typically in the range 0-255). The returned list
            is a shallow copy of the internal RAM, so modifying it will not
            affect the emulator's internal state.
        """
        return list(self.ram)

    def snapshot_rom(self) -> List[int]:
        """Return a snapshot copy of the ROM contents.

        Returns:
            A list of integers representing the ROM data at the time of the call.
        """
        return list(self.rom)
