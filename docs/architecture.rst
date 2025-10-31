Architecture
============

This guide provides a detailed overview of the Tiny8 CPU architecture, including its registers, memory model, instruction execution, and status flags.

CPU Overview
------------

Tiny8 implements a simplified 8-bit CPU architecture inspired by the AVR family (ATmega series). The design prioritizes educational clarity over cycle-accurate emulation, making it ideal for learning computer architecture fundamentals.

Key Specifications
~~~~~~~~~~~~~~~~~~

* **Word size**: 8 bits
* **Registers**: 32 general-purpose 8-bit registers (R0-R31)
* **Memory**: 2KB RAM (configurable)
* **Stack**: Grows downward from high memory
* **Instruction set**: ~60 instructions (AVR-inspired)
* **Status register**: 8 flags (SREG)

Register Architecture
---------------------

General-Purpose Registers
~~~~~~~~~~~~~~~~~~~~~~~~~

Tiny8 has 32 general-purpose 8-bit registers, labeled **R0** through **R31**.

.. code-block:: text

   ┌─────────────────────────────────────┐
   │  R0  │  R1  │  R2  │   ...  │  R31  │
   ├──────┴──────┴──────┴────────┴───────┤
   │     32 x 8-bit registers            │
   └─────────────────────────────────────┘

All registers are fully general-purpose - there are no dedicated accumulator, index, or pointer registers. However, some instructions may work only with specific register ranges:

* **LDI (Load Immediate)**: Only works with R16-R31
* **Most arithmetic/logic**: Works with any register R0-R31

.. note::
   While all registers are general-purpose, you may want to establish conventions in your programs (e.g., using R0-R15 for temporary values and R16-R31 for important data).

Special Registers
~~~~~~~~~~~~~~~~~

In addition to general-purpose registers, the CPU has several special registers:

Program Counter (PC)
^^^^^^^^^^^^^^^^^^^^

* Points to the current instruction in the program
* Automatically increments after each instruction
* Modified by branch, jump, and call instructions
* **Width**: Depends on program size (virtual, not a physical register)

Stack Pointer (SP)
^^^^^^^^^^^^^^^^^^

* Points to the top of the stack in memory
* Initialized to the end of RAM (default: 0x07FF with 2KB RAM)
* Decrements on PUSH, increments on POP
* Used implicitly by CALL and RET instructions

Status Register (SREG)
^^^^^^^^^^^^^^^^^^^^^^

* 8-bit register containing condition flags
* Updated by arithmetic, logic, and comparison instructions
* Used by conditional branch instructions

.. code-block:: text

   SREG: [ I | T | H | S | V | N | Z | C ]
         Bit 7                         Bit 0

See the `Status Flags`_ section for detailed flag descriptions.

Memory Model
------------

Address Space
~~~~~~~~~~~~~

Tiny8 uses a flexible, byte-addressable memory model with configurable RAM size.

**Default Configuration:**

* RAM size: 2048 bytes (2KB)
* Address range: 0x0000 to 0x07FF
* Stack pointer initializes to 0x07FF (ram_size - 1)

**Memory Layout:**

.. code-block:: text

   0x07FF  ┌──────────────┐ ← SP (initial position)
           │              │
           │  Stack Area  │ Stack grows downward (PUSH decrements SP)
           │              │
           │ ↓ ↓ ↓ ↓ ↓ ↓  │
           │              │
           │              │
           │   Free RAM   │ Available for program use
           │              │
           │              │
           │ ↑ ↑ ↑ ↑ ↑ ↑  │
           │              │
           │  Data Area   │ Variables and data grow upward
           │              │
   0x0000  └──────────────┘ Program starts here (PC=0)

**Key Points:**

* Memory is byte-addressable (each address holds one 8-bit value)
* Full 2KB address space available by default
* No fixed boundaries between stack and data areas
* Stack and data can grow toward each other (watch for collisions!)
* All memory initializes to 0 on CPU creation
* RAM size is configurable via ``Memory(ram_size=...)``

**Memory Access:**

The CPU uses register-indirect addressing for memory operations:

.. code-block:: asm

   ; Load from memory
   ldi r26, 0x00        ; Set address low byte
   ldi r27, 0x02        ; Set address high byte (address = 0x0200)
   ld r16, r26          ; Load byte from address in R26 into R16
   
   ; Store to memory  
   ldi r26, 0x50        ; Address = 0x50
   ldi r16, 42          ; Value to store
   st r26, r16          ; Store R16 to memory[R26]

Memory Operations
~~~~~~~~~~~~~~~~~

**Stack Operations**

The stack is used for temporary storage and subroutine calls:

.. code-block:: asm

   push r16             ; Push R16 onto stack (SP decrements)
   pop r17              ; Pop from stack into R17 (SP increments)
   
   call my_function     ; Pushes return address, then jumps
   ret                  ; Pops return address, then returns

**I/O Operations**

Access I/O ports and special registers:

.. code-block:: asm

   in r16, 0x3F         ; Read from I/O port 0x3F into R16
   out 0x3F, r16        ; Write R16 to I/O port 0x3F

Memory Initialization
~~~~~~~~~~~~~~~~~~~~~

* All memory is initialized to 0 on CPU creation
* The assembler loads program instructions starting at address 0
* Stack pointer is initialized to the top of memory

Status Flags
------------

