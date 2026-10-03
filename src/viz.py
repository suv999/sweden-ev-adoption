"""Shared chart style and helpers for the analysis notebooks.

Palette: validated default categorical slots (blue, orange, aqua) for identity, one-hue blue ramp
for magnitude, blue <-> red with a grey midpoint for polarity. Chrome is kept recessive.
"""
from pathlib import Path
import matplotlib as mpl
import pandas as pd

BONUS_END = pd.Timestamp("2022-11-08")

BLUE, ORANGE, AQUA, RED = "#2a78d6", "#eb6834", "#1baf7a", "#e34948"
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
GREY_DARK, GREY_LIGHT, SURFACE = "#6f6e69", "#b5b3ab", "#fcfcfb"
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

PCT = mpl.ticker.PercentFormatter(1.0, decimals=0)


def apply_style():
    mpl.rcParams.update({
        "figure.figsize": (10, 4.2), "figure.dpi": 110, "savefig.dpi": 150, "savefig.bbox": "tight",
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS, "axes.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
        "axes.grid": True, "axes.grid.axis": "y", "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlepad": 12,
        "axes.labelcolor": INK2, "text.color": INK, "xtick.color": MUTED, "ytick.color": MUTED,
        "ytick.left": False, "lines.linewidth": 2, "legend.frameon": False,
        "font.family": "sans-serif", "font.sans-serif": ["Segoe UI", "DejaVu Sans"],
    })


def blue_cmap():
    return mpl.colors.LinearSegmentedColormap.from_list("blue_ramp", BLUE_RAMP)


def mark_bonus(ax, y=0.97):
    ax.axvline(BONUS_END, color=AXIS, lw=1, zorder=0)
    ax.annotate("Bonus ends 8 Nov 2022", (BONUS_END, y), xycoords=("data", "axes fraction"),
                xytext=(4, 0), textcoords="offset points", fontsize=8.5, color=INK2, va="top")


def label_end(ax, s, text, dy=0):
    s = s.dropna()
    ax.annotate(text, (s.index[-1], s.iloc[-1]), xytext=(6, dy), textcoords="offset points",
                fontsize=9, color=INK2, va="center")


def save(fig, name, figs_dir):
    Path(figs_dir).mkdir(parents=True, exist_ok=True)
    fig.savefig(Path(figs_dir) / f"{name}.png")
