; Factorial: compute 5!
; Output: R16 = 120

start:
    ldi r18, 5        ; n = 5
    ldi r16, 1        ; result = 1
    
    ; if n <= 1, done
    cpi r18, 2
    brlt done

loop:
    ; result *= n (stores product in R1:R0 per AVR specification)
    mul r16, r18
    mov r16, r0
    
    ; n--
    dec r18
    
    ; continue if n > 1
    cpi r18, 2
    brge loop

done:
    jmp done
