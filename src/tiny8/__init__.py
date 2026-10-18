"""A tiny AVR-like 8-bit CPU simulator package.

Provides a compact CPU implementation, assembler, C compiler, and
interactive Textual CLI for experimentation and teaching.
"""

from .assembler import AsmResult, assemble, assemble_file
from .compiler import (
    compile_c,
    compile_c_file,
    compile_c_file_with_symbols,
    compile_c_with_symbols,
)
from .cpu import CPU
from .tui import run_cli
from .utils import ProgressBar

__all__ = [
    "CPU",
    "AsmResult",
    "assemble",
    "assemble_file",
    "compile_c",
    "compile_c_file",
    "compile_c_with_symbols",
    "compile_c_file_with_symbols",
    "run_cli",
    "ProgressBar",
]

__version__ = "0.2.0"
