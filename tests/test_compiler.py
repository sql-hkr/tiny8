"""Unit tests for Tiny8 C compiler."""

import pytest

from tiny8 import CPU, assemble
from tiny8.compiler import compile_c, optimize_assembly


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
