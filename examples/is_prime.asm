; Is prime: check if 17 is a prime number using trial division
; Tests divisibility by all numbers from 2 to n/2
; Registers: R16 = result (1=prime, 0=not prime), R17 = n, R18 = divisor, R19-R20 = temp
; Output: R16 = 1 (17 is prime)

start:
    ldi r17, 17       ; n = 17 (number to test for primality)
    
    ; special cases: numbers <= 1 are not prime
    cpi r17, 2
    brlt not_prime    ; branch if n < 2
    
    ; special case: 2 is prime (smallest prime)
    cpi r17, 2
    breq is_prime
    
    ; test divisibility: check divisors from 2 upwards
    ldi r18, 2        ; divisor = 2

check_loop:
    ; check if n is divisible by current divisor: n % divisor == 0
    mov r19, r17

mod_loop:
    cp r19, r18
    brlt mod_done
    sub r19, r18
    jmp mod_loop

mod_done:
    ; if remainder in r19 == 0, n is divisible (not prime)
    cpi r19, 0
    breq not_prime
    
    ; try next divisor
    inc r18
    
    ; optimization: if divisor * 2 > n, no need to continue (number is prime)
    mov r19, r18
    ldi r20, 2
    mul r19, r20      ; product in R1:R0 per AVR specification
    mov r19, r0       ; r19 = divisor * 2
    cp r17, r19       ; compare n with divisor * 2
    brlt is_prime     ; if n < divisor * 2, number is prime
    
    jmp check_loop

is_prime:
    ldi r16, 1        ; result = 1 (number is prime)
    jmp done

not_prime:
    ldi r16, 0        ; result = 0 (number is not prime)

done:
    jmp done          ; infinite loop (halt)
