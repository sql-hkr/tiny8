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
