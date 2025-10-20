"""Visualization helpers using Matplotlib to plot register/memory changes.

This module provides a simple Visualizer class that can create an animated
visualization of the CPU step trace showing SREG bits, registers and a
memory range.
"""

try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None


class Visualizer:
    def __init__(self, cpu):
        self.cpu = cpu

    def animate_combined(
        self,
        mem_addr_start: int = 0,
        mem_addr_end: int = 31,
        filename: str | None = None,
        interval: int = 200,
        fps: int = 30,
        fontsize=9,
        cmap="inferno",
        plot_every: int = 1,
    ):
        """Animate SREG bits, registers (R0..R31), and a memory range as three stacked subplots.

        Args:
            mem_addr_start: Start memory address for memory subplot (default 0).
            mem_addr_end: End memory address for memory subplot (default 31).
            filename: Optional output filename for saving an animation (GIF). If
                not provided, show the plot interactively.
            interval: Milliseconds between frames in the animation.
            fps: Frames per second for saving output.
            fontsize: Font size for labels and ticks.
            cmap: Matplotlib colormap name for the heatmaps.
            plot_every: Plot every N cycles (downsampling of frames).

        Notes:
            Requires numpy and matplotlib. If Matplotlib's animation or ffmpeg
            is not available, the method will attempt to show a static figure.
        """
        try:
            import numpy as np
        except Exception:
            print("numpy is required for animation")
            return
        if plt is None:
            print("matplotlib not available - cannot animate")
            return

        # Build time dimension from step_trace or reg_trace fallback
        if plot_every <= 0:
            plot_every = 1
        if self.cpu.step_trace:
            max_cycle = max(e["cycle"] for e in self.cpu.step_trace)
            cols = max_cycle
        else:
            traces = self.cpu.reg_trace
            if not traces:
                print("No activity to animate")
                return
            cols = max((c for (c, _, _) in traces), default=0) + 1

        # SREG matrix: 8 flags x cols
        flag_names = ["I", "T", "H", "S", "V", "N", "Z", "C"]
        sreg_mat = np.zeros((8, cols), dtype=float)
        # registers matrix
        rows = 32
        reg_mat = np.zeros((rows, cols), dtype=float)
        # memory matrix
        mem_rows = mem_addr_end - mem_addr_start + 1
        mem_mat = np.zeros((mem_rows, cols), dtype=float)

        # initialize with NaN for proper forward-fill
        sreg_mat[:] = np.nan
        reg_mat[:] = np.nan
        mem_mat[:] = np.nan

        # populate from step_trace entries
        for e in self.cpu.step_trace:
            cidx = max(0, e["cycle"] - 1)
            # sreg bits
            s = e.get("sreg", 0)
            for b in range(8):
                sreg_mat[7 - b, cidx] = 1.0 if ((s >> b) & 1) else 0.0
            # regs snapshot (post-exec uses pre-exec regs snapshot stored as 'regs')
            regs = e.get("regs", [])
            for r in range(min(rows, len(regs))):
                reg_mat[r, cidx] = regs[r]
            # mem snapshot: only filled where present
            memsnap = e.get("mem", {})
            for a, v in memsnap.items():
                if mem_addr_start <= a <= mem_addr_end:
                    mem_mat[a - mem_addr_start, cidx] = v

        # forward-fill along time axis
        for c in range(1, cols):
            for arr in (sreg_mat, reg_mat, mem_mat):
                mask = np.isnan(arr[:, c])
                arr[mask, c] = arr[mask, c - 1]
        sreg_mat = np.nan_to_num(sreg_mat, nan=0.0)
        reg_mat = np.nan_to_num(reg_mat, nan=0.0)
        mem_mat = np.nan_to_num(mem_mat, nan=0.0)

        plt.style.use("dark_background")

        # create subplots with tight spacing
        fig, axes = plt.subplots(
            3, 1, figsize=(15, 10), gridspec_kw={"height_ratios": [1, 4, 4]}
        )

        im_sreg = axes[0].imshow(
            sreg_mat, aspect="auto", cmap=cmap, interpolation="nearest", vmin=0, vmax=1
        )
        axes[0].set_yticks(range(8))
        axes[0].set_yticklabels(flag_names, fontsize=fontsize)
        axes[0].set_ylabel("SREG", fontsize=fontsize)

        im_regs = axes[1].imshow(
            reg_mat, aspect="auto", cmap=cmap, interpolation="nearest", vmin=0, vmax=255
        )
        axes[1].set_yticks(range(rows))
        axes[1].set_yticklabels([f"R{i}" for i in range(rows)], fontsize=fontsize)
        axes[1].set_ylabel("Registers", fontsize=fontsize)

        im_mem = axes[2].imshow(
            mem_mat, aspect="auto", cmap=cmap, interpolation="nearest", vmin=0, vmax=255
        )
        axes[2].set_yticks(range(mem_rows))
        axes[2].set_yticklabels(
            [hex(a) for a in range(mem_addr_start, mem_addr_end + 1)], fontsize=fontsize
        )
        axes[2].set_ylabel("Memory", fontsize=fontsize)
        axes[2].set_xlabel("cycle", fontsize=fontsize)

        # Reduce tick padding and label sizes to minimize margins
        for ax in axes:
            ax.tick_params(axis="x", which="both", pad=2, labelsize=fontsize)
            ax.tick_params(axis="y", which="both", pad=2)

        # smaller colorbars to avoid expanding figure margins
        fig.colorbar(
            im_sreg, ax=axes[0], orientation="vertical", fraction=0.015, pad=0.01
        )
        fig.colorbar(
            im_regs, ax=axes[1], orientation="vertical", fraction=0.015, pad=0.01
        )
        fig.colorbar(
            im_mem, ax=axes[2], orientation="vertical", fraction=0.015, pad=0.01
        )

        # Apply tight layout and then manually nudge subplot bounds to minimize margins
        try:
            plt.tight_layout(pad=0.2)
        except Exception:
            pass
        # shrink margins as much as reasonable
        fig.subplots_adjust(top=0.96, bottom=0.035, hspace=0.02)

        try:
            from matplotlib import animation
        except Exception:
            animation = None

        def update(frame):
            # frame will be the actual column index (cycle index) when frames is an iterable
            fidx = frame

            # update images to show up to fidx (inclusive)
            def mask_after(arr):
                disp = arr.copy()
                if fidx + 1 < disp.shape[1]:
                    disp[:, fidx + 1 :] = 0
                return disp

            im_sreg.set_data(mask_after(sreg_mat))
            im_regs.set_data(mask_after(reg_mat))
            im_mem.set_data(mask_after(mem_mat))

            # instruction text
            instr_text = ""
            pc_val = getattr(self.cpu, "pc", None)
            sp_val = getattr(self.cpu, "sp", None)
            try:
                entry = next(
                    (e for e in self.cpu.step_trace if e["cycle"] - 1 == fidx), None
                )
                if entry:
                    instr_text = entry.get("instr", "")
                    pc_val = entry.get("pc", pc_val)
                    sp_val = entry.get("sp", sp_val)
            except Exception:
                instr_text = ""

            left = (
                f"Cycle: {fidx:5d}, PC: 0x{pc_val:04x}, SP: 0x{sp_val:04x}, Run: {instr_text}"
                if instr_text
                else f"Cycle {fidx}"
            )
            fig.suptitle(left, x=0, ha="left")
            return (im_sreg, im_regs, im_mem)

        if animation is None:
            print("matplotlib.animation not available; showing static figure")
            plt.show()
            return

        frame_iter = range(0, cols, plot_every)
        anim = animation.FuncAnimation(
            fig, update, frames=frame_iter, interval=interval, blit=False
        )
        if filename:
            try:
                anim.save(filename, fps=fps)
            except Exception as e:
                print("Failed to save animation:", e)
                plt.show()
        else:
            plt.show()
