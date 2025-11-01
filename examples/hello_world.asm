; Hello World - Store ASCII string "HELLO" in memory
; Demonstrates basic memory store operations
; Output: RAM[0x60..0x64] contains "HELLO" in ASCII

start:
    ldi r16, 0x60     ; Base address
    
    ldi r17, 72       ; 'H'
    st r16, r17
    inc r16
    
    ldi r17, 69       ; 'E'
    st r16, r17
    inc r16
    
    ldi r17, 76       ; 'L'
    st r16, r17
    inc r16
    
    st r16, r17       ; 'L' (reuse value)
    inc r16
    
    ldi r17, 79       ; 'O'
    st r16, r17

done:
    jmp done          ; infinite loop (halt)
