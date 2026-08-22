"""Train an ultra-compact Diffusion Model on MNIST digit 8 and export Tiny8 AVR assembly.

Uses PyTorch and torchvision.datasets.MNIST to train a compact 8-step reverse diffusion
model generating the digit 8 at native 28x28 resolution, quantizes the parameters, and exports a pure
AVR assembly implementation (`examples/diffusion_mnist8.asm`) that runs directly on the Tiny8 8-bit CPU,
rendering each denoising step into 32x32 VRAM (centered 28x28 canvas).
"""

from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import torchvision
import torchvision.transforms as transforms


class TinyDiffusion8(nn.Module):
    """Ultra-compact 8-step diffusion model for native 28x28 MNIST digit 8."""

    def __init__(self, t_steps: int = 8, hidden_dim: int = 12) -> None:
        super().__init__()
        self.t_steps = t_steps
        self.hidden_dim = hidden_dim

        # Encoder: 784 pixels -> hidden_dim (bias=False since t_embed provides per-step bias)
        self.enc = nn.Linear(784, hidden_dim, bias=False)
        # Timestep embedding: t_steps -> hidden_dim
        self.t_embed = nn.Embedding(t_steps, hidden_dim)
        # Decoder: hidden_dim -> 784 pixels
        self.dec = nn.Linear(hidden_dim, 784)

    def forward(self, x: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
        # h = clamp(ReLU(enc(x) + t_embed(t)), max=127/64) matching AVR 7-bit ReLU range
        h = torch.clamp(torch.relu(self.enc(x) + self.t_embed(t)), max=127.0 / 64.0)
        # Logits prediction of clean x0
        return self.dec(h)


def train_model(
    epochs: int = 15,
    batch_size: int = 256,
    lr: float = 0.01,
    seed: int = 42,
    data_dir: str | Path = "./data",
) -> tuple[TinyDiffusion8, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Load MNIST digit 8 and train TinyDiffusion8 model."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    transform = transforms.Compose(
        [
            transforms.ToTensor(),
        ]
    )
    mnist = torchvision.datasets.MNIST(
        root=str(data_dir), train=True, download=True, transform=transform
    )
    eights = torch.stack([img.view(-1) for img, label in mnist if label == 8])
    target_eights = (eights > 0.25).float()
    print(f"Loaded {len(eights)} digit 8 samples from torchvision MNIST (28x28).")

    t_steps = 8
    betas = torch.linspace(0.1, 0.5, t_steps)
    alphas = 1.0 - betas
    alphas_bar = torch.cumprod(alphas, dim=0)

    model = TinyDiffusion8(t_steps=t_steps, hidden_dim=12)
    opt = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)

    dataset = TensorDataset(target_eights)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, drop_last=False)

    for ep in range(epochs):
        epoch_loss = 0.0
        num_batches = 0
        for (x0,) in loader:
            t = torch.randint(0, t_steps, (x0.size(0),))
            a_bar = alphas_bar[t].unsqueeze(1)
            noise = torch.randn_like(x0)
            xt = torch.sqrt(a_bar) * x0 + torch.sqrt(1.0 - a_bar) * noise
            logits = model(xt, t)
            loss = nn.functional.binary_cross_entropy_with_logits(logits, x0)
            opt.zero_grad()
            loss.backward()
            opt.step()

            # Clamp weights to prevent 16-bit signed MAC overflow on 8-bit AVR CPU
            with torch.no_grad():
                model.enc.weight.clamp_(-0.5, 0.5)
                model.t_embed.weight.clamp_(-0.99, 0.99)

            epoch_loss += loss.item()
            num_batches += 1

        if (ep + 1) % 5 == 0 or ep == epochs - 1:
            avg_loss = epoch_loss / max(1, num_batches)
            print(f"Epoch {ep + 1}/{epochs}, Loss: {avg_loss:.4f}")

    return model, betas, alphas, alphas_bar


