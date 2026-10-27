"""Unit tests for Tiny8 C compiler."""

import pytest

from tiny8 import CPU, assemble
from tiny8.compiler import (
    BinaryOp,
    Call,
    CodeGenerator,
    ContinueStmt,
    DoWhileStmt,
    Lexer,
    Literal,
    Parser,
    Token,
    UnaryOp,
    _fold_binary,
    _fold_unary,
    compile_c,
    compile_c_file,
    compile_c_file_with_symbols,
    optimize_assembly,
)


def test_compiler_variable_and_arithmetic():
    c_code = """
    int main() {
        int a = 10;
        int b = 25;
        int c = a + b;
        poke(0x80, c);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=100, show_progress=False)

    # 10 + 25 = 35
    assert cpu.read_ram(0x80) == 35


def test_compiler_while_loop():
    c_code = """
    int main() {
        int sum = 0;
        int i = 5;
        while (i > 0) {
            sum = sum + i;
            i = i - 1;
        }
        poke(0x81, sum);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=200, show_progress=False)

    # 5 + 4 + 3 + 2 + 1 = 15
    assert cpu.read_ram(0x81) == 15


def test_compiler_do_while_basic():
    c_code = """
    int main() {
        int sum = 0;
        int i = 1;
        do {
            sum = sum + i;
            i = i + 1;
        } while (i <= 5);
        poke(0x81, sum);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=300, show_progress=False)

    # 1 + 2 + 3 + 4 + 5 = 15
    assert cpu.read_ram(0x81) == 15


def test_compiler_do_while_false_condition_executes_once():
    c_code = """
    int main() {
        int x = 10;
        do {
            x = x + 5;
        } while (0);
        poke(0x82, x);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=100, show_progress=False)

    # Executed exactly once: 10 + 5 = 15
    assert cpu.read_ram(0x82) == 15


def test_compiler_do_while_break_and_continue():
    c_code = """
    int main() {
        int sum = 0;
        int i = 0;
        do {
            i = i + 1;
            if (i == 2) {
                continue;
            }
            if (i == 4) {
                break;
            }
            sum = sum + i;
        } while (i < 5);
        poke(0x83, sum);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=300, show_progress=False)

    # i=1: sum = 1
    # i=2: continue (sum not added)
    # i=3: sum = 1 + 3 = 4
    # i=4: break (loop terminates)
    assert cpu.read_ram(0x83) == 4


def test_compiler_do_while_single_statement():
    c_code = """
    int main() {
        int x = 0;
        do x = x + 1; while (x < 3);
        poke(0x84, x);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=200, show_progress=False)

    assert cpu.read_ram(0x84) == 3


def test_compiler_do_while_ast_and_lexer():
    tokens = Lexer("do { x = 1; } while (x < 10);").tokenize()
    assert tokens[0].type == "KEYWORD"
    assert tokens[0].value == "do"

    prog = Parser(Lexer("void main() { do { x = 1; } while (1); }").tokenize()).parse()
    stmt = prog.functions[0].body.statements[0]
    assert isinstance(stmt, DoWhileStmt)
    assert len(stmt.body.statements) == 1
    assert isinstance(stmt.condition, Literal)
    assert stmt.condition.value == 1


def test_compiler_if_else():
    c_code = """
    int main() {
        int x = 20;
        int res = 0;
        if (x < 15) {
            res = 1;
        } else {
            res = 2;
        }
        poke(0x82, res);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=100, show_progress=False)

    assert cpu.read_ram(0x82) == 2


def test_compiler_function_call():
    c_code = """
    int double_val(int x) {
        return x * 2;
    }

    int main() {
        int val = double_val(21);
        poke(0x83, val);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=150, show_progress=False)

    # 21 * 2 = 42
    assert cpu.read_ram(0x83) == 42


