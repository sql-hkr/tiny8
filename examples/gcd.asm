; GCD - Compute greatest common divisor using Euclidean algorithm
; Example: gcd(48, 18) = 6
; Output: R16 = 6

start:
    ldi r16, 48       ; a = 48
    ldi r18, 18       ; b = 18

loop:
    cp r16, r18       ; compare a and b
    breq done         ; if a == b, gcd found in R16
    brlt less         ; if a < b, branch
    sub r16, r18      ; a = a - b
    jmp loop

less:
    sub r18, r16      ; b = b - a
    jmp loop

done:
    jmp done
