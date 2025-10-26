"""tiny8 - a tiny AVR-like 8-bit CPU simulator package.

Provides a compact CPU implementation, assembler and visualization helpers
for experimentation and teaching.
"""

from .assembler import assemble, assemble_file
from .cli import run_cli
from .cpu import CPU
from .visualizer import Visualizer

__all__ = ["CPU", "assemble", "assemble_file", "Visualizer", "run_cli"]

__version__ = "0.1.1"