def test_compiler_for_loop_and_break():
    c_code = """
    int main() {
        int sum = 0;
        int i = 0;
        for (i = 0; i < 10; i = i + 1) {
            if (i == 4) {
                break;
            }
            sum = sum + i;
        }
        poke(0x84, sum);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=300, show_progress=False)

    # 0 + 1 + 2 + 3 = 6
    assert cpu.read_ram(0x84) == 6


def test_compiler_while_loop_continue():
    c_code = """
    int main() {
        int sum = 0;
        int i = 0;
        while (i < 6) {
            i = i + 1;
            if (i == 3) {
                continue;
            }
            sum = sum + i;
        }
        poke(0x84, sum);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=300, show_progress=False)

    # 1 + 2 + 4 + 5 + 6 = 18
    assert cpu.read_ram(0x84) == 18


def test_compiler_for_loop_continue():
    c_code = """
    int main() {
        int sum = 0;
        int i = 0;
        for (i = 0; i < 6; i = i + 1) {
            if (i == 3) {
                continue;
            }
            sum = sum + i;
        }
        poke(0x84, sum);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=300, show_progress=False)

    # 0 + 1 + 2 + 4 + 5 = 12
    assert cpu.read_ram(0x84) == 12


def test_compiler_nested_loops_continue_and_break():
    c_code = """
    int main() {
        int sum = 0;
        int i = 0;
        int j = 0;
        for (i = 0; i < 4; i = i + 1) {
            if (i == 1) {
                continue;
            }
            j = 0;
            while (j < 4) {
                j = j + 1;
                if (j == 2) {
                    continue;
                }
                if (j == 4) {
                    break;
                }
                sum = sum + 1;
            }
        }
        poke(0x84, sum);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=1000, show_progress=False)

    # i: 0, 2, 3 (i=1 skipped)
    # for each i: j=1 -> sum++, j=2 -> continue, j=3 -> sum++, j=4 -> break
    # sum = 3 * 2 = 6
    assert cpu.read_ram(0x84) == 6


def test_compiler_continue_ast_and_lexer():
    tokens = Lexer("continue;").tokenize()
    assert len(tokens) == 2
    assert tokens[0].type == "KEYWORD"
    assert tokens[0].value == "continue"

    prog = Parser(Lexer("void main() { continue; }").tokenize()).parse()
    assert isinstance(prog.functions[0].body.statements[0], ContinueStmt)


def test_compiler_array():
    c_code = """
    int main() {
        int arr[4];
        arr[0] = 10;
        arr[1] = 20;
        arr[2] = 30;
        arr[3] = arr[0] + arr[1] + arr[2];
        poke(0x85, arr[3]);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=300, show_progress=False)

    assert cpu.read_ram(0x85) == 60


def test_compiler_vram():
    c_code = """
    int main() {
        vram_set(2, 3, 5);
        int v = vram_get(2, 3);
        poke(0x86, v);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=200, show_progress=False)

    # 0x0200 + 3*32 + 2 = 0x0200 + 98 = 610
    assert cpu.read_ram(512 + 3 * 32 + 2) == 5
    assert cpu.read_ram(0x86) == 5


def test_compiler_char_literals():
    c_code = """
    int main() {
        char ch = 'T';
        poke(0x87, ch);
        vram_set(0, 0, 'O');
        int v = vram_get(0, 0);
        poke(0x88, v);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=200, show_progress=False)

    assert cpu.read_ram(0x87) == ord("T")
    assert cpu.read_ram(512) == ord("O")
    assert cpu.read_ram(0x88) == ord("O")


def test_compiler_vram_puts():
    c_code = """
    int main() {
        vram_puts(14, 1, "TINY8");
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=200, show_progress=False)

    # row 1, col 14: 0x0200 + 1*32 + 14 = 512 + 32 + 14 = 558
    assert "".join(chr(cpu.read_ram(558 + i)) for i in range(5)) == "TINY8"


