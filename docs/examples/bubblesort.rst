Bubble Sort
===========

This advanced example demonstrates bubble sort: a classic sorting algorithm that sorts an array in memory.

Overview
--------

**Difficulty**: Advanced

**Concepts**: Nested loops, memory operations, array manipulation, pseudo-random number generation

**Output**: Sorted array at RAM[0x60..0x7F] (32 bytes in ascending order)

The Program
-----------

.. literalinclude:: ../../examples/bubblesort.asm
   :language: asm
   :linenos:

Algorithm Overview
------------------

The program has two main phases:

1. **Initialization**: Generate 32 pseudo-random values and store them in RAM
2. **Bubble Sort**: Sort the array using the bubble sort algorithm

Phase 1: Array Initialization
------------------------------

Pseudo-Random Number Generator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The program uses a simple linear congruential generator (LCG):

.. code-block:: text

   seed(n+1) = (seed(n) × 75) + 1

This generates a sequence of pseudo-random 8-bit values.

.. code-block:: asm

   ldi r18, 123      ; PRNG seed (starting value)
   ldi r25, 75       ; PRNG multiplier

   init_loop:
       mul r18, r25  ; multiply seed by 75
       inc r18       ; add 1
       st r16, r18   ; store at RAM[base + index]
       ; ...

After 32 iterations, RAM[0x60..0x7F] contains pseudo-random values.

Phase 2: Bubble Sort
---------------------

Algorithm Explanation
~~~~~~~~~~~~~~~~~~~~~

Bubble sort works by repeatedly stepping through the array, comparing adjacent elements, and swapping them if they're in the wrong order.

.. code-block:: text

   for i = 0 to n-2:
       for j = 0 to n-2:
           if array[j] > array[j+1]:
               swap(array[j], array[j+1])

Outer Loop
~~~~~~~~~~

.. code-block:: asm

   ldi r18, 0        ; i = 0
   outer_loop:
       ; ... inner loop ...
       inc r18
       ldi r23, 31
       cp r18, r23
       breq done
       jmp outer_loop

Runs 31 times (i = 0 to 30).

Inner Loop
~~~~~~~~~~

.. code-block:: asm

   ldi r19, 0        ; j = 0
   inner_loop:
       ; load element A = RAM[0x60 + j]
       ldi r20, 0x60
       add r20, r19
       ld r21, r20     ; r21 = A
       
       ; load element B = RAM[0x60 + j + 1]
       ldi r22, 0x60
       add r22, r19
       ldi r23, 1
       add r22, r23
       ld r24, r22     ; r24 = B
       
       ; compare and swap if A > B (for ascending order)
       cp r21, r24
       brcs no_swap    ; skip if A < B
       st r20, r24     ; swap: RAM[addr_A] = B
       st r22, r21     ; swap: RAM[addr_B] = A
       
   no_swap:
       inc r19
       ; ...

For each j:

1. Load adjacent elements (j and j+1)
2. Compare them
3. Swap if first > second (for ascending order)
3. Swap if first > second
4. Advance to next pair

Register Usage
--------------

.. list-table:: Register Allocation
   :header-rows: 1
   :widths: 15 85

   * - Register
     - Purpose
   * - R16
     - Memory address pointer / base address
   * - R17
     - Array index during initialization
   * - R18
     - PRNG seed / outer loop counter (i)
   * - R19
     - Inner loop counter (j)
   * - R20
     - Address of element A
   * - R21
     - Value of element A
   * - R22
     - Address of element B
   * - R23
     - Temporary comparison value
   * - R24
     - Value of element B
   * - R25
     - PRNG multiplier constant (75)

Memory Layout
-------------

.. code-block:: text

   ┌──────────────────────────────────┐
   │ Address  │ Content               │
   ├──────────┼───────────────────────┤
   │ 0x0060   │ Random value 1        │
   │ 0x0061   │ Random value 2        │
   │ 0x0062   │ Random value 3        │
   │   ...    │   ...                 │
   │ 0x007F   │ Random value 32       │
   └──────────────────────────────────┘
   
   After sorting: values in ascending order

Execution Example
-----------------

Initial Array (pseudo-random)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   [123, 78, 234, 45, 190, 67, 12, 198, ...]

After Bubble Sort
~~~~~~~~~~~~~~~~~

.. code-block:: text

   [12, 45, 67, 78, 123, 190, 198, 234, ...]

Bubble sort compares and swaps adjacent elements until the entire array is sorted.

Running the Example
-------------------

Interactive Debugger
~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   tiny8 examples/bubblesort.asm

