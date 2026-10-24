Architecture
============

This guide provides a detailed overview of the Tiny8 CPU architecture, including its registers, memory model, instruction execution, and status flags.

CPU Overview
------------

Tiny8 implements an 8-bit RISC CPU architecture modeled directly after the Atmel / Microchip AVR instruction set architecture. Instruction semantics, flag behaviors, and operations strictly adhere to the official specification:

* **Official Specification**: `Microchip AVR® Instruction Set Manual (DS40002198A) <https://ww1.microchip.com/downloads/en/DeviceDoc/AVR-Instruction-Set-Manual-DS40002198A.pdf>`_

The design balances hardware realism with educational clarity, providing full visibility and interactive step debugging.

Key Specifications
~~~~~~~~~~~~~~~~~~

* **Word size**: 8 bits
* **Registers**: 32 general-purpose 8-bit registers (R0-R31)
* **Memory**: 64KB RAM (configurable)
* **Stack**: Grows downward from high memory (SP decrements on push)
* **Instruction set**: 67 instructions compliant with AVR DS40002198A
* **Status register**: 8 flags (SREG: I, T, H, S, V, N, Z, C)

Register Architecture
---------------------

In strict alignment with the **Microchip AVR® Instruction Set Manual (DS40002198A, Section 4)**, the CPU register file consists of 32 8-bit general-purpose working registers, labeled **R0** through **R31**. All 32 registers have direct, single-cycle access to the Arithmetic Logic Unit (ALU).

.. code-block:: text

   ┌────────────────────────────────────────────────────────────────────────┐
   │                            AVR Register File                           │
   ├──────────────────────────────────┬─────────────────────────────────────┤
   │       R0 – R15 (General)         │     R16 – R31 (Upper Working)       │
   ├──────────────────────────────────┼─────────────────────────────────────┤
   │  R0   R1   ...   R14   R15       │  R16  R17  ...   R24   R25          │
   └──────────────────────────────────┴─────────────────────────────────────┘
                                      │  R26 (XL)   R27 (XH)  → X-register  │
                                      │  R28 (YL)   R29 (YH)  → Y-register  │
                                      │  R30 (ZL)   R31 (ZH)  → Z-register  │
                                      └─────────────────────────────────────┘

Register Organization & Special Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **General Working Registers (R0–R15)**:
  Operate with all two-register arithmetic, logical, and bit operations (e.g., ``ADD``, ``SUB``, ``AND``, ``OR``, ``EOR``, ``MOV``, ``CP``).
* **Upper Registers (R16–R31)**:
  Support direct immediate instructions (``LDI``, ``SUBI``, ``SBCI``, ``ANDI``, ``ORI``, ``CPI``) where an 8-bit constant :math:`K` is supplied in the instruction.
* **16-bit Word Operand Pairs (R25:R24, X, Y, Z)**:
  The word operations ``ADIW`` (Add Immediate to Word) and ``SBIW`` (Subtract Immediate from Word) operate exclusively on the upper register pairs:
  * ``R25:R24``
  * ``R27:R26`` (X-register)
  * ``R29:R28`` (Y-register)
  * ``R31:R30`` (Z-register)
* **16-bit Pointer Registers (X, Y, Z)**:
  Six registers (R26–R31) serve as three 16-bit indirect address pointers for Data Space memory addressing:
  * **X-register**: ``XL = R26`` (low byte), ``XH = R27`` (high byte)
  * **Y-register**: ``YL = R28`` (low byte), ``YH = R29`` (high byte)
  * **Z-register**: ``ZL = R30`` (low byte), ``ZH = R31`` (high byte)

Special Registers
~~~~~~~~~~~~~~~~~

Program Counter (PC)
^^^^^^^^^^^^^^^^^^^^

* 16-bit program address pointer referencing instructions in program memory.
* Automatically increments during sequential execution.
* Modified by jump (``JMP``, ``RJMP``), subroutine call/return (``CALL``, ``RCALL``, ``RET``, ``RETI``), skip instructions (``CPSE``, ``SBRS``, ``SBRC``, ``SBIS``, ``SBIC``), and conditional branches (``BRxx``).

Stack Pointer (SP)
^^^^^^^^^^^^^^^^^^

* 16-bit stack pointer pointing to the current top of the stack in Data SRAM.
* Initialized to the end of RAM (default: ``0xFFFF`` with 64KB RAM).
* Decrements during ``PUSH``, ``CALL``, and ``RCALL`` (post-decrement).
* Increments during ``POP``, ``RET``, and ``RETI`` (pre-increment).

