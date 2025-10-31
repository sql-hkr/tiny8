Visualization
=============

Tiny8 provides two powerful visualization tools to help you understand program execution: an **interactive terminal debugger** and a **graphical animation system** for generating videos.

Terminal Debugger
-----------------

The interactive terminal debugger provides a comprehensive, real-time view of your program execution with Vim-style keyboard controls.

Launching the Debugger
~~~~~~~~~~~~~~~~~~~~~~

Run any assembly program with the ``tiny8`` command:

.. code-block:: bash

   tiny8 program.asm

This opens the terminal-based visualizer showing your program state.

Interface Overview
~~~~~~~~~~~~~~~~~~

The debugger interface is divided into several sections:

.. code-block:: text

   ┌─────────────────────────────────────────────┐
   │          SOURCE CODE (with PC)              │
   │  Shows your assembly with current line      │
   ├─────────────────────────────────────────────┤
   │              REGISTERS                      │
   │  R0-R31 with changed values highlighted     │
   ├─────────────────────────────────────────────┤
   │            STATUS FLAGS (SREG)              │
   │  I T H S V N Z C - visual indicators        │
   ├─────────────────────────────────────────────┤
   │               MEMORY                        │
   │  RAM contents with addresses and values     │
   ├─────────────────────────────────────────────┤
   │            CONTROL INFO                     │
   │  PC, SP, Step count, Help hint              │
   └─────────────────────────────────────────────┘

Keyboard Controls
~~~~~~~~~~~~~~~~~

Navigation
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Key
     - Action
   * - ``l`` or ``→``
     - Step forward one instruction
   * - ``h`` or ``←``
     - Step backward one instruction
   * - ``0``
     - Go to first step
   * - ``$``
     - Go to last step
   * - ``w``
     - Jump forward 10 steps
   * - ``b``
     - Jump backward 10 steps
   * - ``Space``
     - Toggle play/pause mode
   * - ``[`` / ``]``
     - Slower/faster playback speed

Auto-Play Mode
^^^^^^^^^^^^^^

Press ``Space`` to automatically advance through execution:

* Program steps forward continuously
* Use ``[`` and ``]`` to adjust playback speed (slower/faster)
* Press ``Space`` again to pause
* Press ``l``/``h`` to take manual control

Commands and Search
^^^^^^^^^^^^^^^^^^^

Press ``:`` to enter command mode for advanced navigation:

**Command Examples:**

* ``123`` - Jump to step 123
* ``+50`` - Jump forward 50 steps  
* ``-20`` - Jump backward 20 steps
* ``/add`` - Search forward for "add" instruction
* ``?ldi`` - Search backward for "ldi" instruction
* ``@100`` - Jump to PC address 100
* ``r10`` - Find next change to register R10
* ``r10=42`` - Find where R10 equals 42
* ``m100`` - Find next change to memory[100]
* ``m100=0xFF`` - Find where memory[100] equals 0xFF
* ``fZ`` - Find next change to flag Z
* ``fC=1`` - Find where flag C equals 1
* ``h`` or ``help`` - Show command help

Marks and Bookmarks
^^^^^^^^^^^^^^^^^^^

Set marks to quickly jump to important execution points:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Key
     - Action
   * - ``m`` + letter
     - Set mark at current step (e.g., ``ma``, ``mb``)
   * - ``'`` + letter
     - Jump to mark (e.g., ``'a``, ``'b``)

Example workflow:

1. Step to an interesting point: ``ma`` (set mark 'a')
2. Explore elsewhere in execution
3. Return instantly: ``'a`` (jump to mark 'a')

View Options
^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Key
     - Action
   * - ``r``
     - Toggle between changed/all registers view
   * - ``M``
     - Toggle between non-zero/all memory view
   * - ``j``
     - Scroll memory view down
   * - ``k``
     - Scroll memory view up
   * - ``=``
     - Show detailed step information

Other Controls
^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Key
     - Action
   * - ``/``
     - Show help screen
   * - ``q`` or ``Esc``
     - Quit debugger

Visual Indicators
~~~~~~~~~~~~~~~~~

Change Highlighting
^^^^^^^^^^^^^^^^^^^

The debugger highlights changes at each step:

* **Registers**: Changed values appear in a different color
* **Flags**: Set flags are highlighted
* **Memory**: Modified memory cells are marked
* **PC indicator**: Shows current instruction with ``►`` or color

Understanding the Display
^^^^^^^^^^^^^^^^^^^^^^^^^^

**Registers Display**

.. code-block:: text

   R0:  000  R1:  000  R2:  000  R3:  000
   R16: 042  R17: 010  R18: 005  R19: 000
        ^^^       ^^^  (highlighted if changed)

**Status Flags (SREG)**

.. code-block:: text

   SREG: [I:0] [T:0] [H:0] [S:0] [V:0] [N:0] [Z:1] [C:0]
                                             ^^^
                                             (set flags highlighted)

**Memory Display**

.. code-block:: text

   0x0200: 42  ← Changed this step
   0x0201: 00
   0x0202: FF  ← Changed this step

Tips and Tricks
~~~~~~~~~~~~~~~

Debugging Workflow
^^^^^^^^^^^^^^^^^^

1. **Set marks at key points**: Before loops, after calculations
2. **Use search**: Find where registers or memory addresses are accessed
3. **Toggle views**: Show only changed registers when debugging large programs
4. **Auto-play**: Watch algorithm execution in real-time

Finding Issues
^^^^^^^^^^^^^^

