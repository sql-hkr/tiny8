; Factorial: compute 5!
; Output: R16 = 120

start:
    ldi r17, 5        ; n = 5
    ldi r16, 1        ; result = 1
    
    ; if n <= 1, done
    cpi r17, 2
    brlt done

loop:
    ; result *= n
    mul r16, r17
    
    ; n--
    dec r17
    
    ; continue if n > 1
    cpi r17, 2
    brge loop

done:
    jmp done
