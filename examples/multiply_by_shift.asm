; Multiply by shift: compute 7 * 8 using shifts
; Output: R16 = 56

start:
    ldi r17, 7        ; multiplicand
    ldi r18, 8        ; multiplier
    ldi r16, 0        ; result = 0

loop:
    ; if multiplier is zero, done
    cpi r18, 0
    breq done
    
    ; if multiplier LSB is 1, add multiplicand
    mov r19, r18
    ldi r20, 1
    and r19, r20
    cpi r19, 1
    brne no_add
    add r16, r17

no_add:
    ; shift multiplicand left (*2)
    ldi r20, 2
    mul r17, r20
    
    ; shift multiplier right (/2)
    div r18, r20
    
    jmp loop

done:
    jmp done
