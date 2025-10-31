; GCD: compute gcd(48, 18)
; Output: R16 = 6

start:
    ldi r16, 48       ; a = 48
    ldi r17, 18       ; b = 18
    
    ; if b == 0, done
    cpi r17, 0
    breq done

loop:
    ; compute remainder: a % b
    mov r18, r16      ; save a
    div r16, r17      ; r16 = a / b
    mul r16, r17      ; r16 = (a / b) * b
    mov r19, r18
    sub r19, r16      ; r19 = a % b
    
    ; shift: a = b, b = remainder
    mov r16, r17
    mov r17, r19
    
    ; continue if b != 0
    cpi r17, 0
    brne loop

done:
    jmp done
