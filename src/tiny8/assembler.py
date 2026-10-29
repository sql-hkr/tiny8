"""Assembler for tiny8 converting assembly text into program listings."""

import re
from dataclasses import dataclass, field


@dataclass
class AsmResult:
    """Result of assembling assembly source code.

    Attributes:
        program: List of instruction tuples in (mnemonic, operands) format.
        labels: Mapping of label names to program counter addresses.
        pc_to_line: Mapping of program counter to source line numbers.
        source_lines: Original source lines for display and debugging.
    """

    program: list[tuple[str, tuple]] = field(default_factory=list)
    labels: dict[str, int] = field(default_factory=dict)
    pc_to_line: dict[int, int] = field(default_factory=dict)
    source_lines: list[str] = field(default_factory=list)


def _parse_number(token: str) -> int:
    """Parse numeric literal token into integer.

    Supports hexadecimal ($FF, 0xFF), binary (0b1010), and decimal values,
    with an optional leading '#' immediate prefix.

    Args:
        token: Numeric token string to parse.

    Returns:
        Parsed integer value.

    Raises:
        ValueError: If token cannot be parsed as a number.
    """
    t = token.strip().removeprefix("#")
    if not t:
        raise ValueError(f"Unable to parse numeric token: {token}")
    c0 = t[0]
    if c0 == "$":
        return int(t[1:], 16)
    if t.startswith(("0x", "0X")):
        return int(t, 16)
    if t.startswith(("0b", "0B")):
        return int(t, 2)
    if c0.isdigit() or (c0 == "-" and len(t) > 1 and t[1:].isdigit()):
        return int(t)
    raise ValueError(f"Unable to parse numeric token: {token}")


def parse_asm(text: str) -> AsmResult:
    """Parse assembly source text into an AsmResult structure.

    Args:
        text: Assembly source text.

    Returns:
        AsmResult containing parsed program, labels, and line mappings.
    """
    result = AsmResult()
    pc = 0
    lines = text.splitlines()
    result.source_lines = lines.copy()

    for line_num, raw_line in enumerate(lines):
        line = raw_line.split(";", 1)[0].strip()
        if not line:
            continue
        if ":" in line:
            left, right = line.split(":", 1)
            result.labels[left.strip()] = pc
            line = right.strip()
            if not line:
                continue

        line = re.sub(r"([XYZxyz]|r\d+|R\d+)\s*\+\s*(\w+)", r"\1+\2", line)
        parts = line.replace(",", " ").split()
        instr = parts[0].upper()
        ops = []
        for p in parts[1:]:
            if (p[0] == "r" or p[0] == "R") and len(p) > 1 and p[1:].isdigit():
                ops.append(("reg", int(p[1:])))
            elif p.upper() in ("X", "Y", "Z"):
                reg_map = {"X": 26, "Y": 28, "Z": 30}
                ops.append(("reg", reg_map[p.upper()]))
            elif "+" in p:
                base, disp = p.split("+", 1)
                base_u = base.upper()
                reg_map = {"X": 26, "Y": 28, "Z": 30}
                if base_u in reg_map:
                    base_reg = reg_map[base_u]
                elif base_u.startswith("R") and base_u[1:].isdigit():
                    base_reg = int(base_u[1:])
                else:
                    base_reg = int(base)
                disp_val = _parse_number(disp)
                ops.append(("disp", base_reg, disp_val))
            else:
                try:
                    ops.append(_parse_number(p))
                except ValueError:
                    ops.append(p)

        result.program.append((instr, tuple(ops)))
        result.pc_to_line[pc] = line_num
        pc += 1

    return result


def assemble(text: str) -> AsmResult:
    """Assemble source text into program instructions and label mappings.

    Args:
        text: Assembly source code string.

    Returns:
        AsmResult containing parsed program, labels, and line mappings.
    """
    return parse_asm(text)


def assemble_file(path: str) -> AsmResult:
    """Assemble source file into program instructions and label mappings.

    Args:
        path: Path to the assembly source file.

    Returns:
        AsmResult containing parsed program, labels, and line mappings.

    Raises:
        FileNotFoundError: If the source file does not exist.
        OSError: If reading the file fails.
    """
    with open(path, "r", encoding="utf-8") as f:
        return assemble(f.read())
