; Sum 1+2+3+...+N - Calculate sum of integers from 1 to 20
; Demonstrates loop with accumulator pattern
; Output: R16 = 210

start:
    ldi r17, 20       ; N = 20
    ldi r16, 0        ; sum = 0
    ldi r18, 1        ; i = 1

loop:
    add r16, r18      ; sum += i
    inc r18           ; i++
    cp r18, r17       ; Compare i with N
    brlt loop         ; Continue if i < N
    breq loop         ; Continue if i == N

done:
    jmp done
