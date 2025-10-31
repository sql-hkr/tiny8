; Hello World: store ASCII string "HELLO" in memory
; Demonstrates basic memory storage operations
; Registers: R16 = address pointer, R17 = ASCII character value
; Output: RAM[0x60..0x64] contains bytes [72, 69, 76, 76, 79] ("HELLO")

start:
    ; store 'H' (ASCII 72 = 0x48)
    ldi r16, 0x60     ; address = 0x60
    ldi r17, 72       ; ASCII code for 'H'
    st r16, r17       ; RAM[0x60] = 'H'
    
    ; store 'E' (ASCII 69 = 0x45)
    ldi r16, 0x61     ; address = 0x61
    ldi r17, 69       ; ASCII code for 'E'
    st r16, r17       ; RAM[0x61] = 'E'
    
    ; store first 'L' (ASCII 76 = 0x4C)
    ldi r16, 0x62     ; address = 0x62
    ldi r17, 76       ; ASCII code for 'L'
    st r16, r17       ; RAM[0x62] = 'L'
    
    ; store second 'L' (ASCII 76 = 0x4C)
    ldi r16, 0x63     ; address = 0x63
    ldi r17, 76       ; ASCII code for 'L'
    st r16, r17       ; RAM[0x63] = 'L'
    
    ; store 'O' (ASCII 79 = 0x4F)
    ldi r16, 0x64     ; address = 0x64
    ldi r17, 79       ; ASCII code for 'O'
    st r16, r17       ; RAM[0x64] = 'O'

done:
    jmp done          ; infinite loop (halt)
