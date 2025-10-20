"""Example runner that executes the `examples/fibonacci.asm` program.

This script assembles and runs the Fibonacci example using the tiny8 CPU
model. It writes input ``n`` into register R17 and runs the program, then
prints selected CPU state.
"""

from tiny8 import CPU, assemble_file

n = 13

assert n <= 13, "n must be <= 13 to avoid 8-bit overflow"

program, labels = assemble_file("examples/fibonacci.asm")
cpu = CPU()
cpu.load_program(program, labels)

cpu.write_reg(17, n)
cpu.run(max_cycles=1000)

print("R16 =", cpu.read_reg(16))
print("R17 =", cpu.read_reg(17))
print("PC =", cpu.pc)
print("SP =", cpu.sp)
print("register changes (reg_trace):\n", *[str(reg) + "\n" for reg in cpu.reg_trace])
