Fibonacci
==========

This example demonstrates a simple iterative implementation of the Fibonacci sequence in Tiny8 assembly language. The program computes the n-th Fibonacci number, where n is provided in register R17, and returns the result in register R16.


.. code-block:: asm
    :caption: fibonacci.asm

    ; Simple iterative Fibonacci
    ; Purpose: compute fib(n) and leave the result in R16.
    ; Registers:
    ;   R17 - input n (non-negative integer)
    ;   R16 - 'a' (accumulator / result)
    ;   R18 - 'b' (next Fibonacci term)
    ;   R19 - temporary scratch used for moves/subtracts
    ;
    ; Algorithm (iterative):
    ;   a = 0
    ;   b = 1
    ;   if n == 0 -> result = a
    ;   if n == 1 -> result = b
    ;   else repeat (n-1) times: (a, b) = (b, a + b)

    start:
        ; initialize: a = 0, b = 1
        LDI R16, 0        ; a = 0
        LDI R18, 1        ; b = 1

        ; quick exit: if n == 0 then result is a (R16 == 0)
        CPI R17, 0
        BREQ done

        ; main loop: run until we've advanced n-1 times
    main_loop:
        ; if n == 1 then the current 'b' is the result
        CPI R17, 1
        BREQ from_b

        ; decrement n (n = n - 1)
        LDI R19, 1
        SUB R17, R19

        ; compute a = a + b (new 'sum' temporarily in R16)
        ADD R16, R18

        ; rotate registers: new a = old b, new b = sum (we used R19 as temp)
        MOV R19, R16      ; temp = sum
        MOV R16, R18      ; a = old b
        MOV R18, R19      ; b = sum

        JMP main_loop

    from_b:
        ; when n reached 1, result is b
        MOV R16, R18
        ; fall through to halt

    done:
        ; infinite loop to halt; result in R16
        JMP done

.. code-block:: python
    :caption: Running the Fibonacci Example

    from tiny8 import CPU, assemble_file

    n = 13

    assert n <= 13, "n must be <= 13 to avoid 8-bit overflow"

    program, labels = assemble_file("examples/fibonacci.asm")
    cpu = CPU()
    cpu.load_program(program, labels)

    cpu.write_reg(17, n)
    cpu.run(max_cycles=1000)

    print("R16 =", cpu.read_reg(16))
    print("R17 =", cpu.read_reg(17))
    print("PC =", cpu.pc)
    print("SP =", cpu.sp)
    print("register changes (reg_trace):\n", *[str(reg) + "\n" for reg in cpu.reg_trace])


.. code-block:: bash
    :caption: Example Output

    R16 = 233
    R17 = 1
    PC = 14
    SP = 2047
    register changes (reg_trace):
    (0, 17, 13)
    (1, 18, 1)
    (6, 19, 1)
    (7, 17, 12)
    (8, 16, 1)
    (16, 17, 11)
    (17, 16, 2)
    (18, 19, 2)
    (19, 16, 1)
    (20, 18, 2)
    (24, 19, 1)
    (25, 17, 10)
    (26, 16, 3)
    (27, 19, 3)
    (28, 16, 2)
    (29, 18, 3)
    (33, 19, 1)
    (34, 17, 9)
    (35, 16, 5)
    (36, 19, 5)
    (37, 16, 3)
    (38, 18, 5)
    (42, 19, 1)
    (43, 17, 8)
    (44, 16, 8)
    (45, 19, 8)
    (46, 16, 5)
    (47, 18, 8)
    (51, 19, 1)
    (52, 17, 7)
    (53, 16, 13)
    (54, 19, 13)
    (55, 16, 8)
    (56, 18, 13)
    (60, 19, 1)
    (61, 17, 6)
    (62, 16, 21)
    (63, 19, 21)
    (64, 16, 13)
    (65, 18, 21)
    (69, 19, 1)
    (70, 17, 5)
    (71, 16, 34)
    (72, 19, 34)
    (73, 16, 21)
    (74, 18, 34)
    (78, 19, 1)
    (79, 17, 4)
    (80, 16, 55)
    (81, 19, 55)
    (82, 16, 34)
    (83, 18, 55)
    (87, 19, 1)
    (88, 17, 3)
    (89, 16, 89)
    (90, 19, 89)
    (91, 16, 55)
    (92, 18, 89)
    (96, 19, 1)
    (97, 17, 2)
    (98, 16, 144)
    (99, 19, 144)
    (100, 16, 89)
    (101, 18, 144)
    (105, 19, 1)
    (106, 17, 1)
    (107, 16, 233)
    (108, 19, 233)
    (109, 16, 144)
    (110, 18, 233)
    (114, 16, 233)