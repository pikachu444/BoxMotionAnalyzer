"""
Static mockups for the proposed slice / processing / result workflow.

These images intentionally follow the current Step 1 / Step 2 layout:
- Step 1 keeps the top preview + right panel + bottom controls structure.
- Step 1.5 reuses the Step 1 visual language for processing.
- Step 2 keeps the current time window + 3-column body + main plot layout.
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np


OUT_DIR = Path("/root/BoxMotionAnalyzer-slice-mockup/docs/analysis/design/gui_mockups")

BG = "#f4f5f7"
PANEL = "#ffffff"
BORDER = "#c9cdd4"
TEXT = "#1f2933"
MUTED = "#606f7b"
BLUE = "#2b6cb0"
GREEN = "#38a169"
LIGHT_GREEN = "#89cf8a"
GREY_BAR = "#d7dbe0"
BUTTON = "#edf2f7"


def fig_ax(width=16, height=10):
    fig = plt.figure(figsize=(width, height), dpi=140)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(BG)
    return fig, ax


def round_box(ax, x, y, w, h, fc=PANEL, ec=BORDER, lw=1.0, radius=0.012):
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
    return patch


def group_box(ax, x, y, w, h, title):
    round_box(ax, x, y, w, h, fc=PANEL, ec=BORDER, lw=0.9, radius=0.014)
    ax.text(x + 0.012, y + h - 0.02, title, fontsize=10.5, fontweight="bold", color=TEXT, va="top")


def button(ax, x, y, w, h, label, primary=False):
    fc = BLUE if primary else BUTTON
    ec = BLUE if primary else "#b7bec7"
    tc = "#ffffff" if primary else TEXT
    round_box(ax, x, y, w, h, fc=fc, ec=ec, lw=0.9, radius=0.01)
    ax.text(x + w / 2, y + h / 2, label, fontsize=9.3, color=tc, va="center", ha="center",
            fontweight="bold" if primary else "normal")


def line_edit(ax, x, y, w, h, value, align="left"):
    round_box(ax, x, y, w, h, fc="#ffffff", ec=BORDER, lw=0.9, radius=0.008)
    ha = "center" if align == "center" else "left"
    tx = x + w / 2 if align == "center" else x + 0.01
    ax.text(tx, y + h / 2, value, fontsize=9, color=TEXT, va="center", ha=ha)


def checkbox(ax, x, y, label, checked=False):
    ax.add_patch(Rectangle((x, y), 0.012, 0.012, facecolor="#ffffff", edgecolor="#8e99a8", linewidth=0.9))
    if checked:
        ax.add_patch(Rectangle((x + 0.0025, y + 0.0025), 0.007, 0.007, facecolor=BLUE, edgecolor=BLUE))
    ax.text(x + 0.018, y + 0.006, label, fontsize=9, color=TEXT, va="center")


def radio(ax, x, y, label, checked=False):
    circ = plt.Circle((x + 0.006, y + 0.006), 0.006, facecolor="#ffffff", edgecolor="#8e99a8", linewidth=0.9)
    ax.add_patch(circ)
    if checked:
        ax.add_patch(plt.Circle((x + 0.006, y + 0.006), 0.0033, facecolor=BLUE, edgecolor=BLUE))
    ax.text(x + 0.018, y + 0.006, label, fontsize=9, color=TEXT, va="center")


def label(ax, x, y, text, size=9, color=TEXT, bold=False, va="top", ha="left"):
    ax.text(x, y, text, fontsize=size, color=color, fontweight="bold" if bold else "normal", va=va, ha=ha)


def draw_toolbar(ax, x, y, w, h):
    round_box(ax, x, y, w, h, fc="#f8fafc", ec=BORDER, lw=0.8, radius=0.004)
    offsets = [0.015, 0.04, 0.065, 0.09, 0.13, 0.17]
    for off in offsets:
        ax.add_patch(Rectangle((x + off, y + 0.006), 0.014, h - 0.012, facecolor="#ffffff", edgecolor="#bfc5ce", linewidth=0.7))


def draw_preview_plot(fig, ax, x, y, w, h, title, xlim=(0, 100), slice_range=(20, 30), padded_range=None, ylabel="Value"):
    plot = fig.add_axes([x, y, w, h])
    xs = np.linspace(xlim[0], xlim[1], 500)
    ys = 45 + 9 * np.sin(xs / 6.2) + 2 * np.cos(xs / 2.7)
    plot.plot(xs, ys, color=BLUE, linewidth=1.6)
    if padded_range is not None:
        plot.axvspan(padded_range[0], padded_range[1], color="#b7e4c7", alpha=0.45)
    plot.axvspan(slice_range[0], slice_range[1], color=LIGHT_GREEN, alpha=0.5)
    plot.set_title(title, fontsize=10)
    plot.set_xlabel("Time (s)", fontsize=8.5)
    plot.set_ylabel(ylabel, fontsize=8.5)
    plot.grid(True, alpha=0.25)
    plot.tick_params(labelsize=7.5)


def draw_main_plot(fig, ax, x, y, w, h):
    plot = fig.add_axes([x, y, w, h])
    xs = np.linspace(20, 30, 300)
    plot.plot(xs, 0.42 * np.sin(xs * 2.1), label="Velocity X (Box Local Frame)", linewidth=1.3)
    plot.plot(xs, 0.30 * np.cos(xs * 1.7), label="Velocity Y (Box Local Frame)", linewidth=1.3)
    plot.plot(xs, 4.0 + 0.55 * np.sin(xs * 0.7), label="Relative Height (C1)", linewidth=1.3)
    plot.axvline(25.4, color="#c53030", linestyle="--", linewidth=1.0)
    plot.set_xlabel("Time (s)", fontsize=8.5)
    plot.set_ylabel("Value", fontsize=8.5)
    plot.grid(True, alpha=0.25)
    plot.legend(fontsize=7.2, loc="upper right")
    plot.tick_params(labelsize=7.5)


def draw_step1():
    fig, ax = fig_ax(15, 9.2)
    label(ax, 0.03, 0.965, "Step 1: Raw Data Slice", size=16, bold=True)
    group_box(ax, 0.03, 0.05, 0.94, 0.88, "Raw Data Slice")

    # Top region
    round_box(ax, 0.045, 0.45, 0.68, 0.45)
    draw_toolbar(ax, 0.06, 0.845, 0.65, 0.032)
    draw_preview_plot(
        fig, ax, 0.065, 0.50, 0.64, 0.33,
        "Raw Data Preview", xlim=(0, 120), slice_range=(40, 70)
    )

    round_box(ax, 0.74, 0.45, 0.20, 0.45)
    button(ax, 0.76, 0.84, 0.13, 0.045, "Load CSV File...", primary=True)
    label(ax, 0.76, 0.81, "D:/DropTest/Run_07.csv", size=8.8)

    group_box(ax, 0.755, 0.66, 0.16, 0.12, "Raw File Summary")
    label(ax, 0.77, 0.735, "Full Range: 0.000s ~ 118.520s", size=8.8)
    label(ax, 0.77, 0.708, "Rows: 4,812,114", size=8.8)
    label(ax, 0.77, 0.681, "Next Action: save scene slices", size=8.8, color=MUTED)

    group_box(ax, 0.755, 0.53, 0.16, 0.10, "Saved Scenes")
    label(ax, 0.77, 0.595, "impact_01  20.0s ~ 30.0s", size=8.4)
    label(ax, 0.77, 0.572, "impact_02  40.0s ~ 70.0s", size=8.4)
    label(ax, 0.77, 0.549, "return_01  75.0s ~ 90.0s", size=8.4)

    group_box(ax, 0.755, 0.46, 0.16, 0.05, "Log")
    label(ax, 0.77, 0.49, "[INFO] Ready to save scene slices.", size=8.3, color=MUTED)

    # Bottom controls
    group_box(ax, 0.05, 0.18, 0.24, 0.20, "Plot Options")
    button(ax, 0.065, 0.29, 0.085, 0.04, "Select Data...")
    label(ax, 0.16, 0.312, "Selected: RigidBody Center", size=8.8, va="center")
    label(ax, 0.065, 0.25, "Axis:", size=9)
    line_edit(ax, 0.10, 0.228, 0.10, 0.04, "Position-X")

    group_box(ax, 0.31, 0.18, 0.18, 0.20, "Slice Range")
    checkbox(ax, 0.325, 0.32, "Enable slice selection", checked=True)
    label(ax, 0.325, 0.275, "Start:", size=9)
    line_edit(ax, 0.365, 0.255, 0.07, 0.04, "40.0")
    label(ax, 0.325, 0.225, "End:", size=9)
    line_edit(ax, 0.365, 0.205, 0.07, 0.04, "70.0")

    group_box(ax, 0.51, 0.18, 0.22, 0.20, "Scene Slice")
    label(ax, 0.525, 0.315, "Scene Name:", size=9)
    line_edit(ax, 0.61, 0.295, 0.10, 0.04, "impact_02")
    label(ax, 0.525, 0.265, "Output:", size=9)
    line_edit(ax, 0.58, 0.245, 0.13, 0.04, "drop07_impact_02.bmaslice.parquet")
    label(ax, 0.525, 0.203, "Save each scene once so large raw CSV does not need to be reopened.", size=8.4, color=MUTED)

    round_box(ax, 0.75, 0.18, 0.17, 0.20)
    button(ax, 0.775, 0.305, 0.12, 0.045, "Save Scene Slice", primary=True)
    button(ax, 0.775, 0.248, 0.12, 0.040, "Open Slice Folder")
    label(ax, 0.775, 0.21, "Saved file type:", size=8.5, color=MUTED)
    label(ax, 0.855, 0.21, ".bmaslice.parquet", size=8.5, bold=True)

    return fig


def draw_step15():
    fig, ax = fig_ax(15, 9.2)
    label(ax, 0.03, 0.965, "Step 1.5: Slice Processing", size=16, bold=True)
    group_box(ax, 0.03, 0.05, 0.94, 0.88, "Slice Processing")

    round_box(ax, 0.045, 0.45, 0.68, 0.45)
    draw_toolbar(ax, 0.06, 0.845, 0.65, 0.032)
    draw_preview_plot(
        fig, ax, 0.065, 0.50, 0.64, 0.33,
        "Slice Preview / Processing Result Overlay",
        xlim=(39.2, 70.8),
        slice_range=(40.0, 70.0),
        padded_range=(39.2, 70.8),
    )

    round_box(ax, 0.74, 0.45, 0.20, 0.45)
    button(ax, 0.76, 0.84, 0.13, 0.045, "Load Slice...", primary=True)
    label(ax, 0.76, 0.81, "drop07_impact_02.bmaslice.parquet", size=8.7)

    group_box(ax, 0.755, 0.66, 0.16, 0.11, "Slice Context")
    label(ax, 0.77, 0.73, "User Slice: 40.000s ~ 70.000s", size=8.5)
    label(ax, 0.77, 0.705, "Padding Range: 39.200s ~ 70.800s", size=8.5)
    label(ax, 0.77, 0.68, "Rows: 128,401", size=8.5)

    group_box(ax, 0.755, 0.53, 0.16, 0.10, "Current Result")
    label(ax, 0.77, 0.595, "Mode: Standard", size=8.5)
    label(ax, 0.77, 0.572, "Resampling: 2x", size=8.5)
    label(ax, 0.77, 0.549, "Ready for Step 2 view", size=8.5, color=MUTED)

    group_box(ax, 0.755, 0.46, 0.16, 0.05, "Log")
    label(ax, 0.77, 0.49, "[INFO] Processing completed.", size=8.3, color=MUTED)

    group_box(ax, 0.05, 0.18, 0.18, 0.20, "Slice File")
    label(ax, 0.065, 0.315, "Input:", size=9)
    line_edit(ax, 0.105, 0.295, 0.11, 0.04, "impact_02.bmaslice.parquet")
    label(ax, 0.065, 0.247, "Source scene is fixed here.", size=8.5, color=MUTED)

    group_box(ax, 0.25, 0.18, 0.18, 0.20, "Resampling")
    checkbox(ax, 0.265, 0.32, "Enable Resampling", checked=True)
    label(ax, 0.265, 0.275, "Factor:", size=9)
    line_edit(ax, 0.315, 0.255, 0.08, 0.04, "2x")
    label(ax, 0.265, 0.203, "Applied after slice load.", size=8.4, color=MUTED)

    group_box(ax, 0.45, 0.18, 0.29, 0.20, "Processing Mode")
    radio(ax, 0.465, 0.318, "Raw", checked=False)
    radio(ax, 0.53, 0.318, "Standard", checked=True)
    radio(ax, 0.62, 0.318, "Advanced", checked=False)
    button(ax, 0.615, 0.285, 0.11, 0.04, "Advanced Settings...")
    label(ax, 0.465, 0.248, "Mode affects smoothing / derivative / filtering only.", size=8.5, color=MUTED)
    label(ax, 0.465, 0.222, "The scene slice itself does not change here.", size=8.5, color=MUTED)

    round_box(ax, 0.76, 0.18, 0.17, 0.20)
    button(ax, 0.78, 0.315, 0.13, 0.045, "Run Processing", primary=True)
    button(ax, 0.78, 0.26, 0.13, 0.040, "Save Processed Result")
    button(ax, 0.78, 0.205, 0.13, 0.040, "Open in Step 2")
    label(ax, 0.78, 0.185, ".bmaproc.parquet", size=8.3, color=MUTED)

    return fig


def draw_step2():
    fig, ax = fig_ax(15.5, 10)
    label(ax, 0.03, 0.965, "Step 2: Results Analysis", size=16, bold=True)

    group_box(ax, 0.03, 0.85, 0.94, 0.09, "Time Window")
    label(ax, 0.05, 0.905, "Active File:", size=9)
    label(ax, 0.115, 0.905, "impact_02_standard.bmaproc.parquet", size=9)
    label(ax, 0.53, 0.905, "Number of Samples:", size=9)
    label(ax, 0.64, 0.905, "1201", size=9)
    label(ax, 0.05, 0.875, "Full: 0.000s ~ 118.520s | Slice: 40.000s ~ 70.000s", size=8.8, color=MUTED)
    ax.add_patch(Rectangle((0.05, 0.857), 0.22, 0.012, facecolor=GREY_BAR, edgecolor="none"))
    ax.add_patch(Rectangle((0.27, 0.857), 0.18, 0.012, facecolor=LIGHT_GREEN, edgecolor="none"))
    ax.add_patch(Rectangle((0.45, 0.857), 0.38, 0.012, facecolor=GREY_BAR, edgecolor="none"))

    # Body
    group_box(ax, 0.03, 0.34, 0.18, 0.46, "1. Result Files")
    button(ax, 0.05, 0.74, 0.13, 0.04, "Load Processed Result...")
    button(ax, 0.05, 0.69, 0.13, 0.04, "Use In-Memory Result")
    label(ax, 0.05, 0.655, "Folder Path:", size=8.8)
    line_edit(ax, 0.05, 0.615, 0.13, 0.04, "D:/DropTest/Processed")
    for idx, name in enumerate([
        "impact_02_standard.bmaproc.parquet",
        "impact_02_raw.bmaproc.parquet",
        "impact_01_standard.bmaproc.parquet",
    ]):
        yy = 0.56 - idx * 0.07
        round_box(ax, 0.05, yy, 0.13, 0.05, fc="#eef5ff" if idx == 0 else PANEL, ec="#b7c5d6", lw=0.8, radius=0.008)
        label(ax, 0.058, yy + 0.032, name, size=7.8, va="center")

    group_box(ax, 0.23, 0.34, 0.44, 0.46, "2. Data Selection")
    round_box(ax, 0.25, 0.48, 0.40, 0.27, fc="#fbfcfd", ec=BORDER, lw=0.8, radius=0.01)
    label(ax, 0.265, 0.73, "Select Data to Plot", size=9.5, bold=True)
    items = [
        "Velocity / CoM / Box Local X",
        "Velocity / CoM / Box Local Y",
        "Velocity / CoM / Box Local Z",
        "Analysis / C1 / Relative Height",
    ]
    yy = 0.69
    for item in items:
        checkbox(ax, 0.27, yy - 0.012, item, checked=True)
        yy -= 0.05
    label(ax, 0.255, 0.46,
          "Displayed names expand export keys into readable labels, for example Velocity X (Box Local Frame).",
          size=8.3, color=MUTED)
    button(ax, 0.25, 0.39, 0.09, 0.04, "Clear Selection")
    button(ax, 0.35, 0.39, 0.11, 0.04, "Plot Selected Results")
    button(ax, 0.47, 0.39, 0.13, 0.04, "Open Popup (Current Selection)")
    button(ax, 0.52, 0.345, 0.10, 0.04, "Close All Popups")
    label(ax, 0.25, 0.355, "Opened Popups: 1", size=8.6)
    label(ax, 0.39, 0.355, "Checked Columns: 4", size=8.6)

    group_box(ax, 0.69, 0.34, 0.28, 0.46, "3. Peak & Point Selection / 4. Export Analysis Input")
    label(ax, 0.71, 0.745, "Target:", size=9)
    line_edit(ax, 0.76, 0.723, 0.18, 0.04, "Velocity / CoM / Box Local X")
    label(ax, 0.71, 0.69, "Peak search uses the metric currently selected in Target.", size=8.3, color=MUTED)
    button(ax, 0.71, 0.63, 0.05, 0.035, "Abs Max")
    button(ax, 0.77, 0.63, 0.04, 0.035, "Max")
    button(ax, 0.82, 0.63, 0.04, 0.035, "Min")
    label(ax, 0.71, 0.59, "Selected Point: 25.400s", size=8.8)
    button(ax, 0.83, 0.575, 0.11, 0.04, "Export Point Data...")

    checkbox(ax, 0.71, 0.515, "Manual Offset", checked=False)
    checkbox(ax, 0.83, 0.515, "Manual Height", checked=False)
    for idx in range(3):
        y = 0.47 - idx * 0.055
        label(ax, 0.71, y + 0.02, f"Offset{idx}:", size=8.8)
        line_edit(ax, 0.77, y, 0.05, 0.035, f"C{idx + 1}")
        line_edit(ax, 0.84, y, 0.04, 0.035, "H")
    label(ax, 0.71, 0.31, "Run Time:", size=8.8)
    line_edit(ax, 0.78, 0.292, 0.08, 0.035, "0.1")
    label(ax, 0.71, 0.267, "Step:", size=8.8)
    line_edit(ax, 0.78, 0.249, 0.08, 0.035, "1e-7")
    label(ax, 0.71, 0.224, "Scene Name:", size=8.8)
    line_edit(ax, 0.78, 0.206, 0.12, 0.035, "impact_02")
    button(ax, 0.78, 0.155, 0.14, 0.042, "Export Scenario CSV")

    group_box(ax, 0.03, 0.05, 0.94, 0.24, "Main Plot")
    draw_toolbar(ax, 0.05, 0.25, 0.90, 0.025)
    draw_main_plot(fig, ax, 0.06, 0.09, 0.88, 0.14)

    return fig


def save_fig(fig, path):
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = [
        OUT_DIR / "step1_scene_slice_mock_v34.png",
        OUT_DIR / "step15_slice_processing_mock_v34.png",
        OUT_DIR / "step2_processed_result_mock_v34.png",
    ]
    save_fig(draw_step1(), paths[0])
    save_fig(draw_step15(), paths[1])
    save_fig(draw_step2(), paths[2])
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
