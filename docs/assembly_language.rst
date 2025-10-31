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
