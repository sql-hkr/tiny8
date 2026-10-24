; Power: compute 3^4
; Output: R16 = 81

start:
    ldi r16, 3        ; base = 3
    ldi r18, 4        ; exp = 4
    
    ; save base
    mov r19, r16
    
    ; if exp == 0, result = 1
    cpi r18, 0
    breq exp_zero
    
    ; if exp == 1, done
    cpi r18, 1
    breq done
    
    ; counter = 1
    ldi r20, 1

loop:
    ; result *= base (stores into R1:R0 per AVR specification)
    mul r16, r19
    mov r16, r0
    
    ; counter++
    inc r20
    
    ; continue if counter < exp
    cp r20, r18
    brlt loop
    
    jmp done

exp_zero:
    ldi r16, 1

done:
    jmp done