Status Register (SREG)
^^^^^^^^^^^^^^^^^^^^^^

* 8-bit condition flag register containing flags: ``I``, ``T``, ``H``, ``S``, ``V``, ``N``, ``Z``, ``C``.
* Updated by arithmetic, logical, and shift operations according to exact Boolean algebra defined in DS40002198A.

.. code-block:: text

   SREG: [ I | T | H | S | V | N | Z | C ]
         Bit 7                         Bit 0

Memory Model & Addressing Modes
-------------------------------

Data Memory Space
~~~~~~~~~~~~~~~~~

Tiny8 provides a flat, byte-addressable memory space modeled after AVR SRAM with configurable capacity (default: 65536 bytes / 64KB, addressable range ``0x0000`` to ``0xFFFF``).

.. code-block:: text

   0xFFFF  ┌──────────────────────────────────┐ ← SP (Initial Position)
           │            Stack Area            │ Stack grows downward (PUSH, CALL)
           │            ↓  ↓  ↓  ↓            │
   0x0600  ├──────────────────────────────────┤
           │      Upper RAM & Model Weights   │ Dynamic data, arrays, diffusion weights
   0x0200  ├──────────────────────────────────┤
           │  Display VRAM Matrix (32x32)     │ Memory-mapped display (1024 bytes)
           │  ASCII Text & Heatmap Output     │ Fits 28x28 MNIST digits (margin: 2)
   0x0060  ├──────────────────────────────────┤
           │            User SRAM             │ General data & arrays start at 0x0060
   0x0020  ├──────────────────────────────────┤
           │          I/O Registers           │ 64 I/O ports (0x00..0x3F via IN/OUT)
   0x0000  ├──────────────────────────────────┤
           │    General Working Registers     │ 32 registers (R0..R31) / Reserved
           └──────────────────────────────────┘

AVR Addressing Modes
~~~~~~~~~~~~~~~~~~~~

Tiny8 strictly adheres to the standard AVR addressing modes specified in DS40002198A:

1. **Direct Single Register**: Operates on a single working register :math:`Rd` (e.g. ``INC Rd``, ``DEC Rd``, ``NEG Rd``, ``COM Rd``, ``CLR Rd``, ``SER Rd``, ``SWAP Rd``, ``LSL Rd``, ``LSR Rd``).
2. **Direct Two-Register**: Operates on two working registers :math:`Rd` and :math:`Rr` (e.g. ``ADD Rd, Rr``, ``ADC Rd, Rr``, ``SUB Rd, Rr``, ``SBC Rd, Rr``, ``AND Rd, Rr``, ``OR Rd, Rr``, ``EOR Rd, Rr``, ``CP Rd, Rr``, ``MOV Rd, Rr``).
3. **Immediate Addressing**: An 8-bit constant :math:`K` operates on an upper register :math:`R16 \le Rd \le R31` (e.g. ``LDI Rd, K``, ``SUBI Rd, K``, ``SBCI Rd, K``, ``ANDI Rd, K``, ``ORI Rd, K``, ``CPI Rd, K``).
4. **Word Immediate Addressing**: A 6-bit constant :math:`0 \le K \le 63` operates on register pairs :math:`R25:R24`, :math:`X`, :math:`Y`, or :math:`Z` (e.g. ``ADIW Rd, K``, ``SBIW Rd, K``).
5. **Direct Data Addressing**: 16-bit absolute memory address :math:`k` loads or stores directly to Data Space (e.g. ``LDS Rd, k``, ``STS k, Rr``).
6. **Data Indirect Addressing with Pointer Registers (X, Y, Z)**: Accesses Data Space through 16-bit register pointers :math:`X` (R27:R26), :math:`Y` (R29:R28), or :math:`Z` (R31:R30) (e.g. ``LD Rd, X``, ``ST X, Rr``).
7. **I/O Direct Addressing**: Reads or writes to 6-bit I/O addresses :math:`0 \le P \le 63` (e.g. ``IN Rd, P``, ``OUT P, Rr``, ``SBI P, b``, ``CBI P, b``, ``SBIS P, b``, ``SBIC P, b``).
8. **Relative Program Addressing**: Jumps or branches relative to the current Program Counter within range :math:`PC + k + 1` (e.g. ``RJMP k``, ``RCALL k``, ``BREQ k``, ``BRNE k``, ``BRCS k``, ``BRCC k``, ``BRLO k``, ``BRSH k``, ``BRGE k``, ``BRLT k``, ``BRMI k``, ``BRPL k``).
9. **Direct Program Addressing**: Unconditional jump or long subroutine call directly to 16-bit program address :math:`k` (e.g. ``JMP k``, ``CALL k``).
10. **Indirect Program Addressing**: Return from subroutine or interrupt through return address popped from the stack (e.g. ``RET``, ``RETI``).

