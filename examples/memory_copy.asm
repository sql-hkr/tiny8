; Memory copy: copy 6 bytes from RAM[0x60..0x65] to RAM[0x70..0x75]
; Output: RAM[0x70..0x75] = copy of RAM[0x60..0x65]

start:
    ; store source data at RAM[0x60..0x65]
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
    
    ; copy to destination
    ldi r16, 0x60     ; src
    ldi r17, 0x70     ; dst
    ldi r18, 6        ; count

copy_loop:
    ld r19, r16       ; load from src
    st r17, r19       ; store to dst
    
    inc r16           ; next src
    inc r17           ; next dst
    dec r18           ; count--
    
    cpi r18, 0
    brne copy_loop

done:
    jmp done
