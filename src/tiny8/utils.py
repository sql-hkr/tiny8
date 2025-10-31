"""Utility functions for Tiny8, including tqdm-like progress bar.

The ProgressBar class provides a simple, tqdm-like progress indicator that
can be used to visualize long-running CPU executions or other iterative
processes. The progress bar automatically adapts to the terminal width.

Example usage with CPU:
    >>> from tiny8 import CPU, assemble
    >>> asm = assemble("ldi r16, 10\\nloop:\\ndec r16\\njmp loop")
    >>> cpu = CPU()
    >>> cpu.load_program(asm)
    >>> cpu.run(max_steps=1000, show_progress=True)
    CPU execution: 100.0%|████████████| 1000/1000 [00:00<00:00, 5000.00it/s]

Example usage standalone (auto-detect width):
    >>> from tiny8 import ProgressBar
    >>> with ProgressBar(total=100, desc="Processing") as pb:
    ...     for i in range(100):
    ...         # do work
    ...         pb.update(1)

Example usage with custom width:
    >>> with ProgressBar(total=100, desc="Processing", ncols=60) as pb:
    ...     for i in range(100):
    ...         pb.update(1)
"""

import shutil
import sys
import time
from typing import Optional


class ProgressBar:
    """A simple tqdm-like progress bar for Tiny8 CPU execution.

    Usage:
        with ProgressBar(total=1000, desc="Running") as pb:
            for i in range(1000):
                # do work
                pb.update(1)

    Or:
        pb = ProgressBar(total=1000)
        for i in range(1000):
            # do work
            pb.update(1)
        pb.close()
    """

    def __init__(
        self,
        total: Optional[int] = None,
        desc: str = "",
        disable: bool = False,
        ncols: Optional[int] = None,
        mininterval: float = 0.1,
    ):
        """Initialize progress bar.

        Args:
            total: Total number of iterations (None for indeterminate)
            desc: Description prefix for the progress bar
            disable: If True, disable the progress bar completely
            ncols: Width of the progress bar in characters (None for auto-detect)
            mininterval: Minimum time between updates in seconds
        """
        self.total = total
        self.desc = desc
        self.disable = disable
        self.ncols = ncols
        self.mininterval = mininterval
        self.n = 0
        self.start_time = time.time()
        self.last_print_time = 0

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False

    def update(self, n: int = 1):
        """Update progress by n steps.

        Args:
            n: Number of steps to increment
        """
        if self.disable:
            return

        self.n += n
        current_time = time.time()

        if current_time - self.last_print_time < self.mininterval:
            if self.total is not None and self.n >= self.total:
                self._print_bar()
            return

        self.last_print_time = current_time
        self._print_bar()

    def _get_terminal_width(self) -> int:
        """Get the current terminal width.

        Returns:
            Terminal width in characters, defaults to 80 if unable to detect
        """
        if self.ncols is not None:
            return self.ncols

        try:
            return shutil.get_terminal_size(fallback=(80, 24)).columns
        except Exception:
            return 80

    def _print_bar(self):
        """Print the progress bar to stderr."""
        if self.disable:
            return

        terminal_width = self._get_terminal_width()
        elapsed = time.time() - self.start_time

        if self.total is not None and self.total > 0:
            percent = min(100, (self.n / self.total) * 100)

            rate = self.n / elapsed if elapsed > 0 else 0
            eta = (self.total - self.n) / rate if rate > 0 else 0

            prefix = f"{self.desc}: {percent:>5.1f}%|"
            suffix = f"| {self.n}/{self.total} [{self._format_time(elapsed)}<{self._format_time(eta)}, {rate:.2f}it/s]"

            fixed_width = len(prefix) + len(suffix) + 1
            bar_width = max(10, terminal_width - fixed_width)

            filled = int(bar_width * self.n / self.total)
            bar = "█" * filled + "░" * (bar_width - filled)

            output = f"\r{prefix}{bar}{suffix}"
        else:
            spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            spin_char = spinner[self.n % len(spinner)]
            rate = self.n / elapsed if elapsed > 0 else 0

            output = f"\r{self.desc}: {spin_char} {self.n} [{self._format_time(elapsed)}, {rate:.2f}it/s]"

        if len(output) > terminal_width:
            output = output[: terminal_width - 3] + "..."

        sys.stderr.write(output)
        sys.stderr.flush()

    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS or HH:MM:SS.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted time string
        """
        if seconds < 0 or seconds != seconds:
            return "??:??"

        seconds = int(seconds)
        if seconds < 3600:
            return f"{seconds // 60:02d}:{seconds % 60:02d}"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def set_description(self, desc: str):
        """Update the description.

        Args:
            desc: New description string
        """
        self.desc = desc
        self._print_bar()

    def close(self):
        """Close the progress bar and print newline."""
        if self.disable:
            return

        self._print_bar()
        sys.stderr.write("\n")
        sys.stderr.flush()

    def reset(self):
        """Reset the progress bar to initial state."""
        self.n = 0
        self.start_time = time.time()
        self.last_print_time = 0
