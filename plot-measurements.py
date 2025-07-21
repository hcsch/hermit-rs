#!/usr/bin/env python3

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import itertools

# Output editable text to the SVGs instead of text rendered to path elements
plt.rcParams["svg.fonttype"] = "none"
plt.rcParams["font.family"] = [
    "NewComputerModernSans10",
    "CMU Sans Serif",
    "sans-serif",
]

CONFIGS_KIND = ["hermit", "linux"]
CONFIGS_BALLOON = ["without-balloon", "with-balloon"]
CONFIGS_AMP = ["without-amp", "with-amp"]
CONFIGS_NUM_PARALLEL = [1, 2, 4]

fig, ax_grid = plt.subplots(
    figsize=(12, 12),
    nrows=len(CONFIGS_KIND) * len(CONFIGS_BALLOON) * len(CONFIGS_AMP),
    ncols=len(CONFIGS_NUM_PARALLEL),
    sharey=True,
    sharex=True,
)

for (amp_name, kind, balloon_name), ax_row in zip(
    itertools.product(CONFIGS_AMP, CONFIGS_KIND, CONFIGS_BALLOON),
    ax_grid,
):
    for n, ax in zip(CONFIGS_NUM_PARALLEL, ax_row):
        ax.set_title(
            f"{kind} ×{n} {balloon_name} {amp_name}",
            loc="left",
            fontstyle="oblique",
            fontsize="medium",
        )

        measurements = pd.read_csv(
            f"measurements/{kind}-{balloon_name}-{amp_name}-{n}-measurements.csv"
        )
        measurements = measurements.set_index(["elapsed_s", "pid"])
        # Convert RSS from kibibytes to Gibibytes
        measurements.rss = measurements.rss.astype("float64") / (1024 * 1024)

        measurements["rss"].unstack(level="pid").plot(
            ax=ax,
            kind="area",
            stacked=True,
            xlabel="t [s]",
            ylabel="RSS [GiB]",
            grid=True,
        )

        ax.get_legend().remove()

fig.tight_layout()
fig.savefig(f"measurements/plot.svg")


fig, ax_grid = plt.subplots(
    figsize=(12, 12),
    nrows=len(CONFIGS_KIND) * len(CONFIGS_BALLOON) * len(CONFIGS_AMP),
    ncols=len(CONFIGS_NUM_PARALLEL),
    sharex=True,
)

for (kind, balloon_name, amp_name), ax_row in zip(
    itertools.product(CONFIGS_KIND, CONFIGS_BALLOON, CONFIGS_AMP),
    ax_grid,
):
    for n, ax in zip(CONFIGS_NUM_PARALLEL, ax_row):
        ax.set_title(
            f"{kind} ×{n} {balloon_name} {amp_name}",
            loc="left",
            fontstyle="oblique",
            fontsize="medium",
        )

        timings = pd.read_csv(
            f"measurements/{kind}-{balloon_name}-{amp_name}-{n}-timings.csv"
        )
        timings.pid = timings.pid.astype("str")
        timings = timings.set_index("pid")

        ax.barh(
            y=timings.index,
            width=timings["workload_runtime_s"],
        )

        ax.set_xlabel("t [s]")


fig.tight_layout()
fig.savefig(f"measurements/timings.svg")
