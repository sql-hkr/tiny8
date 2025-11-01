"""tiny8 - a tiny AVR-like 8-bit CPU simulator package.

Provides a compact CPU implementation, assembler and visualization helpers
for experimentation and teaching.
"""

from .assembler import AsmResult, assemble, assemble_file
from .cli import run_cli
from .cpu import CPU
from .utils import ProgressBar
from .visualizer import Visualizer

__all__ = [
    "CPU",
    "AsmResult",
    "assemble",
    "assemble_file",
    "Visualizer",
    "run_cli",
    "ProgressBar",
]

__version__ = "0.2.0"
