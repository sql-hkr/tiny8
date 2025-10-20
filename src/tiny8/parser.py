"""Simple parser shim for tiny8.

This module re-exports the assembler's ``parse_asm`` function and serves as
the future location for a more featureful parser if needed.
"""

from .assembler import parse_asm as parse_asm

__all__ = ["parse_asm"]
