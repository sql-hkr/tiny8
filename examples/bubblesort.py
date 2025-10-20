"""Example runner that executes the `examples/bubblesort.asm` program.

This script assembles and runs the bubblesort example and prints the
contents of RAM[100..131]. Optionally it can create an animation using
matplotlib if available.
"""

from tiny8 import CPU, Visualizer, assemble_file

prog, labels = assemble_file("examples/bubblesort.asm")
cpu = CPU()
cpu.load_program(prog, labels)
cpu.run(max_cycles=15000)

print([cpu.read_ram(i) for i in range(100, 132)])

viz = Visualizer(cpu)
base = 100
viz.animate_combined(
    interval=1,
    mem_addr_start=base,
    mem_addr_end=base + 31,
    plot_every=100,
    # filename="bubblesort.gif",
    # fps=60,
)
