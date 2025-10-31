.. Tiny8 documentation master file

Tiny8 Documentation
===================

**An educational 8-bit CPU simulator with interactive visualization**

Tiny8 is a lightweight and educational toolkit for exploring the fundamentals of computer architecture through hands-on assembly programming and real-time visualization. Designed for learning and experimentation, it features an AVR-inspired 8-bit CPU with 32 registers, a rich instruction set, and powerful debugging tools — all with zero heavy dependencies.

.. image:: https://github.com/user-attachments/assets/6d4f07ba-21b3-483f-a5d4-7603334c40f4
   :alt: Animated bubble sort visualization
   :align: center
   :width: 600px

.. centered:: *Real-time visualization of a bubble sort algorithm executing on Tiny8*

Features
--------

🎯 Interactive Terminal Debugger
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. image:: https://github.com/user-attachments/assets/5317ebcd-53d5-4966-84be-be94b7830899
   :alt: CLI visualizer screenshot
   :align: center
   :width: 600px

* **Vim-style navigation**: Step through execution with intuitive keyboard controls
* **Change highlighting**: See exactly what changed at each step (registers, flags, memory)
* **Advanced search**: Find instructions, track register/memory changes, locate PC addresses
* **Marks and bookmarks**: Set and jump to important execution points
* **Vertical scrolling**: Handle programs with large memory footprints

🎬 Graphical Animation
~~~~~~~~~~~~~~~~~~~~~~~

* Generate high-quality GIF/MP4 videos of program execution
* Visualize register evolution, memory access patterns, and flag changes
* Perfect for presentations, documentation, and learning materials

🏗️ Complete 8-bit Architecture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **32 general-purpose registers** (R0-R31)
* **8-bit ALU** with arithmetic, logical, and bit manipulation operations
* **Status register (SREG)** with 8 condition flags
* **2KB address space** for unified memory and I/O
* **Stack operations** with dedicated stack pointer
* **AVR-inspired instruction set** with 60+ instructions

📚 Educational Focus
~~~~~~~~~~~~~~~~~~~~

* Clean, readable Python implementation
* Comprehensive examples (Fibonacci, bubble sort, factorial, and more)
* Step-by-step execution traces for debugging
* Full API documentation and instruction set reference

Quick Start
-----------

Installation
~~~~~~~~~~~~

Install Tiny8 using pip:

.. code-block:: bash

   pip install tiny8

Your First Program
~~~~~~~~~~~~~~~~~~

Create a file called ``fibonacci.asm``:

.. code-block:: asm

   ; Fibonacci Sequence Calculator
   ; Calculates the 10th Fibonacci number (F(10) = 55)
   
       ldi r16, 0          ; F(0) = 0
       ldi r17, 1          ; F(1) = 1
       ldi r18, 9          ; Counter: 9 more iterations
   
   loop:
       add r16, r17        ; F(n) = F(n-1) + F(n-2)
       mov r19, r16        ; Save result temporarily
       mov r16, r17        ; Shift: previous = current
       mov r17, r19        ; Shift: current = new result
       dec r18             ; Decrement counter
       brne loop           ; Continue if counter != 0
   
   done:
       jmp done            ; Infinite loop at end

Run it with the interactive debugger:

.. code-block:: bash

   tiny8 fibonacci.asm

Or generate an animation:

.. code-block:: bash

   tiny8 fibonacci.asm -m ani -o fibonacci.gif

Using the Python API
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from tiny8 import CPU, assemble_file
   
   # Assemble and load program
   asm = assemble_file("fibonacci.asm")
   cpu = CPU()
   cpu.load_program(asm)
   
   # Run the program
   cpu.run(max_steps=1000)
   
   # Check the result
   print(f"Result: R17 = {cpu.read_reg(17)}")  # Final Fibonacci number

Documentation Contents
----------------------

.. toctree::
   :maxdepth: 2
   :caption: User Guide
   
   getting_started
   architecture
   assembly_language
   visualization

.. toctree::
   :maxdepth: 2
   :caption: Examples
   
   examples/index

.. toctree::
   :maxdepth: 2
   :caption: API Reference
   
   api/modules

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
