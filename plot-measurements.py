#!/usr/bin/env python3

from typing import Optional
from matplotlib.axes import Axes
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


def plot_rss_measurement(
    *, ax: Axes, kind: str, balloon_name: str, amp_name: str, num_parallel: int
):
    ax.set_title(
        f"{kind} {amp_name} {balloon_name} {num_parallel}×",
        loc="left",
        fontstyle="oblique",
        fontsize="medium",
    )

    measurements = pd.read_csv(
        f"measurements/{kind}-{balloon_name}-{amp_name}-{num_parallel}-measurements.csv"
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


print("plotting rss measurements overview...")

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
    for num_parallel, ax in zip(CONFIGS_NUM_PARALLEL, ax_row):
        plot_rss_measurement(
            ax=ax,
            kind=kind,
            balloon_name=balloon_name,
            amp_name=amp_name,
            num_parallel=num_parallel,
        )

fig.tight_layout()
fig.savefig(f"measurements/plot.svg")


print("plotting rss comparison pairs")

COMPARISON_PAIRS = [
    (
        ("hermit", "without-balloon", "without-amp", 1),
        ("hermit", "with-balloon", "without-amp", 1),
    ),
    (
        ("linux", "without-balloon", "without-amp", 1),
        ("linux", "with-balloon", "without-amp", 1),
    ),
    (
        ("hermit", "with-balloon", "without-amp", 1),
        ("linux", "with-balloon", "without-amp", 1),
    ),
    (
        ("hermit", "with-balloon", "with-amp", 2),
        ("hermit", "with-balloon", "without-amp", 4),
    ),
]

for comparison_index, (left, right) in enumerate(COMPARISON_PAIRS):
    fig, ax_row = plt.subplots(
        figsize=(8, 4),
        nrows=1,
        ncols=2,
        sharey=True,
        sharex=True,
    )

    for (kind, balloon_name, amp_name, num_parallel), ax in zip(
        [left, right],
        ax_row,
    ):
        plot_rss_measurement(
            ax=ax,
            kind=kind,
            balloon_name=balloon_name,
            amp_name=amp_name,
            num_parallel=num_parallel,
        )

    fig.tight_layout()
    fig.savefig(f"measurements/comparison-{comparison_index}.svg")


print("plotting workload execution times")

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


mean_timings = timings.groupby(
    by=["num_parallel", "with_amp", "kind", "with_balloon"]
).mean()

fig, ax_col = plt.subplots(
    figsize=(5, 8),
    nrows=len(CONFIGS_AMP) * len(CONFIGS_BALLOON),
    ncols=1,
    sharey=True,
    sharex=True,
)

for (amp_name, balloon_name), ax in zip(
    itertools.product(CONFIGS_AMP, CONFIGS_BALLOON),
    ax_col,
):
    ax.set_title(
        f"{balloon_name} {amp_name}",
        loc="left",
        fontstyle="oblique",
        fontsize="medium",
    )

    plot = (
        mean_timings["workload_runtime_s"][:, amp_name, :, balloon_name]
        .unstack(level="kind")
        .plot.bar(
            ylabel="workload runtime [s]",
            rot=0,
            color=["tab:orange", "tab:blue"],
            ax=ax,
        )
    )
    plot.legend(loc="upper right", bbox_to_anchor=(1.5, 1.0))

fig.tight_layout()
fig.savefig(f"measurements/timings.svg")
