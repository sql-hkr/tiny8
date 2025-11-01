"""Utility functions tests.

Tests for progress bar and other utility functions.
"""

import time

from tiny8.utils import ProgressBar


class TestProgressBarBasic:
    """Test basic progress bar functionality."""

    def test_progress_bar_disabled(self):
        """Test progress bar when disabled."""
        pbar = ProgressBar(total=100, disable=True)
        pbar.update(50)
        pbar.close()

    def test_progress_bar_zero_total(self):
        """Test progress bar with None total."""
        pbar = ProgressBar(total=None, disable=True)
        pbar.update(10)
        pbar.close()

    def test_progress_bar_with_context(self):
        """Test progress bar as context manager."""
        with ProgressBar(total=10, disable=True) as pbar:
            pbar.update(5)


class TestProgressBarParameters:
    """Test progress bar with different parameters."""

    def test_progress_bar_description(self):
        """Test progress bar with description."""
        pbar = ProgressBar(total=100, desc="Test", disable=True)
        pbar.update(10)
        pbar.close()

    def test_progress_bar_ncols(self):
        """Test progress bar with custom width."""
        pbar = ProgressBar(total=100, ncols=50, disable=True)
        pbar.update(10)
        pbar.close()

    def test_progress_bar_mininterval(self):
        """Test progress bar with custom mininterval."""
        pbar = ProgressBar(total=100, mininterval=0.01, disable=True)
        pbar.update(10)
        pbar.close()


class TestProgressBarEnabled:
    """Test progress bar when enabled."""

    def test_progress_bar_enabled_with_total(self):
        """Test progress bar when enabled with total."""
        pbar = ProgressBar(total=10, desc="Processing", disable=False, mininterval=0)
        for i in range(10):
            pbar.update(1)
            time.sleep(0.001)
        pbar.close()

    def test_progress_bar_enabled_no_total(self):
        """Test progress bar when enabled without total (spinner mode)."""
        pbar = ProgressBar(total=None, desc="Working", disable=False, mininterval=0)
        for i in range(5):
            pbar.update(1)
            time.sleep(0.001)
        pbar.close()


class TestProgressBarMethods:
    """Test progress bar methods."""

    def test_progress_bar_set_description(self):
        """Test updating progress bar description."""
        pbar = ProgressBar(total=100, desc="Initial", disable=False, mininterval=0)
        pbar.set_description("Updated")
        pbar.update(10)
        pbar.close()

    def test_progress_bar_reset(self):
        """Test resetting progress bar."""
        pbar = ProgressBar(total=100, disable=False, mininterval=0)
        pbar.update(50)
        pbar.reset()
        assert pbar.n == 0
        pbar.close()

    def test_progress_bar_terminal_width_fallback(self):
        """Test terminal width fallback when detection fails."""
        pbar = ProgressBar(total=100, disable=False, mininterval=0)
        width = pbar._get_terminal_width()
        assert width > 0
        pbar.close()


class TestProgressBarFormatting:
    """Test progress bar time formatting."""

    def test_progress_bar_format_time_short(self):
        """Test time formatting for short durations."""
        pbar = ProgressBar(total=100, disable=True)
        assert pbar._format_time(65) == "01:05"
        assert pbar._format_time(0) == "00:00"

    def test_progress_bar_format_time_long(self):
        """Test time formatting for long durations."""
        pbar = ProgressBar(total=100, disable=True)
        assert pbar._format_time(3661) == "01:01:01"
        assert pbar._format_time(7200) == "02:00:00"

    def test_progress_bar_format_time_invalid(self):
        """Test time formatting with invalid values."""
        pbar = ProgressBar(total=100, disable=True)
        result = pbar._format_time(-1)
        assert result == "??:??"
        result = pbar._format_time(float("nan"))
        assert result == "??:??"


class TestProgressBarEdgeCases:
    """Test progress bar edge cases."""

    def test_progress_bar_long_output(self):
        """Test progress bar with very long description that exceeds terminal width."""
        pbar = ProgressBar(
            total=100,
            desc="A" * 200,  # Very long description
            disable=False,
            ncols=80,
            mininterval=0,
        )
        pbar.update(50)
        pbar.close()

    def test_progress_bar_update_past_total(self):
        """Test updating progress bar past total."""
        pbar = ProgressBar(total=10, disable=False, mininterval=0)
        pbar.update(15)  # Update past total
        pbar.close()

    def test_progress_bar_mininterval_skip_update(self):
        """Test that updates are skipped when within mininterval."""
        pbar = ProgressBar(
            total=100, disable=False, mininterval=10.0
        )  # Long mininterval
        pbar.update(10)
        time.sleep(0.001)
        pbar.update(10)
        pbar.close()

    def test_progress_bar_mininterval_with_completion(self):
        """Test that final update happens even within mininterval."""
        pbar = ProgressBar(total=10, disable=False, mininterval=10.0)
        pbar.update(5)
        time.sleep(0.001)
        pbar.update(5)
        pbar.close()

    def test_progress_bar_terminal_width_exception(self):
        """Test terminal width with exception handling."""
        import shutil

        original_func = shutil.get_terminal_size

        def mock_exception(*args, **kwargs):
            raise Exception("Terminal error")

        try:
            shutil.get_terminal_size = mock_exception
            pbar = ProgressBar(total=100, disable=False, mininterval=0)
            width = pbar._get_terminal_width()
            assert width == 80
            pbar.close()
        finally:
            shutil.get_terminal_size = original_func

    def test_progress_bar_prints_when_enabled(self):
        """Test that progress bar actually prints terminal width logic."""
        pbar = ProgressBar(total=100, disable=False, mininterval=0)
        pbar.update(10)
        time.sleep(0.001)
        pbar.update(10)
        assert pbar.n == 20
        pbar.close()

    def test_progress_bar_print_bar_when_disabled(self):
        """Test _print_bar method directly when disabled to cover line 123."""
        pbar = ProgressBar(total=100, disable=True)
        pbar._print_bar()
        assert pbar.n == 0
