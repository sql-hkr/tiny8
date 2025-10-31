"""Pytest configuration and shared fixtures for Tiny8 test suite.

This module provides common fixtures, helpers, and configuration for all tests.
"""

import pytest

from tiny8 import CPU, assemble, assemble_file


@pytest.fixture
def cpu():
    """Provide a fresh CPU instance for each test.

    Returns:
        CPU: A new, uninitialized CPU instance.
    """
    return CPU()


@pytest.fixture
def cpu_with_program(cpu):
    """Provide a helper function to load and optionally run a program.

    Returns:
        Callable: Function that takes assembly source and returns configured CPU.
    """

    def _load_program(src: str, max_steps: int = 1000, run: bool = True) -> CPU:
        """Load assembly code into CPU and optionally run it.

        Args:
            src: Assembly source code string.
            max_steps: Maximum steps to execute.
            run: Whether to run the program immediately.

        Returns:
            CPU instance with program loaded (and possibly executed).
        """
        asm = assemble(src)
        cpu.load_program(asm)
        if run:
            cpu.run(max_steps=max_steps)
        return cpu

    return _load_program


@pytest.fixture
def cpu_from_file(cpu):
    """Provide a helper function to load and run a program from file.

    Returns:
        Callable: Function that takes file path and returns configured CPU.
    """

    def _load_file(path: str, max_steps: int = 10000) -> CPU:
        """Load assembly file into CPU and run it.

        Args:
            path: Path to assembly file.
            max_steps: Maximum steps to execute.

        Returns:
            CPU instance with program executed.
        """
        asm = assemble_file(path)
        cpu.load_program(asm)
        cpu.run(max_steps=max_steps)
        return cpu

    return _load_file


class CPUTestHelper:
    """Helper class providing common CPU testing utilities."""

    @staticmethod
    def assert_register(cpu: CPU, reg: int, expected: int, msg: str = None):
        """Assert register value with helpful error message.

        Args:
            cpu: CPU instance to check.
            reg: Register number (0-31).
            expected: Expected value.
            msg: Optional custom message.
        """
        actual = cpu.read_reg(reg)
        if msg:
            assert actual == expected, f"{msg}: R{reg}={actual}, expected {expected}"
        else:
            assert actual == expected, (
                f"R{reg}={actual} (0x{actual:02X}), expected {expected} (0x{expected:02X})"
            )

    @staticmethod
    def assert_registers(cpu: CPU, values: dict):
        """Assert multiple register values.

        Args:
            cpu: CPU instance to check.
            values: Dictionary mapping register number to expected value.
        """
        for reg, expected in values.items():
            CPUTestHelper.assert_register(cpu, reg, expected)

    @staticmethod
    def assert_memory(cpu: CPU, addr: int, expected: int, msg: str = None):
        """Assert memory value with helpful error message.

        Args:
            cpu: CPU instance to check.
            addr: Memory address.
            expected: Expected value.
            msg: Optional custom message.
        """
        actual = cpu.read_ram(addr)
        if msg:
            assert actual == expected, (
                f"{msg}: MEM[0x{addr:04X}]={actual}, expected {expected}"
            )
        else:
            assert actual == expected, (
                f"MEM[0x{addr:04X}]={actual} (0x{actual:02X}), expected {expected} (0x{expected:02X})"
            )

    @staticmethod
    def assert_flag(cpu: CPU, flag: int, expected: bool, name: str = None):
        """Assert SREG flag value.

        Args:
            cpu: CPU instance to check.
            flag: Flag bit position.
            expected: Expected boolean value.
            name: Optional flag name for error message.
        """
        actual = cpu.get_flag(flag)
        flag_name = name or f"flag[{flag}]"
        assert actual == expected, f"{flag_name}={actual}, expected {expected}"

    @staticmethod
    def assert_flags(cpu: CPU, flags: dict):
        """Assert multiple flag values.

        Args:
            cpu: CPU instance to check.
            flags: Dictionary mapping flag bit to expected boolean value.
        """
        from tiny8.cpu import (
            SREG_C,
            SREG_H,
            SREG_I,
            SREG_N,
            SREG_S,
            SREG_T,
            SREG_V,
            SREG_Z,
        )

        flag_names = {
            SREG_C: "C",
            SREG_Z: "Z",
            SREG_N: "N",
            SREG_V: "V",
            SREG_S: "S",
            SREG_H: "H",
            SREG_T: "T",
            SREG_I: "I",
        }

        for flag, expected in flags.items():
            CPUTestHelper.assert_flag(cpu, flag, expected, flag_names.get(flag))


@pytest.fixture
def helper():
    """Provide CPUTestHelper instance for tests.

    Returns:
        CPUTestHelper: Helper class with assertion utilities.
    """
    return CPUTestHelper()


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "parametrize: marks parametrized tests")
