Fibonacci Sequence
==================

This example calculates the 10th Fibonacci number using an iterative approach.

Overview
--------

**Difficulty**: Beginner

**Concepts**: Loops, register arithmetic, conditional branching

**Output**: R17 contains F(10) = 55

The Program
-----------

.. literalinclude:: ../../examples/fibonacci.asm
   :language: asm
   :linenos:

Algorithm Explanation
---------------------

The Fibonacci sequence is defined as:

* F(0) = 0
* F(1) = 1
* F(n) = F(n-1) + F(n-2) for n > 1

This program uses an iterative approach with three registers:

* **R16**: Previous Fibonacci number (F(n-1))
* **R17**: Current Fibonacci number (F(n))
* **R18**: Counter (remaining iterations)

Step-by-Step Walkthrough
-------------------------

Initialization (Lines 8-10)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: asm

   ldi r16, 0          ; F(0) = 0
   ldi r17, 1          ; F(1) = 1
   ldi r18, 9          ; Counter: 9 more iterations

We start with F(0) = 0 and F(1) = 1. Since we want F(10), we need 9 more iterations (F(2) through F(10)).

Main Loop (Lines 12-18)
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: asm

   loop:
       add r16, r17        ; F(n) = F(n-1) + F(n-2)
       mov r19, r16        ; Save result temporarily
       mov r16, r17        ; Shift: previous = current
       mov r17, r19        ; Shift: current = new result
       dec r18             ; Decrement counter
       brne loop           ; Continue if counter != 0

Each iteration:

1. **Add**: Compute next Fibonacci number (R16 + R17)
2. **Save**: Store result in temporary register R19
3. **Shift**: Move R17 to R16 (previous ← current)
4. **Update**: Move R19 to R17 (current ← new result)
5. **Decrement**: Decrease counter
6. **Branch**: Loop if counter ≠ 0

Execution Trace
---------------

Here's how the registers evolve:

.. list-table:: Fibonacci Calculation
   :header-rows: 1
   :widths: 10 15 15 15 30

   * - Iter
     - R16 (prev)
     - R17 (curr)
     - R18 (count)
     - Calculation
   * - Init
     - 0
     - 1
     - 9
     - F(0), F(1)
   * - 1
     - 1
     - 1
     - 8
     - F(2) = 0 + 1 = 1
   * - 2
     - 1
     - 2
     - 7
     - F(3) = 1 + 1 = 2
   * - 3
     - 2
     - 3
     - 6
     - F(4) = 1 + 2 = 3
   * - 4
     - 3
     - 5
     - 5
     - F(5) = 2 + 3 = 5
   * - 5
     - 5
     - 8
     - 4
     - F(6) = 3 + 5 = 8
   * - 6
     - 8
     - 13
     - 3
     - F(7) = 5 + 8 = 13
   * - 7
     - 13
     - 21
     - 2
     - F(8) = 8 + 13 = 21
   * - 8
     - 21
     - 34
     - 1
     - F(9) = 13 + 21 = 34
   * - 9
     - 34
     - 55
     - 0
     - F(10) = 21 + 34 = 55

Running the Example
-------------------

Interactive Debugger
~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   tiny8 examples/fibonacci.asm

Step through with ``j`` and watch registers R16, R17, and R18 evolve.

Animation
~~~~~~~~~

.. code-block:: bash

   tiny8 examples/fibonacci.asm -m ani -o fibonacci.gif

Visualize the register changes over time.

Python API
~~~~~~~~~~

.. code-block:: python

   from tiny8 import CPU, assemble_file
   
   cpu = CPU()
   cpu.load_program(assemble_file("examples/fibonacci.asm"))
   cpu.run(max_steps=100)
   
   print(f"F(10) = {cpu.read_reg(17)}")  # Output: 55

Key Concepts
------------

Loop Structure
~~~~~~~~~~~~~~

The loop pattern is common in assembly:

.. code-block:: asm

   ldi r18, N          ; Initialize counter
   loop:
       ; ... loop body ...
       dec r18         ; Decrement counter
       brne loop       ; Branch if not equal to zero

Register Shifting
~~~~~~~~~~~~~~~~~

Moving values between registers for state management:

.. code-block:: asm

   mov r19, r16        ; Temporary save
   mov r16, r17        ; Shift values
   mov r17, r19        ; Update with new value

This "register rotation" is a fundamental technique in assembly programming.

Exercises
---------

1. **Modify the counter**: Calculate F(15) instead of F(10)
2. **Different starting values**: Try F(0) = 1, F(1) = 1 (alternative definition)
3. **Store in memory**: Save each Fibonacci number to memory
4. **Detect overflow**: Check when the result exceeds 255

Solutions
~~~~~~~~~

**F(15) modification**:

.. code-block:: asm

   ldi r18, 14         ; 14 iterations for F(15)

Note: F(15) = 610, which exceeds 8-bit range (wraps to 98).

**Store in memory**:

.. code-block:: asm

   ldi r20, 0x60       ; Memory base address
   loop:
       add r16, r17
       sts r20, r17    ; Store current Fibonacci number
       inc r20         ; Advance memory pointer
       ; ... rest of loop ...

Related Examples
----------------

* :doc:`factorial` - Another iterative calculation
* :doc:`sum_1_to_n` - Similar loop structure
* :doc:`power` - Repeated operation pattern

Next Steps
----------

* Learn about :doc:`../assembly_language` syntax
* Review the :doc:`../instruction_reference` for ADD, MOV, DEC, BRNE
* Try the :doc:`../visualization` tools to see execution flow