Watch the sorting process step-by-step. Set marks at the beginning of inner_loop to track passes.

Animation
~~~~~~~~~

.. code-block:: bash

   tiny8 examples/bubblesort.asm -m ani -o bubblesort.gif \
       --mem-start 0x60 --mem-end 0x7F

Creates a visualization showing:

* Memory heatmap of the array being sorted
* Register changes during comparisons
* Visual pattern of values moving to their correct positions

Python API
~~~~~~~~~~

.. code-block:: python

   from tiny8 import CPU, assemble_file
   
   cpu = CPU()
   cpu.load_program(assemble_file("examples/bubblesort.asm"))
   cpu.run(max_steps=50000)  # Bubble sort needs many steps!
   
   # Read sorted array
   sorted_array = [cpu.read_ram(i) for i in range(0x60, 0x80)]
   print("Sorted array:", sorted_array)
   
   # Verify it's sorted in ascending order
   assert all(sorted_array[i] <= sorted_array[i+1] 
              for i in range(len(sorted_array)-1))
   print("✓ Array is correctly sorted!")

Performance Analysis
--------------------

Time Complexity
~~~~~~~~~~~~~~~

* **Best case**: O(n²) - 31 × 31 = 961 comparisons
* **Worst case**: O(n²) - Same as best (this implementation doesn't optimize)
* **Average case**: O(n²)

For 32 elements:

* Outer loop: 31 iterations
* Inner loop: 31 iterations per outer
* Total comparisons: ~961
* Total swaps: Variable (depends on initial order)

Instruction Count
~~~~~~~~~~~~~~~~~

Each comparison involves approximately:

* 10 instructions to load addresses and values
* 5 instructions for comparison and potential swap
* 3 instructions for loop control

Total: ~15,000+ instructions for a complete sort.

Key Concepts
------------

Nested Loops
~~~~~~~~~~~~

Two loop counters working together:

.. code-block:: asm

   outer_loop:
       ldi r19, 0
       inner_loop:
           ; ... work ...
           inc r19
           ; ... inner loop test ...
       inc r18
       ; ... outer loop test ...

Address Calculation
~~~~~~~~~~~~~~~~~~~

Computing memory addresses dynamically:

.. code-block:: asm

   ldi r20, 0x60     ; Base address
   add r20, r19      ; Add offset
   ld r21, r20       ; Load from computed address

Conditional Swapping
~~~~~~~~~~~~~~~~~~~~

.. code-block:: asm

   cp r21, r24       ; Compare values (A vs B)
   brcs no_swap      ; Skip swap if A < B (already in order)
   st r20, r24       ; Perform swap: RAM[A] = B
   st r22, r21       ; Perform swap: RAM[B] = A
   no_swap:

Exercises
---------

1. **Count swaps**: Add a counter to track number of swaps
2. **Optimize**: Add early exit if no swaps occurred in a pass
3. **Different sizes**: Sort 16 or 64 elements instead
4. **Descending order**: Modify to sort in descending order
5. **Different algorithm**: Implement selection sort or insertion sort

Solutions Hints
~~~~~~~~~~~~~~~

**Count swaps**: Add ``inc r26`` in the swap section, initialize R26 to 0.

**Optimize**: Set a flag when swapping, check it at end of outer loop.

**Descending order**: Change ``brcs no_swap`` to ``brcc no_swap``.

Visualization Tips
------------------

When viewing the animation:

* **Memory panel**: Watch values "bubble" to their positions
* **Register panel**: R19 (j) cycles 0-30 repeatedly
* **Register panel**: R18 (i) increments slowly

Look for:

* Large values moving right (higher addresses)
* Small values moving left (lower addresses)
* Progressively fewer changes as array becomes sorted

Comparison with Other Sorts
----------------------------

.. list-table:: Sorting Algorithm Comparison
   :header-rows: 1
   :widths: 25 25 25 25

   * - Algorithm
     - Time Complexity
     - Space
     - Stability
   * - Bubble Sort
     - O(n²)
     - O(1)
     - Yes
   * - Selection Sort
     - O(n²)
     - O(1)
     - No
   * - Insertion Sort
     - O(n²)
     - O(1)
     - Yes
   * - Quick Sort
     - O(n log n)
     - O(log n)
     - No

Bubble sort is chosen for this example because it's conceptually simple and demonstrates memory operations clearly.

Related Examples
----------------

* :doc:`linear_search` - Sequential array access
* :doc:`find_max` - Array comparison operations
* :doc:`reverse` - Array manipulation
