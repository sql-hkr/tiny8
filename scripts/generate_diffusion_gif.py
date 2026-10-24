"""Generate high-resolution animated GIF of diffusion_mnist8.asm in Tiny8 TUI.

Sequential storytelling format with clean upper-right status label (transparent black bg with white text):
1. Weight Initialization & LFSR Noise Generation in HEX mode (showing low-level CPU memory manipulation)
2. Reverse Diffusion Denoising Trajectory (STEP 8 -> STEP 0) in PIXEL mode (showing AI digit 8 convergence)
"""

import argparse
import asyncio
from dataclasses import dataclass
import io
from pathlib import Path
import shutil
import subprocess
from typing import Any

from PIL import Image, ImageDraw, ImageFont
import resvg_py

from tiny8 import CPU, assemble
from tiny8.tui import PLAYBACK_RATES, MemoryWidget, Tiny8App


@dataclass
class FrameSpec:
    target_step: int
    show_hex: bool
    mem_start: int
    duration_ms: int
    label: str


# Comprehensive, easy-to-follow diffusion process checkpoints
DEFAULT_FRAME_SPECS = [
    # Phase 1: Boot & Weight Initialization in HEX
    FrameSpec(1, True, 0x0A00, 800, "CPU Boot | Memory Init (HEX)"),
    FrameSpec(10000, True, 0x0A00, 200, "Encoder weights (0x0A00) (HEX)"),
    FrameSpec(40000, True, 0x2F20, 200, "Decoder weights (0x2F20) (HEX)"),
    FrameSpec(58000, True, 0x53E0, 250, "Decoder biases (0x53E0) (HEX)"),
    # Phase 2: 16-bit PRNG LFSR Noise Generation in HEX (0x0200)
    FrameSpec(65000, True, 0x0200, 250, "16-bit LFSR noise gen (HEX)"),
    FrameSpec(72000, True, 0x0200, 250, "Loading noise into VRAM (HEX)"),
    FrameSpec(75149, True, 0x0200, 700, "STEP 8: Initial noise (HEX)"),
    # Phase 3: Mode Toggle to PIXEL Mode (STEP 8)
    FrameSpec(75149, False, 0x0200, 500, "STEP 8: Initial noise (PIXEL)"),
    # Phase 4: Reverse Diffusion Trajectory (STEP 8 -> 0) in PIXEL mode
    FrameSpec(160000, False, 0x0200, 160, "Denoising step 8 -> 7"),
    FrameSpec(241412, False, 0x0200, 200, "STEP 7: Coarse centroid"),
    FrameSpec(325000, False, 0x0200, 160, "Denoising step 7 -> 6"),
    FrameSpec(407675, False, 0x0200, 200, "STEP 6: Vertical lobes forming"),
    FrameSpec(490000, False, 0x0200, 160, "Denoising step 6 -> 5"),
    FrameSpec(573938, False, 0x0200, 220, "STEP 5: Dual loops separating"),
    FrameSpec(655000, False, 0x0200, 160, "Denoising step 5 -> 4"),
    FrameSpec(740205, False, 0x0200, 220, "STEP 4: Digit 8 shape clear"),
    FrameSpec(820000, False, 0x0200, 160, "Denoising step 4 -> 3"),
    FrameSpec(906436, False, 0x0200, 220, "STEP 3: Background cleared"),
    FrameSpec(990000, False, 0x0200, 160, "Denoising step 3 -> 2"),
    FrameSpec(1072668, False, 0x0200, 220, "STEP 2: Stroke refined"),
    FrameSpec(1155000, False, 0x0200, 160, "Denoising step 2 -> 1"),
    FrameSpec(1238899, False, 0x0200, 250, "STEP 1: Final reverse step"),
    FrameSpec(1320000, False, 0x0200, 180, "Final pixel reconstruction"),
    FrameSpec(1400400, False, 0x0200, 400, "STEP 0: Synthesized digit 8"),
    # Phase 5: Synthesis Convergence
    FrameSpec(1405127, False, 0x0200, 2200, "Convergence complete (RJMP halt)"),
]

DEFAULT_FONT = 'Menlo, Monaco, "SF Mono", "Cascadia Code", "JetBrains Mono", monospace'


