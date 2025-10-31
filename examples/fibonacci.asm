; Fibonacci Sequence Calculator
; Calculates the 10th Fibonacci number (F(10) = 55)
; F(0) = 0, F(1) = 1, F(n) = F(n-1) + F(n-2)
;
; Results stored in registers:
; R16 and R17 hold the two most recent Fibonacci numbers

    ldi r16, 0          ; F(0) = 0
    ldi r17, 1          ; F(1) = 1
    ldi r18, 9          ; Counter: 9 more iterations to reach F(10)

loop:
    add r16, r17        ; F(n) = F(n-1) + F(n-2)
    mov r19, r16        ; Save result temporarily
    mov r16, r17        ; Shift: previous = current
    mov r17, r19        ; Shift: current = new result
    dec r18             ; Decrement counter
    brne loop           ; Continue if counter != 0

done:
    jmp done            ; Infinite loop at end