def test_compiler_array_initializer():
    c_code = """
    int g_arr[3] = {10, 20, 30};
    int main() {
        int l_arr[] = {40, 50};
        poke(0x70, g_arr[1]);
        poke(0x71, l_arr[0]);
        poke(0x72, l_arr[1]);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=500, show_progress=False)

    assert cpu.read_ram(0x70) == 20
    assert cpu.read_ram(0x71) == 40
    assert cpu.read_ram(0x72) == 50


def _run_c(c_code: str, max_steps: int = 2000) -> CPU:
    cpu = CPU()
    cpu.load_program(assemble(compile_c(c_code)))
    cpu.run(max_steps=max_steps, show_progress=False)
    return cpu


def test_compiler_shift_by_literal():
    cpu = _run_c(
        """
    int main() {
        int x = 3;
        int y = 200;
        int z = 0x81;
        poke(0xC0, x << 3);
        poke(0xC1, y >> 2);
        poke(0xC2, z << 1);
        poke(0xC3, z >> 7);
        poke(0xC4, x << 0);
        poke(0xC5, y >> 8);
        poke(0xC6, y << 9);
        return 0;
    }
    """
    )
    assert cpu.read_ram(0xC0) == 24
    assert cpu.read_ram(0xC1) == 50
    assert cpu.read_ram(0xC2) == 0x02  # bit 7 shifted out of the 8-bit value
    assert cpu.read_ram(0xC3) == 1  # logical shift: no sign extension
    assert cpu.read_ram(0xC4) == 3
    assert cpu.read_ram(0xC5) == 0
    assert cpu.read_ram(0xC6) == 0


def test_compiler_shift_by_variable():
    cpu = _run_c(
        """
    int main() {
        int a = 5;
        int b = 0xF0;
        int n = 3;
        int zero = 0;
        poke(0xC0, a << n);
        poke(0xC1, b >> n);
        poke(0xC2, a << zero);
        poke(0xC3, b >> zero);
        n = 8;
        poke(0xC4, b >> n);
        return 0;
    }
    """
    )
    assert cpu.read_ram(0xC0) == 40
    assert cpu.read_ram(0xC1) == 30
    assert cpu.read_ram(0xC2) == 5
    assert cpu.read_ram(0xC3) == 0xF0
    assert cpu.read_ram(0xC4) == 0


def test_compiler_shift_precedence():
    cpu = _run_c(
        """
    int main() {
        int x = 1;
        int y = 3;
        poke(0xC0, x << 2 + 1);
        poke(0xC1, y << 1 < 7);
        poke(0xC2, y << 1 > 7);
        poke(0xC3, 64 >> 2 >> 1);
        return 0;
    }
    """
    )
    assert cpu.read_ram(0xC0) == 8  # x << (2 + 1)
    assert cpu.read_ram(0xC1) == 1  # (y << 1) < 7
    assert cpu.read_ram(0xC2) == 0  # (y << 1) > 7
    assert cpu.read_ram(0xC3) == 8  # left-associative: (64 >> 2) >> 1


def test_compiler_shift_by_literal_is_unrolled():
    asm = compile_c(
        """
    int main() {
        int x = 3;
        return x << 3;
    }
    """
    )
    assert asm.count("LSL R16") == 3
    assert "shift_loop" not in asm


def test_compiler_shift_by_eight_or_more_is_zero_without_unrolling():
    asm = compile_c(
        """
    int main() {
        int x = 3;
        return x << 200;
    }
    """
    )
    assert "LSL" not in asm
    assert "shift_loop" not in asm


class TestCompilerOptimization:
    """Unit tests for compiler peephole optimization and constant folding."""

    def test_constant_folding_basic_arithmetic(self):
        """Verify that arithmetic on literals is folded at compile time."""
        src = """
        int main() {
            int x = 10 + 20 * 2;
            return x;
        }
        """
        asm = compile_c(src, optimize=True)
        # 10 + 20 * 2 = 50 -> should emit LDI R16, 50 directly without ADD/MUL
        assert "LDI R16, 50" in asm
        assert "ADD" not in asm
        assert "MUL" not in asm

    def test_constant_folding_bitwise_and_logic(self):
        """Verify bitwise and relational expressions are folded at compile time."""
        src = """
        int main() {
            int a = 0xFF & 0x0F;
            int b = 5 > 2;
            int c = !0;
            return a + b + c;
        }
        """
        asm = compile_c(src, optimize=True)
        assert "LDI R16, 15" in asm  # 0xFF & 0x0F = 15
        assert "LDI R16, 1" in asm  # 5 > 2 = 1, !0 = 1

    def test_constant_folding_shifts(self):
        """Verify shifts on literals are folded to 8-bit results."""
        src = """
        int main() {
            int a = 1 << 7;
            int b = 0xF0 >> 4;
            int c = 0x81 << 1;
            return a + b + c;
        }
        """
        asm = compile_c(src, optimize=True)
        assert "LDI R16, 128" in asm
        assert "LDI R16, 15" in asm
        assert "LDI R16, 2" in asm
        assert "LSL" not in asm
        assert "LSR" not in asm
        assert "shift_loop" not in asm

    def test_peephole_remove_redundant_mov(self):
        """Verify that MOV Rx, Rx is eliminated."""
        lines = [
            "    LDI R16, 42",
            "    MOV R16, R16",
            "    MOV R17, R17",
            "    RET",
        ]
        opt = optimize_assembly(lines)
        assert opt == ["    LDI R16, 42", "    RET"]

    def test_peephole_push_pop_simplification(self):
        """Verify PUSH Rx; POP Ry becomes MOV Ry, Rx and PUSH Rx; POP Rx is eliminated."""
        lines = [
            "    PUSH R16",
            "    POP R17",
            "    PUSH R18",
            "    POP R18",
            "    RET",
        ]
        opt = optimize_assembly(lines)
        assert opt == ["    MOV R17, R16", "    RET"]

    def test_peephole_remove_redundant_store_reload(self):
        """Verify store followed immediately by reload is eliminated."""
        lines = [
            "    LDI R30, 96",
            "    ST R30, R16",
            "    LDI R30, 96",
            "    LD R16, R30",
            "    RET",
        ]
        opt = optimize_assembly(lines)
        assert opt == [
            "    LDI R30, 96",
            "    ST R30, R16",
            "    RET",
        ]

    def test_peephole_remove_jump_to_next_label(self):
        """Verify JMP target immediately preceding target: is removed."""
        lines = [
            "    JMP loop",
            "loop:",
            "    NOP",
        ]
        opt = optimize_assembly(lines)
        assert opt == ["loop:", "    NOP"]


def _run_compound_program(c_code, max_steps=5000):
    cpu = CPU()
    cpu.load_program(assemble(compile_c(c_code)))
    cpu.run(max_steps=max_steps, show_progress=False)
    return cpu


def test_compiler_compound_assign_scalar_operators():
    cpu = _run_compound_program(
        """
        int main() {
            int a = 10;
            a += 5;
            poke(0x80, a);
            a -= 3;
            poke(0x81, a);
            a *= 2;
            poke(0x82, a);
            a /= 5;
            poke(0x83, a);
            a %= 3;
            poke(0x84, a);
            a |= 6;
            poke(0x85, a);
            a &= 5;
            poke(0x86, a);
            a ^= 3;
            poke(0x87, a);
            return 0;
        }
        """
    )
    assert [cpu.read_ram(0x80 + i) for i in range(8)] == [15, 12, 24, 4, 1, 7, 5, 6]


def test_compiler_compound_assign_uses_whole_right_hand_side():
    cpu = _run_compound_program(
        """
        int main() {
            int a = 3;
            int b = 4;
            a += b * 2;
            poke(0x80, a);
            return 0;
        }
        """
    )
    assert cpu.read_ram(0x80) == 11


def test_compiler_compound_assign_in_for_loop_step():
    cpu = _run_compound_program(
        """
        int main() {
            int sum = 0;
            int i = 0;
            for (i = 0; i < 10; i += 2) {
                sum += i;
            }
            poke(0x80, sum);
            return 0;
        }
        """
    )
    assert cpu.read_ram(0x80) == 20


def test_compiler_compound_assign_array_elements():
    cpu = _run_compound_program(
        """
        int main() {
            int arr[3] = {1, 2, 3};
            arr[1] += 10;
            arr[2] *= 4;
            poke(0x80, arr[0]);
            poke(0x81, arr[1]);
            poke(0x82, arr[2]);
            return 0;
        }
        """
    )
    assert [cpu.read_ram(0x80 + i) for i in range(3)] == [1, 12, 12]


def test_compiler_compound_assign_array_index_evaluated_once():
    # The index expression writes to RAM as a side effect, so evaluating it twice
    # would read one element and write another.
    cpu = _run_compound_program(
        """
        int main() {
            int arr[2] = {5, 7};
            arr[poke(0x90, peek(0x90) + 1) - 1] += 10;
            poke(0x80, arr[0]);
            poke(0x81, arr[1]);
            return 0;
        }
        """
    )
    assert cpu.read_ram(0x90) == 1
    assert cpu.read_ram(0x80) == 15
    assert cpu.read_ram(0x81) == 7


def test_compiler_inc_dec_scalars():
    cpu = _run_compound_program(
        """
        int main() {
            int a = 10;
            int b = a++;
            poke(0x80, a);
            poke(0x81, b);

            int c = ++a;
            poke(0x82, a);
            poke(0x83, c);

            int d = a--;
            poke(0x84, a);
            poke(0x85, d);

            int e = --a;
            poke(0x86, a);
            poke(0x87, e);
            return 0;
        }
        """
    )
    # a was 10. b = a++ -> a becomes 11, b is 10.
    assert cpu.read_ram(0x80) == 11
    assert cpu.read_ram(0x81) == 10

    # a was 11. c = ++a -> a becomes 12, c is 12.
    assert cpu.read_ram(0x82) == 12
    assert cpu.read_ram(0x83) == 12

    # a was 12. d = a-- -> a becomes 11, d is 12.
    assert cpu.read_ram(0x84) == 11
    assert cpu.read_ram(0x85) == 12

    # a was 11. e = --a -> a becomes 10, e is 10.
    assert cpu.read_ram(0x86) == 10
    assert cpu.read_ram(0x87) == 10


def test_compiler_inc_dec_standalone_statements():
    cpu = _run_compound_program(
        """
        int main() {
            int x = 5;
            x++;
            poke(0x80, x);
            ++x;
            poke(0x81, x);
            x--;
            poke(0x82, x);
            --x;
            poke(0x83, x);
            return 0;
        }
        """
    )
    assert [cpu.read_ram(0x80 + i) for i in range(4)] == [6, 7, 6, 5]


def test_compiler_inc_dec_for_loop():
    cpu = _run_compound_program(
        """
        int main() {
            int sum = 0;
            int i = 0;
            for (i = 0; i < 5; i++) {
                sum += i;
            }
            poke(0x80, sum);
            poke(0x81, i);

            int count = 0;
            for (i = 5; i > 0; --i) {
                count += 1;
            }
            poke(0x82, count);
            poke(0x83, i);
            return 0;
        }
        """
    )
    assert cpu.read_ram(0x80) == 10
    assert cpu.read_ram(0x81) == 5
    assert cpu.read_ram(0x82) == 5
    assert cpu.read_ram(0x83) == 0


def test_compiler_inc_dec_while_loop_issue_example():
    # Example from Issue #36
    cpu = _run_compound_program(
        """
        int main() {
            int i = 0;
            while (i++ < 5) {
                poke(0x80, i);
            }
            poke(0x81, i);
            return 0;
        }
        """
    )
    # The last value poked inside the loop should be 5
    assert cpu.read_ram(0x80) == 5
    # When loop terminates (5 < 5 is False), i has been incremented to 6
    assert cpu.read_ram(0x81) == 6


def test_compiler_inc_dec_while_countdown():
    cpu = _run_compound_program(
        """
        int main() {
            int n = 4;
            int count = 0;
            while (n--) {
                count++;
            }
            poke(0x80, count);
            return 0;
        }
        """
    )
    # Runs for n = 4, 3, 2, 1 (4 times)
    assert cpu.read_ram(0x80) == 4


def test_compiler_inc_dec_array_elements():
    cpu = _run_compound_program(
        """
        int main() {
            int arr[3] = {10, 20, 30};
            int a = arr[0]++;
            poke(0x80, a);
            poke(0x81, arr[0]);

            int b = ++arr[1];
            poke(0x82, b);
            poke(0x83, arr[1]);

            int c = arr[2]--;
            poke(0x84, c);
            poke(0x85, arr[2]);

            int d = --arr[2];
            poke(0x86, d);
            poke(0x87, arr[2]);
            return 0;
        }
        """
    )
    assert cpu.read_ram(0x80) == 10
    assert cpu.read_ram(0x81) == 11
    assert cpu.read_ram(0x82) == 21
    assert cpu.read_ram(0x83) == 21
    assert cpu.read_ram(0x84) == 30
    assert cpu.read_ram(0x85) == 29
    assert cpu.read_ram(0x86) == 28
    assert cpu.read_ram(0x87) == 28


def test_compiler_inc_dec_array_statement():
    cpu = _run_compound_program(
        """
        int main() {
            int arr[2] = {100, 200};
            arr[0]++;
            arr[1]--;
            poke(0x80, arr[0]);
            poke(0x81, arr[1]);
            return 0;
        }
        """
    )
    assert cpu.read_ram(0x80) == 101
    assert cpu.read_ram(0x81) == 199


def test_compiler_inc_dec_array_index_evaluated_once():
    cpu = _run_compound_program(
        """
        int main() {
            int arr[2] = {5, 7};
            arr[poke(0x90, peek(0x90) + 1) - 1]++;
            poke(0x80, arr[0]);
            poke(0x81, arr[1]);
            return 0;
        }
        """
    )
    assert cpu.read_ram(0x90) == 1
    assert cpu.read_ram(0x80) == 6
    assert cpu.read_ram(0x81) == 7


def test_compiler_inc_dec_in_expressions():
    cpu = _run_compound_program(
        """
        int main() {
            int x = 5;
            int y = x++ + 10;
            poke(0x80, x);
            poke(0x81, y);

            int z = ++x * 2;
            poke(0x82, x);
            poke(0x83, z);
            return 0;
        }
        """
    )
    # x was 5. y = 5 + 10 = 15. x becomes 6.
    assert cpu.read_ram(0x80) == 6
    assert cpu.read_ram(0x81) == 15
    # x was 6. ++x -> x is 7. z = 7 * 2 = 14.
    assert cpu.read_ram(0x82) == 7
    assert cpu.read_ram(0x83) == 14


def test_compiler_inc_dec_overflow_underflow():
    cpu = _run_compound_program(
        """
        int main() {
            int a = 255;
            a++;
            poke(0x80, a);

            int b = 0;
            b--;
            poke(0x81, b);
            return 0;
        }
        """
    )
    assert cpu.read_ram(0x80) == 0
    assert cpu.read_ram(0x81) == 255


def test_compiler_inc_dec_invalid_lvalue_raises():
    with pytest.raises(SyntaxError):
        compile_c("int main() { 5++; return 0; }")

    with pytest.raises(SyntaxError):
        compile_c("int main() { ++5; return 0; }")

    with pytest.raises(SyntaxError):
        compile_c("int main() { (1 + 2)++; return 0; }")


def test_constant_folding_all_operators():
    # _fold_binary
    assert _fold_binary("-", Literal(10), Literal(4)) == Literal(6)
    assert _fold_binary("/", Literal(10), Literal(3)) == Literal(3)
    assert _fold_binary("%", Literal(10), Literal(3)) == Literal(1)
    assert _fold_binary("/", Literal(10), Literal(0)) == BinaryOp(
        "/", Literal(10), Literal(0)
    )
    assert _fold_binary("%", Literal(10), Literal(0)) == BinaryOp(
        "%", Literal(10), Literal(0)
    )
    assert _fold_binary("|", Literal(2), Literal(4)) == Literal(6)
    assert _fold_binary("^", Literal(3), Literal(1)) == Literal(2)
    assert _fold_binary("==", Literal(5), Literal(5)) == Literal(1)
    assert _fold_binary("==", Literal(5), Literal(6)) == Literal(0)
    assert _fold_binary("!=", Literal(5), Literal(6)) == Literal(1)
    assert _fold_binary("!=", Literal(5), Literal(5)) == Literal(0)
    assert _fold_binary("<", Literal(4), Literal(5)) == Literal(1)
    assert _fold_binary("<", Literal(5), Literal(5)) == Literal(0)
    assert _fold_binary("<=", Literal(5), Literal(5)) == Literal(1)
    assert _fold_binary("<=", Literal(6), Literal(5)) == Literal(0)
    assert _fold_binary(">=", Literal(5), Literal(5)) == Literal(1)
    assert _fold_binary(">=", Literal(4), Literal(5)) == Literal(0)
    assert _fold_binary("&&", Literal(1), Literal(2)) == Literal(1)
    assert _fold_binary("&&", Literal(0), Literal(2)) == Literal(0)
    assert _fold_binary("||", Literal(1), Literal(0)) == Literal(1)
    assert _fold_binary("||", Literal(0), Literal(0)) == Literal(0)

    # _fold_unary
    assert _fold_unary("-", Literal(5)) == Literal((-5) & 0xFF)
    assert _fold_unary("~", Literal(0)) == Literal(255)
    assert _fold_unary("!", Literal(0)) == Literal(1)
    assert _fold_unary("!", Literal(42)) == Literal(0)
    assert _fold_unary("?", Literal(5)) == UnaryOp("?", Literal(5))


def test_parser_consume_errors():
    p = Parser([])
    with pytest.raises(SyntaxError, match="Unexpected end of input"):
        p.consume("int")

    p2 = Parser([Token("KEYWORD", "char", 1)])
    with pytest.raises(SyntaxError, match="Expected 'int', got 'char'"):
        p2.consume("int")

    p3 = Parser([])
    with pytest.raises(SyntaxError, match="Unexpected end of statement"):
        p3.parse_stmt()


def test_global_variables_and_arrays():
    c_code = """
    int g_arr[] = {10, 20, 30};
    int g_val = 42;
    int g_uninit;
    int g_hex[0x04];
    int main() {
        g_uninit = g_arr[1] + g_val;
        g_hex[0] = 5;
        poke(0x80, g_uninit);
        poke(0x81, g_hex[0]);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=300, show_progress=False)
    assert cpu.read_ram(0x80) == 62
    assert cpu.read_ram(0x81) == 5

    # Global array missing size & initializer
    with pytest.raises(SyntaxError, match="Array size missing"):
        compile_c("int bad_arr[]; int main() { return 0; }")

    # Local array missing size & initializer
    with pytest.raises(SyntaxError, match="Array size missing"):
        compile_c("int main() { int bad_arr[]; return 0; }")


