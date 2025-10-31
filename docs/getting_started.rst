Getting Started
===============

This guide will help you get started with Tiny8, from installation to running your first programs.

Installation
------------

Requirements
~~~~~~~~~~~~

Tiny8 requires Python 3.11 or later. Check your Python version:

.. code-block:: bash

   python --version

Installing Tiny8
~~~~~~~~~~~~~~~~

Install Tiny8 using pip:

.. code-block:: bash

   pip install tiny8

This will install the ``tiny8`` command-line tool and make the Python API available for import.

Verifying Installation
~~~~~~~~~~~~~~~~~~~~~~

Verify that Tiny8 is installed correctly:

.. code-block:: bash

   tiny8 --version

You should see the version number printed to the terminal.

Your First Program
------------------

Let's write a simple program that adds two numbers.

Create the Assembly File
~~~~~~~~~~~~~~~~~~~~~~~~

Create a new file called ``add.asm`` with the following content:

.. code-block:: asm

   ; Simple addition program
   ; Adds 5 + 3 and stores the result in R16
   
       ldi r16, 5          ; Load 5 into R16
       ldi r17, 3          ; Load 3 into R17
       add r16, r17        ; Add R17 to R16
   
   done:
       jmp done            ; Infinite loop

Understanding the Code
~~~~~~~~~~~~~~~~~~~~~~

Let's break down what each line does:

* ``ldi r16, 5`` - **L** oa **d** **I** mmediate: Loads the value 5 directly into register 16
* ``ldi r17, 3`` - Loads the value 3 into register 17
* ``add r16, r17`` - Adds the contents of R17 to R16, storing the result in R16
* ``jmp done`` - Jumps to the label ``done``, creating an infinite loop

.. note::
   Lines starting with ``;`` are comments and are ignored by the assembler.

Running with the Interactive Debugger
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Run your program using the Tiny8 interactive debugger:

.. code-block:: bash

   tiny8 add.asm

You'll see a terminal-based interface showing:

* **Source code** - Your assembly program with the current instruction highlighted
* **Registers** - The 32 general-purpose registers (R0-R31)
* **Status flags** - The SREG flags (I, T, H, S, V, N, Z, C)
* **Memory** - RAM contents
* **Control information** - Program counter (PC), stack pointer (SP), and step count

Debugger Controls
~~~~~~~~~~~~~~~~~

Use these keyboard shortcuts to control execution:

**Navigation:**

* ``l`` or ``→`` - Step forward one instruction
* ``h`` or ``←`` - Step backward one instruction  
* ``w`` - Jump forward 10 steps
* ``b`` - Jump backward 10 steps
* ``0`` - Go to first step
* ``$`` - Go to last step

**Playback:**

* ``Space`` - Toggle play/pause
* ``[`` - Slower playback
* ``]`` - Faster playback

**Display:**

* ``r`` - Toggle showing all registers
* ``M`` - Toggle showing all memory
* ``=`` - Show detailed step information
* ``j`` - Scroll memory view down
* ``k`` - Scroll memory view up

**Marks:**

* ``m`` + letter - Set a mark at current position
* ``'`` + letter - Jump to a saved mark

**Search/Commands:**

* ``/`` - Show help screen
* ``:`` - Enter command mode (for advanced navigation and search)

**Exit:**

* ``q`` or ``Esc`` - Quit

Try stepping through your program with ``l`` and watch how the registers change!

Running from Python
-------------------

You can also run Tiny8 programs from Python code.

Basic Execution
~~~~~~~~~~~~~~~

.. code-block:: python

   from tiny8 import CPU, assemble_file
   
   # Assemble the program
   asm = assemble_file("add.asm")
   
   # Create a CPU instance
   cpu = CPU()
   
   # Load the program
   cpu.load_program(asm)
   
   # Run the program (with a safety limit)
   cpu.run(max_steps=100)
   
   # Read the result
   print(f"R16 = {cpu.read_reg(16)}")  # Should print 8

Step-by-Step Execution
~~~~~~~~~~~~~~~~~~~~~~~

For more control, you can step through the program manually:

.. code-block:: python

   from tiny8 import CPU, assemble
   
   # Parse assembly code directly
   code = """
       ldi r16, 10
       ldi r17, 5
       sub r16, r17
   """
   asm = assemble(code)
   
   # Set up and run
   cpu = CPU()
   cpu.load_program(asm)
   
   # Step through manually
   while cpu.pc < len(cpu.program):
       print(f"Step {cpu.step_count}: PC={cpu.pc}")
       cpu.step()
       if cpu.step_count > 10:
           break
   
   print(f"Final result: R16 = {cpu.read_reg(16)}")

Inspecting CPU State
~~~~~~~~~~~~~~~~~~~~

You can inspect various aspects of the CPU state:

.. code-block:: python

   # Read registers
   value = cpu.read_reg(16)
   
   # Read memory
   mem_value = cpu.mem.read(0x0100)
   
   # Check flags
   zero_flag = cpu.get_flag(1)  # Z flag
   carry_flag = cpu.get_flag(0)  # C flag
   
   # Get trace information
   reg_changes = cpu.reg_trace
   mem_changes = cpu.mem_trace

Common Assembly Patterns
-------------------------

Loading Immediate Values
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: asm

   ldi r16, 42         ; Load decimal
   ldi r17, 0xFF       ; Load hexadecimal
   ldi r18, 0b1010     ; Load binary

Working with Memory
~~~~~~~~~~~~~~~~~~~

.. code-block:: asm

   ; Store register to memory
   ldi r16, 100
   sts 0x0200, r16     ; Store R16 at address 0x0200
   
   ; Load from memory to register
   lds r17, 0x0200     ; Load from address 0x0200 into R17

Loops
~~~~~

.. code-block:: asm

   ; Count down from 10 to 0
       ldi r16, 10
   
   loop:
       dec r16             ; Decrement R16
       brne loop           ; Branch if not equal to zero
   
   ; Continue execution here

Conditional Branching
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: asm

   ; Compare two values
       ldi r16, 5
       ldi r17, 10
       cp r16, r17         ; Compare R16 with R17
       brlo less_than      ; Branch if lower (unsigned)
       
       ; R16 >= R17
       ldi r18, 1
       jmp done
       
   less_than:
       ; R16 < R17
       ldi r18, 0
       
   done:
       jmp done
