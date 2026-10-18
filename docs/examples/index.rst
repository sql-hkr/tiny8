Examples
========

This section contains detailed walkthroughs of example programs that demonstrate Tiny8's capabilities and teach assembly programming concepts.

Overview
--------

The examples are organized by complexity and concept:

**Basic Examples**
  Simple programs demonstrating fundamental operations
  
**Intermediate Examples**
  Programs using loops, conditionals, and memory operations
  
**Advanced Examples**
  Complex algorithms including sorting and mathematical computations

All examples are available in the ``examples/`` directory of the Tiny8 repository.

Running Examples
----------------

You can run any example with the interactive debugger:

.. code-block:: bash

   tiny8 examples/fibonacci.asm

Or use the Python API:

.. code-block:: python

   from tiny8 import CPU, assemble_file
   
   cpu = CPU()
   cpu.load_program(assemble_file("examples/fibonacci.asm"))
   cpu.run(max_steps=1000)

Example Programs
----------------

Basic Examples
~~~~~~~~~~~~~~

.. toctree::
   :maxdepth: 1
   
   hello_world
   fibonacci
   factorial

Intermediate Examples
~~~~~~~~~~~~~~~~~~~~~~

.. toctree::
   :maxdepth: 1
   
   sum_1_to_n
   array_sum
   find_max
   linear_search
   memory_copy

Advanced Examples
~~~~~~~~~~~~~~~~~

.. toctree::
   :maxdepth: 1
   
   bubblesort
   gcd
   power
   multiply_by_shift
   count_bits
   is_prime
   reverse

C Language Programs & Interactive Demos
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tiny8 includes an embedded C subset compiler capable of compiling and running C programs directly on the simulated CPU:

* **factorial.c**: Recursive factorial calculation demonstration.

Quick Reference
---------------

.. list-table:: Example Summary
   :header-rows: 1
   :widths: 20 40 40

   * - Program
     - Concept
     - Key Instructions / Language
   * - Hello World
     - Basic memory writing
     - LDI, ST, INC, JMP
   * - Fibonacci
     - Iterative sequence
     - ADD, MOV, DEC, BRNE
   * - Factorial (ASM)
     - Iterative multiplication
     - MUL, DEC, CPI, BRGE
   * - Factorial (C)
     - Recursive function calls
     - C Compiler (CALL, RET, PUSH, POP)
   * - Sum 1 to N
     - Loop accumulation
     - ADD, INC, CP, BRLT, BREQ
   * - Array Sum
     - Pointer iteration
     - LD, ST, ADD, INC, BRNE
   * - Find Max
     - Array scanning & comparison
     - LD, ST, CP, BRGE, MOV
   * - Linear Search
     - Target search & sentinel
     - LD, ST, CP, BREQ, INC
   * - Memory Copy
     - Block memory transfer
     - LD, ST, INC, DEC, BRNE
   * - Bubble Sort
     - PRNG & in-place sort
     - MUL, LD, ST, CP, BRCS
   * - GCD
     - Euclidean algorithm
     - DIV, MOV, CPI, BREQ
   * - Power
     - Exponentiation
     - MUL, INC, CP, BRLT
   * - Multiply by Shift
     - Binary shift multiplication
     - LSL, LSR, ANDI, ADD
   * - Count Bits
     - Bit testing & division
     - AND, DIV, CPI, BRNE
   * - Is Prime
     - Trial division
     - DIV, MUL, CP, BRGE, BRLT
   * - Reverse Array
     - Two-pointer array reverse
     - LD, ST, CP, BRGE, INC, DEC
   * - MNIST Diffusion (ASM)
     - Iterative reverse-diffusion synthesis
     - ASM (diffusion_mnist8.asm)

Learning Path
-------------

Recommended order for learning:

1. **Start with basics**: hello_world, fibonacci, factorial
2. **Learn memory**: array_sum, memory_copy, find_max
3. **Master control flow**: linear_search, gcd
4. **Tackle algorithms**: bubblesort, power, is_prime
5. **Explore bit operations**: multiply_by_shift, count_bits
