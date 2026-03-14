"""Unit tests for Tiny8 C compiler."""

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