Memory Access Examples
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: asm

   ; 1. Direct Data Addressing
   lds r16, 0x0200      ; Load byte directly from address 0x0200
   sts 0x0200, r16      ; Store byte directly to address 0x0200
   
   ; 2. Data Indirect Addressing via X Pointer Register (R27:R26)
   ldi r26, 0x50        ; XL = 0x50
   ldi r27, 0x02        ; XH = 0x02 (X = 0x0250)
   ld r16, r26          ; Load from memory[X] into R16
   st r26, r17          ; Store R17 to memory[X]

   ; 3. Stack Operations
   push r16             ; Push R16 onto stack (SP decrements)
   pop r17              ; Pop from stack into R17 (SP increments)

   ; 4. I/O Port Operations
   in r16, 0x10         ; Read from keyboard buffer port (0x0010)
   out 0x3F, r16        ; Write to I/O port 0x3F

* All memory is initialized to 0 on CPU creation
* The assembler loads program instructions starting at address 0
* Stack pointer is initialized to the top of memory

Status Flags
------------

The Status Register (SREG) contains 8 condition flags that reflect the result of operations and control program flow. In accordance with the **Microchip AVR® Instruction Set Manual (DS40002198A)**, each flag is defined and updated according to exact Boolean algebraic formulas.

Flag Descriptions & Boolean Formulas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 6 12 22 60

   * - Bit
     - Flag
     - Name
     - DS40002198A Definition & Formula
   * - 7
     - **I**
     - Global Interrupt
     - Set by ``SEI``, cleared by ``CLI`` or hardware interrupt entry.
   * - 6
     - **T**
     - Bit Copy Storage
     - Transferred between SREG and register bit locations by ``BST`` / ``BLD``.
   * - 5
     - **H**
     - Half Carry
     - Indicates carry/borrow across nibble boundary (bit 3 to bit 4). ADD: :math:`Rd3 \cdot Rr3 + Rr3 \cdot \overline{R3} + \overline{R3} \cdot Rd3`. SUB: :math:`\overline{Rd3} \cdot Rr3 + Rr3 \cdot R3 + R3 \cdot \overline{Rd3}`.
   * - 4
     - **S**
     - Sign Bit
     - True algebraic sign test considering two's complement overflow: :math:`S = N \oplus V`.
   * - 3
     - **V**
     - Overflow
     - Two's complement signed overflow flag. ADD: :math:`Rd7 \cdot Rr7 \cdot \overline{R7} + \overline{Rd7} \cdot \overline{Rr7} \cdot R7`. SUB: :math:`Rd7 \cdot \overline{Rr7} \cdot \overline{R7} + \overline{Rd7} \cdot Rr7 \cdot R7`.
   * - 2
     - **N**
     - Negative
     - Set if the most significant bit (MSB, bit 7) of the result is 1: :math:`N = R7`.
   * - 1
     - **Z**
     - Zero
     - Set if the result equals zero: :math:`Z = \overline{R7} \cdot \overline{R6} \cdot \overline{R5} \cdot \overline{R4} \cdot \overline{R3} \cdot \overline{R2} \cdot \overline{R1} \cdot \overline{R0}`.
   * - 0
     - **C**
     - Carry / Borrow
     - Unsigned carry out of bit 7 or borrow. ADD: :math:`Rd7 \cdot Rr7 + Rr7 \cdot \overline{R7} + \overline{R7} \cdot Rd7`. SUB: :math:`\overline{Rd7} \cdot Rr7 + Rr7 \cdot R7 + R7 \cdot \overline{Rd7}`.

Flag Updates by Instruction Category
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

According to AVR Instruction Set Manual DS40002198A:

**Arithmetic (ADD, ADC, SUB, SUBI, SBC, SBCI)**
  Updates all condition flags: ``H``, ``S``, ``V``, ``N``, ``Z``, ``C``.

**Comparisons (CP, CPI)**
  Identical flag updates to subtraction (``SUB`` / ``SUBI``), but the register value is discarded.

