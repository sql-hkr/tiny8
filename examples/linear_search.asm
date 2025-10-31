; Linear search: find 56 in array [12, 45, 7, 89, 23, 56, 34, 78]
; Output: R16 = 5 (index), or 255 if not found

start:
    ; store array at RAM[0x60..0x67]
    ldi r20, 0x60
    ldi r21, 12
    st r20, r21
    
    ldi r20, 0x61
    ldi r21, 45
    st r20, r21
    
    ldi r20, 0x62
    ldi r21, 7
    st r20, r21
    
    ldi r20, 0x63
    ldi r21, 89
    st r20, r21
    
    ldi r20, 0x64
    ldi r21, 23
    st r20, r21
    
    ldi r20, 0x65
    ldi r21, 56
    st r20, r21
    
    ldi r20, 0x66
    ldi r21, 34
    st r20, r21
    
    ldi r20, 0x67
    ldi r21, 78
    st r20, r21
    
    ; search for target = 56
    ldi r17, 56       ; target
    ldi r18, 0x60     ; address
    ldi r19, 8        ; count
    ldi r20, 0        ; index

search_loop:
    ld r21, r18       ; load value
    
    ; if value == target, found
    cp r21, r17
    breq found
    
    inc r18           ; next address
    inc r20           ; next index
    dec r19           ; count--
    
    cpi r19, 0
    brne search_loop

not_found:
    ldi r16, 255
    jmp done

found:
    mov r16, r20

done:
    jmp done
