"""Tests for all example programs in examples/ directory."""

from pathlib import Path

from tiny8 import CPU, assemble, assemble_file, compile_c_file

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def test_example_array_sum():
    """Verify examples/array_sum.asm computes sum 180 in R16."""
    cpu = CPU()
    cpu.load_program(assemble_file(str(EXAMPLES_DIR / "array_sum.asm")))
    cpu.run(max_steps=1000)
    assert cpu.read_reg(16) == 180


def test_example_bubblesort():
    """Verify examples/bubblesort.asm sorts 32 elements in ascending order."""
    cpu = CPU()
    cpu.load_program(assemble_file(str(EXAMPLES_DIR / "bubblesort.asm")))
    cpu.run(max_steps=50000, show_progress=False)
    arr = [cpu.read_ram(0x60 + i) for i in range(32)]
    assert arr == sorted(arr)
    assert arr[0] <= arr[-1]
    assert len(set(arr)) > 15  # Rich distribution of pseudo-random values


def test_example_count_bits():
    """Verify examples/count_bits.asm counts 5 set bits in 181."""
    cpu = CPU()
    cpu.load_program(assemble_file(str(EXAMPLES_DIR / "count_bits.asm")))
    cpu.run(max_steps=1000)
    assert cpu.read_reg(16) == 5


def test_example_factorial_asm():
    """Verify examples/factorial.asm computes 5! = 120 in R16."""
    cpu = CPU()
    cpu.load_program(assemble_file(str(EXAMPLES_DIR / "factorial.asm")))
    cpu.run(max_steps=1000)
    assert cpu.read_reg(16) == 120


def test_example_factorial_c():
    """Verify examples/factorial.c compiles and computes 5! = 120 in RAM[0x80]."""
    asm_code = compile_c_file(str(EXAMPLES_DIR / "factorial.c"))
    cpu = CPU()
    cpu.load_program(assemble(asm_code))
    cpu.run(max_steps=5000)
    assert cpu.read_ram(0x80) == 120


def test_example_fibonacci():
    """Verify examples/fibonacci.asm computes 10th Fibonacci number 55 in R17."""
    cpu = CPU()
    cpu.load_program(assemble_file(str(EXAMPLES_DIR / "fibonacci.asm")))
    cpu.run(max_steps=1000)
    assert cpu.read_reg(17) == 55


def test_example_find_max():
    """Verify examples/find_max.asm finds maximum value 89 at index 3."""
    cpu = CPU()
    cpu.load_program(assemble_file(str(EXAMPLES_DIR / "find_max.asm")))
    cpu.run(max_steps=1000)
    assert cpu.read_reg(16) == 89
    assert cpu.read_reg(17) == 3


def test_example_gcd():
    """Verify examples/gcd.asm computes gcd(48, 18) = 6 in R16."""
    cpu = CPU()
    cpu.load_program(assemble_file(str(EXAMPLES_DIR / "gcd.asm")))
    cpu.run(max_steps=1000)
    assert cpu.read_reg(16) == 6


def test_example_hello_world():
    """Verify examples/hello_world.asm writes ASCII 'HELLO' to RAM[0x60..0x64]."""
    cpu = CPU()
    cpu.load_program(assemble_file(str(EXAMPLES_DIR / "hello_world.asm")))
    cpu.run(max_steps=1000)
    chars = bytes([cpu.read_ram(0x60 + i) for i in range(5)])
    assert chars == b"HELLO"


def test_example_is_prime():
    """Verify examples/is_prime.asm identifies 17 as prime (R16 = 1)."""
    cpu = CPU()
    cpu.load_program(assemble_file(str(EXAMPLES_DIR / "is_prime.asm")))
    cpu.run(max_steps=1000)
    assert cpu.read_reg(16) == 1


def test_example_linear_search():
    """Verify examples/linear_search.asm finds target value 56 at index 5."""
    cpu = CPU()
    cpu.load_program(assemble_file(str(EXAMPLES_DIR / "linear_search.asm")))
    cpu.run(max_steps=1000)
    assert cpu.read_reg(16) == 5


def test_example_memory_copy():
    """Verify examples/memory_copy.asm copies 6 bytes to RAM[0x70..0x75]."""
    cpu = CPU()
    cpu.load_program(assemble_file(str(EXAMPLES_DIR / "memory_copy.asm")))
    cpu.run(max_steps=1000)
    assert [cpu.read_ram(0x70 + i) for i in range(6)] == [10, 20, 30, 40, 50, 60]


def test_example_multiply_by_shift():
    """Verify examples/multiply_by_shift.asm computes 7 * 8 = 56 in R16 using shifts."""
    cpu = CPU()
    cpu.load_program(assemble_file(str(EXAMPLES_DIR / "multiply_by_shift.asm")))
    cpu.run(max_steps=1000)
    assert cpu.read_reg(16) == 56


def test_example_power():
    """Verify examples/power.asm computes 3^4 = 81 in R16."""
    cpu = CPU()
    cpu.load_program(assemble_file(str(EXAMPLES_DIR / "power.asm")))
    cpu.run(max_steps=1000)
    assert cpu.read_reg(16) == 81


def test_example_reverse():
    """Verify examples/reverse.asm reverses array in RAM[0x60..0x65]."""
    cpu = CPU()
    cpu.load_program(assemble_file(str(EXAMPLES_DIR / "reverse.asm")))
    cpu.run(max_steps=1000)
    assert [cpu.read_ram(0x60 + i) for i in range(6)] == [60, 50, 40, 30, 20, 10]


def test_example_sum_1_to_n():
    """Verify examples/sum_1_to_n.asm computes sum of 1..20 = 210 in R16."""
    cpu = CPU()
    cpu.load_program(assemble_file(str(EXAMPLES_DIR / "sum_1_to_n.asm")))
    cpu.run(max_steps=1000)
    assert cpu.read_reg(16) == 210


def test_example_diffusion_mnist8_asm():
    """Verify examples/diffusion_mnist8.asm assembles and executes reverse diffusion on Tiny8."""
    asm_file = str(EXAMPLES_DIR / "diffusion_mnist8.asm")
    asm = assemble_file(asm_file)
    assert len(asm.program) > 1000

    cpu = CPU()
    cpu.load_program(asm)

    # Initial noise rendering at step 8 (~70,000 instructions for 28x28 data init)
    cpu.run(max_steps=70000, show_progress=False)
    header_step8 = "".join(chr(cpu.read_ram(0x0200 + i)) for i in range(32))
    assert "DIFFUSION MNIST:8" in header_step8
    assert "STEP:[8]" in header_step8

    # First denoising reverse step transition to step 7 (~180,000 additional instructions)
    cpu.run(max_steps=180000, show_progress=False)
    header_step7 = "".join(chr(cpu.read_ram(0x0200 + i)) for i in range(32))
    assert "STEP:[7]" in header_step7

    # Verify non-zero heatmap pixels rendered in 28x28 VRAM region
    pixels = [
        cpu.read_ram(0x0200 + r * 32 + c) for r in range(2, 30) for c in range(2, 30)
    ]
    assert any(p > 0 for p in pixels)
