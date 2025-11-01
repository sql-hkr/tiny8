# Tiny8

[![PyPI version](https://img.shields.io/pypi/v/tiny8)](https://pypi.org/project/tiny8/)
[![License](https://img.shields.io/github/license/sql-hkr/tiny8)](LICENSE)
[![Python versions](https://img.shields.io/pypi/pyversions/tiny8)](https://pypi.org/project/tiny8/)
[![CI](https://github.com/sql-hkr/tiny8/actions/workflows/ci.yml/badge.svg)](https://github.com/sql-hkr/tiny8/actions/workflows/ci.yml)
[![codecov](https://codecov.io/github/sql-hkr/tiny8/graph/badge.svg?token=OBM58R8MCL)](https://codecov.io/github/sql-hkr/tiny8)

> **An educational 8-bit CPU simulator with interactive visualization**

Tiny8 is a lightweight and educational toolkit for exploring the fundamentals of computer architecture through hands-on assembly programming and real-time visualization. Designed for learning and experimentation, it features an AVR-inspired 8-bit CPU with 32 registers, a rich instruction set, and powerful debugging tools — all with zero heavy dependencies.


<div align="center">
  <img src="https://github.com/user-attachments/assets/6d4f07ba-21b3-483f-a5d4-7603334c40f4" alt="Animated bubble sort visualization" width="600">
  <p><em>Real-time visualization of a bubble sort algorithm executing on Tiny8</em></p>
</div>

## ✨ Features

### 🎯 **Interactive Terminal Debugger**
<img width="600" src="https://github.com/user-attachments/assets/5317ebcd-53d5-4966-84be-be94b7830899" alt="CLI visualizer screenshot">

- **Vim-style navigation**: Step through execution with intuitive keyboard controls
- **Change highlighting**: See exactly what changed at each step (registers, flags, memory)
- **Advanced search**: Find instructions, track register/memory changes, locate PC addresses
- **Marks and bookmarks**: Set and jump to important execution points
- **Vertical scrolling**: Handle programs with large memory footprints

### 🎬 **Graphical Animation**
- Generate high-quality GIF/MP4 videos of program execution
- Visualize register evolution, memory access patterns, and flag changes
- Perfect for presentations, documentation, and learning materials

### 🏗️ **Complete 8-bit Architecture**
- **32 general-purpose registers** (R0-R31)
- **8-bit ALU** with arithmetic, logical, and bit manipulation operations
- **Status register (SREG)** with 8 condition flags
- **2KB address space** for unified memory and I/O
- **Stack operations** with dedicated stack pointer
- **AVR-inspired instruction set** with 60+ instructions

### 📚 **Educational Focus**
- Clean, readable Python implementation
- Comprehensive examples (Fibonacci, bubble sort, factorial, and more)
- Step-by-step execution traces for debugging
- Full API documentation and instruction set reference

## 🚀 Quick Start

### Installation

```bash
pip install tiny8
```

### Your First Program

Create `fibonacci.asm`:
```asm
; Fibonacci Sequence Calculator
; Calculates the 10th Fibonacci number (F(10) = 55)
; F(0) = 0, F(1) = 1, F(n) = F(n-1) + F(n-2)
;
; Results stored in registers:
; R16 and R17 hold the two most recent Fibonacci numbers

    ldi r16, 0          ; F(0) = 0
    ldi r17, 1          ; F(1) = 1
    ldi r18, 9          ; Counter: 9 more iterations to reach F(10)

loop:
    add r16, r17        ; F(n) = F(n-1) + F(n-2)
    mov r19, r16        ; Save result temporarily
    mov r16, r17        ; Shift: previous = current
    mov r17, r19        ; Shift: current = new result
    dec r18             ; Decrement counter
    brne loop           ; Continue if counter != 0

done:
    jmp done            ; Infinite loop at end
```

Run it:
```bash
tiny8 fibonacci.asm # Interactive debugger
tiny8 fibonacci.asm -m ani -o fibonacci.gif # Generate animation
```

### Python API

```python
from tiny8 import CPU, assemble_file

asm = assemble_file("fibonacci.asm")
cpu = CPU()
cpu.load_program(asm)
cpu.run(max_steps=1000)

print(f"Result: R17 = {cpu.read_reg(17)}")  # Final Fibonacci number
```

## 💡 Why Tiny8?

**For Students** — Write assembly, see immediate results with visual feedback. Understand how each instruction affects CPU state without abstractions.

**For Educators** — Interactive demonstrations, easy assignment creation, and generate animations for lectures.

**For Hobbyists** — Rapid algorithm prototyping at the hardware level with minimal overhead and an extensible, readable codebase.

## 📖 Documentation

- [**Full Documentation**](https://sql-hkr.github.io/tiny8/) — Complete API reference and guides
- [**Instruction Set Reference**](#instruction-set-reference) — All 60+ instructions
- [**CLI Guide**](#interactive-cli-controls) — Terminal debugger keyboard shortcuts
- [**Examples**](#examples) — Sample programs with explanations
- [**Contributing**](CONTRIBUTING.md) — Guidelines for contributors

## 🎮 Interactive CLI Controls

The terminal-based debugger provides powerful navigation and inspection capabilities.

### Navigation & Playback

- `l` / `h` or `→` / `←` — Step forward/backward
- `w` / `b` — Jump ±10 steps
- `0` / `$` — Jump to first/last step
- `Space` — Play/pause auto-execution
- `[` / `]` — Decrease/increase playback speed

### Display & Inspection

- `r` — Toggle register display (all/changed only)
- `M` — Toggle memory display (all/non-zero only)
- `=` — Show detailed step information
- `j` / `k` — Scroll memory view up/down

### Search & Navigation Commands (press `:`)

- `:123` — Jump to step 123
- `:+50` / `:-20` — Relative jumps
- `:/ldi` — Search forward for instruction "ldi"
- `:?add` — Search backward for "add"
- `:@0x100` — Jump to PC address 0x100
- `:r10` — Find next change to register R10
- `:r10=42` — Find where R10 equals 42
- `:m100` — Find next change to memory[100]
- `:fZ` — Find next change to flag Z

### Marks & Help

- `ma` — Set mark 'a' at current step
- `'a` — Jump to mark 'a'
- `/` — Show help screen
- `q` or `ESC` — Quit

## 🎓 Examples

The `examples/` directory contains programs demonstrating key concepts:

| Example | Description |
|---------|-------------|
| `fibonacci.asm` | Fibonacci sequence using registers |
| `bubblesort.asm` | Sorting algorithm with memory visualization |
| `factorial.asm` | Recursive factorial calculation |
| `find_max.asm` | Finding maximum value in array |
| `is_prime.asm` | Prime number checking algorithm |
| `gcd.asm` | Greatest common divisor (Euclidean algorithm) |

### Bubble Sort

Sort 32 bytes in memory:

```bash
tiny8 examples/bubblesort.asm -ms 0x60 -me 0x80 # Watch live
tiny8 examples/bubblesort.asm -m ani -o sort.gif -ms 0x60 -me 0x80   # Create GIF
```

### Using Python

```python
from tiny8 import CPU, assemble_file

cpu = CPU()
cpu.load_program(*assemble_file("examples/bubblesort.asm"))
cpu.run()

print("Sorted:", [cpu.read_ram(i) for i in range(100, 132)])
```

## 🔧 CLI Options

### Command Syntax

```bash
tiny8 FILE [OPTIONS]
```

### General Options

| Option | Description |
|--------|-------------|
| `-m, --mode {cli,ani}` | Visualization mode: `cli` for interactive debugger (default), `ani` for animation |
| `-v, --version` | Show version and exit |
| `--max-steps N` | Maximum execution steps (default: `15000`) |

### Memory Display Options

| Option | Description |
|--------|-------------|
| `-ms, --mem-start ADDR` | Starting memory address (decimal or `0xHEX`, default: `0x00`) |
| `-me, --mem-end ADDR` | Ending memory address (decimal or `0xHEX`, default: `0xFF`) |

### CLI Mode Options

| Option | Description |
|--------|-------------|
| `-d, --delay SEC` | Initial playback delay in seconds (default: `0.15`) |

### Animation Mode Options

| Option | Description |
|--------|-------------|
| `-o, --output FILE` | Output filename (`.gif`, `.mp4`, `.png`) |
| `-f, --fps FPS` | Frames per second (default: `60`) |
| `-i, --interval MS` | Update interval in milliseconds (default: `1`) |
| `-pe, --plot-every N` | Update plot every N steps (default: `100`, higher = faster) |

> **Windows**: CLI debugger requires WSL or `windows-curses`. Animation works natively.

## 📋 Instruction Set Reference

Tiny8 implements an AVR-inspired instruction set with 62 instructions organized into logical categories. All mnemonics are case-insensitive. Registers are specified as R0-R31, immediates support decimal, hex (`$FF` or `0xFF`), and binary (`0b11111111`) notation.

### Data Transfer

| Instruction | Description | Example |
|-------------|-------------|---------|
| `LDI Rd, K` | Load 8-bit immediate into register | `ldi r16, 42` |
| `MOV Rd, Rr` | Copy register to register | `mov r17, r16` |
| `LD Rd, Rr` | Load from RAM at address in Rr | `ld r18, r16` |
| `ST Rr, Rs` | Store Rs to RAM at address in Rr | `st r16, r18` |
| `IN Rd, port` | Read from I/O port into register | `in r16, 0x3F` |
| `OUT port, Rr` | Write register to I/O port | `out 0x3F, r16` |
| `PUSH Rr` | Push register onto stack | `push r16` |
| `POP Rd` | Pop from stack into register | `pop r16` |

### Arithmetic Operations

| Instruction | Description | Example |
|-------------|-------------|---------|
| `ADD Rd, Rr` | Add registers | `add r16, r17` |
| `ADC Rd, Rr` | Add with carry | `adc r16, r17` |
| `SUB Rd, Rr` | Subtract registers | `sub r16, r17` |
| `SUBI Rd, K` | Subtract immediate | `subi r16, 10` |
| `SBC Rd, Rr` | Subtract with carry | `sbc r16, r17` |
| `SBCI Rd, K` | Subtract immediate with carry | `sbci r16, 5` |
| `INC Rd` | Increment register | `inc r16` |
| `DEC Rd` | Decrement register | `dec r16` |
| `MUL Rd, Rr` | Multiply (result in Rd:Rd+1) | `mul r16, r17` |
| `DIV Rd, Rr` | Divide (quotient→Rd, remainder→Rd+1) | `div r16, r17` |
| `NEG Rd` | Two's complement negation | `neg r16` |
| `ADIW Rd, K` | Add immediate to word (16-bit) | `adiw r24, 1` |
| `SBIW Rd, K` | Subtract immediate from word | `sbiw r24, 1` |

### Logical & Bit Operations

| Instruction | Description | Example |
|-------------|-------------|---------|
| `AND Rd, Rr` | Logical AND | `and r16, r17` |
| `ANDI Rd, K` | AND with immediate | `andi r16, 0x0F` |
| `OR Rd, Rr` | Logical OR | `or r16, r17` |
| `ORI Rd, K` | OR with immediate | `ori r16, 0x80` |
| `EOR Rd, Rr` | Exclusive OR | `eor r16, r17` |
| `EORI Rd, K` | XOR with immediate | `eori r16, 0xFF` |
| `COM Rd` | One's complement | `com r16` |
| `CLR Rd` | Clear register (XOR with self) | `clr r16` |
| `SER Rd` | Set register to 0xFF | `ser r16` |
| `TST Rd` | Test for zero or negative | `tst r16` |
| `SWAP Rd` | Swap nibbles (high/low 4 bits) | `swap r16` |
| `SBI port, bit` | Set bit in I/O register | `sbi 0x18, 3` |
| `CBI port, bit` | Clear bit in I/O register | `cbi 0x18, 3` |

### Shifts & Rotates

| Instruction | Description | Example |
|-------------|-------------|---------|
| `LSL Rd` | Logical shift left | `lsl r16` |
| `LSR Rd` | Logical shift right | `lsr r16` |
| `ROL Rd` | Rotate left through carry | `rol r16` |
| `ROR Rd` | Rotate right through carry | `ror r16` |

### Control Flow

| Instruction | Description | Example |
|-------------|-------------|---------|
| `JMP label` | Unconditional jump | `jmp loop` |
| `RJMP offset` | Relative jump | `rjmp -5` |
| `CALL label` | Call subroutine | `call function` |
| `RCALL offset` | Relative call | `rcall -10` |
| `RET` | Return from subroutine | `ret` |
| `RETI` | Return from interrupt | `reti` |
| `BRNE label` | Branch if not equal (Z=0) | `brne loop` |
| `BREQ label` | Branch if equal (Z=1) | `breq done` |
| `BRCS label` | Branch if carry set (C=1) | `brcs overflow` |
| `BRCC label` | Branch if carry clear (C=0) | `brcc no_carry` |
| `BRGE label` | Branch if greater/equal | `brge positive` |
| `BRLT label` | Branch if less than | `brlt negative` |
| `BRMI label` | Branch if minus (N=1) | `brmi negative` |
| `BRPL label` | Branch if plus (N=0) | `brpl positive` |

### Compare Instructions

| Instruction | Description | Example |
|-------------|-------------|---------|
| `CP Rd, Rr` | Compare registers (Rd - Rr) | `cp r16, r17` |
| `CPI Rd, K` | Compare with immediate | `cpi r16, 42` |
| `CPSE Rd, Rr` | Compare, skip if equal | `cpse r16, r17` |

### Skip Instructions

| Instruction | Description | Example |
|-------------|-------------|---------|
| `SBRS Rd, bit` | Skip if bit in register is set | `sbrs r16, 7` |
| `SBRC Rd, bit` | Skip if bit in register is clear | `sbrc r16, 7` |
| `SBIS port, bit` | Skip if bit in I/O register is set | `sbis 0x16, 3` |
| `SBIC port, bit` | Skip if bit in I/O register is clear | `sbic 0x16, 3` |

### MCU Control

| Instruction | Description | Example |
|-------------|-------------|---------|
| `NOP` | No operation | `nop` |
| `SEI` | Set global interrupt enable | `sei` |
| `CLI` | Clear global interrupt enable | `cli` |

### Status Register (SREG) Flags

The 8-bit status register contains condition flags updated by instructions:

| Bit | Flag | Description |
|-----|------|-------------|
| 7 | **I** | Global interrupt enable |
| 6 | **T** | Bit copy storage |
| 5 | **H** | Half carry (BCD arithmetic) |
| 4 | **S** | Sign bit (N ⊕ V) |
| 3 | **V** | Two's complement overflow |
| 2 | **N** | Negative |
| 1 | **Z** | Zero |
| 0 | **C** | Carry/borrow |

Flags are used for conditional branching and tracking arithmetic results.

### Assembly Syntax Notes

- **Comments**: Use `;` for line comments
- **Labels**: Must end with `:` (e.g., `loop:`)
- **Registers**: Case-insensitive R0-R31 (r16, R16 equivalent)
- **Immediates**: Decimal (42), hex ($2A, 0x2A), binary (0b00101010)
- **Whitespace**: Flexible indentation, spaces/tabs interchangeable

## 🏗️ Architecture Overview

### CPU Components

- **32 General-Purpose Registers** (R0-R31) — 8-bit working registers
- **Program Counter (PC)** — 16-bit, addresses up to 64KB
- **Stack Pointer (SP)** — 16-bit, grows downward from high memory
- **Status Register (SREG)** — 8 condition flags (I, T, H, S, V, N, Z, C)
- **64KB Address Space** — Unified memory for RAM and I/O

### Memory Map

```text
0x0000 - 0x001F    Memory-mapped I/O (optional)
0x0020 - 0xFFFF    Available RAM (stack grows downward from top)
```

## 🧪 Testing

```bash
pytest                                    # Run all tests
pytest --cov=src/tiny8 --cov-report=html  # With coverage
pytest tests/test_arithmetic.py           # Specific test file
```

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Areas for contribution**: New instructions, example programs, documentation, visualizations, performance optimizations.

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/sql-hkr/tiny8/issues)
- **Discussions**: [GitHub Discussions](https://github.com/sql-hkr/tiny8/discussions)
- **Documentation**: [sql-hkr.github.io/tiny8](https://sql-hkr.github.io/tiny8/)

---

**Made with ❤️ for learners, educators, and curious minds**

*Star ⭐ the repo if you find it useful!*
