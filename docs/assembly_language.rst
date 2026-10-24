Assembly Language
=================

This guide covers the Tiny8 assembly language syntax, including instruction format, operand types, labels, and assembler directives.

Syntax Overview
---------------

Basic Structure
~~~~~~~~~~~~~~~

A Tiny8 assembly program consists of:

* **Instructions**: CPU operations (e.g., ``add``, ``mov``, ``ldi``)
* **Labels**: Named locations in the program
* **Comments**: Documentation prefixed with ``;``
* **Blank lines**: For readability (ignored by assembler)

Example Program
~~~~~~~~~~~~~~~

.. code-block:: asm

   ; Calculate the sum of 1 to N
   ; N is stored in R16, result in R17
   
       ldi r16, 10         ; N = 10
       ldi r17, 0          ; Sum = 0
       ldi r18, 1          ; Counter = 1
   
   loop:
       add r17, r18        ; Sum += Counter
       inc r18             ; Counter++
       cp r18, r16         ; Compare Counter with N
       brlo loop           ; Loop if Counter < N
       breq loop           ; Loop if Counter == N
   
   done:
       jmp done            ; Infinite loop

Comments
--------

Single-Line Comments
~~~~~~~~~~~~~~~~~~~~

Comments start with a semicolon (``;``) and extend to the end of the line:

.. code-block:: asm

   ldi r16, 42          ; Load the answer
   ; This is a full-line comment
   add r16, r17         ; Add registers

Comments are stripped during assembly and don't affect the generated program.

Whitespace
~~~~~~~~~~

* Leading and trailing whitespace is ignored
* Multiple spaces between tokens are treated as single space
* Blank lines are allowed and ignored

Labels
------

Defining Labels
~~~~~~~~~~~~~~~

Labels mark locations in your program and can be used as jump/branch targets:

.. code-block:: asm

   start:               ; Label on its own line
       ldi r16, 0
   
   loop: dec r16        ; Label before instruction
       brne loop

Label Rules
~~~~~~~~~~~

* Labels must end with a colon (``:``)
* Label names are case-sensitive
* Valid characters: letters, digits, underscore
* Cannot start with a digit
* Cannot be a reserved instruction mnemonic

**Valid labels:**

.. code-block:: asm

   start:
   loop_1:
   CalculateFibonacci:
   _private:

**Invalid labels:**

.. code-block:: text

   123start:          ; Cannot start with digit
   my-label:          ; Hyphens not allowed
   add:               ; Reserved instruction name

Using Labels
~~~~~~~~~~~~

Labels are most commonly used with control flow instructions:

.. code-block:: asm

   ; Unconditional jump
   jmp start
   
   ; Conditional branches
   breq equal_case
   brne not_equal
   brlo lower_case
   
   ; Subroutines
   call subroutine
   
   subroutine:
       ; ... code ...
       ret

Operand Types
-------------

Registers
~~~~~~~~~

Register operands are specified as ``r`` followed by the register number (0-31):

.. code-block:: asm

   mov r0, r1           ; R0-R31 are valid
   add r16, r17
   ldi r31, 255

.. note::
   Some instructions (like ``ldi``) only work with registers R16-R31.

Immediate Values
~~~~~~~~~~~~~~~~

Immediate values are constants embedded in the instruction:

**Decimal** (default)

.. code-block:: asm

   ldi r16, 42          ; Decimal 42
   ldi r17, 255         ; Decimal 255
   ldi r18, -1          ; Negative values allowed

**Hexadecimal** (prefix with ``0x`` or ``$``)

.. code-block:: asm

   ldi r16, 0xFF        ; Hexadecimal FF (255)
   ldi r17, $A5         ; Hexadecimal A5 (165)
   ldi r18, 0x10        ; Hexadecimal 10 (16)

**Binary** (prefix with ``0b``)

.. code-block:: asm

   ldi r16, 0b11111111  ; Binary (255)
   ldi r17, 0b10101010  ; Binary (170)
   ldi r18, 0b00001111  ; Binary (15)