**Bitwise Logical (AND, ANDI, OR, ORI, EOR, TST)**
  Updates ``S``, ``V=0`` (cleared), ``N``, ``Z``. Carry ``C`` and Half-Carry ``H`` are **unaffected** (``-``). ``TST Rd`` is an alias for ``AND Rd, Rd``.

**Register Clearing & Setting (CLR, SER)**
  * ``CLR Rd`` is an alias for ``EOR Rd, Rd``: sets ``Z=1``, ``S=0``, ``V=0``, ``N=0``; leaves ``C`` and ``H`` unaffected.
  * ``SER Rd`` is an alias for ``LDI Rd, 0xFF``: **no flags affected**.

**Single-Operand Arithmetic (INC, DEC, NEG, COM)**
  * ``INC`` / ``DEC``: Update ``S``, ``V``, ``N``, ``Z``. Carry ``C`` is **unaffected** (allows loop counters without clobbering carry).
  * ``NEG``: Two's complement negation (:math:`R = 0 - Rd`). Updates ``H``, ``S``, ``V``, ``N``, ``Z``, ``C``. (:math:`C = (R \neq 0)`, :math:`V = (Rd = 0x80)`).
  * ``COM``: One's complement inversion (:math:`R = 0xFF - Rd`). Updates ``S``, ``V=0``, ``N``, ``Z``, and forces ``C=1``.

**Shifts & Rotates (LSL, LSR, ROL, ROR, SWAP)**
  * ``LSL Rd``: Alias for ``ADD Rd, Rd``.
  * ``ROL Rd``: Alias for ``ADC Rd, Rd``.
  * ``LSR Rd``: Logical shift right. Sets :math:`C = Rd0`, :math:`N = 0`, :math:`Z = (R = 0)`, :math:`V = N \oplus C = C`, :math:`S = N \oplus V = C`.
  * ``ROR Rd``: Rotate right through carry. Sets :math:`C = Rd0`, :math:`N = R7`, :math:`Z = (R = 0)`, :math:`V = N \oplus C`, :math:`S = N \oplus V`.
  * ``SWAP Rd``: Swaps nibbles. **No flags affected**.

**Word Operations (ADIW, SBIW)**
  16-bit word addition / subtraction on pointer register pairs (R25:R24, R27:R26, R29:R28, R31:R30). Updates ``S``, ``V``, ``N``, ``Z``, ``C``.

**Data Transfer & Branches (LDI, MOV, LD, ST, LDS, STS, PUSH, POP, IN, OUT, JMP, RJMP, CALL, RCALL, RET, BRxx)**
  Do not affect status flags, except ``RETI`` which sets the Global Interrupt Flag ``I = 1``.

Using Flags for Branches
~~~~~~~~~~~~~~~~~~~~~~~~~

Conditional branch instructions inspect specific SREG condition flags (all branches take target label or relative offset without altering flags):

.. list-table::
   :header-rows: 1
   :widths: 15 20 65

   * - Mnemonic
     - Condition
     - Description (per DS40002198A)
   * - ``BREQ label``
     - Z = 1
     - Branch if Equal
   * - ``BRNE label``
     - Z = 0
     - Branch if Not Equal
   * - ``BRCS label``
     - C = 1
     - Branch if Carry Set
   * - ``BRCC label``
     - C = 0
     - Branch if Carry Clear
   * - ``BRLO label``
     - C = 1
     - Branch if Lower (Unsigned, alias for ``BRCS``)
   * - ``BRSH label``
     - C = 0
     - Branch if Same or Higher (Unsigned, alias for ``BRCC``)
   * - ``BRGE label``
     - S = 0 (N ⊕ V = 0)
     - Branch if Greater or Equal (Signed)
   * - ``BRLT label``
     - S = 1 (N ⊕ V = 1)
     - Branch if Less Than (Signed)
   * - ``BRMI label``
     - N = 1
     - Branch if Minus
   * - ``BRPL label``
     - N = 0
     - Branch if Plus

Instruction Execution & ALU
----------------------------

ALU Operation & Register Access
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In strict compliance with the **AVR® Instruction Set Manual (DS40002198A, Section 4)**, the high-performance AVR Arithmetic Logic Unit (ALU) operates in direct connection with all 32 general-purpose registers:

* **Single-Cycle Operation**: Arithmetic and logical register-to-register operations execute within a single instruction transition. In this cycle:
  1. Two operand registers are read from the Register File.
  2. The operation (Arithmetic, Logical, or Bit manipulation) is evaluated.
  3. The result is written back to the destination register :math:`Rd`.
  4. The Status Register (SREG) condition flags are updated according to exact Boolean algebraic formulas.
