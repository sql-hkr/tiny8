; Find Maximum - Find max value and index in [12, 45, 7, 89, 23, 56, 34, 78]
; Output: R16 = 89 (max value), R17 = 3 (index)

start:
    ; Initialize array at RAM[0x60..0x67]
    ldi r20, 0x60
    ldi r21, 12
    st r20, r21
    inc r20
    
    ldi r21, 45
    st r20, r21
    inc r20
    
    ldi r21, 7
    st r20, r21
    inc r20
    
    ldi r21, 89       ; Maximum value
    st r20, r21
    inc r20
    
    ldi r21, 23
    st r20, r21
    inc r20
    
    ldi r21, 56
    st r20, r21
    inc r20
    
    ldi r21, 34
    st r20, r21
    inc r20
    
    ldi r21, 78
    st r20, r21
    
    ; Find maximum
    ldi r16, 0        ; max = 0
    ldi r17, 0        ; max_index = 0
    ldi r18, 0x60     ; address
    ldi r19, 8        ; count
    ldi r20, 0        ; current_index

find_loop:
    ld r21, r18       ; Load array[i]
    
    cp r16, r21       ; Compare max with current
    brge no_update    ; Skip if max >= current
    mov r16, r21      ; max = current
    mov r17, r20      ; max_index = i

no_update:
    inc r18           ; address++
    inc r20           ; i++
    dec r19           ; count--
    
    cpi r19, 0
    brne find_loop

done:
    jmp done
