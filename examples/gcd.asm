; GCD - Compute greatest common divisor using Euclidean algorithm
; Example: gcd(48, 18) = 6
; Output: R16 = 6

start:
    ldi r16, 48       ; a = 48
    ldi r17, 18       ; b = 18
    
    cpi r17, 0
    breq done

loop:
    ; Compute remainder: a % b
    mov r18, r16      ; Save a
    div r16, r17      ; a / b
    mul r16, r17      ; (a / b) * b
    mov r19, r18
    sub r19, r16      ; remainder = a - (a/b)*b
    
    ; Shift: a = b, b = remainder
    mov r16, r17
    mov r17, r19
    
    cpi r17, 0
    brne loop

done:
    jmp done
