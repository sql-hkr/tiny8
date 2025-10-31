; Bubble sort: fill RAM[0x60..0x80] with random values and sort ascending
; Uses PRNG (pseudo-random number generator) to create test data
; Then performs bubble sort by comparing adjacent elements
; Registers: R16 = address, R17 = index/i, R18 = seed/i, R19 = j
;            R20-R24 = temp values, R25 = PRNG multiplier
; Output: Sorted array at RAM[0x60..0x80] (32 bytes)

    ; initialize PRNG and loop counters
    ldi r16, 0x60     ; base address
    ldi r17, 0        ; index = 0
    ldi r18, 123      ; PRNG seed (starting value)
    ldi r25, 75       ; PRNG multiplier (constant for random generation)

init_loop:
    ; generate pseudo-random byte: seed = (seed * 75) + 1
    mul r18, r25      ; multiply seed by 75 (low byte only)
    inc r18           ; add 1 to avoid zero cycles
    
    ; store generated value at RAM[base + index]
    st r16, r18       ; RAM[0x60 + index] = random value
    inc r16           ; advance base pointer
    inc r17           ; increment index
    
    ; check if we've generated 32 values
    ldi r23, 32
    cp r17, r23       ; compare index with 32
    brne init_loop    ; continue if not done

    ; bubble sort: 32 elements (outer loop runs 31 times)
    ldi r18, 0        ; i = 0 (outer loop counter)

outer_loop:
    ldi r19, 0        ; j = 0 (inner loop counter - element index)

inner_loop:
    ; load element A = RAM[0x60 + j]
    ldi r20, 0x60      ; compute address of element A
    add r20, r19
    ld r21, r20       ; r21 = value of element A
    
    ; load element B = RAM[0x60 + j + 1]
    ldi r22, 0x60      ; compute address of element B
    add r22, r19
    ldi r23, 1
    add r22, r23      ; address = 0x60 + j + 1
    ld r24, r22       ; r24 = value of element B
    
    ; compare and swap if A > B (ascending order)
    cp r21, r24       ; compare A with B
    brcc no_swap      ; skip swap if A < B (carry clear)
    st r20, r24       ; RAM[addr_A] = B
    st r22, r21       ; RAM[addr_B] = A

no_swap:
    ; advance to next pair of elements
    inc r19           ; j++
    ldi r23, 31       ; check if j < 31 (last valid pair)
    cp r19, r23
    breq end_inner    ; exit inner loop if j == 31
    jmp inner_loop

end_inner:
    ; advance outer loop counter
    inc r18           ; i++
    ldi r23, 31       ; check if i < 31 (need 31 passes)
    cp r18, r23
    breq done         ; exit if all passes complete
    jmp outer_loop

done:
    jmp done          ; infinite loop (halt)
