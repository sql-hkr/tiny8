; Array Sum - Sum array elements [5, 10, 15, 20, 25, 30, 35, 40]
; Demonstrates array initialization and iteration
; Output: R16 = 180

start:
    ; Initialize array at RAM[0x60..0x67]
    ldi r20, 0x60
    ldi r21, 5
    st r20, r21
    inc r20
    
    ldi r21, 10
    st r20, r21
    inc r20
    
    ldi r21, 15
    st r20, r21
    inc r20
    
    ldi r21, 20
    st r20, r21
    inc r20
    
    ldi r21, 25
    st r20, r21
    inc r20
    
    ldi r21, 30
    st r20, r21
    inc r20
    
    ldi r21, 35
    st r20, r21
    inc r20
    
    ldi r21, 40
    st r20, r21
    
    ; Sum array elements
    ldi r16, 0        ; sum = 0
    ldi r17, 0x60     ; address
    ldi r18, 8        ; count

sum_loop:
    ld r19, r17       ; Load array[i]
    add r16, r19      ; sum += array[i]
    inc r17           ; address++
    dec r18           ; count--
    
    ; continue if more elements remain
    cpi r18, 0
    brne sum_loop     ; branch if count != 0

done:
    jmp done          ; infinite loop (halt)
