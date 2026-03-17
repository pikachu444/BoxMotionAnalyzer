"""
Static workflow mockups for the slice-first processing proposal.

This generator avoids Qt so it can run in minimal environments.
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np


OUT_DIR = Path("/root/BoxMotionAnalyzer-slice-mockup/docs/analysis/design/gui_mockups")


def add_box(ax, x, y, w, h, label="", fc="#ffffff", ec="#cbd5e0", lw=1.2, radius=0.015):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.004,rounding_size={radius}",
        facecolor=fc,
        edgecolor=ec,
        linewidth=lw,
    )
    ax.add_patch(patch)
    if label:
        ax.text(x + 0.012, y + h - 0.028, label, fontsize=11, fontweight="bold", va="top", color="#1a202c")
    return patch


def add_text(ax, x, y, text, size=10, color="#2d3748", weight="normal", ha="left", va="top"):
    ax.text(x, y, text, fontsize=size, color=color, fontweight=weight, ha=ha, va=va)


def add_button(ax, x, y, w, h, label, fc="#edf2f7", ec="#a0aec0", text_color="#1a202c", bold=False):
    add_box(ax, x, y, w, h, fc=fc, ec=ec, lw=1.0, radius=0.01)
    add_text(ax, x + w / 2, y + h / 2 + 0.004, label, size=9.5, color=text_color, weight="bold" if bold else "normal", ha="center", va="center")


def add_chip(ax, x, y, w, label, fc, color):
    add_box(ax, x, y, w, 0.04, fc=fc, ec=fc, lw=0.8, radius=0.02)
    add_text(ax, x + w / 2, y + 0.022, label, size=9.2, color=color, weight="bold", ha="center", va="center")


def add_field(ax, x, y, w, label, value):
    add_text(ax, x, y + 0.03, label, size=9, color="#4a5568")
    add_box(ax, x + 0.085, y, w - 0.085, 0.045, fc="#ffffff", ec="#cbd5e0", lw=1.0, radius=0.008)
    add_text(ax, x + 0.095, y + 0.024, value, size=9, color="#1a202c", va="center")


def add_status_line(ax, x, y, label, value, color):
    add_text(ax, x, y, f"{label}: ", size=10, color="#4a5568", weight="bold")
    add_text(ax, x + 0.09, y, value, size=10, color=color, weight="bold")


def setup_canvas(title):
    fig = plt.figure(figsize=(16, 10), dpi=140)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("#f7fafc")
    add_text(ax, 0.03, 0.965, title, size=18, weight="bold", color="#1a202c")
    return fig, ax


def draw_plot_preview(ax, x, y, w, h):
    add_box(ax, x, y, w, h, "Raw Data Preview", fc="#ffffff")
    plot_ax = ax.figure.add_axes([x + 0.02, y + 0.06, w - 0.04, h - 0.1])
    t = np.linspace(0, 120, 600)
    signal = 50 + 6 * np.sin(t / 8) + 1.2 * np.cos(t / 2.5)
    plot_ax.plot(t, signal, color="#1f4f8a", linewidth=1.8)
    plot_ax.axvspan(39.2, 70.8, color="#b2f5ea", alpha=0.5)
    plot_ax.axvspan(40, 70, color="#68d391", alpha=0.6)
    plot_ax.set_xlim(0, 120)
    plot_ax.set_title("RigidBody Center / Position-X", fontsize=10)
    plot_ax.set_xlabel("Time (s)", fontsize=9)
    plot_ax.set_ylabel("Value", fontsize=9)
    plot_ax.grid(True, alpha=0.25)
    plot_ax.tick_params(labelsize=8)


def draw_main_plot(ax, x, y, w, h):
    add_box(ax, x, y, w, h, "Main Plot", fc="#ffffff")
    plot_ax = ax.figure.add_axes([x + 0.02, y + 0.06, w - 0.04, h - 0.1])
    t = np.linspace(40, 70, 400)
    plot_ax.plot(t, 0.45 * np.sin(t * 0.45), label="Velocity / CoM / Box Local X")
    plot_ax.plot(t, 0.30 * np.cos(t * 0.52), label="Velocity / CoM / Box Local Y")
    plot_ax.plot(t, 0.25 * np.sin(t * 0.34 + 1.4), label="Velocity / CoM / Box Local Z")
    plot_ax.plot(t, 4.3 + 0.6 * np.sin(t * 0.16), label="Analysis / C1 / Relative Height")
    plot_ax.axvline(54.27, color="#c53030", linestyle="--", linewidth=1.2)
    plot_ax.set_xlabel("Time (s)", fontsize=9)
    plot_ax.set_ylabel("Value", fontsize=9)
    plot_ax.grid(True, alpha=0.25)
    plot_ax.legend(fontsize=7.8, ncol=2, loc="upper right")
    plot_ax.tick_params(labelsize=8)


def draw_step1_mock():
    fig, ax = setup_canvas("Step 1: Load, Slice, and Process")

    add_chip(ax, 0.03, 0.90, 0.11, "Source: Loaded", "#e6fffa", "#234e52")
    add_chip(ax, 0.15, 0.90, 0.10, "Slice: Ready", "#ebf8ff", "#2a4365")
    add_chip(ax, 0.26, 0.90, 0.14, "Result: In Memory", "#f0fff4", "#22543d")

    draw_plot_preview(ax, 0.03, 0.46, 0.63, 0.40)

    add_box(ax, 0.69, 0.46, 0.28, 0.40, "Session Summary", fc="#ffffff")
    add_button(ax, 0.72, 0.79, 0.16, 0.045, "Load CSV File...", fc="#2b6cb0", ec="#2b6cb0", text_color="#ffffff", bold=True)
    add_text(ax, 0.72, 0.755, "D:/DropTest/Run_07.csv", size=9.2)

    add_box(ax, 0.72, 0.63, 0.22, 0.10, "Source")
    add_text(ax, 0.735, 0.69, "Full Range: 0.000s ~ 120.000s", size=9.2)
    add_text(ax, 0.735, 0.665, "Rows: 4,812,114", size=9.2)
    add_text(ax, 0.735, 0.64, "Target: RigidBody Center", size=9.2)

    add_box(ax, 0.72, 0.49, 0.22, 0.12, "Slice")
    add_text(ax, 0.735, 0.57, "User Slice: 40.000s ~ 70.000s", size=9.2)
    add_text(ax, 0.735, 0.545, "Padding: 0.800s on each side", size=9.2)
    add_text(ax, 0.735, 0.52, "Processing Range: 39.200s ~ 70.800s", size=9.2)
    add_text(ax, 0.735, 0.495, "Prepared Slice Rows: 128,401", size=9.2)

    add_box(ax, 0.03, 0.28, 0.24, 0.13, "Plot Options", fc="#ffffff")
    add_button(ax, 0.045, 0.325, 0.08, 0.04, "Select Data...")
    add_text(ax, 0.135, 0.347, "Selected: RigidBody Center", size=9.2, va="center")
    add_text(ax, 0.045, 0.305, "Axis", size=9)
    add_box(ax, 0.085, 0.285, 0.12, 0.04, fc="#ffffff", ec="#cbd5e0", lw=1.0, radius=0.008)
    add_text(ax, 0.095, 0.305, "Position-X", size=9, va="center")

    add_box(ax, 0.29, 0.28, 0.28, 0.13, "Slice Settings", fc="#ffffff")
    add_field(ax, 0.305, 0.34, 0.11, "Start", "40.0")
    add_field(ax, 0.43, 0.34, 0.11, "End", "70.0")
    add_text(ax, 0.305, 0.305, "Padding Mode", size=9, color="#4a5568")
    add_box(ax, 0.39, 0.285, 0.15, 0.045, fc="#ffffff", ec="#cbd5e0", lw=1.0, radius=0.008)
    add_text(ax, 0.40, 0.307, "Auto (from processing)", size=8.5, va="center")

    add_box(ax, 0.59, 0.28, 0.38, 0.13, "Processing Settings", fc="#ffffff")
    add_text(ax, 0.605, 0.347, "Mode", size=9, color="#4a5568")
    for idx, label in enumerate(["Raw", "Standard", "Advanced"]):
        cx = 0.66 + idx * 0.075
        ax.add_patch(Rectangle((cx, 0.333), 0.015, 0.015, facecolor="#ffffff", edgecolor="#718096", linewidth=1))
        if label == "Standard":
            ax.add_patch(Rectangle((cx + 0.003, 0.336), 0.009, 0.009, facecolor="#2b6cb0", edgecolor="#2b6cb0"))
        add_text(ax, cx + 0.022, 0.347, label, size=9, va="center")
    add_button(ax, 0.86, 0.332, 0.09, 0.04, "Advanced Settings...")
    ax.add_patch(Rectangle((0.605, 0.292), 0.015, 0.015, facecolor="#ffffff", edgecolor="#718096", linewidth=1))
    add_text(ax, 0.628, 0.305, "Enable Resampling", size=9, va="center")
    add_box(ax, 0.74, 0.285, 0.07, 0.04, fc="#ffffff", ec="#cbd5e0", lw=1.0, radius=0.008)
    add_text(ax, 0.752, 0.305, "2x", size=9, va="center")
    add_text(
        ax,
        0.605,
        0.274,
        "Processing settings can change without rebuilding the prepared slice.",
        size=8.8,
        color="#4a5568",
    )

    add_box(ax, 0.03, 0.11, 0.94, 0.12, "Workflow Actions", fc="#ffffff")
    buttons = [
        ("Prepare Slice", "#2b6cb0", "#ffffff"),
        ("Save Slice As...", "#edf2f7", "#1a202c"),
        ("Run Processing", "#2f855a", "#ffffff"),
        ("Open in Step 2", "#3182ce", "#ffffff"),
        ("Export Final Result", "#edf2f7", "#1a202c"),
    ]
    x = 0.05
    for label, fc, tc in buttons:
        add_button(ax, x, 0.16, 0.15, 0.045, label, fc=fc, ec=fc if fc != "#edf2f7" else "#a0aec0", text_color=tc, bold=fc != "#edf2f7")
        x += 0.18

    add_status_line(ax, 0.05, 0.135, "Slice state", "Ready", "#2a4365")
    add_status_line(ax, 0.33, 0.135, "Result state", "Processed in memory", "#22543d")
    add_status_line(ax, 0.68, 0.135, "Export state", "Not exported yet", "#975a16")
    add_text(
        ax,
        0.05,
        0.10,
        "If slice range changes: re-prepare slice and re-run processing. If only processing settings change: re-run processing only.",
        size=9,
        color="#744210",
    )

    return fig


def draw_step2_mock():
    fig, ax = setup_canvas("Step 2: Results Analysis")

    add_box(ax, 0.03, 0.90, 0.94, 0.045, fc="#fffaf0", ec="#f6ad55", lw=1.0, radius=0.008)
    add_text(
        ax,
        0.045,
        0.922,
        "Viewing in-memory result from Step 1. Export is optional and can be done after review.",
        size=10,
        color="#744210",
        weight="bold",
        va="center",
    )

    add_box(ax, 0.03, 0.79, 0.94, 0.09, "Time Window", fc="#ffffff")
    add_text(ax, 0.05, 0.84, "Active Source: run_07_slice_40_70.parquet", size=9.5)
    add_text(ax, 0.36, 0.84, "Result State: In Memory", size=9.5)
    add_text(ax, 0.58, 0.84, "Samples: 12,801", size=9.5)
    add_text(ax, 0.05, 0.815, "Full: 0.000s ~ 120.000s | Slice: 40.000s ~ 70.000s | Processing Range: 39.200s ~ 70.800s", size=9.3)
    ax.add_patch(Rectangle((0.05, 0.795), 0.30, 0.012, facecolor="#d7dbe0", edgecolor="none"))
    ax.add_patch(Rectangle((0.35, 0.795), 0.23, 0.012, facecolor="#68d391", edgecolor="none"))
    ax.add_patch(Rectangle((0.58, 0.795), 0.27, 0.012, facecolor="#d7dbe0", edgecolor="none"))

    add_box(ax, 0.03, 0.39, 0.18, 0.35, "1. Result Source", fc="#ffffff")
    add_box(ax, 0.05, 0.64, 0.14, 0.06, fc="#ebf8ff", ec="#90cdf4", radius=0.01)
    add_text(ax, 0.06, 0.677, "In-memory result (current)", size=9.2, weight="bold")
    add_box(ax, 0.05, 0.57, 0.14, 0.05, fc="#ffffff", ec="#e2e8f0", radius=0.01)
    add_text(ax, 0.06, 0.602, "run_05_result.csv", size=9)
    add_box(ax, 0.05, 0.51, 0.14, 0.05, fc="#ffffff", ec="#e2e8f0", radius=0.01)
    add_text(ax, 0.06, 0.542, "run_06_result.csv", size=9)
    add_button(ax, 0.05, 0.43, 0.14, 0.045, "Import Exported Result...")

    add_box(ax, 0.23, 0.39, 0.45, 0.35, "2. Data Selection", fc="#ffffff")
    columns = [
        ("Velocity", ["CoM / Box Local X", "CoM / Box Local Y", "CoM / Box Local Z", "CoM / Global Norm"]),
        ("Analysis", ["C1 / Relative Height"]),
    ]
    y = 0.69
    for section, items in columns:
        add_text(ax, 0.25, y, section, size=10, weight="bold")
        y -= 0.03
        for item in items:
            ax.add_patch(Rectangle((0.255, y - 0.01), 0.012, 0.012, facecolor="#2b6cb0", edgecolor="#2b6cb0", linewidth=1))
            add_text(ax, 0.275, y, item, size=9.1)
            y -= 0.028
        y -= 0.01
    add_button(ax, 0.25, 0.43, 0.09, 0.04, "Clear Selection")
    add_button(ax, 0.355, 0.43, 0.11, 0.04, "Plot Selected")
    add_button(ax, 0.48, 0.43, 0.09, 0.04, "Open Popup")
    add_text(ax, 0.25, 0.405, "Checked Columns: 5", size=9.3, weight="bold", color="#2d3748")
    add_button(ax, 0.54, 0.395, 0.12, 0.045, "Export Final Result", fc="#2f855a", ec="#2f855a", text_color="#ffffff", bold=True)

    add_box(ax, 0.70, 0.39, 0.27, 0.35, "3. Review Actions", fc="#ffffff")
    add_box(ax, 0.72, 0.59, 0.23, 0.12, "Session Summary")
    add_text(ax, 0.735, 0.665, "Source File: Run_07.csv", size=9.1)
    add_text(ax, 0.735, 0.64, "Slice Artifact: run_07_slice_40_70.parquet", size=9.1)
    add_text(ax, 0.735, 0.615, "Processing Mode: Standard", size=9.1)
    add_text(ax, 0.735, 0.59, "Export: Pending", size=9.1)
    add_button(ax, 0.72, 0.53, 0.10, 0.042, "Back to Step 1")
    add_button(ax, 0.84, 0.53, 0.11, 0.042, "Export Final Result", fc="#2f855a", ec="#2f855a", text_color="#ffffff", bold=True)
    add_box(ax, 0.72, 0.41, 0.23, 0.10, "Point Analysis")
    add_text(ax, 0.735, 0.475, "Target: Velocity / CoM / Box Local X", size=9)
    add_button(ax, 0.735, 0.43, 0.05, 0.035, "Abs Max")
    add_button(ax, 0.79, 0.43, 0.04, 0.035, "Max")
    add_button(ax, 0.835, 0.43, 0.04, 0.035, "Min")
    add_text(ax, 0.735, 0.405, "Selected Point: 54.270s", size=9)

    draw_main_plot(ax, 0.03, 0.05, 0.94, 0.28)

    return fig


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    step1_path = OUT_DIR / "step1_slice_workflow_mock_v33.png"
    step2_path = OUT_DIR / "step2_in_memory_result_mock_v33.png"

    fig1 = draw_step1_mock()
    fig1.savefig(step1_path, bbox_inches="tight")
    plt.close(fig1)

    fig2 = draw_step2_mock()
    fig2.savefig(step2_path, bbox_inches="tight")
    plt.close(fig2)

    print(step1_path)
    print(step2_path)


if __name__ == "__main__":
    main()
