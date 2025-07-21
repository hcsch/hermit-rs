#!/usr/bin/env python3

from typing import Optional
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


timings: Optional[pd.DataFrame] = None

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

        single_timings = pd.read_csv(
            f"measurements/{kind}-{balloon_name}-{amp_name}-{n}-timings.csv"
        )

        single_timings["kind"] = kind
        single_timings["with_balloon"] = balloon_name
        single_timings["with_amp"] = amp_name
        single_timings["num_parallel"] = n

        single_timings = single_timings.set_index(
            ["num_parallel", "with_amp", "kind", "with_balloon", "pid"]
        )

        if timings is None:
            timings = single_timings
        else:
            timings = pd.concat([timings, single_timings])

print(timings)

mean_timings = timings.groupby(
    by=["num_parallel", "with_amp", "kind", "with_balloon"]
).mean()

mean_timings["rel_overhead"] = (
    mean_timings["workload_runtime_s"]
    / mean_timings.loc[1, "without-amp", "hermit", "without-balloon"][
        "workload_runtime_s"
    ]
    - 1.0
) * 100.0

fig, ax_grid = plt.subplots(
    figsize=(6, 8),
    nrows=len(CONFIGS_AMP) * len(CONFIGS_BALLOON),
    ncols=len(CONFIGS_KIND),
    sharey=True,
    sharex=True,
)

for (amp_name, balloon_name), ax_row in zip(
    itertools.product(CONFIGS_AMP, CONFIGS_BALLOON),
    ax_grid,
):
    for kind, ax in zip(CONFIGS_KIND, ax_row):
        ax.set_title(
            f"{kind} {balloon_name} {amp_name}",
            loc="left",
            fontstyle="oblique",
            fontsize="medium",
        )

        plot = mean_timings["rel_overhead"][:, amp_name, kind, balloon_name].plot(
            kind="bar", rot=0, grid=True, ylabel="exec time overhead [%]", ax=ax
        )

fig.tight_layout()
fig.savefig(f"measurements/timings.svg")
