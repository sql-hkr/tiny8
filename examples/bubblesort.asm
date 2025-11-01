; Bubble Sort - Generate and sort 32 random bytes in ascending order
; Uses PRNG to fill RAM[0x60..0x7F], then bubble sorts in place
; Output: Sorted array at RAM[0x60..0x7F]

    ; Initialize PRNG and counters
    ldi r16, 0x60     ; Base address
    ldi r17, 0        ; Index
    ldi r18, 123      ; PRNG seed
    ldi r25, 75       ; PRNG multiplier

init_loop:
    ; Generate random byte: seed = (seed * 75) + 1
    mul r18, r25
    inc r18
    
    st r16, r18       ; Store random value
    inc r16
    inc r17
    
    ldi r23, 32
    cp r17, r23
    brne init_loop

    ; Bubble sort: 32 elements
    ldi r18, 0        ; Outer loop: i = 0

outer_loop:
    ldi r19, 0        ; Inner loop: j = 0

inner_loop:
    ; Load pair: A = RAM[0x60 + j], B = RAM[0x60 + j + 1]
    ldi r20, 0x60
    add r20, r19
    ld r21, r20       ; r21 = A
    
    ldi r22, 0x60
    add r22, r19
    ldi r23, 1
    add r22, r23
    ld r24, r22       ; r24 = B
    
    ; Swap if A > B (ascending order)
    cp r21, r24
    brcs no_swap      ; Skip if A < B
    st r20, r24       ; RAM[addr_A] = B
    st r22, r21       ; RAM[addr_B] = A

no_swap:
    inc r19
    ldi r23, 31
    cp r19, r23
    breq end_inner
    jmp inner_loop

end_inner:
    inc r18
    ldi r23, 31
    cp r18, r23
    breq done
    jmp outer_loop

done:
    jmp done