def test_for_loop_inline_variations():
    c_code = """
    void dummy() {}
    int main() {
        int sum = 0;
        int i = 0;
        for (; i < 1; i++) {
            sum += 1;
        }
        for (i = 1; i < 2; i++) {
            sum += 1;
        }
        for (int j = 0; j < 2; j += 1) {
            sum += 1;
        }
        for (i += 0; i < 3; ++i) {
            sum += 1;
        }
        for (dummy(); i < 4; dummy()) {
            i++;
            sum += 1;
        }
        poke(0x80, sum);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=400, show_progress=False)
    assert cpu.read_ram(0x80) == 6


def test_char_literal_escapes_and_parser_errors():
    c_code = r"""
    int main() {
        char n = '\n';
        char t = '\t';
        char z = '\0';
        char bs = '\\';
        char sq = '\'';
        char unk = '\a';
        poke(0x80, n);
        poke(0x81, t);
        poke(0x82, z);
        poke(0x83, bs);
        poke(0x84, sq);
        poke(0x85, unk);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=200, show_progress=False)
    assert cpu.read_ram(0x80) == 10
    assert cpu.read_ram(0x81) == 9
    assert cpu.read_ram(0x82) == 0
    assert cpu.read_ram(0x83) == ord("\\")
    assert cpu.read_ram(0x84) == ord("'")
    assert cpu.read_ram(0x85) == ord("\\")

    # Primary unexpected token
    with pytest.raises(SyntaxError, match="Unexpected token ';'"):
        compile_c("int main() { ; return 0; }")