The Status Register (SREG) contains 8 condition flags that reflect the result of operations and control program flow.

Flag Descriptions
~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 10 15 75

   * - Bit
     - Name
     - Description
   * - 7
     - **I** (Interrupt)
     - Global interrupt enable flag. When set, interrupts are enabled.
   * - 6
     - **T** (Transfer)
     - Bit copy storage. Used by BLD and BST instructions for bit manipulation.
   * - 5
     - **H** (Half Carry)
     - Half-carry flag. Set when there's a carry from bit 3 to bit 4 in arithmetic operations. Used for BCD arithmetic.
   * - 4
     - **S** (Sign)
     - Sign flag, computed as N ⊕ V (N XOR V). Indicates true sign of result considering two's complement overflow.
   * - 3
     - **V** (Overflow)
     - Two's complement overflow flag. Set when signed arithmetic produces a result outside the range -128 to +127.
   * - 2
     - **N** (Negative)
     - Negative flag. Set when the result of an operation has bit 7 set (i.e., the result is negative in two's complement).
   * - 1
     - **Z** (Zero)
     - Zero flag. Set when the result of an operation is zero.
   * - 0
     - **C** (Carry)
     - Carry flag. Set when there's a carry out of bit 7 (unsigned overflow) or a borrow in subtraction.

Flag Updates
~~~~~~~~~~~~

Different instructions update flags in different ways:

**Arithmetic Instructions** (ADD, SUB, ADC, SBC)
  Update all flags: C, Z, N, V, S, H

**Logical Instructions** (AND, OR, EOR)
  Update Z, N, S; Clear V; Leave C unchanged

**Comparison** (CP, CPI)
  Update all flags like subtraction, but don't store result

**Test** (TST)
  Update Z, N, S, V; Clear V

**Increment/Decrement** (INC, DEC)
  Update Z, N, V, S; Leave C unchanged

Using Flags for Branches
~~~~~~~~~~~~~~~~~~~~~~~~~

Conditional branch instructions test specific flag conditions:

.. code-block:: asm

   ; Branch if equal (Z flag set)
   breq label
   
   ; Branch if not equal (Z flag clear)
   brne label
   
   ; Branch if carry set (C flag set)
   brcs label
   
   ; Branch if less than (signed: S flag set)
   brlt label
   
   ; Branch if lower (unsigned: C flag set)
   brlo label

Instruction Execution
---------------------

Fetch-Decode-Execute Cycle
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tiny8 uses a simplified instruction execution model:

1. **Fetch**: Read instruction at address PC
2. **Decode**: Parse instruction mnemonic and operands
3. **Execute**: Perform the operation
4. **Update**: Increment PC, update flags, record traces

.. code-block:: text

   ┌──────────┐
   │  FETCH   │ ← Read instruction at PC
   └────┬─────┘
        │
   ┌────▼─────┐
   │  DECODE  │ ← Parse mnemonic and operands
   └────┬─────┘
        │
   ┌────▼─────┐
   │ EXECUTE  │ ← Perform operation
   └────┬─────┘
        │
   ┌────▼─────┐
   │  UPDATE  │ ← Update PC, flags, traces
   └──────────┘

Instruction Format
~~~~~~~~~~~~~~~~~~

Instructions are stored as tuples in memory:

.. code-block:: python

   (mnemonic, (operand1, operand2, ...))
   
   # Examples:
   ("ldi", (("reg", 16), 42))      # ldi r16, 42
   ("add", (("reg", 16), ("reg", 17)))  # add r16, r17
   ("jmp", ("loop",))              # jmp loop

Operand Types
~~~~~~~~~~~~~

Operands can be:

* **Register**: ``("reg", N)`` where N is 0-31
* **Immediate**: Integer value
* **Label**: String referring to a program location
* **Address**: Memory address (integer)

Step Tracing
~~~~~~~~~~~~

The CPU automatically records traces during execution:

**Register Trace**
  Records all register changes as ``(step, register, new_value)``

**Memory Trace**
  Records all memory writes as ``(step, address, new_value)``

**Step Trace**
  Records full CPU state snapshots for visualization

These traces enable the interactive debugger and animation features.

Performance Characteristics
---------------------------

Execution Model
~~~~~~~~~~~~~~~

* **Single-cycle execution**: Each instruction completes in one "step"
* **No pipeline**: Instructions execute sequentially
* **No timing accuracy**: Simplified model for education

.. note::
   Real AVR microcontrollers have variable instruction timing (1-4 cycles) and pipelined execution. Tiny8 abstracts these details for simplicity.

Limitations
~~~~~~~~~~~

* No I/O peripherals (timers, UART, etc.)
* No interrupt handling (I flag exists but not functional)
* Simplified flag semantics
* No program memory vs. data memory separation (Von Neumann architecture)

Design Philosophy
-----------------

Tiny8's architecture is designed with these principles:

1. **Simplicity**: Easy to understand and implement
2. **Educational value**: Teaches fundamental concepts
3. **Inspectability**: Full visibility into CPU state
4. **Extensibility**: Easy to add new instructions
5. **Practicality**: Can run real algorithms and demonstrate CS concepts

The architecture strikes a balance between realism (AVR-inspired) and pedagogy (simplified execution model), making it suitable for:

* Computer architecture courses
* Assembly language learning
* Algorithm visualization
* Embedded systems concepts
* Compiler/assembler development
