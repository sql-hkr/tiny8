"""Simple assembler for tiny8 - converts assembly text into program tuples.

This module provides a tiny assembler that tokenizes and parses a simple
assembly syntax and returns a list of instructions and a label mapping.
"""

import re
from typing import Dict, List, Tuple


def _parse_number(token: str) -> int:
    """Parse a numeric assembly token and return its integer value.

    The function accepts tokens used by a simple assembler and supports
    several notations:

    - Optional immediate marker '#' prefixes the token and is ignored.
    - Hexadecimal with a leading '$' (e.g. '$FF') or Python-style '0x'
      (e.g. '0xFF').
    - Binary with a leading '0b' (e.g. '0b1010').
    - Decimal integers, including negative values (e.g. '42', '-7').

    Args:
        token: The input token to parse.

    Returns:
        The integer value represented by the token.

    Raises:
        ValueError: If the token cannot be interpreted as a numeric literal
            (e.g. when it is a label or otherwise non-numeric).
    """
    t = token.strip()
    # strip immediate marker
    if t.startswith("#"):
        t = t[1:]
    # $nn as hex
    if t.startswith("$"):
        return int(t[1:], 16)
    if t.startswith("0x"):
        return int(t, 16)
    if t.startswith("0b"):
        return int(t, 2)
    if t.isdigit() or (t.startswith("-") and t[1:].isdigit()):
        return int(t)
    # otherwise return as-is (label)
    raise ValueError(f"Unable to parse numeric token: {token}")


def parse_asm(text: str) -> Tuple[List[Tuple[str, Tuple]], Dict[str, int]]:
    """Parse assembly source text into a program listing and a label table.

    The function scans the given assembly text line-by-line and produces two
    values:

    - program: a list of instructions, where each instruction is a tuple
      (MNEMONIC, OPERANDS_TUPLE). MNEMONIC is stored in uppercase for
      readability (the CPU/runtime looks up handlers using mnemonic.lower()).
      OPERANDS_TUPLE is an immutable tuple of operand values in the order they
      appear.
    - labels: a mapping from label name (str) to program counter (int), where
      the program counter is the zero-based index of the instruction in the
      produced program list.

    Args:
        text: Assembly source code as a single string. May contain comments,
            blank lines and labels.

    Returns:
        A pair (program, labels) as described above.

    Notes:
        - Comments begin with ';' and extend to the end of the line and are
          removed before parsing.
        - Labels may appear on a line by themselves or before an instruction
          with the form "label: instr ...". A label associates the name
          with the current instruction index.
        - Registers are encoded as ("reg", N) where N is the register number.
        - Numeric operands are parsed using _parse_number; non-numeric tokens
          are preserved as strings (symbols) for later resolution.
    """
    program: List[Tuple[str, Tuple]] = []
    labels: Dict[str, int] = {}
    pc = 0
    lines = text.splitlines()
    for line in lines:
        # remove comments
        line = line.split(";", 1)[0].strip()
        if not line:
            continue
        # label on same line: "label: instr ops"
        if ":" in line:
            left, right = line.split(":", 1)
            lbl = left.strip()
            labels[lbl] = pc
            line = right.strip()
            if not line:
                continue
        # tokenization by commas and whitespace
        parts = [p for p in re.split(r"[\s,]+", line) if p != ""]
        # store mnemonic in uppercase for readability; handlers are looked up
        # using lower() by the CPU when dispatching.
        instr = parts[0].upper()
        ops = []
        for p in parts[1:]:
            pl = p.lower()
            # register like r0: mark as a register operand to preserve formatting
            if pl.startswith("r") and pl[1:].isdigit():
                ops.append(("reg", int(pl[1:])))
            else:
                # try numeric parse, otherwise keep as label string
                try:
                    n = _parse_number(p)
                    ops.append(n)
                except ValueError:
                    ops.append(p)
        program.append((instr, tuple(ops)))
        pc += 1
    return program, labels


def assemble(text: str) -> Tuple[List[Tuple[str, Tuple]], Dict[str, int]]:
    """Parse assembly source text and return parsed instructions and label map.

    Args:
        text (str): Assembly source code as a single string. May contain
            multiple lines, labels and comments.

    Returns:
        Tuple[List[Tuple[str, Tuple]], Dict[str, int]]: A pair (instructions, labels):
            - instructions: list of parsed instructions in source order. Each
              instruction is a tuple (mnemonic, operands) where `mnemonic` is a
              string and `operands` is a tuple of operand values as produced by
              the assembler.
            - labels: mapping from label names (str) to integer addresses
              (instruction indices).

    Raises:
        Exception: Propagates parsing errors from the underlying parser
            (for example, syntax or operand errors).

    Notes:
        This function is a thin wrapper around parse_asm(...) and forwards any
        exceptions raised by the parser.

    Example:
        >>> src = "start: MOV R1, 5\\nJMP start"
        >>> instructions, labels = assemble(src)
        >>> labels
        {'start': 0}
    """
    return parse_asm(text)


def assemble_file(path: str):
    """Assemble the contents of a source file.

    Reads the entire file at `path` and passes its contents to assemble(...).

    Args:
        path (str): Path to the source file to assemble.

    Returns:
        Any: The result produced by calling assemble(source_text). The exact
        type depends on the implementation of assemble(...).

    Raises:
        FileNotFoundError: If the specified file does not exist.
        OSError: For other I/O related errors when opening or reading the file.
        Exception: Any exception raised by assemble(...) will be propagated.

    Notes:
        The file is opened in text mode and read entirely into memory; for very
        large files this may be inefficient.

    Example:
        >>> result = assemble_file("program.asm")
        >>> # result now holds the assembled output produced by assemble(...)
    """
    with open(path, "r") as f:
        return assemble(f.read())
