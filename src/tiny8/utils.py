"""Utility helpers for tiny8 including terminal progress bar."""

import math
import shutil
import sys
import time


class ProgressBar:
    """Terminal progress bar indicator adapting to terminal width.

    Args:
        total: Total number of iterations, or None for indeterminate progress.
        desc: Prefix description string. Defaults to "".
        disable: True to disable output completely. Defaults to False.
        ncols: Explicit width in characters, or None for auto-detection.
        mininterval: Minimum interval in seconds between screen refreshes.

    Attributes:
        total: Total iterations expected.
        desc: Description prefix text.
        disable: Flag controlling output suppression.
        ncols: Target bar character width.
        mininterval: Refresh rate throttle in seconds.
        n: Current iteration step count.
        start_time: Monotonic start timestamp.
        last_print_time: Timestamp of last bar render.
    """

    def __init__(
        self,
        total: int | None = None,
        desc: str = "",
        disable: bool = False,
        ncols: int | None = None,
        mininterval: float = 0.1,
    ) -> None:
        self.total = total
        self.desc = desc
        self.disable = disable
        self.ncols = ncols
        self.mininterval = mininterval
        self.n = 0
        self.start_time = time.time()
        self.last_print_time = 0.0

    def __enter__(self) -> "ProgressBar":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit context manager and flush output."""
        self.close()
        return False

    def update(self, n: int = 1) -> None:
        """Increment progress by n steps.

        Args:
            n: Number of iterations to increment. Defaults to 1.
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
        """Return detected or default terminal width in characters.

        Returns:
            Width in characters, fallback to 80.
        """
        if self.ncols is not None:
            return self.ncols

        try:
            return shutil.get_terminal_size(fallback=(80, 24)).columns
        except Exception:
            return 80

    def _print_bar(self) -> None:
        """Render and output progress bar to stderr."""
        if self.disable:
            return

        terminal_width = self._get_terminal_width()
        elapsed = time.time() - self.start_time

        if self.total is not None and self.total > 0:
            percent = min(100.0, (self.n / self.total) * 100)
            rate = self.n / elapsed if elapsed > 0 else 0.0
            eta = (self.total - self.n) / rate if rate > 0 else 0.0

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
            rate = self.n / elapsed if elapsed > 0 else 0.0
            output = f"\r{self.desc}: {spin_char} {self.n} [{self._format_time(elapsed)}, {rate:.2f}it/s]"

        if len(output) > terminal_width:
            output = output[: terminal_width - 3] + "..."

        sys.stderr.write(output)
        sys.stderr.flush()

    def _format_time(self, seconds: float) -> str:
        """Format duration in seconds as MM:SS or HH:MM:SS string.

        Args:
            seconds: Duration in seconds.

        Returns:
            Formatted time string.
        """
        if seconds < 0 or math.isnan(seconds):
            return "??:??"

        sec = int(seconds)
        if sec < 3600:
            return f"{sec // 60:02d}:{sec % 60:02d}"
        return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"

    def set_description(self, desc: str) -> None:
        """Update description prefix and re-render bar.

        Args:
            desc: New description text.
        """
        self.desc = desc
        self._print_bar()

    def close(self) -> None:
        """Finalize progress bar and print trailing newline."""
        if self.disable:
            return

        self._print_bar()
        sys.stderr.write("\n")
        sys.stderr.flush()

    def reset(self) -> None:
        """Reset progress counter and timers to initial state."""
        self.n = 0
        self.start_time = time.time()
        self.last_print_time = 0.0
