; Sum: compute 1 + 2 + 3 + ... + 20 using loop
; Demonstrates accumulation pattern with counter
; Registers: R16 = sum (accumulator), R17 = n (limit), R18 = i (loop counter)
; Output: R16 = 210 (sum of integers from 1 to 20)

start:
    ldi r17, 20       ; n = 20 (upper limit)
    ldi r16, 0        ; sum = 0 (accumulator starts at zero)
    ldi r18, 1        ; i = 1 (loop counter starts at 1)

loop:
    ; add current counter value to sum: sum += i
    add r16, r18
    
    ; increment counter: i = i + 1
    inc r18
    
    ; continue loop if i <= n
    cp r18, r17       ; compare i with n
    brlt loop         ; branch if i < n
    breq loop         ; also branch if i == n (include n in sum)

done:
    jmp done          ; infinite loop (halt)
