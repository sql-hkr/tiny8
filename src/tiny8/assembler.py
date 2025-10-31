"""Simple assembler for tiny8 - converts assembly text into program tuples.

This module provides a tiny assembler that tokenizes and parses a simple
assembly syntax and returns a list of instructions and a label mapping.
"""

import re
from dataclasses import dataclass, field


@dataclass
class AsmResult:
    """Result of assembling source code.

    Attributes:
        program: List of instruction tuples (mnemonic, operands).
        labels: Mapping from label names to program counter addresses.
        pc_to_line: Mapping from program counter to original source line number.
        source_lines: Original source text split into lines for display.
    """

    program: list[tuple[str, tuple]] = field(default_factory=list)
    labels: dict[str, int] = field(default_factory=dict)
    pc_to_line: dict[int, int] = field(default_factory=dict)
    source_lines: list[str] = field(default_factory=list)


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


def parse_asm(text: str) -> AsmResult:
    """Parse assembly source text into a program listing and a label table.

    The function scans the given assembly text line-by-line and produces
    an AsmResult containing the parsed program, labels, source line
    mapping, and original source text.

    Args:
        text: Assembly source code as a single string. May contain comments,
            blank lines and labels.

    Returns:
        AsmResult object containing program, labels, pc_to_line mapping,
        and source_lines.

    Note:
        - Comments begin with ';' and extend to the end of the line.
        - Labels may appear on a line by themselves or before an instruction
          with the form "label: instr ...".
        - Registers are encoded as ("reg", N) where N is the register number.
        - Numeric operands are parsed using _parse_number; non-numeric tokens
          are preserved as strings (symbols) for later resolution.
    """
    result = AsmResult()
    pc = 0
    lines = text.splitlines()
    result.source_lines = lines.copy()
    for line_num, line in enumerate(lines):
        line = line.split(";", 1)[0].strip()
        if not line:
            continue
        if ":" in line:
            left, right = line.split(":", 1)
            lbl = left.strip()
            result.labels[lbl] = pc
            line = right.strip()
            if not line:
                continue
        parts = [p for p in re.split(r"[\s,]+", line) if p != ""]
        instr = parts[0].upper()
        ops = []
        for p in parts[1:]:
            pl = p.lower()
            if pl.startswith("r") and pl[1:].isdigit():
                ops.append(("reg", int(pl[1:])))
            else:
                try:
                    n = _parse_number(p)
                    ops.append(n)
                except ValueError:
                    ops.append(p)
        result.program.append((instr, tuple(ops)))
        result.pc_to_line[pc] = line_num
        pc += 1
    return result


def assemble(text: str) -> AsmResult:
    """Parse assembly source text and return parsed instructions and label map.

    Args:
        text: Assembly source code as a single string. May contain
            multiple lines, labels and comments.

    Returns:
        AsmResult object containing program, labels, source line mapping,
        and original source text.

    Raises:
        Exception: Propagates parsing errors from the underlying parser.

    Example:
        >>> src = "start: MOV R1, 5\\nJMP start"
        >>> result = assemble(src)
        >>> result.labels
        {'start': 0}
    """
    return parse_asm(text)


def assemble_file(path: str) -> AsmResult:
    """Assemble the contents of a source file.

    Args:
        path: Path to the source file to assemble.

    Returns:
        The result produced by calling assemble(source_text).

    Raises:
        FileNotFoundError: If the specified file does not exist.
        OSError: For other I/O related errors when opening or reading the file.
        Exception: Any exception raised by assemble(...) will be propagated.

    Note:
        The file is opened in text mode and read entirely into memory.

    Example:
        >>> result = assemble_file("program.asm")
    """
    with open(path, "r") as f:
        return assemble(f.read())