def _draw_top_right_label(
    img: Image.Image,
    label: str,
) -> Image.Image:
    """Render a compact, transparent black pill with white text in the upper-right corner."""
    if not label:
        return img

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ov = ImageDraw.Draw(overlay)

    font_candidates = [
        "/System/Library/Fonts/SFNSMono.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Monaco.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    font = None
    for fp in font_candidates:
        if Path(fp).exists():
            try:
                font = ImageFont.truetype(fp, 36)
                break
            except Exception:
                continue

    if font is None:
        font = ImageFont.load_default()

    bb = ov.textbbox((0, 0), label, font=font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]

    pad_x = 24
    pad_y = 12
    badge_w = tw + pad_x * 2
    badge_h = th + pad_y * 2

    margin_right = 35
    margin_top = 8

    x1 = img.width - margin_right
    x0 = x1 - badge_w
    y0 = margin_top
    y1 = y0 + badge_h

    # Transparent black background with subtle translucent border
    ov.rounded_rectangle(
        [x0, y0, x1, y1],
        radius=12,
        fill=(0, 0, 0, 205),
        outline=(255, 255, 255, 75),
        width=2,
    )

    # Crisp white text
    ov.text((x0 + pad_x, y0 + pad_y - 2), label, fill=(255, 255, 255, 255), font=font)

    return Image.alpha_composite(img, overlay)


async def _render_snapshot_frame(
    base_cpu: CPU,
    snap: dict[str, Any],
    color_mode: str,
    spec: FrameSpec,
    playing: bool,
    play_direction: int,
    rate_idx: int,
    term_width: int,
    term_height: int,
    font: str = DEFAULT_FONT,
) -> bytes:
    """Render a single TUI frame with upper-right status label from a checkpoint snapshot."""
    cpu = CPU()
    cpu.program = base_cpu.program
    cpu.labels = base_cpu.labels
    cpu.pc_to_line = base_cpu.pc_to_line
    cpu.source_lines = base_cpu.source_lines
    cpu._predecoded = base_cpu._predecoded
    cpu.regs = list(snap["regs"])
    cpu.sreg = snap["sreg"]
    cpu.sp = snap["sp"]
    cpu.pc = snap["pc"]
    cpu.step_count = snap["step"]
    cpu.running = True
    cpu.mem.ram = bytearray(snap["ram"])
    cpu.mem.nonzero_ram = dict(snap["nonzero_ram"])

    trace_entry = {
        "step": snap["step"],
        "pc": snap["pc"],
        "instr": snap["instr"],
        "regs": list(snap["regs"]),
        "mem": dict(snap["nonzero_ram"]),
        "sreg": snap["sreg"],
        "sp": snap["sp"],
        "source_line": snap["source_line"],
    }
    cpu.step_trace = [trace_entry]

    app = Tiny8App(
        cpu=cpu,
        file_path="examples/diffusion_mnist8.asm",
        precompute_cache=False,
    )
    app.traces = [trace_entry]
    app.num_traces = 1
    app.current_idx = 0
    app.mem_start = spec.mem_start
    app.speed_ms = 30
    app.playback_rate_idx = rate_idx
    app.batch_size = 5000
    app.color_mode = color_mode
    app.show_hex = spec.show_hex
    app.playing = playing
    app.play_direction = play_direction

    async with app.run_test(size=(term_width, term_height)) as pilot:
        app.color_mode = color_mode
        app.show_hex = spec.show_hex
        app.playing = playing
        app.play_direction = play_direction
        app.mem_start = spec.mem_start
        try:
            mem_w = app.query_one("#mem-view", MemoryWidget)
            mem_w.start_addr = spec.mem_start
            mem_w.show_hex = spec.show_hex
            mem_w.color_mode = color_mode
        except Exception:
            pass

        app.update_views()
        await pilot.pause()
        svg_content = app.export_screenshot(title="Tiny8")

    # Replace font-family with Kitty-style monospace terminal font
    if font:
        svg_content = svg_content.replace(
            "font-family: Fira Code, monospace;",
            f"font-family: {font};",
        )

    png_bytes = resvg_py.svg_to_bytes(svg_content)
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    bg = Image.new("RGB", img.size, (0, 0, 0))
    bg.paste(img, mask=img.split()[3])

    # Overlay simple top-right label (transparent black bg with white text)
    labeled_img = _draw_top_right_label(
        bg.convert("RGBA"),
        label=spec.label,
    )

    out_buf = io.BytesIO()
    labeled_img.convert("RGB").save(out_buf, format="PNG")
    return out_buf.getvalue()


async def generate_gif(
    palette: str = "viridis",
    specs: list[FrameSpec] | None = None,
    with_reverse: bool = True,
    output_path: str = "docs/_static/diffusion_mnist8.gif",
    term_width: int = 160,
    term_height: int = 42,
    font: str = DEFAULT_FONT,
    keep_frames: bool = False,
) -> None:
    """Simulate Tiny8 execution, render storytelling HEX -> PIXEL frames with top-right label, and compile into GIF."""
    color_mode = "grayscale" if palette in ("grayscale", "gray", "grey") else "viridis"
    frame_specs = specs or DEFAULT_FRAME_SPECS

    print(
        f"Generating diffusion GIF: palette={color_mode}, frames={len(frame_specs)}, "
        f"with_reverse={with_reverse}, font={font}, size={term_width}x{term_height} -> {output_path}"
    )

    temp_dir = Path("scratch") / f"gif_frames_{color_mode}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    asm_path = Path("examples/diffusion_mnist8.asm")
    asm = assemble(asm_path.read_text(encoding="utf-8"))
    halt_pc = asm.labels["halt_loop"]

    base_cpu = CPU()
    base_cpu.load_program(asm)
    base_cpu.running = True

    rate_5000_idx = PLAYBACK_RATES.index(5000) if 5000 in PLAYBACK_RATES else 6

    # 1. Forward simulation: capture checkpoints for all required target steps
    unique_steps = sorted(set(spec.target_step for spec in frame_specs))
    print(f"Simulating CPU execution checkpoints ({len(unique_steps)} unique steps)...")
    step_to_snapshot: dict[int, dict[str, Any]] = {}
    for target_step in unique_steps:
        while (
            base_cpu.running
            and base_cpu.step_count < target_step
            and base_cpu.pc != halt_pc
        ):
            base_cpu.step(record_trace=False)

        pre_pc = base_cpu.pc
        instr_tuple = (
            base_cpu.program[pre_pc]
            if 0 <= pre_pc < len(base_cpu.program)
            else ("NOP", ())
        )
        instr_name = instr_tuple[0]
        instr_ops = instr_tuple[1] if len(instr_tuple) > 1 else ()

        if base_cpu._predecoded and pre_pc < len(base_cpu._predecoded):
            instr_text = base_cpu._predecoded[pre_pc][2]
        else:
            instr_text = f"{instr_name} {instr_ops}"

        step_to_snapshot[target_step] = {
            "step": max(1, base_cpu.step_count),
            "pc": pre_pc,
            "instr": instr_text,
            "regs": list(base_cpu.regs),
            "ram": bytes(base_cpu.mem.ram),
            "nonzero_ram": dict(base_cpu.mem.nonzero_ram),
            "sreg": base_cpu.sreg,
            "sp": base_cpu.sp,
            "source_line": asm.pc_to_line.get(pre_pc, -1),
        }

    frame_paths: list[Path] = []
    durations_ms: list[int] = []
    frame_counter = 0

    # 2. Render Storytelling Frames (HEX weights/noise -> PIXEL denoising)
    print("Rendering Diffusion Inference Frames with top-right label...")
    for i, spec in enumerate(frame_specs):
        snap = step_to_snapshot[spec.target_step]
        is_first = i == 0
        playing = not is_first
        play_dir = 1

        frame_bytes = await _render_snapshot_frame(
            base_cpu=base_cpu,
            snap=snap,
            color_mode=color_mode,
            spec=spec,
            playing=playing,
            play_direction=play_dir,
            rate_idx=rate_5000_idx,
            term_width=term_width,
            term_height=term_height,
            font=font,
        )

        png_path = temp_dir / f"frame_{frame_counter:03d}.png"
        png_path.write_bytes(frame_bytes)
        frame_paths.append(png_path)
        frame_counter += 1
        durations_ms.append(spec.duration_ms)

        mode_str = "HEX" if spec.show_hex else "PIXEL"
        print(f"  [{i + 1:2d}/{len(frame_specs)}] step {snap['step']:,} [{mode_str} @ 0x{spec.mem_start:04X}]: {spec.label}")

    # 3. Optional Reverse Phase (back down to STEP 8 initial noise in PIXEL mode)
    if with_reverse:
        print("Rendering Reverse Phase back down to STEP 8 PIXEL noise...")
        pixel_start_idx = -1
        for idx, s in enumerate(frame_specs):
            if s.target_step == 75149 and not s.show_hex:
                pixel_start_idx = idx
                break

        if pixel_start_idx >= 0:
            rev_specs = frame_specs[len(frame_specs) - 2 : pixel_start_idx - 1 : -1]
        else:
            rev_specs = list(reversed(frame_specs))

        for j, spec in enumerate(rev_specs):
            snap = step_to_snapshot[spec.target_step]
            is_last = j == len(rev_specs) - 1
            frame_bytes = await _render_snapshot_frame(
                base_cpu=base_cpu,
                snap=snap,
                color_mode="grayscale",
                spec=spec,
                playing=True,
                play_direction=-1,
                rate_idx=rate_5000_idx,
                term_width=term_width,
                term_height=term_height,
                font=font,
            )
            png_path = temp_dir / f"frame_{frame_counter:03d}.png"
            png_path.write_bytes(frame_bytes)
            frame_paths.append(png_path)
            frame_counter += 1
            durations_ms.append(spec.duration_ms if is_last else 160)
            print(f"  [rev {j + 1:2d}/{len(rev_specs)}] step {snap['step']:,} [PIXEL @ 0x{spec.mem_start:04X}]: {spec.label}")

    concat_txt = temp_dir / "input.txt"
    with open(concat_txt, "w", encoding="utf-8") as f:
        for p, dur_ms in zip(frame_paths, durations_ms):
            f.write(f"file '{p.name}'\n")
            f.write(f"duration {dur_ms / 1000.0:.3f}\n")
        f.write(f"file '{frame_paths[-1].name}'\n")

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    if shutil.which("ffmpeg"):
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_txt.resolve()),
            "-vf",
            "scale=1280:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=256:reserve_transparent=0[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3",
            "-loop",
            "0",
            str(out_file.resolve()),
        ]
        subprocess.run(cmd, check=True)
    else:
        # Fallback to Pillow
        images = []
        for p in frame_paths:
            im = Image.open(p)
            w, h = im.size
            new_h = int(h * 1280 / w)
            im_resized = im.resize((1280, new_h), Image.Resampling.LANCZOS)
            images.append(im_resized)
        images[0].save(
            out_file,
            save_all=True,
            append_images=images[1:],
            duration=durations_ms,
            loop=0,
            optimize=True,
        )

    print(f"Done! GIF saved to {out_file} ({out_file.stat().st_size:,} bytes)")

    if not keep_frames:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate animated GIF of diffusion_mnist8.asm in Tiny8 TUI with upper-right status label."
    )
    parser.add_argument(
        "--palette",
        "-p",
        choices=["grayscale", "gray", "grey", "viridis"],
        default="viridis",
        help="Color palette for memory heatmap (default: viridis)",
    )
    parser.add_argument(
        "--font",
        "-f",
        default=DEFAULT_FONT,
        help="Font family stack for TUI terminal rendering (default: Menlo / SF Mono / Kitty font)",
    )
    parser.add_argument(
        "--no-reverse",
        action="store_true",
        help="Disable reverse playback phase (enabled by default down to STEP 8 initial noise)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="docs/_static/diffusion_mnist8.gif",
        help="Destination path for output GIF (default: docs/_static/diffusion_mnist8.gif)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=160,
        help="Terminal width in columns (default: 160)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=42,
        help="Terminal height in lines (default: 42)",
    )

    args = parser.parse_args()

    asyncio.run(
        generate_gif(
            palette=args.palette,
            with_reverse=not args.no_reverse,
            output_path=args.output,
            term_width=args.width,
            term_height=args.height,
            font=args.font,
        )
    )


if __name__ == "__main__":
    main()
