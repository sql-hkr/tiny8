.. Tiny8 documentation master file

Tiny8 Documentation
===================

**From bare-metal computer architecture to Generative AI — an educational 8-bit AVR RISC CPU simulator with real-time interactive visualization**

Tiny8 is a lightweight educational toolkit that bridges bare-metal computer architecture and modern Generative AI. Designed for hands-on learning and experimentation, it guides you through the full stack of computing — from 32 general-purpose registers, ALU operations, stack frames, and C compilation up to executing an iterative reverse-diffusion model synthesizing 28x28 MNIST digits directly on an AVR 8-bit RISC processor. With an interactive Vim-inspired terminal debugger, time-travel reverse execution, and a 32x32 TrueColor memory heatmap, Tiny8 lets you see, step through, and understand computation at every level.

.. figure:: https://github.com/user-attachments/assets/bd3e88da-9bcb-4a41-bb9e-57d9d4e39bc6
   :alt: Real-time generative reverse-diffusion synthesis (MNIST 8) at x5,000 speed in Tiny8 TUI (Viridis Palette, HEX init -> PIXEL denoising)
   :align: center
   :width: 100%

   *Real-time generative reverse-diffusion synthesis (MNIST digit 8) executing at x5,000 speed in Tiny8 TUI (HEX mode for weight/LFSR init &rarr; PIXEL mode for reverse denoising trajectory)*

Features
--------

Interactive Terminal Debugger
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Vim-style navigation**: Step through execution with intuitive keyboard controls
* **Change highlighting**: See exactly what changed at each step (registers, flags, memory)
* **Time-travel debugging**: Step forward and backward with sparse checkpoint restoration
* **32x32 TrueColor Heatmap**: VRAM memory matrix with Viridis/Grayscale visualization
* **Built-in Vim Editor**: Launch full-screen modal editor anytime with ``e``

Complete 8-bit Architecture
~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **32 general-purpose registers** (R0-R31)
* **8-bit ALU** with arithmetic, logical, and bit manipulation operations
* **Status register (SREG)** with 8 condition flags
* **64KB address space** for unified memory and I/O
* **Stack operations** with dedicated stack pointer
* **AVR instruction set** with 67 instructions compliant with Microchip DS40002198A

Educational Focus
~~~~~~~~~~~~~~~~~

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
