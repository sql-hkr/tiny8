; Array sum: compute sum of array values [5, 10, 15, 20, 25, 30, 35, 40]
; Demonstrates array initialization and iteration
; Registers: R16 = sum, R17 = address, R18 = count, R19 = temp, R20-R21 = init
; Output: R16 = 180 (sum of all array elements)

start:
    ; initialize array at RAM[0x60..0x67] with values [5, 10, 15, 20, 25, 30, 35, 40]
    ldi r20, 0x60
    ldi r21, 5
    st r20, r21       ; RAM[0x60] = 5
    
    ldi r20, 0x61
    ldi r21, 10
    st r20, r21       ; RAM[0x61] = 10
    
    ldi r20, 0x62
    ldi r21, 15
    st r20, r21       ; RAM[0x62] = 15
    
    ldi r20, 0x63
    ldi r21, 20
    st r20, r21       ; RAM[0x63] = 20
    
    ldi r20, 0x64
    ldi r21, 25
    st r20, r21       ; RAM[0x64] = 25
    
    ldi r20, 0x65
    ldi r21, 30
    st r20, r21       ; RAM[0x65] = 30
    
    ldi r20, 0x66
    ldi r21, 35
    st r20, r21       ; RAM[0x66] = 35
    
    ldi r20, 0x67
    ldi r21, 40
    st r20, r21       ; RAM[0x67] = 40
    
    ; compute sum by iterating through array
    ldi r16, 0        ; sum = 0 (accumulator)
    ldi r17, 0x60     ; address = 0x60 (start of array)
    ldi r18, 8        ; count = 8 (number of elements)

sum_loop:
    ld r19, r17       ; load current array element into r19
    add r16, r19      ; add element to sum: sum += array[i]
    inc r17           ; advance to next address: address++
    dec r18           ; decrement counter: count--
    
    ; continue if more elements remain
    cpi r18, 0
    brne sum_loop     ; branch if count != 0

done:
    jmp done          ; infinite loop (halt)