def test_runtime_operators_codegen():
    c_code = """
    int main() {
        int a = 10;
        int b = 20;
        int c = 0;

        int neg = -a;
        int com = ~a;
        int not1 = !a;
        int not2 = !c;

        int land1 = a && b;
        int land2 = a && c;
        int lor1 = a || c;
        int lor2 = c || c;

        int neq1 = a != b;
        int neq2 = a != a;

        int div = b / a;
        int mod = 25 % a;

        int bor = a | b;
        int bxor = a ^ b;
        int band = a & b;
        int gte = b >= a;

        poke(0x80, neg);
        poke(0x81, com);
        poke(0x82, not1);
        poke(0x83, not2);
        poke(0x84, land1);
        poke(0x85, land2);
        poke(0x86, lor1);
        poke(0x87, lor2);
        poke(0x88, neq1);
        poke(0x89, neq2);
        poke(0x8A, div);
        poke(0x8B, mod);
        poke(0x8C, bor);
        poke(0x8D, bxor);
        poke(0x8E, band);
        poke(0x8F, gte);
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=500, show_progress=False)
    assert cpu.read_ram(0x80) == (-10) & 0xFF
    assert cpu.read_ram(0x81) == (~10) & 0xFF
    assert cpu.read_ram(0x82) == 0
    assert cpu.read_ram(0x83) == 1
    assert cpu.read_ram(0x84) == 1
    assert cpu.read_ram(0x85) == 0
    assert cpu.read_ram(0x86) == 1
    assert cpu.read_ram(0x87) == 0
    assert cpu.read_ram(0x88) == 1
    assert cpu.read_ram(0x89) == 0
    assert cpu.read_ram(0x8A) == 2
    assert cpu.read_ram(0x8B) == 5
    assert cpu.read_ram(0x8C) == (10 | 20)
    assert cpu.read_ram(0x8D) == (10 ^ 20)
    assert cpu.read_ram(0x8E) == (10 & 20)
    assert cpu.read_ram(0x8F) == 1


def test_peephole_rules_3_and_5():
    # Rule 3: ST R30, R16 followed by LD R16, R30
    lines = [
        "ST R30, R16",
        "LD R16, R30",
    ]
    opt = optimize_assembly(lines)
    assert opt == ["ST R30, R16"]

    # Rule 5: Consecutive duplicate LDI
    lines2 = [
        "LDI R16, 42",
        "LDI R16, 42",
    ]
    opt2 = optimize_assembly(lines2)
    assert opt2 == ["LDI R16, 42"]


def test_builtins_vram_clear_in_out_and_many_args():
    c_code = """
    int main() {
        out(0x10, 42);
        int val = in(0x10);
        poke(0x80, val);
        vram_clear();
        return 0;
    }
    """
    asm = compile_c(c_code)
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=5000, show_progress=False)
    assert cpu.read_ram(0x80) == 42
    # Verify vram was cleared (0x200..0x600 should be 32 (space))
    assert cpu.read_ram(0x0200) == 32

    # Call with > 4 arguments generates POP R0
    gen = CodeGenerator()
    gen.gen_expr(Call("foo", [Literal(i) for i in range(5)]))
    assert "POP R0" in "\n".join(gen.asm)


def test_ram_allocation_boundary_and_high_addresses():
    gen = CodeGenerator()
    # Test allocate_var jumping over VRAM (0x0200..0x05FF)
    gen.next_ram = 0x0200
    addr = gen.allocate_var("v1")
    assert addr == 0x0600

    # Test allocate_array jumping over VRAM
    gen.next_ram = 0x01FF
    arr_addr = gen.allocate_array("a1", 10)
    assert arr_addr == 0x0600

    # Compilation with high RAM addresses (>= 256)
    c_code = """
    int pad[200];
    int g_high[2] = {10, 20};
    int g_single = 99;
    int test_fn(int arg1) {
        int loc = 1;
        loc = loc;
        int larr[2] = {5, 6};
        loc++;
        ++loc;
        return loc + arg1 + g_high[0] + g_single + larr[0];
    }
    int main() {
        return test_fn(2);
    }
    """
    asm = compile_c(c_code)
    assert "LDI R31," in asm
    asm_res = assemble(asm)
    cpu = CPU()
    cpu.load_program(asm_res)
    cpu.run(max_steps=300, show_progress=False)
    # test_fn returns: loc(3) + arg1(2) + g_high[0](10) + g_single(99) + larr[0](5) = 119
    assert cpu.read_reg(16) == 119


def test_compile_c_files(tmp_path):
    f = tmp_path / "test.c"
    f.write_text("int main() { int x = 10; return x; }")
    asm = compile_c_file(str(f))
    assert "main:" in asm

    asm_sym, syms = compile_c_file_with_symbols(str(f))
    assert "main:" in asm_sym
    assert "x" in syms
