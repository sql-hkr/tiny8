; Count bits: count set bits in 0b10110101 (181)
; Output: R16 = 5

start:
    ldi r17, 181      ; input = 0b10110101 (5 set bits)
    ldi r16, 0        ; count = 0
    mov r18, r17      ; working copy

loop:
    ; check if value is zero
    cpi r18, 0
    breq done
    
    ; if LSB is 1, increment count
    mov r19, r18
    ldi r20, 1
    and r19, r20
    cpi r19, 1
    brne no_inc
    inc r16

no_inc:
    ; shift right (divide by 2)
    ldi r20, 2
    div r18, r20
    
    jmp loop

done:
    jmp done