* **Infinite loops**: Watch step counter; if PC stops changing, you're stuck
* **Wrong results**: Step through and watch registers; mark where values diverge
* **Memory issues**: Search for memory addresses; check reads/writes
* **Flag problems**: Watch SREG; verify flags after comparisons

Graphical Animation
-------------------

Generate high-quality GIF or MP4 videos showing program execution with register and memory evolution.

Basic Animation
~~~~~~~~~~~~~~~

Create an animation from your program:

.. code-block:: bash

   tiny8 program.asm -m ani -o output.gif

This generates ``output.gif`` showing:

* SREG flag evolution over time
* All 32 registers as a heatmap
* Memory contents in a specified range

Advanced Options
~~~~~~~~~~~~~~~~

Command-Line Arguments
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   tiny8 program.asm -m ani \
       --output animation.gif \
       --mem-start 0x0200 \
       --mem-end 0x02FF \
       --interval 200 \
       --fps 30

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Option
     - Description
   * - ``-m ani``
     - Enable animation mode
   * - ``-o FILE``
     - Output filename (.gif or .mp4)
   * - ``--mem-start ADDR``
     - Start address for memory visualization
   * - ``--mem-end ADDR``
     - End address for memory visualization
   * - ``--interval MS``
     - Milliseconds per frame
   * - ``--fps N``
     - Frames per second (for video)

Animation Layout
~~~~~~~~~~~~~~~~

The generated animation has three panels:

**Top Panel: SREG Flags**
  8 rows showing each flag (I, T, H, S, V, N, Z, C) over time
  * Bright = flag set (1)
  * Dark = flag clear (0)

**Middle Panel: Registers**
  32 rows (R0-R31) showing register values over time
  * Color intensity = value (0-255)
  * Bright = high values
  * Dark = low values

**Bottom Panel: Memory**
  Selected memory range showing contents over time
  * Same color scheme as registers
  * Track data structure evolution

Reading the Animation
~~~~~~~~~~~~~~~~~~~~~

**Time Axis (Horizontal)**
  Each column represents one execution step
  * Left side: Program start
  * Right side: Program end
  * Watch values change across time

**Value Axis (Vertical)**
  Each row is a register or memory location
  * Track individual items vertically
  * See patterns and data flow

Example Use Cases
~~~~~~~~~~~~~~~~~

Visualizing Algorithms
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Visualize bubble sort
   tiny8 examples/bubblesort.asm -m ani -o bubblesort.gif

Watch the sorting algorithm:

* Registers holding array indices
* Memory showing array elements being swapped
* Flags changing during comparisons

Debugging Data Flow
^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Track Fibonacci sequence generation
   tiny8 examples/fibonacci.asm -m ani -o fib.gif

Observe:

* R16 and R17 alternating as Fibonacci numbers grow
* Loop counter (R18) decrementing
* Flag changes at each iteration

Presentations and Education
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Animations are perfect for:

* Teaching computer architecture concepts
* Explaining algorithms visually
* Documenting program behavior
* Creating engaging educational content

Python API for Visualization
-----------------------------

You can also create visualizations programmatically using the Python API.

Using the Visualizer Class
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from tiny8 import CPU, assemble, Visualizer
   
   # Create and run program
   code = """
       ldi r16, 0
       ldi r17, 10
   loop:
       add r16, r17
       dec r17
       brne loop
   """
   
   asm = assemble(code)
   cpu = CPU()
   cpu.load_program(asm)
   cpu.run(max_steps=100)
   
   # Create visualization
   viz = Visualizer(cpu)
   viz.animate_execution(
       mem_addr_start=0x0200,
       mem_addr_end=0x02FF,
       filename="my_animation.gif",
       interval=200,  # ms between frames
       fps=30,
       cmap="viridis"  # matplotlib colormap
   )

Customization Options
~~~~~~~~~~~~~~~~~~~~~

The ``animate_execution`` method accepts several parameters:

.. code-block:: python

   viz.animate_execution(
       mem_addr_start=0x60,      # Start of memory range
       mem_addr_end=0x7F,        # End of memory range
       filename="output.gif",    # Output file
       interval=200,              # Frame interval (ms)
       fps=30,                   # Frames per second
       fontsize=9,               # Label font size
       cmap="inferno",           # Color map name
       plot_every=1              # Downsample: plot every N steps
   )

Available colormaps: ``viridis``, ``plasma``, ``inferno``, ``magma``, ``cividis``, ``cool``, ``hot``, and many more from Matplotlib.

Visualization Best Practices
-----------------------------

For Terminal Debugging
~~~~~~~~~~~~~~~~~~~~~~

1. **Start simple**: Run through once to understand program flow
2. **Mark key points**: Set marks at loop starts, branches, important calculations
3. **Use search**: Find where specific registers/memory are modified
4. **Toggle views**: Hide unchanged registers for clarity in large programs
5. **Auto-play for overview**: Watch execution flow at high level

For Animations
~~~~~~~~~~~~~~

1. **Choose memory range carefully**: Show only relevant data
2. **Adjust frame rate**: Slower for detailed analysis, faster for overview
3. **Pick good colormaps**: High contrast for presentations, perceptually uniform for analysis
4. **Downsample long programs**: Use ``plot_every`` to skip steps
5. **Combine with comments**: Explain what viewers should watch for

Performance Tips
~~~~~~~~~~~~~~~~

For very long-running programs:

* Use ``max_steps`` parameter to limit execution
* Enable ``plot_every`` downsampling for animations
* Focus memory range on active data regions
* Consider using the CLI debugger instead of generating full animation
