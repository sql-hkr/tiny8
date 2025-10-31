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

Or generate an animation:

.. code-block:: bash

   tiny8 examples/bubblesort.asm -m ani -o bubblesort.gif

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

Quick Reference
---------------

.. list-table:: Example Summary
   :header-rows: 1
   :widths: 20 40 40

   * - Program
     - Concept
     - Key Instructions
   * - Hello World
     - Basic structure
     - LDI, JMP
   * - Fibonacci
     - Loops, arithmetic
     - ADD, MOV, DEC, BRNE
   * - Factorial
     - Multiplication
     - MUL, DEC, CPI, BRGE
   * - Sum 1 to N
     - Accumulation
     - ADD, INC, CP, BRLO
   * - Array Sum
     - Memory access
     - LDS, ADD, INC
   * - Find Max
     - Comparison
     - CP, BRLO, MOV
   * - Linear Search
     - Sequential search
     - LDS, CP, BREQ
   * - Memory Copy
     - Data transfer
     - LDS, STS, INC
   * - Bubble Sort
     - Sorting algorithm
     - LD, ST, CP, BRCC
   * - GCD
     - Euclidean algorithm
     - DIV, MUL, SUB, MOV
   * - Power
     - Repeated multiplication
     - MUL, DEC, BRNE
   * - Multiply by Shift
     - Bit manipulation
     - LSL, LSR, ADD
   * - Count Bits
     - Bit operations
     - LSR, ANDI
   * - Is Prime
     - Number theory
     - DIV, MUL, CP
   * - Reverse Array
     - Array manipulation
     - LDS, STS, SWAP

Learning Path
-------------

Recommended order for learning:

1. **Start with basics**: hello_world, fibonacci, factorial
2. **Learn memory**: array_sum, memory_copy, find_max
3. **Master control flow**: linear_search, gcd
4. **Tackle algorithms**: bubblesort, power, is_prime
5. **Explore bit operations**: multiply_by_shift, count_bits

Next Steps
----------

* Read the detailed :doc:`fibonacci` walkthrough
* Study the :doc:`bubblesort` algorithm implementation  
* Review the :doc:`../architecture` for CPU details
* Practice with :doc:`../visualization` tools
* Explore the :doc:`../api/modules` for Python integration