**With Immediate Marker** (optional ``#`` prefix)

.. code-block:: asm

   ldi r16, #42         ; # is optional and ignored
   ldi r17, #0xFF

Memory Addresses
~~~~~~~~~~~~~~~~

Memory addresses are used with load and store instructions:

.. code-block:: asm

   lds r16, 0x0200      ; Load from address 0x0200
   sts 0x0300, r16      ; Store to address 0x0300
   lds r17, 512         ; Decimal addresses also work

Label References
~~~~~~~~~~~~~~~~

Labels can be used as operands for jumps, branches, and calls:

.. code-block:: asm

       jmp start
       breq equal_handler
       call calculate_sum
   
   start:
       ; ...
   
   equal_handler:
       ; ...
   
   calculate_sum:
       ; ...
       ret

Instruction Format
------------------

General Pattern
~~~~~~~~~~~~~~~

Instructions follow this pattern:

.. code-block:: text

   [label:] mnemonic [operand1[, operand2[, ...]]]

* **label**: Optional label ending with ``:``
* **mnemonic**: Instruction name (e.g., ``add``, ``mov``, ``ldi``)
* **operands**: Zero or more operands separated by commas

Operand Count
~~~~~~~~~~~~~

Different instructions take different numbers of operands:

.. code-block:: asm

   ; Zero operands
   nop                  ; No operation
   ret                  ; Return from subroutine
   
   ; One operand
   inc r16              ; Increment register
   dec r17              ; Decrement register
   jmp loop             ; Jump to label
   push r16             ; Push register
   
   ; Two operands
   mov r16, r17         ; Move R17 to R16
   add r16, r17         ; Add R17 to R16
   ldi r16, 42          ; Load immediate into R16
   lds r16, 0x0200      ; Load from memory

Case Sensitivity
~~~~~~~~~~~~~~~~

* **Instructions**: Case-insensitive (``ADD``, ``add``, ``Add`` are all valid)
* **Registers**: Case-insensitive (``r16``, ``R16`` are both valid)
* **Labels**: Case-sensitive (``Loop`` and ``loop`` are different)

.. code-block:: asm

   ; These are all equivalent
   ADD r16, r17
   add r16, r17
   Add R16, R17
   
   ; But these labels are different
   Loop:
       ; ...
       jmp loop        ; Error! Label "loop" not defined

Program Structure
-----------------

Typical Program Layout
~~~~~~~~~~~~~~~~~~~~~~

Most Tiny8 programs follow this structure:

.. code-block:: asm

   ; ============================================
   ; Program: Description
   ; Author: Your Name
   ; Description: What the program does
   ; ============================================
   
   ; --- Initialization ---
       ldi r16, initial_value
       ldi r17, 0
   
   ; --- Main Loop ---
   main_loop:
       ; ... main program logic ...
       jmp main_loop
   
   ; --- Subroutines ---
   subroutine1:
       ; ... subroutine code ...
       ret
   
   subroutine2:
       ; ... subroutine code ...
       ret
   
   ; --- End ---
   done:
       jmp done         ; Infinite loop

Initialization
~~~~~~~~~~~~~~

Initialize registers and memory at the start of your program:

.. code-block:: asm

   ; Initialize working registers
   ldi r16, 0           ; Counter
   ldi r17, 1           ; Accumulator
   ldi r18, 10          ; Loop limit
   
   ; Initialize memory if needed
   ldi r19, 0xFF
   sts 0x0200, r19      ; Store initial value

Main Loop
~~~~~~~~~

Most programs have a main execution loop:

.. code-block:: asm

   main:
       ; Read input
       lds r16, input_addr
       
       ; Process
       call process_data
       
       ; Write output
       sts output_addr, r16
       
       ; Repeat
       jmp main

Program Termination
~~~~~~~~~~~~~~~~~~~

Since Tiny8 doesn't have a "halt" instruction, programs typically end with an infinite loop:

.. code-block:: asm

   done:
       jmp done         ; Loop forever
   
   ; Or explicitly spin
   end:
       nop
       jmp end

Assembler Behavior
------------------

Two-Pass Assembly
~~~~~~~~~~~~~~~~~

The assembler makes two passes through your code:

1. **First pass**: Collect all labels and their addresses
2. **Second pass**: Resolve label references and generate instructions

This allows forward references:

.. code-block:: asm

   ; Forward reference (allowed)
       jmp forward_label
       nop
       nop
   forward_label:
       ret

Number Parsing
~~~~~~~~~~~~~~

The assembler recognizes several number formats:

.. list-table::
   :header-rows: 1
   :widths: 30 30 40

   * - Format
     - Example
     - Value
   * - Decimal
     - ``42``
     - 42
   * - Negative decimal
     - ``-10``
     - -10 (stored as 246 in 8-bit)
   * - Hexadecimal (0x)
     - ``0xFF``
     - 255
   * - Hexadecimal ($)
     - ``$FF``
     - 255
   * - Binary
     - ``0b11111111``
     - 255

Error Handling
~~~~~~~~~~~~~~

The assembler will report errors for:

* Invalid instruction mnemonics
* Wrong number of operands
* Invalid register numbers (< 0 or > 31)
* Undefined label references
* Invalid number formats

Best Practices
--------------

Code Organization
~~~~~~~~~~~~~~~~~

1. **Use meaningful labels**: ``calculate_sum`` not ``label1``
2. **Comment liberally**: Explain what and why, not just how
3. **Group related code**: Keep subroutines together
4. **Use blank lines**: Separate logical sections

.. code-block:: asm

   ; Good: Clear structure and documentation
   ; Calculate factorial of N
   ; Input: R16 = N
   ; Output: R17 = N!
   factorial:
       ldi r17, 1           ; result = 1
   
   fact_loop:
       mul r17, r16         ; result *= N
       dec r16              ; N--
       brne fact_loop       ; Continue if N != 0
       ret

Naming Conventions
~~~~~~~~~~~~~~~~~~

* **Labels**: Use ``snake_case`` or ``CamelCase`` consistently
* **Constants**: Use ``UPPER_CASE`` for important constants
* **Temporary values**: Use lower registers (R0-R15)
* **Important data**: Use upper registers (R16-R31)

Register Allocation
~~~~~~~~~~~~~~~~~~~

Plan your register usage:

.. code-block:: asm

   ; Document register usage at top of program
   ; R16: Loop counter
   ; R17: Accumulator
   ; R18: Temporary storage
   ; R19-R20: Function parameters

Value Ranges
~~~~~~~~~~~~

Remember that Tiny8 uses 8-bit values:

* Unsigned range: 0 to 255
* Signed range: -128 to +127
* Overflow wraps around

.. code-block:: asm

   ldi r16, 255
   inc r16              ; R16 = 0 (wraps around)
   
   ldi r17, 0
   dec r17              ; R17 = 255 (wraps around)

Common Patterns
---------------

See the :doc:`getting_started` guide for common assembly patterns like loops, conditionals, and memory operations.

Instruction Set Reference
-------------------------

The Tiny8 instruction set strictly follows the **Microchip AVR® Instruction Set Manual (DS40002198A)**. All mnemonics and register identifiers are case-insensitive. Immediates can be specified in decimal, hexadecimal (``$FF`` or ``0xFF``), or binary (``0b11111111``).

Arithmetic and Logic Instructions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 18 26 36 20

   * - Mnemonic & Operands
     - Description (DS40002198A)
     - Operation
     - Flags
   * - ``ADD Rd, Rr``
     - Add without Carry
     - Rd ← Rd + Rr
     - H, S, V, N, Z, C
   * - ``ADC Rd, Rr``
     - Add with Carry
     - Rd ← Rd + Rr + C
     - H, S, V, N, Z, C
   * - ``ADIW Rd, K``
     - Add Immediate to Word
     - Rd+1:Rd ← Rd+1:Rd + K
     - S, V, N, Z, C
   * - ``SUB Rd, Rr``
     - Subtract without Carry
     - Rd ← Rd - Rr
     - H, S, V, N, Z, C
   * - ``SUBI Rd, K``
     - Subtract Immediate
     - Rd ← Rd - K
     - H, S, V, N, Z, C
   * - ``SBC Rd, Rr``
     - Subtract with Carry
     - Rd ← Rd - Rr - C
     - H, S, V, N, Z, C
   * - ``SBCI Rd, K``
     - Subtract Immediate with Carry
     - Rd ← Rd - K - C
     - H, S, V, N, Z, C
   * - ``SBIW Rd, K``
     - Subtract Immediate from Word
     - Rd+1:Rd ← Rd+1:Rd - K
     - S, V, N, Z, C
   * - ``AND Rd, Rr``
     - Logical AND
     - Rd ← Rd · Rr
     - S, V=0, N, Z
   * - ``ANDI Rd, K``
     - Logical AND with Immediate
     - Rd ← Rd · K
     - S, V=0, N, Z
   * - ``OR Rd, Rr``
     - Logical OR
     - Rd ← Rd ∨ Rr
     - S, V=0, N, Z
   * - ``ORI Rd, K``
     - Logical OR with Immediate
     - Rd ← Rd ∨ K
     - S, V=0, N, Z
   * - ``EOR Rd, Rr``
     - Exclusive OR
     - Rd ← Rd ⊕ Rr
     - S, V=0, N, Z
   * - ``COM Rd``
     - One's Complement
     - Rd ← 0xFF - Rd
     - S, V=0, N, Z, C=1
   * - ``NEG Rd``
     - Two's Complement Negation
     - Rd ← 0x00 - Rd
     - H, S, V, N, Z, C
   * - ``INC Rd``
     - Increment
     - Rd ← Rd + 1
     - S, V, N, Z
   * - ``DEC Rd``
     - Decrement
     - Rd ← Rd - 1
     - S, V, N, Z
   * - ``TST Rd``
     - Test for Zero or Minus
     - Rd ← Rd · Rd (alias for AND)
     - S, V=0, N, Z
   * - ``CLR Rd``
     - Clear Register
     - Rd ← Rd ⊕ Rd (alias for EOR)
     - S=0, V=0, N=0, Z=1
   * - ``SER Rd``
     - Set Register
     - Rd ← 0xFF (alias for LDI)
     - None
   * - ``MUL Rd, Rr``
     - Multiply Unsigned
     - R1:R0 ← Rd × Rr
     - Z, C
   * - ``MULS Rd, Rr``
     - Multiply Signed
     - R1:R0 ← Rd × Rr (signed)
     - Z, C
   * - ``MULSU Rd, Rr``
     - Multiply Signed with Unsigned
     - R1:R0 ← Rd × Rr (Rd signed, Rr unsigned)
     - Z, C

Branch Instructions
~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 18 26 36 20

   * - Mnemonic & Operands
     - Description (DS40002198A)
     - Operation
     - Flags
   * - ``JMP target``
     - Jump
     - PC ← target
     - None
   * - ``RJMP offset``
     - Relative Jump
     - PC ← PC + offset + 1
     - None
   * - ``CALL target``
     - Long Call to Subroutine
     - STACK ← PC + 1, PC ← target
     - None
   * - ``RCALL offset``
     - Relative Call to Subroutine
     - STACK ← PC + 1, PC ← PC + offset + 1
     - None
   * - ``RET``
     - Return from Subroutine
     - PC ← STACK
     - None
   * - ``RETI``
     - Return from Interrupt
     - PC ← STACK, I ← 1
     - I
   * - ``CPSE Rd, Rr``
     - Compare Skip if Equal
     - If Rd = Rr then skip next instruction
     - None
   * - ``CP Rd, Rr``
     - Compare
     - Rd - Rr
     - H, S, V, N, Z, C
   * - ``CPI Rd, K``
     - Compare with Immediate
     - Rd - K
     - H, S, V, N, Z, C
   * - ``BREQ label``
     - Branch if Equal
     - If Z = 1 then PC ← label
     - None
   * - ``BRNE label``
     - Branch if Not Equal
     - If Z = 0 then PC ← label
     - None
   * - ``BRCS label``
     - Branch if Carry Set
     - If C = 1 then PC ← label
     - None
   * - ``BRCC label``
     - Branch if Carry Clear
     - If C = 0 then PC ← label
     - None
   * - ``BRLO label``
     - Branch if Lower (Unsigned)
     - If C = 1 then PC ← label (alias for BRCS)
     - None
   * - ``BRSH label``
     - Branch if Same or Higher
     - If C = 0 then PC ← label (alias for BRCC)
     - None
   * - ``BRGE label``
     - Branch if Greater or Equal (Signed)
     - If S = 0 (N ⊕ V = 0) then PC ← label
     - None
   * - ``BRLT label``
     - Branch if Less Than (Signed)
     - If S = 1 (N ⊕ V = 1) then PC ← label
     - None
   * - ``BRMI label``
     - Branch if Minus
     - If N = 1 then PC ← label
     - None
   * - ``BRPL label``
     - Branch if Plus
     - If N = 0 then PC ← label
     - None

Data Transfer Instructions
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 18 26 36 20

   * - Mnemonic & Operands
     - Description (DS40002198A)
     - Operation
     - Flags
   * - ``MOV Rd, Rr``
     - Copy Register
     - Rd ← Rr
     - None
   * - ``LDI Rd, K``
     - Load Immediate
     - Rd ← K (16 ≤ d ≤ 31)
     - None
   * - ``LD Rd, addr_reg``
     - Load Indirect from Data Space
     - Rd ← (addr_reg)
     - None
   * - ``ST addr_reg, Rr``
     - Store Indirect to Data Space
     - (addr_reg) ← Rr
     - None
   * - ``LDS Rd, addr``
     - Load Direct from Data Space
     - Rd ← (addr)
     - None
   * - ``STS addr, Rr``
     - Store Direct to Data Space
     - (addr) ← Rr
     - None
   * - ``IN Rd, port``
     - Load an I/O Location to Register
     - Rd ← P
     - None
   * - ``OUT port, Rr``
     - Store Register to an I/O Location
     - P ← Rr
     - None
   * - ``PUSH Rr``
     - Push Register on Stack
     - STACK ← Rr, SP ← SP - 1
     - None
   * - ``POP Rd``
     - Pop Register from Stack
     - SP ← SP + 1, Rd ← STACK
     - None

Bit and Bit-Test Instructions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 18 26 36 20

   * - Mnemonic & Operands
     - Description (DS40002198A)
     - Operation
     - Flags
   * - ``SBI port, bit``
     - Set Bit in I/O Register
     - I/O(P, bit) ← 1
     - None
   * - ``CBI port, bit``
     - Clear Bit in I/O Register
     - I/O(P, bit) ← 0
     - None
   * - ``LSL Rd``
     - Logical Shift Left
     - Rd ← Rd ≪ 1 (alias for ADD Rd, Rd)
     - H, S, V, N, Z, C
   * - ``LSR Rd``
     - Logical Shift Right
     - 0 → Rd7 … Rd0 → C
     - S, V, N, Z, C
   * - ``ASR Rd``
     - Arithmetic Shift Right
     - Rd7 → Rd7 … Rd0 → C
     - S, V, N, Z, C
   * - ``ROL Rd``
     - Rotate Left through Carry
     - C ← Rd7 … Rd0 ← C (alias for ADC Rd, Rd)
     - H, S, V, N, Z, C
   * - ``ROR Rd``
     - Rotate Right through Carry
     - C → Rd7 … Rd0 → C
     - S, V, N, Z, C
   * - ``SWAP Rd``
     - Swap Nibbles
     - Rd(7..4) ↔ Rd(3..0)
     - None
   * - ``SBRS Rd, bit``
     - Skip if Bit in Register is Set
     - If Rd(bit) = 1 then skip next instruction
     - None
   * - ``SBRC Rd, bit``
     - Skip if Bit in Register is Cleared
     - If Rd(bit) = 0 then skip next instruction
     - None
   * - ``SBIS port, bit``
     - Skip if Bit in I/O Register is Set
     - If I/O(P, bit) = 1 then skip next instruction
     - None
   * - ``SBIC port, bit``
     - Skip if Bit in I/O Register is Cleared
     - If I/O(P, bit) = 0 then skip next instruction
     - None

MCU Control Instructions
~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 18 26 36 20

   * - Mnemonic & Operands
     - Description (DS40002198A)
     - Operation
     - Flags
   * - ``NOP``
     - No Operation
     - No operation performed
     - None
   * - ``SEI``
     - Set Global Interrupt Flag
     - I ← 1
     - I
   * - ``CLI``
     - Clear Global Interrupt Flag
     - I ← 0
     - I