* **ALU Functional Blocks**:
  * **Arithmetic**: Addition (``ADD``, ``ADC``, ``ADIW``), Subtraction (``SUB``, ``SUBI``, ``SBC``, ``SBCI``, ``SBIW``), Comparison (``CP``, ``CPI``), Negation (``NEG``), Increment (``INC``), Decrement (``DEC``), and Multiplication (``MUL``, ``MULS``, ``MULSU``).
  * **Logical**: Bitwise AND (``AND``, ``ANDI``, ``TST``), OR (``OR``, ``ORI``), Exclusive-OR (``EOR``, ``CLR``), and One's Complement (``COM``).
  * **Bit & Shift Functions**: Bit set/clear (``SBI``, ``CBI``), Shifts (``LSL``, ``LSR``, ``ASR``), Rotates through carry (``ROL``, ``ROR``), and Nibble swap (``SWAP``).

Fetch-Decode-Execute Cycle
~~~~~~~~~~~~~~~~~~~~~~~~~~

Tiny8 executes programs through the classical CPU cycle:

.. code-block:: text

   ┌─────────────────────────────────────────────────────────────┐
   │                          CPU Cycle                          │
   ├───────────┬───────────┬───────────────────┬─────────────────┤
   │   FETCH   │  DECODE   │      EXECUTE      │   WRITE & STEP  │
   │ Read from │ Opcode &  │ ALU / Branch /    │ Update Reg/RAM, │
   │ PC address│ Operands  │ Memory Operation  │ SREG & Advance  │
   └───────────┴───────────┴───────────────────┴─────────────────┘

Instruction Format & Encoding
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In physical AVR microcontrollers:
* Most instructions are **16-bit (1-word)** opcodes.
* Direct memory instructions (``LDS``, ``STS``) and long jumps/calls (``JMP``, ``CALL``) are **32-bit (2-word)** opcodes.

In Tiny8, the assembler validates operands according to AVR DS40002198A constraints (e.g., verifying that ``LDI``, ``SUBI``, ``CPI`` only target upper registers R16–R31, and that ``ADIW`` / ``SBIW`` target valid pointer register pairs), then stores them as pre-decoded execution tuples:

.. code-block:: python

   (mnemonic, (operand1, operand2, ...))

   # Examples:
   ("ldi", (16, 42))        # LDI R16, 42
   ("add", (16, 17))        # ADD R16, R17
   ("lds", (16, 0x0200))    # LDS R16, 0x0200
   ("jmp", ("loop",))       # JMP loop

Step Tracing & State Inspection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

During each execution step, Tiny8 records changes to facilitate visual debugging:

* **Register Trace**: Tracks register writes as ``(step, register_index, new_value)``.
* **Memory Trace**: Tracks SRAM writes as ``(step, address, new_value)``.
* **Step Telemetry**: Records PC, SREG flags, cycle counts, and call stack backtraces.

Hardware Realism & AVR Compliance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tiny8 is strictly grounded in the **Microchip AVR® Instruction Set Manual (DS40002198A)**:

* **Instruction Set Fidelity**: All 61 supported instructions strictly follow official Microchip AVR definitions, operands, and SREG Boolean formulas without non-standard instruction extensions.
* **Hardware MUL Compliance**: In accordance with AVR DS40002198A, ``MUL Rd, Rr`` writes the 16-bit unsigned product strictly into the dedicated register pair ``R1:R0`` (R0 = low byte, R1 = high byte).
* **Software Division**: Conforming to physical AVR silicon, integer division is performed via standard software routines (e.g., subtraction loops or shift-and-subtract) rather than non-standard hardware instructions.
* **Execution & Memory Model**: Instructions execute in discrete single-step transitions across a unified flat address space with memory-mapped I/O (ports 0x00..0x3F including CRT matrix and keyboard buffer) for full visibility and educational inspectability.

Design Philosophy
-----------------

Tiny8's architecture is designed with these principles:

1. **Simplicity**: Easy to understand and implement
2. **Educational value**: Teaches fundamental concepts
3. **Inspectability**: Full visibility into CPU state
4. **Extensibility**: Easy to add new instructions
5. **Practicality**: Can run real algorithms and demonstrate CS concepts

The architecture strikes a balance between realism (standard AVR architecture) and pedagogy (simplified execution model), making it suitable for:

* Computer architecture courses
* Assembly language learning
* Algorithm visualization
* Embedded systems concepts
* Compiler/assembler development
