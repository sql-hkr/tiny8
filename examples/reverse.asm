; Reverse: reverse array [10, 20, 30, 40, 50, 60]
; Output: RAM[0x60..0x65] = [60, 50, 40, 30, 20, 10]

start:
    ; store array at RAM[0x60..0x65]
    ldi r20, 0x60
    ldi r21, 10
    st r20, r21
    
    ldi r20, 0x61
    ldi r21, 20
    st r20, r21
    
    ldi r20, 0x62
    ldi r21, 30
    st r20, r21
    
    ldi r20, 0x63
    ldi r21, 40
    st r20, r21
    
    ldi r20, 0x64
    ldi r21, 50
    st r20, r21
    
    ldi r20, 0x65
    ldi r21, 60
    st r20, r21
    
    ; reverse: swap from both ends
    ldi r16, 0x60     ; left = 0x60
    ldi r17, 0x65     ; right = 0x65

reverse_loop:
    ; check if left >= right
    cp r16, r17
    brge done
    
    ; swap RAM[left] and RAM[right]
    ld r18, r16       ; temp = RAM[left]
    ld r19, r17       ; RAM[left] = RAM[right]
    st r16, r19
    st r17, r18       ; RAM[right] = temp
    
    ; move pointers
    inc r16           ; left++
    dec r17           ; right--
    
    jmp reverse_loop

done:
    jmp done
