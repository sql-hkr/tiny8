"""Simple C compiler for Tiny8 converting a subset of C into Tiny8 assembly.

Features:
- Variable declarations and assignments (int/char)
- Compound assignment operators (+=, -=, *=, /=, %=, &=, |=, ^=)
- Increment and decrement operators (++, --)
- Arithmetic (+, -, *, /, %), bitwise (&, |, ^, ~), logical (!), and relational (<, <=, >, >=, ==, !=)
- Control structures: if / else, while, return
- Functions with register-based parameter passing (R16..R19) and return value in R16
- Hardware builtins: peek(addr), poke(addr, val), in(port), out(port, val)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class Token:
    """Lexical token."""

    type: str
    value: str
    line: int


class Lexer:
    """Tokenize C source code."""

    TOKEN_SPEC = [
        ("COMMENT_LINE", r"//.*"),
        ("COMMENT_BLOCK", r"/\*[\s\S]*?\*/"),
        ("NUMBER", r"0x[0-9a-fA-F]+|\d+"),
        ("CHAR", r"'(\\.|[^\\'])'"),
        ("STRING", r'"([^"\\]|\\.)*"'),
        (
            "KEYWORD",
            r"\b(int|char|void|if|else|while|for|break|return|peek|poke|in|out|vram_set|vram_get|vram_clear|vram_puts)\b",
        ),
        ("ID", r"[a-zA-Z_]\w*"),
        ("OP", r"\+\+|--|<<|>>|==|!=|<=|>=|&&|\|\||[+\-*/%&|^]=|[+\-*/%&|^=!<>]"),
        ("PUNCT", r"[;,\(\)\{\}\[\]]"),
        ("WS", r"\s+"),
    ]

    def __init__(self, source: str) -> None:
        self.source = source
        self.regex = re.compile(
            "|".join(f"(?P<{name}>{pattern})" for name, pattern in self.TOKEN_SPEC)
        )

    def tokenize(self) -> list[Token]:
        """Convert input source into tokens, ignoring whitespace and comments."""
        tokens: list[Token] = []
        line_num = 1
        for match in self.regex.finditer(self.source):
            kind = match.lastgroup
            val = match.group()
            if kind in ("WS", "COMMENT_LINE", "COMMENT_BLOCK"):
                line_num += val.count("\n")
                continue
            tokens.append(Token(kind or "UNKNOWN", val, line_num))
        return tokens


class ASTNode:
    """Base AST node."""


@dataclass
class Program(ASTNode):
    """Program root containing functions and global declarations."""

    functions: list[FunctionDef]
    globals: list[ASTNode]


@dataclass
class VarDecl(ASTNode):
    """Variable declaration."""

    var_type: str
    name: str
    init_expr: ASTNode | None = None


@dataclass
class ArrayDecl(ASTNode):
    """Array variable declaration."""

    var_type: str
    name: str
    size: int
    init_values: list[ASTNode] | None = None


@dataclass
class ArrayAccess(ASTNode):
    """Array indexing expression: name[index]."""

    name: str
    index: ASTNode


@dataclass
class ArrayAssign(ASTNode):
    """Array element assignment: name[index] = expr."""

    name: str
    index: ASTNode
    expr: ASTNode


@dataclass
class FunctionDef(ASTNode):
    """Function definition."""

    return_type: str
    name: str
    params: list[tuple[str, str]]
    body: Block


@dataclass
class Block(ASTNode):
    """Block of statements."""

    statements: list[ASTNode]


@dataclass
class Assign(ASTNode):
    """Assignment statement."""

    name: str
    expr: ASTNode


@dataclass
class CompoundAssign(ASTNode):
    """Compound assignment statement: name op= expr."""

    name: str
    op: str
    expr: ASTNode


@dataclass
class ArrayCompoundAssign(ASTNode):
    """Array element compound assignment: name[index] op= expr."""

    name: str
    index: ASTNode
    op: str
    expr: ASTNode


@dataclass
class IncDec(ASTNode):
    """Increment or decrement expression: ++x, --x, x++, x--."""

    expr: ASTNode
    is_inc: bool
    is_prefix: bool


@dataclass
class IfStmt(ASTNode):
    """If-else statement."""

    condition: ASTNode
    then_branch: Block
    else_branch: Block | None = None


@dataclass
class WhileStmt(ASTNode):
    """While loop."""

    condition: ASTNode
    body: Block


@dataclass
class ForStmt(ASTNode):
    """For loop."""

    init: ASTNode | None
    condition: ASTNode
    post: ASTNode | None
    body: Block


@dataclass
class BreakStmt(ASTNode):
    """Break statement."""


@dataclass
class ReturnStmt(ASTNode):
    """Return statement."""

    expr: ASTNode | None = None


@dataclass
class ExprStmt(ASTNode):
    """Expression statement."""

    expr: ASTNode


@dataclass
class BinaryOp(ASTNode):
    """Binary expression."""

    op: str
    left: ASTNode
    right: ASTNode


@dataclass
class UnaryOp(ASTNode):
    """Unary expression."""

    op: str
    operand: ASTNode


@dataclass
class Literal(ASTNode):
    """Literal integer value."""

    value: int


@dataclass
class StringLiteral(ASTNode):
    """String literal value."""

    value: str


@dataclass
class Var(ASTNode):
    """Variable reference."""

    name: str


@dataclass
class Call(ASTNode):
    """Function call expression."""

    name: str
    args: list[ASTNode]


def _fold_binary(op: str, left: ASTNode, right: ASTNode) -> ASTNode:
    """Fold binary operations on literals at compile time."""
    if isinstance(left, Literal) and isinstance(right, Literal):
        lv = left.value
        rv = right.value
        if op == "+":
            return Literal((lv + rv) & 0xFF)
        if op == "-":
            return Literal((lv - rv) & 0xFF)
        if op == "*":
            return Literal((lv * rv) & 0xFF)
        if op == "/" and rv != 0:
            return Literal((lv // rv) & 0xFF)
        if op == "%" and rv != 0:
            return Literal((lv % rv) & 0xFF)
        if op == "&":
            return Literal((lv & rv) & 0xFF)
        if op == "|":
            return Literal((lv | rv) & 0xFF)
        if op == "^":
            return Literal((lv ^ rv) & 0xFF)
        if op == "<<":
            return Literal((lv << rv) & 0xFF)
        if op == ">>":
            return Literal((lv >> rv) & 0xFF)
        if op == "==":
            return Literal(1 if lv == rv else 0)
        if op == "!=":
            return Literal(1 if lv != rv else 0)
        if op == "<":
            return Literal(1 if lv < rv else 0)
        if op == "<=":
            return Literal(1 if lv <= rv else 0)
        if op == ">":
            return Literal(1 if lv > rv else 0)
        if op == ">=":
            return Literal(1 if lv >= rv else 0)
        if op == "&&":
            return Literal(1 if (lv != 0 and rv != 0) else 0)
        if op == "||":
            return Literal(1 if (lv != 0 or rv != 0) else 0)
    return BinaryOp(op, left, right)


def _fold_unary(op: str, operand: ASTNode) -> ASTNode:
    """Fold unary operations on literals at compile time."""
    if isinstance(operand, Literal):
        val = operand.value
        if op == "-":
            return Literal((-val) & 0xFF)
        if op == "~":
            return Literal((~val) & 0xFF)
        if op == "!":
            return Literal(1 if val == 0 else 0)
    return UnaryOp(op, operand)


COMPOUND_ASSIGN_OPS = frozenset({"+=", "-=", "*=", "/=", "%=", "&=", "|=", "^="})


class Parser:
    """Recursive descent parser."""

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def consume(self, expected_val: str | None = None) -> Token:
        tok = self.peek()
        if tok is None:
            raise SyntaxError("Unexpected end of input")
        if expected_val and tok.value != expected_val:
            raise SyntaxError(
                f"Line {tok.line}: Expected '{expected_val}', got '{tok.value}'"
            )
        self.pos += 1
        return tok

    def match(self, val: str) -> bool:
        tok = self.peek()
        if tok and tok.value == val:
            self.pos += 1
            return True
        return False

    def parse(self) -> Program:
        functions: list[FunctionDef] = []
        globals_list: list[ASTNode] = []

        while self.peek():
            type_tok = self.consume()
            name_tok = self.consume()

            if self.match("("):
                params: list[tuple[str, str]] = []
                if not self.match(")"):
                    while True:
                        ptype = self.consume().value
                        pname = self.consume().value
                        params.append((ptype, pname))
                        if not self.match(","):
                            self.consume(")")
                            break
                body = self.parse_block()
                functions.append(
                    FunctionDef(type_tok.value, name_tok.value, params, body)
                )
            elif self.match("["):
                size = None
                if self.peek() and self.peek().value != "]":
                    size_tok = self.consume()
                    size = (
                        int(size_tok.value, 16)
                        if size_tok.value.startswith("0x")
                        else int(size_tok.value)
                    )
                self.consume("]")
                init_values = None
                if self.match("="):
                    self.consume("{")
                    init_values = []
                    while self.peek() and self.peek().value != "}":
                        init_values.append(self.parse_expr())
                        if self.match(","):
                            continue
                        break
                    self.consume("}")
                self.consume(";")
                if size is None:
                    if init_values is not None:
                        size = len(init_values)
                    else:
                        raise SyntaxError("Array size missing")
                globals_list.append(
                    ArrayDecl(type_tok.value, name_tok.value, size, init_values)
                )
            else:
                init = None
                if self.match("="):
                    init = self.parse_expr()
                self.consume(";")
                globals_list.append(VarDecl(type_tok.value, name_tok.value, init))

        return Program(functions, globals_list)

    def parse_block(self) -> Block:
        self.consume("{")
        stmts: list[ASTNode] = []
        while self.peek() and self.peek().value != "}":
            stmts.append(self.parse_stmt())
        self.consume("}")
        return Block(stmts)

    def parse_inline_stmt(self) -> ASTNode:
        tok = self.peek()
        if tok and tok.value in ("int", "char"):
            vtype = self.consume().value
            vname = self.consume().value
            init = None
            if self.match("="):
                init = self.parse_expr()
            self.consume(";")
            return VarDecl(vtype, vname, init)
        if tok and tok.type == "ID":
            next_tok = (
                self.tokens[self.pos + 1] if self.pos + 1 < len(self.tokens) else None
            )
            if next_tok and next_tok.value in COMPOUND_ASSIGN_OPS:
                name = self.consume().value
                op = self.consume().value[:-1]
                expr = self.parse_expr()
                self.consume(";")
                return CompoundAssign(name, op, expr)
            if next_tok and next_tok.value == "=":
                name = self.consume().value
                self.consume("=")
                expr = self.parse_expr()
                self.consume(";")
                return Assign(name, expr)
        expr = self.parse_expr()
        self.consume(";")
        return ExprStmt(expr)

    def parse_inline_post(self) -> ASTNode:
        tok = self.peek()
        if tok and tok.value in ("++", "--"):
            op = self.consume().value
            expr = self.parse_unary()
            return IncDec(expr, is_inc=(op == "++"), is_prefix=True)
        if tok and tok.type == "ID":
            next_tok = (
                self.tokens[self.pos + 1] if self.pos + 1 < len(self.tokens) else None
            )
            if next_tok and next_tok.value in ("++", "--"):
                name = self.consume().value
                op = self.consume().value
                return IncDec(Var(name), is_inc=(op == "++"), is_prefix=False)
            if next_tok and next_tok.value in COMPOUND_ASSIGN_OPS:
                name = self.consume().value
                op = self.consume().value[:-1]
                expr = self.parse_expr()
                return CompoundAssign(name, op, expr)
            if next_tok and next_tok.value == "=":
                name = self.consume().value
                self.consume("=")
                expr = self.parse_expr()
                return Assign(name, expr)
        return self.parse_expr()

    def parse_stmt(self) -> ASTNode:
        tok = self.peek()
        if not tok:
            raise SyntaxError("Unexpected end of statement")

        if tok.value in ("int", "char"):
            vtype = self.consume().value
            vname = self.consume().value
            if self.match("["):
                size = None
                if self.peek() and self.peek().value != "]":
                    size_tok = self.consume()
                    size = (
                        int(size_tok.value, 16)
                        if size_tok.value.startswith("0x")
                        else int(size_tok.value)
                    )
                self.consume("]")
                init_values = None
                if self.match("="):
                    self.consume("{")
                    init_values = []
                    while self.peek() and self.peek().value != "}":
                        init_values.append(self.parse_expr())
                        if self.match(","):
                            continue
                        break
                    self.consume("}")
                self.consume(";")
                if size is None:
                    if init_values is not None:
                        size = len(init_values)
                    else:
                        raise SyntaxError("Array size missing")
                return ArrayDecl(vtype, vname, size, init_values)
            init = None
            if self.match("="):
                init = self.parse_expr()
            self.consume(";")
            return VarDecl(vtype, vname, init)

        if tok.value == "break":
            self.consume("break")
            self.consume(";")
            return BreakStmt()

        if tok.value == "for":
            self.consume("for")
            self.consume("(")
            init = None
            if self.peek() and self.peek().value != ";":
                init = self.parse_inline_stmt()
            else:
                self.consume(";")
            cond = (
                self.parse_expr()
                if self.peek() and self.peek().value != ";"
                else Literal(1)
            )
            self.consume(";")
            post = None
            if self.peek() and self.peek().value != ")":
                post = self.parse_inline_post()
            self.consume(")")
            body = (
                self.parse_block()
                if self.peek() and self.peek().value == "{"
                else Block([self.parse_stmt()])
            )
            return ForStmt(init, cond, post, body)

        if tok.value == "if":
            self.consume("if")
            self.consume("(")
            cond = self.parse_expr()
            self.consume(")")
            then_b = (
                self.parse_block()
                if self.peek() and self.peek().value == "{"
                else Block([self.parse_stmt()])
            )
            else_b = None
            if self.match("else"):
                else_b = (
                    self.parse_block()
                    if self.peek() and self.peek().value == "{"
                    else Block([self.parse_stmt()])
                )
            return IfStmt(cond, then_b, else_b)

        if tok.value == "while":
            self.consume("while")
            self.consume("(")
            cond = self.parse_expr()
            self.consume(")")
            body = (
                self.parse_block()
                if self.peek() and self.peek().value == "{"
                else Block([self.parse_stmt()])
            )
            return WhileStmt(cond, body)

        if tok.value == "return":
            self.consume("return")
            expr = None
            if self.peek() and self.peek().value != ";":
                expr = self.parse_expr()
            self.consume(";")
            return ReturnStmt(expr)

        if tok.type == "ID":
            next_tok = (
                self.tokens[self.pos + 1] if self.pos + 1 < len(self.tokens) else None
            )
            if next_tok and next_tok.value == "[":
                name = self.consume().value
                self.consume("[")
                idx_expr = self.parse_expr()
                self.consume("]")
                op_tok = self.peek()
                if op_tok and op_tok.value in COMPOUND_ASSIGN_OPS:
                    self.consume()
                    expr = self.parse_expr()
                    self.consume(";")
                    return ArrayCompoundAssign(name, idx_expr, op_tok.value[:-1], expr)
                if op_tok and op_tok.value in ("++", "--"):
                    self.consume()
                    self.consume(";")
                    return ExprStmt(
                        IncDec(
                            ArrayAccess(name, idx_expr),
                            is_inc=(op_tok.value == "++"),
                            is_prefix=False,
                        )
                    )
                self.consume("=")
                expr = self.parse_expr()
                self.consume(";")
                return ArrayAssign(name, idx_expr, expr)
            if next_tok and next_tok.value in COMPOUND_ASSIGN_OPS:
                name = self.consume().value
                op = self.consume().value[:-1]
                expr = self.parse_expr()
                self.consume(";")
                return CompoundAssign(name, op, expr)
            if next_tok and next_tok.value == "=":
                name = self.consume().value
                self.consume("=")
                expr = self.parse_expr()
                self.consume(";")
                return Assign(name, expr)

        expr = self.parse_expr()
        self.consume(";")
        return ExprStmt(expr)

    def parse_expr(self) -> ASTNode:
        return self.parse_logic_or()

    def parse_logic_or(self) -> ASTNode:
        node = self.parse_logic_and()
        while self.match("||"):
            node = _fold_binary("||", node, self.parse_logic_and())
        return node

    def parse_logic_and(self) -> ASTNode:
        node = self.parse_bitwise()
        while self.match("&&"):
            node = _fold_binary("&&", node, self.parse_bitwise())
        return node

    def parse_bitwise(self) -> ASTNode:
        node = self.parse_equality()
        while True:
            if self.match("|"):
                node = _fold_binary("|", node, self.parse_equality())
            elif self.match("^"):
                node = _fold_binary("^", node, self.parse_equality())
            elif self.match("&"):
                node = _fold_binary("&", node, self.parse_equality())
            else:
                break
        return node

    def parse_equality(self) -> ASTNode:
        node = self.parse_relational()
        while True:
            if self.match("=="):
                node = _fold_binary("==", node, self.parse_relational())
            elif self.match("!="):
                node = _fold_binary("!=", node, self.parse_relational())
            else:
                break
        return node

    def parse_relational(self) -> ASTNode:
        node = self.parse_shift()
        while True:
            if self.match("<"):
                node = _fold_binary("<", node, self.parse_shift())
            elif self.match("<="):
                node = _fold_binary("<=", node, self.parse_shift())
            elif self.match(">"):
                node = _fold_binary(">", node, self.parse_shift())
            elif self.match(">="):
                node = _fold_binary(">=", node, self.parse_shift())
            else:
                break
        return node

    def parse_shift(self) -> ASTNode:
        node = self.parse_additive()
        while True:
            if self.match("<<"):
                node = _fold_binary("<<", node, self.parse_additive())
            elif self.match(">>"):
                node = _fold_binary(">>", node, self.parse_additive())
            else:
                break
        return node

    def parse_additive(self) -> ASTNode:
        node = self.parse_multiplicative()
        while True:
            if self.match("+"):
                node = _fold_binary("+", node, self.parse_multiplicative())
            elif self.match("-"):
                node = _fold_binary("-", node, self.parse_multiplicative())
            else:
                break
        return node

    def parse_multiplicative(self) -> ASTNode:
        node = self.parse_unary()
        while True:
            if self.match("*"):
                node = _fold_binary("*", node, self.parse_unary())
            elif self.match("/"):
                node = _fold_binary("/", node, self.parse_unary())
            elif self.match("%"):
                node = _fold_binary("%", node, self.parse_unary())
            else:
                break
        return node

    def parse_unary(self) -> ASTNode:
        tok = self.peek()
        if tok and tok.value in ("++", "--"):
            op = self.consume().value
            return IncDec(self.parse_unary(), is_inc=(op == "++"), is_prefix=True)
        if tok and tok.value in ("-", "!", "~"):
            op = self.consume().value
            return _fold_unary(op, self.parse_unary())
        return self.parse_postfix()

    def parse_postfix(self) -> ASTNode:
        node = self.parse_primary()
        while True:
            tok = self.peek()
            if tok and tok.value in ("++", "--"):
                op = self.consume().value
                node = IncDec(node, is_inc=(op == "++"), is_prefix=False)
            else:
                break
        return node

    def parse_primary(self) -> ASTNode:
        tok = self.consume()
        if tok.type == "NUMBER":
            val = int(tok.value, 16) if tok.value.startswith("0x") else int(tok.value)
            return Literal(val & 0xFF)
        if tok.type == "CHAR":
            raw = tok.value[1:-1]
            if raw == r"\n":
                val = 10
            elif raw == r"\t":
                val = 9
            elif raw == r"\0":
                val = 0
            elif raw == r"\\":
                val = ord("\\")
            elif raw == r"\'":
                val = ord("'")
            elif len(raw) == 1:
                val = ord(raw)
            else:
                val = ord(raw[0])
            return Literal(val & 0xFF)
        if tok.type == "STRING":
            raw = tok.value[1:-1]
            return StringLiteral(raw)
        if tok.type in ("ID", "KEYWORD"):
            if self.match("["):
                idx_expr = self.parse_expr()
                self.consume("]")
                return ArrayAccess(tok.value, idx_expr)
            if self.match("("):
                args: list[ASTNode] = []
                if not self.match(")"):
                    while True:
                        args.append(self.parse_expr())
                        if not self.match(","):
                            self.consume(")")
                            break
                return Call(tok.value, args)
            return Var(tok.value)
        if tok.value == "(":
            expr = self.parse_expr()
            self.consume(")")
            return expr
        raise SyntaxError(f"Line {tok.line}: Unexpected token '{tok.value}'")


def optimize_assembly(lines: list[str]) -> list[str]:
    """Perform peephole optimizations on generated assembly lines.

    Optimizations include:
    - Removing redundant self register moves (MOV Rx, Rx)
    - Simplifying PUSH Rx followed immediately by POP Ry into MOV Ry, Rx (or eliminating if Rx == Ry)
    - Removing redundant LD R16, R30 immediately after ST R30, R16
    - Removing JMP <label> when the next line is <label>:
    """
    current_lines = list(lines)
    for _ in range(5):
        new_lines: list[str] = []
        changed = False
        i = 0
        n = len(current_lines)
        while i < n:
            curr = current_lines[i]
            s_curr = curr.strip()

            # Rule 1: MOV Rx, Rx
            if s_curr.upper().startswith("MOV "):
                parts = s_curr.replace(",", " ").split()
                if len(parts) == 3 and parts[1].upper() == parts[2].upper():
                    changed = True
                    i += 1
                    continue

            # Check 2-instruction peepholes
            if i + 1 < n:
                nxt = current_lines[i + 1]
                s_nxt = nxt.strip()

                # Rule 2: PUSH Rx followed by POP Ry
                if s_curr.upper().startswith("PUSH ") and s_nxt.upper().startswith(
                    "POP "
                ):
                    p_curr = s_curr.split()
                    p_nxt = s_nxt.split()
                    if len(p_curr) == 2 and len(p_nxt) == 2:
                        rx = p_curr[1].upper()
                        ry = p_nxt[1].upper()
                        if rx == ry:
                            changed = True
                            i += 2
                            continue
                        new_lines.append(f"    MOV {ry}, {rx}")
                        changed = True
                        i += 2
                        continue

                # Rule 3: ST R30, R16 followed by LD R16, R30
                if s_curr.upper() == "ST R30, R16" and s_nxt.upper() == "LD R16, R30":
                    new_lines.append(curr)
                    changed = True
                    i += 2
                    continue

                # Rule 4: ST R30, R16 followed by redundant LDI R30, X; LD R16, R30
                if (
                    s_curr.upper() == "ST R30, R16"
                    and i + 2 < n
                    and current_lines[i + 2].strip().upper() == "LD R16, R30"
                    and i > 0
                    and current_lines[i - 1].strip().upper()
                    == current_lines[i + 1].strip().upper()
                ):
                    new_lines.append(curr)
                    changed = True
                    i += 3
                    continue

                # Rule 5: Consecutive duplicate LDI
                if s_curr.upper().startswith("LDI ") and s_nxt.upper().startswith(
                    "LDI "
                ):
                    if s_curr.upper() == s_nxt.upper():
                        changed = True
                        i += 1
                        continue

                # Rule 6: JMP <label> followed by <label>:
                if s_curr.upper().startswith("JMP "):
                    parts = s_curr.split()
                    if len(parts) == 2 and s_nxt == f"{parts[1]}:":
                        new_lines.append(nxt)
                        changed = True
                        i += 2
                        continue

            new_lines.append(curr)
            i += 1

        current_lines = new_lines
        if not changed:
            break

    return current_lines


class CodeGenerator:
    """Generate Tiny8 assembly from AST using register & stack model."""

    PARAM_REGS = [16, 17, 18, 19]

    def __init__(self) -> None:
        self.asm: list[str] = []
        self.label_counter = 0
        self.var_addresses: dict[str, int] = {}
        self.symbols: dict[str, dict[str, Any]] = {}
        self.next_ram = 0x60
        self.current_func = ""
        self.loop_end_stack: list[str] = []

    def new_label(self, prefix: str = "L") -> str:
        self.label_counter += 1
        return f"{prefix}_{self.label_counter}"

    def emit(self, instr: str) -> None:
        self.asm.append(f"    {instr}")

    def emit_label(self, label: str) -> None:
        self.asm.append(f"{label}:")

    def allocate_var(self, name: str, var_type: str = "int") -> int:
        if name not in self.var_addresses:
            if 0x0200 <= self.next_ram <= 0x05FF:
                self.next_ram = 0x0600
            self.var_addresses[name] = self.next_ram
            self.symbols[name] = {
                "addr": self.next_ram,
                "type": var_type,
                "func": self.current_func,
            }
            self.next_ram += 1
        return self.var_addresses[name]

    def allocate_array(self, name: str, size: int, var_type: str = "int") -> int:
        if name not in self.var_addresses:
            if self.next_ram < 0x0600 and (self.next_ram + size) > 0x0200:
                self.next_ram = 0x0600
            self.var_addresses[name] = self.next_ram
            self.symbols[name] = {
                "addr": self.next_ram,
                "type": f"{var_type}[{size}]",
                "func": self.current_func,
            }
            self.next_ram += size
        return self.var_addresses[name]

    def generate(self, program: Program, optimize: bool = True) -> str:
        self.asm = []
        self.label_counter = 0
        self.var_addresses = {}
        self.symbols = {}
        self.next_ram = 0x60
        self.loop_end_stack = []

        for g in program.globals:
            if isinstance(g, ArrayDecl):
                addr = self.allocate_array(g.name, g.size, g.var_type)
                if g.init_values:
                    self.emit(f"LDI R30, {addr & 0xFF}")
                    if addr >= 256:
                        self.emit(f"LDI R31, {addr >> 8}")
                    for i, expr in enumerate(g.init_values):
                        self.gen_expr(expr)
                        self.emit("ST R30, R16")
                        if i < len(g.init_values) - 1:
                            self.emit("ADIW R30, 1")
                    if (addr + len(g.init_values)) >= 256:
                        self.emit("LDI R31, 0")
            elif isinstance(g, VarDecl):
                addr = self.allocate_var(g.name, g.var_type)
                if g.init_expr:
                    self.gen_expr(g.init_expr)
                    self.emit(f"LDI R30, {addr & 0xFF}")
                    if addr >= 256:
                        self.emit(f"LDI R31, {addr >> 8}")
                    self.emit("ST R30, R16")
                    if addr >= 256:
                        self.emit("LDI R31, 0")

        self.emit("JMP main")

        for f in program.functions:
            self.gen_function(f)

        if optimize:
            self.asm = optimize_assembly(self.asm)

        return "\n".join(self.asm)

    def gen_function(self, func: FunctionDef) -> None:
        self.current_func = func.name
        self.emit_label(func.name)

        for i, (ptype, pname) in enumerate(func.params):
            addr = self.allocate_var(pname, ptype)
            reg = self.PARAM_REGS[i]
            self.emit(f"LDI R30, {addr & 0xFF}")
            if addr >= 256:
                self.emit(f"LDI R31, {addr >> 8}")
            self.emit(f"ST R30, R{reg}")
            if addr >= 256:
                self.emit("LDI R31, 0")

        for stmt in func.body.statements:
            self.gen_stmt(stmt)

        if func.name == "main":
            self.emit("halt: JMP halt")
        else:
            self.emit("RET")

    def gen_stmt(self, stmt: ASTNode) -> None:
        if isinstance(stmt, ArrayDecl):
            addr = self.allocate_array(stmt.name, stmt.size, stmt.var_type)
            if stmt.init_values:
                for i, expr in enumerate(stmt.init_values):
                    self.gen_expr(expr)
                    elem_addr = addr + i
                    self.emit(f"LDI R30, {elem_addr & 0xFF}")
                    if elem_addr >= 256:
                        self.emit(f"LDI R31, {elem_addr >> 8}")
                    self.emit("ST R30, R16")
                    if elem_addr >= 256:
                        self.emit("LDI R31, 0")

        elif isinstance(stmt, VarDecl):
            addr = self.allocate_var(stmt.name, stmt.var_type)
            if stmt.init_expr:
                self.gen_expr(stmt.init_expr)
                self.emit(f"LDI R30, {addr & 0xFF}")
                if addr >= 256:
                    self.emit(f"LDI R31, {addr >> 8}")
                self.emit("ST R30, R16")
                if addr >= 256:
                    self.emit("LDI R31, 0")

        elif isinstance(stmt, ArrayAssign):
            base_addr = self.allocate_var(stmt.name)
            self.gen_expr(stmt.index)
            self.emit(f"LDI R30, {base_addr & 0xFF}")
            self.emit(f"LDI R31, {base_addr >> 8}")
            self.emit("ADD R30, R16")
            self.emit("LDI R17, 0")
            self.emit("ADC R31, R17")
            self.emit("PUSH R30")
            self.emit("PUSH R31")
            self.gen_expr(stmt.expr)
            self.emit("MOV R17, R16")
            self.emit("POP R31")
            self.emit("POP R30")
            self.emit("ST R30, R17")
            if base_addr >= 256 or (base_addr + 256) >= 256:
                self.emit("LDI R31, 0")

        elif isinstance(stmt, Assign):
            addr = self.allocate_var(stmt.name)
            self.gen_expr(stmt.expr)
            self.emit(f"LDI R30, {addr & 0xFF}")
            if addr >= 256:
                self.emit(f"LDI R31, {addr >> 8}")
            self.emit("ST R30, R16")

        elif isinstance(stmt, CompoundAssign):
            self.gen_stmt(
                Assign(
                    stmt.name,
                    BinaryOp(op=stmt.op, left=Var(stmt.name), right=stmt.expr),
                )
            )

        elif isinstance(stmt, ArrayCompoundAssign):
            # Evaluate the index once into a hidden slot so side effects in the
            # index expression are not repeated by the read-modify-write.
            tmp = self.new_label("__cidx")
            self.gen_stmt(Assign(tmp, stmt.index))
            idx = Var(tmp)
            self.gen_stmt(
                ArrayAssign(
                    stmt.name,
                    idx,
                    BinaryOp(
                        op=stmt.op,
                        left=ArrayAccess(stmt.name, idx),
                        right=stmt.expr,
                    ),
                )
            )

        elif isinstance(stmt, ForStmt):
            if stmt.init:
                self.gen_stmt(stmt.init)
            lbl_start = self.new_label("for_start")
            lbl_end = self.new_label("for_end")
            self.loop_end_stack.append(lbl_end)
            self.emit_label(lbl_start)
            self.gen_expr(stmt.condition)
            self.emit("CPI R16, 0")
            self.emit(f"BREQ {lbl_end}")
            self.gen_block(stmt.body)
            if stmt.post:
                self.gen_stmt(stmt.post)
            self.emit(f"JMP {lbl_start}")
            self.emit_label(lbl_end)
            self.loop_end_stack.pop()

        elif isinstance(stmt, BreakStmt):
            if self.loop_end_stack:
                self.emit(f"JMP {self.loop_end_stack[-1]}")

        elif isinstance(stmt, IfStmt):
            else_lbl = self.new_label("else")
            end_lbl = self.new_label("endif")
            self.gen_expr(stmt.condition)
            self.emit("CPI R16, 0")
            self.emit(f"BREQ {else_lbl if stmt.else_branch else end_lbl}")

            for s in stmt.then_branch.statements:
                self.gen_stmt(s)

            if stmt.else_branch:
                self.emit(f"JMP {end_lbl}")
                self.emit_label(else_lbl)
                for s in stmt.else_branch.statements:
                    self.gen_stmt(s)

            self.emit_label(end_lbl)

        elif isinstance(stmt, WhileStmt):
            loop_lbl = self.new_label("while_start")
            end_lbl = self.new_label("while_end")
            self.loop_end_stack.append(end_lbl)
            self.emit_label(loop_lbl)
            self.gen_expr(stmt.condition)
            self.emit("CPI R16, 0")
            self.emit(f"BREQ {end_lbl}")

            for s in stmt.body.statements:
                self.gen_stmt(s)

            self.emit(f"JMP {loop_lbl}")
            self.emit_label(end_lbl)
            self.loop_end_stack.pop()

        elif isinstance(stmt, ReturnStmt):
            if stmt.expr:
                self.gen_expr(stmt.expr)
            if self.current_func == "main":
                self.emit("halt_ret: JMP halt_ret")
            else:
                self.emit("RET")

        elif isinstance(stmt, ExprStmt):
            self.gen_expr(stmt.expr)

        elif isinstance(stmt, IncDec):
            self.gen_expr(stmt)

    def gen_block(self, block: Block) -> None:
        for s in block.statements:
            self.gen_stmt(s)

    def gen_expr(self, expr: ASTNode) -> None:
        """Evaluate expression, leaving the 8-bit result in R16."""
        if isinstance(expr, Literal):
            self.emit(f"LDI R16, {expr.value}")

        elif isinstance(expr, ArrayAccess):
            base_addr = self.allocate_var(expr.name)
            self.gen_expr(expr.index)
            self.emit(f"LDI R30, {base_addr & 0xFF}")
            self.emit(f"LDI R31, {base_addr >> 8}")
            self.emit("ADD R30, R16")
            self.emit("LDI R17, 0")
            self.emit("ADC R31, R17")
            self.emit("LD R16, R30")
            if base_addr >= 256 or (base_addr + 256) >= 256:
                self.emit("LDI R31, 0")

        elif isinstance(expr, Var):
            addr = self.allocate_var(expr.name)
            self.emit(f"LDI R30, {addr & 0xFF}")
            if addr >= 256:
                self.emit(f"LDI R31, {addr >> 8}")
            self.emit("LD R16, R30")
            if addr >= 256:
                self.emit("LDI R31, 0")

        elif isinstance(expr, UnaryOp):
            self.gen_expr(expr.operand)
            if expr.op == "-":
                self.emit("NEG R16")
            elif expr.op == "~":
                self.emit("COM R16")
            elif expr.op == "!":
                lbl_true = self.new_label("not_true")
                lbl_end = self.new_label("not_end")
                self.emit("CPI R16, 0")
                self.emit(f"BREQ {lbl_true}")
                self.emit("LDI R16, 0")
                self.emit(f"JMP {lbl_end}")
                self.emit_label(lbl_true)
                self.emit("LDI R16, 1")
                self.emit_label(lbl_end)

        elif isinstance(expr, IncDec):
            instr = "INC" if expr.is_inc else "DEC"
            if isinstance(expr.expr, Var):
                addr = self.allocate_var(expr.expr.name)
                self.emit(f"LDI R30, {addr & 0xFF}")
                if addr >= 256:
                    self.emit(f"LDI R31, {addr >> 8}")
                self.emit("LD R16, R30")
                if expr.is_prefix:
                    self.emit(f"{instr} R16")
                    self.emit("ST R30, R16")
                else:
                    self.emit("MOV R17, R16")
                    self.emit(f"{instr} R17")
                    self.emit("ST R30, R17")
                if addr >= 256:
                    self.emit("LDI R31, 0")

            elif isinstance(expr.expr, ArrayAccess):
                base_addr = self.allocate_var(expr.expr.name)
                self.gen_expr(expr.expr.index)
                self.emit(f"LDI R30, {base_addr & 0xFF}")
                self.emit(f"LDI R31, {base_addr >> 8}")
                self.emit("ADD R30, R16")
                self.emit("LDI R17, 0")
                self.emit("ADC R31, R17")
                self.emit("LD R16, R30")
                if expr.is_prefix:
                    self.emit(f"{instr} R16")
                    self.emit("ST R30, R16")
                else:
                    self.emit("MOV R17, R16")
                    self.emit(f"{instr} R17")
                    self.emit("ST R30, R17")
                self.emit("LDI R31, 0")

            else:
                raise SyntaxError(f"Invalid lvalue for {'++' if expr.is_inc else '--'}")

        elif (
            isinstance(expr, BinaryOp)
            and expr.op in ("<<", ">>")
            and isinstance(expr.right, Literal)
        ):
            # Constant shift count: unroll into LSL/LSR. Shifting an 8-bit
            # value by 8 or more clears it.
            self.gen_expr(expr.left)
            if expr.right.value >= 8:
                self.emit("LDI R16, 0")
            else:
                instr = "LSL" if expr.op == "<<" else "LSR"
                for _ in range(expr.right.value):
                    self.emit(f"{instr} R16")

        elif isinstance(expr, BinaryOp):
            self.gen_expr(expr.left)
            self.emit("PUSH R16")
            self.gen_expr(expr.right)
            self.emit("MOV R17, R16")
            self.emit("POP R16")

            if expr.op == "+":
                self.emit("ADD R16, R17")
            elif expr.op == "-":
                self.emit("SUB R16, R17")
            elif expr.op == "*":
                self.emit("MUL R16, R17")
                self.emit("MOV R16, R0")
            elif expr.op == "/":
                lbl_loop = self.new_label("div_loop")
                lbl_end = self.new_label("div_end")
                self.emit("CLR R18")
                self.emit_label(lbl_loop)
                self.emit("CP R16, R17")
                self.emit(f"BRLO {lbl_end}")
                self.emit("SUB R16, R17")
                self.emit("INC R18")
                self.emit(f"JMP {lbl_loop}")
                self.emit_label(lbl_end)
                self.emit("MOV R16, R18")
            elif expr.op == "%":
                lbl_loop = self.new_label("mod_loop")
                lbl_end = self.new_label("mod_end")
                self.emit_label(lbl_loop)
                self.emit("CP R16, R17")
                self.emit(f"BRLO {lbl_end}")
                self.emit("SUB R16, R17")
                self.emit(f"JMP {lbl_loop}")
                self.emit_label(lbl_end)
            elif expr.op == "&":
                self.emit("AND R16, R17")
            elif expr.op == "|":
                self.emit("OR R16, R17")
            elif expr.op == "^":
                self.emit("EOR R16, R17")
            elif expr.op in ("<<", ">>"):
                # Variable shift count: shift once per iteration until R17 is 0.
                instr = "LSL" if expr.op == "<<" else "LSR"
                lbl_loop = self.new_label("shift_loop")
                lbl_end = self.new_label("shift_end")
                self.emit_label(lbl_loop)
                self.emit("CPI R17, 0")
                self.emit(f"BREQ {lbl_end}")
                self.emit(f"{instr} R16")
                self.emit("DEC R17")
                self.emit(f"JMP {lbl_loop}")
                self.emit_label(lbl_end)
            elif expr.op == "&&":
                lbl_false = self.new_label("and_false")
                lbl_end = self.new_label("and_end")
                self.emit("CPI R16, 0")
                self.emit(f"BREQ {lbl_false}")
                self.emit("CPI R17, 0")
                self.emit(f"BREQ {lbl_false}")
                self.emit("LDI R16, 1")
                self.emit(f"JMP {lbl_end}")
                self.emit_label(lbl_false)
                self.emit("LDI R16, 0")
                self.emit_label(lbl_end)
            elif expr.op == "||":
                lbl_true = self.new_label("or_true")
                lbl_end = self.new_label("or_end")
                self.emit("CPI R16, 0")
                self.emit(f"BRNE {lbl_true}")
                self.emit("CPI R17, 0")
                self.emit(f"BRNE {lbl_true}")
                self.emit("LDI R16, 0")
                self.emit(f"JMP {lbl_end}")
                self.emit_label(lbl_true)
                self.emit("LDI R16, 1")
                self.emit_label(lbl_end)
            elif expr.op in ("==", "!=", "<", "<=", ">", ">="):
                lbl_true = self.new_label("cmp_true")
                lbl_end = self.new_label("cmp_end")
                if expr.op in (">", ">="):
                    self.emit("CP R17, R16")
                else:
                    self.emit("CP R16, R17")

                if expr.op in ("==",):
                    self.emit(f"BREQ {lbl_true}")
                elif expr.op in ("!=",):
                    self.emit(f"BRNE {lbl_true}")
                elif expr.op in ("<", ">"):
                    self.emit(f"BRLT {lbl_true}")
                elif expr.op in ("<=", ">="):
                    self.emit(f"BRLT {lbl_true}")
                    self.emit(f"BREQ {lbl_true}")

                self.emit("LDI R16, 0")
                self.emit(f"JMP {lbl_end}")
                self.emit_label(lbl_true)
                self.emit("LDI R16, 1")
                self.emit_label(lbl_end)

        elif isinstance(expr, Call):
            if expr.name == "peek":
                self.gen_expr(expr.args[0])
                self.emit("MOV R30, R16")
                self.emit("LD R16, R30")
            elif expr.name == "poke":
                self.gen_expr(expr.args[0])
                self.emit("PUSH R16")
                self.gen_expr(expr.args[1])
                self.emit("MOV R17, R16")
                self.emit("POP R30")
                self.emit("ST R30, R17")
                self.emit("MOV R16, R17")
            elif expr.name == "vram_set":
                self.gen_expr(expr.args[1])
                self.emit("MOV R30, R16")
                self.emit("LDI R17, 32")
                self.emit("MUL R30, R17")
                self.emit("PUSH R0")
                self.emit("PUSH R1")
                self.emit("LDI R31, 0")
                self.gen_expr(expr.args[0])
                self.emit("MOV R17, R16")
                self.emit("POP R31")
                self.emit("POP R30")
                self.emit("ADD R30, R17")
                self.emit("LDI R17, 0")
                self.emit("ADC R31, R17")
                self.emit("LDI R17, 2")
                self.emit("ADD R31, R17")
                self.emit("PUSH R30")
                self.emit("PUSH R31")
                self.emit("LDI R31, 0")
                self.gen_expr(expr.args[2])
                self.emit("MOV R17, R16")
                self.emit("POP R31")
                self.emit("POP R30")
                self.emit("ST R30, R17")
                self.emit("LDI R31, 0")
                self.emit("MOV R16, R17")
            elif expr.name == "vram_get":
                self.gen_expr(expr.args[1])
                self.emit("MOV R30, R16")
                self.emit("LDI R17, 32")
                self.emit("MUL R30, R17")
                self.emit("PUSH R0")
                self.emit("PUSH R1")
                self.emit("LDI R31, 0")
                self.gen_expr(expr.args[0])
                self.emit("MOV R17, R16")
                self.emit("POP R31")
                self.emit("POP R30")
                self.emit("ADD R30, R17")
                self.emit("LDI R17, 0")
                self.emit("ADC R31, R17")
                self.emit("LDI R17, 2")
                self.emit("ADD R31, R17")
                self.emit("LD R16, R30")
                self.emit("LDI R31, 0")
            elif expr.name == "vram_clear":
                lbl_loop = self.new_label("vclr_loop")
                self.emit("LDI R30, 0x00")
                self.emit("LDI R31, 0x02")
                self.emit("LDI R16, 32")
                self.emit_label(lbl_loop)
                self.emit("ST R30, R16")
                self.emit("ADIW R30, 1")
                self.emit("CPI R30, 0x00")
                self.emit(f"BRNE {lbl_loop}")
                self.emit("CPI R31, 0x06")
                self.emit(f"BRNE {lbl_loop}")
                self.emit("LDI R31, 0")
            elif expr.name == "vram_puts":
                str_val = (
                    expr.args[2].value
                    if isinstance(expr.args[2], StringLiteral)
                    else ""
                )
                if str_val:
                    self.gen_expr(expr.args[1])
                    self.emit("MOV R30, R16")
                    self.emit("LDI R17, 32")
                    self.emit("MUL R30, R17")
                    self.emit("PUSH R0")
                    self.emit("PUSH R1")
                    self.emit("LDI R31, 0")
                    self.gen_expr(expr.args[0])
                    self.emit("MOV R17, R16")
                    self.emit("POP R31")
                    self.emit("POP R30")
                    self.emit("ADD R30, R17")
                    self.emit("LDI R17, 0")
                    self.emit("ADC R31, R17")
                    self.emit("LDI R17, 2")
                    self.emit("ADD R31, R17")
                    for i, ch in enumerate(str_val):
                        self.emit(f"LDI R17, {ord(ch)}")
                        self.emit("ST R30, R17")
                        if i < len(str_val) - 1:
                            self.emit("ADIW R30, 1")
                    self.emit("LDI R31, 0")
            elif expr.name == "in":
                self.gen_expr(expr.args[0])
                self.emit("MOV R30, R16")
                self.emit("IN R16, R30")
            elif expr.name == "out":
                self.gen_expr(expr.args[0])
                self.emit("PUSH R16")
                self.gen_expr(expr.args[1])
                self.emit("MOV R17, R16")
                self.emit("POP R30")
                self.emit("OUT R30, R17")
                self.emit("MOV R16, R17")
            else:
                for arg in expr.args:
                    self.gen_expr(arg)
                    self.emit("PUSH R16")
                for i in range(len(expr.args) - 1, -1, -1):
                    if i < len(self.PARAM_REGS):
                        self.emit(f"POP R{self.PARAM_REGS[i]}")
                    else:
                        self.emit("POP R0")
                self.emit(f"RCALL {expr.name}")


def compile_c(source: str, optimize: bool = True) -> str:
    """Compile C source code string into Tiny8 assembly.

    Args:
        source: C language source code text.
        optimize: Whether to apply peephole optimization. Defaults to True.

    Returns:
        Generated Tiny8 assembly source string.
    """
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    ast = parser.parse()
    generator = CodeGenerator()
    return generator.generate(ast, optimize=optimize)


def compile_c_file(path: str, optimize: bool = True) -> str:
    """Read and compile C source file into Tiny8 assembly.

    Args:
        path: Path to C source file.
        optimize: Whether to apply peephole optimization. Defaults to True.

    Returns:
        Generated Tiny8 assembly source string.
    """
    with open(path, "r", encoding="utf-8") as f:
        return compile_c(f.read(), optimize=optimize)


def compile_c_with_symbols(
    source: str, optimize: bool = True
) -> tuple[str, dict[str, dict[str, Any]]]:
    """Compile C source into Tiny8 assembly alongside variable symbol table.

    Args:
        source: C language source code text.
        optimize: Whether to apply peephole optimization. Defaults to True.

    Returns:
        Tuple of (assembly_source_string, symbols_dict).
    """
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    ast = parser.parse()
    generator = CodeGenerator()
    asm = generator.generate(ast, optimize=optimize)
    return asm, generator.symbols


def compile_c_file_with_symbols(
    path: str, optimize: bool = True
) -> tuple[str, dict[str, dict[str, Any]]]:
    """Read and compile C source file into Tiny8 assembly with symbol table.

    Args:
        path: Path to C source file.
        optimize: Whether to apply peephole optimization. Defaults to True.

    Returns:
        Tuple of (assembly_source_string, symbols_dict).
    """
    with open(path, "r", encoding="utf-8") as f:
        return compile_c_with_symbols(f.read(), optimize=optimize)