def generate_assembly(
    model: TinyDiffusion8,
    betas: torch.Tensor,
    alphas: torch.Tensor,
    alphas_bar: torch.Tensor,
    out_path: Path,
) -> None:
    """Quantize model weights and generate Tiny8 AVR assembly code."""
    w_enc = model.enc.weight.detach().numpy()  # (12, 784)
    t_embed = model.t_embed.weight.detach().numpy()  # (8, 12)
    if model.enc.bias is not None:
        t_embed = t_embed + model.enc.bias.detach().numpy()[None, :]
    w_dec = model.dec.weight.detach().numpy()  # (784, 12)
    b_dec = model.dec.bias.detach().numpy()  # (784,)

    # Fixed-point scale alignment:
    # - img is in [0..255] (~256 = 2^8)
    # - w_enc_int is scaled by scale_enc = 8 (2^3) -> w_enc_int * img has scale 2048 (2^11)
    # - t_embed_int is scaled by scale_t = 128 (2^7) and shifted << 4 in ASM -> scale 2048 (2^11)
    # - After >> 5 in ASM, hidden activations have scale 2048 >> 5 = 64 (2^6)
    # - w_dec_int has scale_dec = 16 (2^4), b_dec_int16 has scale 16 * 64 = 1024 (2^10)
    scale_enc = 8.0
    scale_t = scale_enc * 16.0
    scale_dec = 16.0

    w_enc_int = np.clip(np.round(w_enc * scale_enc), -128, 127).astype(np.int8)
    t_embed_int = np.clip(np.round(t_embed * scale_t), -128, 127).astype(np.int8)
    w_dec_int = np.clip(np.round(w_dec * scale_dec), -128, 127).astype(np.int8)
    b_dec_int16 = np.clip(np.round(b_dec * scale_dec * 64.0), -32768, 32767).astype(
        np.int16
    )

    # Verify 16-bit signed accumulator bounds on uniform mid-gray / noise input (mean ~128)
    mean_acc = np.abs(w_enc_int.astype(np.int32).sum(axis=1) * 128) + 128 * 16
    if mean_acc.max() > 32767:
        print(
            f"Warning: encoder MAC mean accumulator {mean_acc.max()} "
            "may exceed 16-bit signed bounds."
        )

    # Precompute blend weights for reverse steps
    t_steps = 8
    c1_list = []
    c2_list = []
    for s in range(t_steps):
        if s > 0:
            a_bar_prev = alphas_bar[s - 1].item()
            a_bar_cur = alphas_bar[s].item()
            beta = betas[s].item()
            c1 = (np.sqrt(a_bar_prev) * beta) / (1 - a_bar_cur)
            c2 = (np.sqrt(alphas[s].item()) * (1 - a_bar_prev)) / (1 - a_bar_cur)
            c_sum = c1 + c2
            c1_int = int(round(c1 / c_sum * 16))
            c2_int = 16 - c1_int
        else:
            c1_int = 16
            c2_int = 0
        c1_list.append(c1_int)
        c2_list.append(c2_int)

    # Memory Map:
    # 0x0060..0x006B: hidden activations (12 bytes)
    # 0x0070..0x007F: temps (step_t, counters)
    # 0x0200..0x05FF: 32x32 VRAM (1024 bytes)
    # 0x0600..0x090F: img buffer (784 bytes, 28x28)
    # 0x0A00..0x2EBF: w_enc (12 x 784 = 9408 bytes)
    # 0x2EC0..0x2F1F: t_embed (8 x 12 = 96 bytes)
    # 0x2F20..0x53DF: w_dec (784 x 12 = 9408 bytes)
    # 0x53E0..0x59FF: b_dec (784 x 2 = 1568 bytes)
    # 0x5D20..0x5D2F: blend coeffs (16 bytes)

    lines = [
        "; ==================================================================",
        "; TINY8 NATIVE 28x28 DIFFUSION MODEL FOR MNIST DIGIT 8",
        "; Trained on torchvision.datasets.MNIST (8 reverse steps)",
        "; Direct 32x32 Heatmap VRAM: 0x0200..0x05FF (1024 bytes)",
        "; Progressive Denoising Trajectory: t = 8 -> 7 -> ... -> 0",
        "; ==================================================================",
        "",
        "; Memory Map in RAM (0x0000..0xFFFF, 64KB total):",
        ";   0x0060..0x006B: hidden (12 bytes, activations 0..127)",
        ";   0x0070..0x007F: temps (step_t, counters)",
        ";   0x0200..0x05FF: 32x32 VRAM (1024 bytes heatmap monitor)",
        ";   0x0600..0x090F: img (784 bytes, 28x28 pixel intensity 0..255)",
        ";   0x0A00..0x2EBF: w_enc (12 x 784 = 9408 bytes, signed int8)",
        ";   0x2EC0..0x2F1F: t_embed (8 x 12 = 96 bytes, signed int8)",
        ";   0x2F20..0x53DF: w_dec (784 x 12 = 9408 bytes, signed int8)",
        ";   0x53E0..0x59FF: b_dec (784 x 2 = 1568 bytes, signed int16)",
        ";   0x5D20..0x5D2F: c1, c2 blend coefficients (8 + 8 bytes)",
        "",
        ".data_init:",
    ]

    # Emit weight tables initialization
    def emit_array_init(base_addr: int, arr: np.ndarray, label: str):
        lines.append(f"; Initialize {label} at 0x{base_addr:04X} ({len(arr)} bytes)")
        lines.append(f"    LDI R30, {base_addr & 0xFF}")
        lines.append(f"    LDI R31, {base_addr >> 8}")
        for i, v in enumerate(arr):
            lines.append(f"    LDI R16, {int(v) & 0xFF}")
            lines.append("    ST R30, R16")
            if i < len(arr) - 1:
                lines.append("    ADIW R30, 1")
        lines.append("    LDI R31, 0")
        lines.append("")

    # Flattened arrays
    emit_array_init(0x0A00, w_enc_int.flatten(), "w_enc")
    emit_array_init(0x2EC0, t_embed_int.flatten(), "t_embed")
    emit_array_init(0x2F20, w_dec_int.flatten(), "w_dec")

    # b_dec as 16-bit little-endian
    b_dec_bytes = []
    for b in b_dec_int16:
        ub = int(b) & 0xFFFF
        b_dec_bytes.append(ub & 0xFF)
        b_dec_bytes.append((ub >> 8) & 0xFF)
    emit_array_init(0x53E0, np.array(b_dec_bytes, dtype=np.uint8), "b_dec")

    # Blend coefficients table at 0x5D20
    lines.append("; Blend coefficients (c1: 8 bytes, c2: 8 bytes at 0x5D20)")
    lines.append("    LDI R30, 0x20")
    lines.append("    LDI R31, 0x5D")
    for c in c1_list + c2_list:
        lines.append(f"    LDI R16, {c}")
        lines.append("    ST R30, R16")
        lines.append("    ADIW R30, 1")
    lines.append("    LDI R31, 0")
    lines.append("")

    # Main control flow
    lines.extend(
        [
            "main:",
            "    ; Generate initial pseudo-Gaussian noise (step 8) into img buffer (0x0600)",
            "    ; 784 bytes = 4 outer * 196 inner, using 16-bit Galois LFSR + 2-byte average",
            "    LDI R26, 0x00      ; X = &img[0] (0x0600)",
            "    LDI R27, 0x06",
            "    LDI R24, 0xE1      ; 16-bit LFSR seed low byte (0xACE1)",
            "    LDI R25, 0xAC      ; 16-bit LFSR seed high byte",
            "    LDI R18, 0xB4      ; LFSR polynomial tap mask",
            "    LDI R22, 4",
            "gen_noise_outer:",
            "    LDI R23, 196",
            "gen_noise_inner:",
            "    LSR R25",
            "    ROR R24",
            "    BRCC no_xor",
            "    EOR R25, R18",
            "no_xor:",
            "    MOV R20, R24",
            "    ADD R20, R25",
            "    ROR R20            ; average two uniform bytes -> bell-shaped 0..255",
            "    ST X, R20",
            "    ADIW R26, 1",
            "    DEC R23",
            "    BRNE gen_noise_inner",
            "    DEC R22",
            "    BRNE gen_noise_outer",
            "",
            "    ; Render Initial Step 8 (Pure Noise)",
            "    LDI R16, 8",
            "    STS 0x0070, R16    ; cur_step = 8",
            "    RCALL render_vram",
            "",
            "    ; Denoising Loop: t = 7 down to 0",
            "    LDI R19, 7         ; R19 = current step t",
            "diffusion_step_loop:",
            "    STS 0x0070, R19    ; save step t",
            "",
            "    ; ----------------------------------------------------------------",
            "    ; Stage 1: Encoder - Compute 12 Hidden Activations",
            "    ; h_k = ReLU( ((t_embed[t, k] << 4) + sum(w_enc[k, j] * img[j])) >> 5 )",
            "    ; ----------------------------------------------------------------",
            "    LDI R22, 0         ; k = 0",
            "node_loop:",
            "    ; Load t_embed[t, k] from 0x2EC0 + t * 12 + k",
            "    LDS R16, 0x0070    ; R16 = t",
            "    LDI R17, 12",
            "    MUL R16, R17       ; R1:R0 = t * 12",
            "    ADD R0, R22        ; + k",
            "    LDI R30, 0xC0",
            "    LDI R31, 0x2E",
            "    ADD R30, R0",
            "    ADC R31, R1",
            "    LD R24, Z          ; R24 = t_embed[t, k] (signed 8-bit)",
            "    LDI R25, 0",
            "    SBRC R24, 7",
            "    LDI R25, 255       ; sign extend",
            "",
            "    ; Shift left 4: R25:R24 << 4",
            "    LDI R18, 4",
            "t_shl_loop:",
            "    LSL R24",
            "    ROL R25",
            "    DEC R18",
            "    BRNE t_shl_loop",
            "",
            "    ; Base address for w_enc[k]: 0x0A00 + k * 784",
            "    ; 784 = 256 * 3 + 16 (0x0310)",
            "    LDI R16, 16",
            "    MUL R22, R16       ; R1:R0 = k * 16",
            "    MOV R20, R0",
            "    MOV R21, R1",
            "    LDI R16, 3",
            "    MUL R22, R16       ; R1:R0 = k * 3",
            "    ADD R21, R0        ; R21:R20 = k * 784",
            "    LDI R30, 0x00",
            "    LDI R31, 0x0A",
            "    ADD R30, R20",
            "    ADC R31, R21       ; Z = &w_enc[k, 0]",
            "",
            "    ; X = &img[0] (0x0600)",
            "    LDI R26, 0x00",
            "    LDI R27, 0x06",
            "",
            "    ; 784 MAC operations: 28 outer * 28 inner",
            "    LDI R18, 28",
            "enc_mac_outer:",
            "    LDI R19, 28",
            "enc_mac_inner:",
            "    LD R16, Z          ; R16 = w_enc[k, j] (signed)",
            "    LD R17, X          ; R17 = img[j] (unsigned)",
            "    MULSU R16, R17     ; R1:R0 = w_enc * img (signed 16-bit)",
            "    ADD R24, R0",
            "    ADC R25, R1",
            "    ADIW R30, 1",
            "    ADIW R26, 1",
            "    DEC R19",
            "    BRNE enc_mac_inner",
            "    DEC R18",
            "    BRNE enc_mac_outer",
            "",
            "    ; Shift right 5 arithmetic: (R25:R24) >> 5",
            "    LDI R18, 5",
            "enc_shr_loop:",
            "    ASR R25",
            "    ROR R24",
            "    DEC R18",
            "    BRNE enc_shr_loop",
            "",
            "    ; ReLU: if sum < 0 then 0, clamp max 127",
            "    SBRC R25, 7",
            "    RJMP relu_zero",
            "    CPI R25, 0",
            "    BRNE relu_clamp_max",
            "    CPI R24, 127",
            "    BRCS relu_ok",
            "relu_clamp_max:",
            "    LDI R24, 127",
            "    RJMP relu_ok",
            "relu_zero:",
            "    LDI R24, 0",
            "relu_ok:",
            "    ; Store into hidden[k] (at 0x0060 + k)",
            "    LDI R30, 0x60",
            "    LDI R31, 0x00",
            "    ADD R30, R22",
            "    ST R30, R24",
            "",
            "    INC R22            ; k++",
            "    CPI R22, 12",
            "    BRNE node_loop",
            "",
            "    ; Cache hidden activations into R2..R13 for high-throughput unrolled decoding",
            "    LDS R2, 0x0060",
            "    LDS R3, 0x0061",
            "    LDS R4, 0x0062",
            "    LDS R5, 0x0063",
            "    LDS R6, 0x0064",
            "    LDS R7, 0x0065",
            "    LDS R8, 0x0066",
            "    LDS R9, 0x0067",
            "    LDS R10, 0x0068",
            "    LDS R11, 0x0069",
            "    LDS R12, 0x006A",
            "    LDS R13, 0x006B",
            "",
            "    ; ----------------------------------------------------------------",
            "    ; Stage 2: Decoder & Blend - Reconstruct and Update img (784 pixels)",
            "    ; Sequential pointers: Y=&b_dec, Z=&w_dec, X=&img",
            "    ; ----------------------------------------------------------------",
            "    LDS R19, 0x0070    ; restore t",
            "    ; Load c1 from 0x5D20 + t, c2 from 0x5D28 + t",
            "    LDI R30, 0x20",
            "    LDI R31, 0x5D",
            "    ADD R30, R19",
            "    LD R14, Z          ; R14 = c1",
            "    LDI R30, 0x28",
            "    LDI R31, 0x5D",
            "    ADD R30, R19",
            "    LD R15, Z          ; R15 = c2",
            "",
            "    ; Pointers for sequential pass:",
            "    ; Y = &b_dec[0] (0x53E0)",
            "    ; Z = &w_dec[0, 0] (0x2F20)",
            "    ; X = &img[0] (0x0600)",
            "    LDI R28, 0xE0",
            "    LDI R29, 0x53",
            "    LDI R30, 0x20",
            "    LDI R31, 0x2F",
            "    LDI R26, 0x00",
            "    LDI R27, 0x06",
            "",
            "    ; 784 pixels: 28 outer * 28 inner",
            "    LDI R22, 28        ; outer loop counter",
            "pixel_dec_outer:",
            "    LDI R23, 28        ; inner loop counter",
            "pixel_dec_inner:",
            "    ; Load 16-bit b_dec from Y",
            "    LD R24, Y",
            "    ADIW R28, 1",
            "    LD R25, Y",
            "    ADIW R28, 1",
            "",
            "    ; Unrolled 12-term MAC directly against cached hidden registers R2..R13",
            "    LD R16, Z",
            "    ADIW R30, 1",
            "    MULS R16, R2",
            "    ADD R24, R0",
            "    ADC R25, R1",
            "",
            "    LD R16, Z",
            "    ADIW R30, 1",
            "    MULS R16, R3",
            "    ADD R24, R0",
            "    ADC R25, R1",
            "",
            "    LD R16, Z",
            "    ADIW R30, 1",
            "    MULS R16, R4",
            "    ADD R24, R0",
            "    ADC R25, R1",
            "",
            "    LD R16, Z",
            "    ADIW R30, 1",
            "    MULS R16, R5",
            "    ADD R24, R0",
            "    ADC R25, R1",
            "",
            "    LD R16, Z",
            "    ADIW R30, 1",
            "    MULS R16, R6",
            "    ADD R24, R0",
            "    ADC R25, R1",
            "",
            "    LD R16, Z",
            "    ADIW R30, 1",
            "    MULS R16, R7",
            "    ADD R24, R0",
            "    ADC R25, R1",
            "",
            "    LD R16, Z",
            "    ADIW R30, 1",
            "    MULS R16, R8",
            "    ADD R24, R0",
            "    ADC R25, R1",
            "",
            "    LD R16, Z",
            "    ADIW R30, 1",
            "    MULS R16, R9",
            "    ADD R24, R0",
            "    ADC R25, R1",
            "",
            "    LD R16, Z",
            "    ADIW R30, 1",
            "    MULS R16, R10",
            "    ADD R24, R0",
            "    ADC R25, R1",
            "",
            "    LD R16, Z",
            "    ADIW R30, 1",
            "    MULS R16, R11",
            "    ADD R24, R0",
            "    ADC R25, R1",
            "",
            "    LD R16, Z",
            "    ADIW R30, 1",
            "    MULS R16, R12",
            "    ADD R24, R0",
            "    ADC R25, R1",
            "",
            "    LD R16, Z",
            "    ADIW R30, 1",
            "    MULS R16, R13",
            "    ADD R24, R0",
            "    ADC R25, R1",
            "",
            "    ; Piecewise Linear Sigmoid: R25:R24 = (R25:R24) >> 2 + 128",
            "    ASR R25",
            "    ROR R24",
            "    ASR R25",
            "    ROR R24",
            "    LDI R16, 128",
            "    ADD R24, R16",
            "    LDI R16, 0",
            "    ADC R25, R16",
            "",
            "    ; Clamp to [0, 255] in R16",
            "    SBRS R25, 7        ; if negative sign bit set -> clamp to 0",
            "    RJMP check_pos_clamp",
            "    LDI R16, 0",
            "    RJMP clamp_done",
            "check_pos_clamp:",
            "    CPI R25, 0",
            "    BREQ clamp_ok",
            "    LDI R16, 255       ; clamp high",
            "    RJMP clamp_done",
            "clamp_ok:",
            "    MOV R16, R24       ; x0_hat[i] is in R16",
            "clamp_done:",
            "",
            "    ; Blend: res = (c1 * R16 + c2 * img[i]) / 16",
            "    MUL R16, R14       ; c1 * x0_hat",
            "    MOV R20, R0",
            "    MOV R21, R1",
            "",
            "    LD R16, X          ; R16 = old img[i]",
            "    MUL R16, R15       ; c2 * img[i]",
            "    ADD R20, R0",
            "    ADC R21, R1",
            "",
            "    ; Divide by 16: shift right 4",
            "    LSR R21",
            "    ROR R20",
            "    LSR R21",
            "    ROR R20",
            "    LSR R21",
            "    ROR R20",
            "    LSR R21",
            "    ROR R20",
            "",
            "    ; Store into img[i] and advance X",
            "    ST X, R20",
            "    ADIW R26, 1",
            "",
            "    DEC R23",
            "    BRNE pixel_dec_inner",
            "    DEC R22",
            "    BRNE pixel_dec_outer",
            "",
            "    ; Render current step to VRAM",
            "    RCALL render_vram",
            "",
            "    LDS R19, 0x0070    ; restore step t",
            "    DEC R19",
            "    CPI R19, 255       ; checks underflow below 0",
            "    BREQ diffusion_done",
            "    RJMP diffusion_step_loop",
            "",
            "diffusion_done:",
            "    ; Infinite halt display loop",
            "halt_loop:",
            "    RJMP halt_loop",
            "",
            "; ==================================================================",
            "; SUBROUTINE: render_vram",
            "; 1:1 Direct copy of 28x28 img (0x0600) into 32x32 VRAM (0x0200)",
            "; Center region: rows 2..29, cols 2..29",
            "; Also writes Header row 0 and Footer row 31",
            "; ==================================================================",
            "render_vram:",
            "    ; Clear Row 0",
            "    LDI R30, 0x00",
            "    LDI R31, 0x02",
            "    LDI R16, 32        ; ' '",
            "    LDI R18, 32",
            "clr_hdr_loop:",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    DEC R18",
            "    BRNE clr_hdr_loop",
            "",
            "    ; Write Header Text at 0x0201: 'DIFFUSION MNIST:8'",
            "    LDI R30, 0x01",
            "    LDI R31, 0x02",
            "    LDI R16, 68 ; 'D'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 73 ; 'I'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 70 ; 'F'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 70 ; 'F'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 85 ; 'U'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 83 ; 'S'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 73 ; 'I'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 79 ; 'O'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 78 ; 'N'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 32 ; ' '",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 77 ; 'M'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 78 ; 'N'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 73 ; 'I'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 83 ; 'S'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 84 ; 'T'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 58 ; ':'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 56 ; '8'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "",
            "    ; Step indicator: 'STEP:[' t ']' at 0x0216",
            "    LDI R30, 0x16",
            "    LDI R31, 0x02",
            "    LDI R16, 83 ; 'S'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 84 ; 'T'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 69 ; 'E'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 80 ; 'P'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 58 ; ':'",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 91 ; '['",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDS R16, 0x0070    ; step t",
            "    LDI R17, 48        ; '0'",
            "    ADD R16, R17       ; ASCII digit",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    LDI R16, 93 ; ']'",
            "    ST R30, R16",
            "",
            "    ; Direct 1:1 copy of 28x28 img into centered 28x28 VRAM (rows 2..29, cols 2..29)",
            "    ; X = &img[0] (0x0600)",
            "    LDI R26, 0x00",
            "    LDI R27, 0x06",
            "    LDI R22, 0         ; r = 0..27",
            "render_r_loop:",
            "    ; VRAM row = 2 + r, col = 2",
            "    ; VRAM row start: 0x0200 + (r + 2) * 32 + 2",
            "    LDI R16, 2",
            "    ADD R16, R22       ; R16 = r + 2",
            "    LDI R17, 32",
            "    MUL R16, R17       ; R1:R0 = (r + 2) * 32",
            "    LDI R30, 0x02      ; col offset 2",
            "    LDI R31, 0x02      ; base 0x0200",
            "    ADD R30, R0",
            "    ADC R31, R1        ; Z = &VRAM[r + 2, 2]",
            "",
            "    LDI R23, 28        ; 28 columns",
            "render_c_loop:",
            "    LD R16, X",
            "    ST R30, R16",
            "    ADIW R26, 1",
            "    ADIW R30, 1",
            "    DEC R23",
            "    BRNE render_c_loop",
            "",
            "    INC R22",
            "    CPI R22, 28",
            "    BRNE render_r_loop",
            "",
            "    ; Clear Footer row 31 (0x05E0..0x05FF)",
            "    LDI R30, 0xE0",
            "    LDI R31, 0x05",
            "    LDI R16, 32",
            "    LDI R18, 32",
            "clr_ftr_loop:",
            "    ST R30, R16",
            "    ADIW R30, 1",
            "    DEC R18",
            "    BRNE clr_ftr_loop",
            "",
            "    RET",
            "",
        ]
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    print(f"Exported Tiny8 AVR assembly model to {out_path} ({len(lines)} lines)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train native 28x28 Tiny8 diffusion model on MNIST digit 8 and export AVR assembly."
    )
    parser.add_argument(
        "--epochs",
        "-e",
        type=int,
        default=15,
        help="Number of full dataset training epochs (default: 15)",
    )
    parser.add_argument(
        "--batch-size",
        "-b",
        type=int,
        default=256,
        help="Mini-batch size (default: 256)",
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=0.01,
        help="Learning rate for Adam optimizer (default: 0.01)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--data-dir",
        default="./data",
        help="Directory for torchvision MNIST dataset (default: ./data)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="examples/diffusion_mnist8.asm",
        help="Output AVR assembly file path (default: examples/diffusion_mnist8.asm)",
    )
    args = parser.parse_args()

    print("--- Training Native 28x28 Tiny8 Diffusion Model on MNIST Digit 8 ---")
    model, betas, alphas, alphas_bar = train_model(
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        seed=args.seed,
        data_dir=args.data_dir,
    )

    asm_path = Path(args.output)
    generate_assembly(model, betas, alphas, alphas_bar, asm_path)
    print(f"Done! Ready to run on Tiny8 CPU via 'uv run tiny8 {asm_path}'")


if __name__ == "__main__":
    main()
