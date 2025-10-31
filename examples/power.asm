; Power: compute 3^4
; Output: R16 = 81

start:
    ldi r16, 3        ; base = 3
    ldi r17, 4        ; exp = 4
    
    ; save base
    mov r18, r16
    
    ; if exp == 0, result = 1
    cpi r17, 0
    breq exp_zero
    
    ; if exp == 1, done
    cpi r17, 1
    breq done
    
    ; counter = 1
    ldi r19, 1

loop:
    ; result *= base
    mul r16, r18
    
    ; counter++
    inc r19
    
    ; continue if counter < exp
    cp r19, r17
    brlt loop
    
    jmp done

exp_zero:
    ldi r16, 1

done:
    jmp done
