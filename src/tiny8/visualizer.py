"""Visualization helpers using Matplotlib to plot register/memory changes.

This module provides a simple Visualizer class that can create an animated
visualization of the CPU step trace showing SREG bits, registers and a
memory range.
"""

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import animation


class Visualizer:
    def __init__(self, cpu):
        self.cpu = cpu

    def animate_execution(
        self,
        mem_addr_start: int = 0x60,
        mem_addr_end: int = 0x7F,
        filename: str | None = None,
        interval: int = 200,
        fps: int = 30,
        fontsize=9,
        cmap="inferno",
        plot_every: int = 1,
    ):
        """Animate SREG bits, registers (R0..R31), and a memory range as three stacked subplots.

        Args:
            mem_addr_start: Start memory address for memory subplot.
            mem_addr_end: End memory address for memory subplot.
            filename: Optional output filename for saving animation.
            interval: Milliseconds between frames.
            fps: Frames per second for saving output.
            fontsize: Font size for labels and ticks.
            cmap: Matplotlib colormap name for the heatmaps.
            plot_every: Plot every N steps (downsampling).
        """
        num_steps = len(self.cpu.step_trace)

        flag_names = ["I", "T", "H", "S", "V", "N", "Z", "C"]
        sreg_mat = np.zeros((8, num_steps))
        reg_mat = np.zeros((32, num_steps))
        mem_rows = mem_addr_end - mem_addr_start + 1
        mem_mat = np.zeros((mem_rows, num_steps))

        for idx, entry in enumerate(self.cpu.step_trace):
            s = entry.get("sreg", 0)
            for b in range(8):
                sreg_mat[7 - b, idx] = 1.0 if ((s >> b) & 1) else 0.0

            regs = entry.get("regs", [])
            for r in range(min(32, len(regs))):
                reg_mat[r, idx] = regs[r]

            memsnap = entry.get("mem", {})
            for a, v in memsnap.items():
                if mem_addr_start <= a <= mem_addr_end:
                    mem_mat[a - mem_addr_start, idx] = v

        plt.style.use("dark_background")
        fig, axes = plt.subplots(
            3, 1, figsize=(15, 10), gridspec_kw={"height_ratios": [1, 4, 4]}
        )

        im_sreg = axes[0].imshow(
            sreg_mat[:, :1],
            aspect="auto",
            cmap=cmap,
            interpolation="nearest",
            vmin=0,
            vmax=1,
        )
        axes[0].set_yticks(range(8))
        axes[0].set_yticklabels(flag_names, fontsize=fontsize)
        axes[0].set_ylabel("SREG", fontsize=fontsize)

        im_regs = axes[1].imshow(
            reg_mat[:, :1],
            aspect="auto",
            cmap=cmap,
            interpolation="nearest",
            vmin=0,
            vmax=255,
        )
        axes[1].set_yticks(range(32))
        axes[1].set_yticklabels([f"R{i}" for i in range(32)], fontsize=fontsize)
        axes[1].set_ylabel("Registers", fontsize=fontsize)

        im_mem = axes[2].imshow(
            mem_mat[:, :1],
            aspect="auto",
            cmap=cmap,
            interpolation="nearest",
            vmin=0,
            vmax=255,
        )
        axes[2].set_yticks(range(mem_rows))
        axes[2].set_yticklabels(
            [hex(a) for a in range(mem_addr_start, mem_addr_end + 1)], fontsize=fontsize
        )
        axes[2].set_ylabel("Memory", fontsize=fontsize)
        axes[2].set_xlabel("Step", fontsize=fontsize)

        for ax in axes:
            ax.tick_params(axis="x", labelsize=fontsize)
            ax.tick_params(axis="y", labelsize=fontsize)

        fig.colorbar(im_sreg, ax=axes[0], fraction=0.015, pad=0.01)
        fig.colorbar(im_regs, ax=axes[1], fraction=0.015, pad=0.01)
        fig.colorbar(im_mem, ax=axes[2], fraction=0.015, pad=0.01)

        plt.tight_layout(pad=0.2)
        fig.subplots_adjust(top=0.96, bottom=0.05, hspace=0.02)

        def update(frame):
            im_sreg.set_data(sreg_mat[:, : frame + 1])
            im_regs.set_data(reg_mat[:, : frame + 1])
            im_mem.set_data(mem_mat[:, : frame + 1])

            im_sreg.set_extent([0, frame + 1, 8, 0])
            im_regs.set_extent([0, frame + 1, 32, 0])
            im_mem.set_extent([0, frame + 1, mem_rows, 0])

            entry = self.cpu.step_trace[frame]
            instr = entry.get("instr", "")
            pc = entry.get("pc", 0)
            sp = entry.get("sp", 0)

            fig.suptitle(
                f"Step: {frame}, PC: 0x{pc:04x}, SP: 0x{sp:04x}, {instr}",
                x=0.01,
                ha="left",
                fontsize=fontsize,
            )
            return im_sreg, im_regs, im_mem

        frames = range(0, num_steps, plot_every)
        anim = animation.FuncAnimation(
            fig, update, frames=frames, interval=interval, blit=False
        )

        if filename:
            anim.save(filename, fps=fps)
        else:
            plt.show()

    def show_register_history(self, registers: list[int] = None, figsize=(14, 8)):
        """Plot timeline of register value changes over execution.

        Args:
            registers: List of register indices to plot (default: R0-R7).
            figsize: Figure size as (width, height).
        """
        if registers is None:
            registers = list(range(8))

        num_steps = len(self.cpu.step_trace)
        reg_data = {r: np.zeros(num_steps) for r in registers}

        for idx, entry in enumerate(self.cpu.step_trace):
            regs = entry.get("regs", [])
            for r in registers:
                if r < len(regs):
                    reg_data[r][idx] = regs[r]

        plt.style.use("dark_background")
        fig, ax = plt.subplots(figsize=figsize)

        for r in registers:
            ax.plot(reg_data[r], label=f"R{r}", linewidth=1.5, marker="o", markersize=3)

        ax.set_xlabel("Step", fontsize=12)
        ax.set_ylabel("Register Value", fontsize=12)
        ax.set_title("Register Values Over Time", fontsize=14, pad=20)
        ax.legend(loc="best", ncol=4, fontsize=10)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

    def show_memory_access(
        self, mem_addr_start: int = 0, mem_addr_end: int = 255, figsize=(12, 8)
    ):
        """Plot a heatmap showing memory access patterns over time.

        Args:
            mem_addr_start: Start memory address.
            mem_addr_end: End memory address.
            figsize: Figure size as (width, height).
        """
        num_steps = len(self.cpu.step_trace)
        mem_rows = mem_addr_end - mem_addr_start + 1
        mem_mat = np.zeros((mem_rows, num_steps))

        for idx, entry in enumerate(self.cpu.step_trace):
            memsnap = entry.get("mem", {})
            for a, v in memsnap.items():
                if mem_addr_start <= a <= mem_addr_end:
                    mem_mat[a - mem_addr_start, idx] = v

        plt.style.use("dark_background")
        fig, ax = plt.subplots(figsize=figsize)

        im = ax.imshow(mem_mat, aspect="auto", cmap="viridis", interpolation="nearest")
        ax.set_xlabel("Step", fontsize=12)
        ax.set_ylabel("Memory Address", fontsize=12)
        ax.set_title(
            f"Memory Access Pattern (0x{mem_addr_start:04x} - 0x{mem_addr_end:04x})",
            fontsize=14,
            pad=20,
        )

        num_ticks = min(20, mem_rows)
        tick_positions = np.linspace(0, mem_rows - 1, num_ticks, dtype=int)
        ax.set_yticks(tick_positions)
        ax.set_yticklabels([hex(mem_addr_start + pos) for pos in tick_positions])

        fig.colorbar(im, ax=ax, label="Value")
        plt.tight_layout()
        plt.show()

    def show_flag_history(self, figsize=(14, 6)):
        """Plot SREG flag changes over execution time.

        Args:
            figsize: Figure size as (width, height).
        """
        flag_names = ["C", "Z", "N", "V", "S", "H", "T", "I"]
        num_steps = len(self.cpu.step_trace)
        flag_data = {name: np.zeros(num_steps) for name in flag_names}

        for idx, entry in enumerate(self.cpu.step_trace):
            s = entry.get("sreg", 0)
            for bit, name in enumerate(flag_names):
                flag_data[name][idx] = 1 if ((s >> bit) & 1) else 0

        plt.style.use("dark_background")
        fig, ax = plt.subplots(figsize=figsize)

        offset = 0
        colors = plt.cm.Set3(np.linspace(0, 1, 8))

        for idx, name in enumerate(flag_names):
            values = flag_data[name] + offset
            ax.fill_between(
                range(num_steps),
                offset,
                values,
                alpha=0.7,
                label=name,
                color=colors[idx],
            )
            offset += 1.2

        ax.set_xlabel("Step", fontsize=12)
        ax.set_ylabel("Flags", fontsize=12)
        ax.set_title("SREG Flag Activity", fontsize=14, pad=20)
        ax.set_yticks([i * 1.2 + 0.5 for i in range(8)])
        ax.set_yticklabels(flag_names)
        ax.legend(loc="upper right", ncol=8, fontsize=10)
        ax.grid(True, alpha=0.2, axis="x")
        plt.tight_layout()
        plt.show()

    def show_statistics(self, top_n: int = 10):
        """Plot execution summary statistics.

        Args:
            top_n: Number of top memory addresses to show in access frequency.
        """
        num_steps = len(self.cpu.step_trace)

        # Count instruction types
        instr_counts = {}
        for entry in self.cpu.step_trace:
            instr = entry.get("instr", "").split()[0]
            instr_counts[instr] = instr_counts.get(instr, 0) + 1

        # Track memory access frequency
        mem_access = {}
        for entry in self.cpu.step_trace:
            memsnap = entry.get("mem", {})
            for addr in memsnap.keys():
                mem_access[addr] = mem_access.get(addr, 0) + 1

        plt.style.use("dark_background")
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # Instruction frequency
        sorted_instrs = sorted(instr_counts.items(), key=lambda x: x[1], reverse=True)[
            :top_n
        ]
        if sorted_instrs:
            instrs, counts = zip(*sorted_instrs)
            axes[0, 0].barh(instrs, counts, color="skyblue")
            axes[0, 0].set_xlabel("Count", fontsize=11)
            axes[0, 0].set_title("Top Instructions", fontsize=12)
            axes[0, 0].invert_yaxis()

        # Memory access frequency
        sorted_mem = sorted(mem_access.items(), key=lambda x: x[1], reverse=True)[
            :top_n
        ]
        if sorted_mem:
            addrs, counts = zip(*sorted_mem)
            addr_labels = [f"0x{a:04x}" for a in addrs]
            axes[0, 1].barh(addr_labels, counts, color="lightcoral")
            axes[0, 1].set_xlabel("Access Count", fontsize=11)
            axes[0, 1].set_title("Top Memory Accesses", fontsize=12)
            axes[0, 1].invert_yaxis()

        # Register usage
        reg_changes = [0] * 32
        for entry in self.cpu.step_trace:
            regs = entry.get("regs", [])
            for r in range(min(32, len(regs))):
                if r < len(regs) and regs[r] != 0:
                    reg_changes[r] += 1

        axes[1, 0].bar(range(32), reg_changes, color="mediumseagreen")
        axes[1, 0].set_xlabel("Register", fontsize=11)
        axes[1, 0].set_ylabel("Non-zero Count", fontsize=11)
        axes[1, 0].set_title("Register Usage", fontsize=12)
        axes[1, 0].set_xticks(range(0, 32, 4))

        # Execution timeline
        axes[1, 1].text(
            0.5,
            0.5,
            f"Total Instructions: {num_steps}\n"
            f"Unique Instructions: {len(instr_counts)}\n"
            f"Memory Locations Accessed: {len(mem_access)}\n"
            f"Final PC: 0x{self.cpu.pc:04x}\n"
            f"Final SP: 0x{self.cpu.sp:04x}",
            ha="center",
            va="center",
            fontsize=14,
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.3),
        )
        axes[1, 1].set_title("Execution Summary", fontsize=12)
        axes[1, 1].axis("off")

        plt.tight_layout()
        plt.show()
