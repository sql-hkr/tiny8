; Find max: find maximum value and its index in array [12, 45, 7, 89, 23, 56, 34, 78]
; Uses linear search to track both maximum value and position
; Registers: R16 = max value, R17 = max index, R18 = address, R19 = count
;            R20 = current index, R21 = current value
; Output: R16 = 89 (maximum value), R17 = 3 (index of maximum)

start:
    ; initialize array at RAM[0x60..0x67] with test data
    ldi r20, 0x60
    ldi r21, 12
    st r20, r21       ; RAM[0x60] = 12
    
    ldi r20, 0x61
    ldi r21, 45
    st r20, r21       ; RAM[0x61] = 45
    
    ldi r20, 0x62
    ldi r21, 7
    st r20, r21       ; RAM[0x62] = 7
    
    ldi r20, 0x63
    ldi r21, 89
    st r20, r21       ; RAM[0x63] = 89 (this is the maximum)
    
    ldi r20, 0x64
    ldi r21, 23
    st r20, r21       ; RAM[0x64] = 23
    
    ldi r20, 0x65
    ldi r21, 56
    st r20, r21       ; RAM[0x65] = 56
    
    ldi r20, 0x66
    ldi r21, 34
    st r20, r21       ; RAM[0x66] = 34
    
    ldi r20, 0x67
    ldi r21, 78
    st r20, r21       ; RAM[0x67] = 78
    
    ; find maximum value and its index
    ldi r16, 0        ; max = 0 (current maximum value)
    ldi r17, 0        ; max_index = 0 (index of maximum)
    ldi r18, 0x60     ; address = 0x60 (current array position)
    ldi r19, 8        ; count = 8 (elements remaining)
    ldi r20, 0        ; current_index = 0

find_loop:
    ld r21, r18       ; load current array element
    
    ; compare current value with max: if value > max, update both
    cp r16, r21       ; compare max with current value
    brge no_update    ; skip update if max >= value
    mov r16, r21      ; update max = current value
    mov r17, r20      ; update max_index = current_index

no_update:
    inc r18           ; advance to next address
    inc r20           ; increment current index
    dec r19           ; decrement count
    
    ; continue if more elements remain
    cpi r19, 0
    brne find_loop    ; branch if count != 0

done:
    jmp done          ; infinite loop (halt)

    mov r16, r21      ; max = value
    mov r17, r20      ; max_index = current_index

no_update:
    inc r18           ; next address
    inc r20           ; next index
    dec r19           ; count--
    
    cpi r19, 0
    brne find_loop

done:
    jmp done
