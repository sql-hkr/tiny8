"""tiny8 - a tiny AVR-like 8-bit CPU simulator package.

Provides a compact CPU implementation, assembler and visualization helpers
for experimentation and teaching.
"""

from .assembler import assemble, assemble_file
from .cpu import CPU
from .visualizer import Visualizer

__all__ = ["CPU", "assemble", "assemble_file", "Visualizer"]

__version__ = "0.1.0"
