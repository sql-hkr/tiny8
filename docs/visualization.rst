Visualization & Debugger
========================

Tiny8 features a modern, real-time terminal visualizer and visual debugger powered by `Textual <https://textual.textualize.io/>`_. It provides interactive execution controls, sparse checkpoint time-travel, a 32x32 TrueColor memory heatmap, and a full-screen built-in modal editor.

Launching the TUI
-----------------

To run any assembly or C program with the interactive debugger:

.. code-block:: bash

   tiny8 program.asm
   tiny8 program.c

You can also specify options such as step limits or editor launch:

.. code-block:: bash

   # Launch with maximum execution steps
   tiny8 program.asm --max-steps 1000

   # Launch directly into the Vim editor
   tiny8 my_code.c --edit

   # Compile C to assembly without running
   tiny8 my_code.c --compile-only

Interface Overview
------------------

.. figure:: https://github.com/user-attachments/assets/bd3e88da-9bcb-4a41-bb9e-57d9d4e39bc6
   :alt: Real-time generative reverse-diffusion synthesis (MNIST 8) at x5,000 speed in Tiny8 TUI (Viridis Palette, HEX init -> PIXEL denoising)
   :align: center
   :width: 100%

   *Real-time generative reverse-diffusion synthesis (MNIST 8) executing at x5,000 speed in Tiny8 TUI (Viridis Palette: HEX init &rarr; PIXEL denoising)*


The debugger interface provides real-time reactive panels:

.. code-block:: text

   ┌──────────────────────────────────┬──────────────────────────────────┐
   │ CODE VIEW                        │ REGISTERS (R00..R31)             │
   │ Source listing & disassembly     │ Live values & delta highlights   │
   │ Current PC pointer & Breakpoints ├──────────────────────────────────┤
   │                                  │ STATUS REGISTER (SREG)           │
   │                                  │ I  T  H  S  V  N  Z  C flags     │
   ├──────────────────────────────────┴──────────────────────────────────┤
   │ TABS: [Memory] [C Variables] [Call Stack]                           │
   │ • 32x32 TrueColor Heatmap Grid (VRAM 0x0200..0x05FF)                │
   │ • Live memory byte inspector & address scroll                       │
   │ • Reconstructed C variable symbols and call stack frames            │
   ├─────────────────────────────────────────────────────────────────────┤
   │ STATUSLINE: [NORMAL] factorial.c  Step: 120/120  PC: 0x0014   h: help │
   └─────────────────────────────────────────────────────────────────────┘

Interactive Controls
--------------------

Execution & Time-Travel
~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Key
     - Action
   * - ``Space``
     - Play / pause automatic continuous execution
   * - ``Shift+Space``
     - Reverse playback automatic continuous execution
   * - ``n``
     - Step forward 1 instruction (+1 step)
   * - ``p``
     - Step backward 1 instruction (-1 step, Time-Travel debug)
   * - ``c``
     - Continue forward until next breakpoint or program halt
   * - ``C`` (``Shift+c``)
     - Reverse continue backward until previous breakpoint or start
   * - ``b``
     - Toggle breakpoint at current PC
   * - ``+`` / ``-``
     - Increase / decrease automatic playback execution speed
   * - ``r``
     - Reset execution back to Step 0
   * - ``q``
     - Quit Tiny8 application

View & Display Controls
~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Key
     - Action
   * - ``j`` / ``k``
     - Scroll memory viewport down / up by 32 bytes (1 row)
   * - ``J`` / ``K``
     - Fast scroll memory viewport down / up by 128 bytes (4 rows)
   * - ``g``
     - Toggle between Viridis and Grayscale color palettes
   * - ``x``
     - Toggle between Hexadecimal digits (02X) and Graphic Pixel blocks
   * - ``m``
     - Cycle view modes (Viridis+Hex -> Viridis+Pixel -> Grayscale+Pixel -> Grayscale+Hex)
   * - ``i``
     - Inspect details of the currently executing instruction
   * - ``h`` or ``?``
     - Open full TUI Application Usage & Keyboard Guide
   * - ``e``
     - Launch the built-in full-screen Vim-style modal editor

Command Bar Prompt (:)
~~~~~~~~~~~~~~~~~~~~~~

Press ``:`` anytime from the debugger to enter commands:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Command
     - Description
   * - ``:goto <step>``
     - Seek directly to an execution step (e.g., ``:goto 500``)
   * - ``:b <pc> [if expr]``
     - Set conditional breakpoint (e.g., ``:b 0x0010 if R16 > 10``)
   * - ``:watch <target>``
     - Set watchpoint on register or memory address
   * - ``:set <reg> <val>``
     - Modify register value dynamically (e.g., ``:set R16 42``)
   * - ``:poke <addr> <val>``
     - Modify RAM byte value dynamically (e.g., ``:poke 0x0200 255``)
   * - ``:exec <asm>``
     - Execute an assembly instruction immediately (e.g., ``:exec LDI R16, 5``)
   * - ``:speed <ms>``
     - Set playback speed interval in milliseconds
   * - ``:m <addr>``
     - Jump memory viewport to specified address
   * - ``:q`` / ``:quit``
     - Exit debugger

Built-in Vim Modal Editor
-------------------------

Press ``e`` anytime or pass ``--edit`` on the command line to enter the full-screen Vim editor:

* **NORMAL Mode**: Full cursor navigation with ``h``/``j``/``k``/``l``, word jump ``w``/``b``, line bounds ``0``/``$``, file bounds ``gg``/``G``, delete character ``x``, delete line ``dd``, copy line ``yy``, paste ``p``, undo ``u``, redo ``Ctrl+r``.
* **INSERT Mode**: Press ``i``, ``a``, or ``o`` to write code freely. Press ``Esc`` to return to NORMAL mode.
* **COMMAND Mode**: Press ``:`` to enter commands:
  * ``:w`` - Save code to file
  * ``:wq`` or ``:x`` - Save and return to debugger
  * ``:run`` - Compile/assemble code and restart debugging immediately
  * ``:q`` or ``:q!`` - Exit editor back to debugger

Documentation Internationalization (i18n)
-----------------------------------------

Tiny8 documentation supports English (en) and Japanese (ja) localization via Sphinx gettext:

.. code-block:: bash

   # Build Japanese HTML documentation
   make -C docs html-ja

   # Build English HTML documentation
   make -C docs html-en

   # Build all languages
   make -C docs html-all
