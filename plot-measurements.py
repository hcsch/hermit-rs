#!/usr/bin/env python3

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import itertools

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

        measurements = pd.read_csv(
            f"measurements/{kind}-{balloon_name}-{amp_name}-{n}.csv"
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
        )
        ax.get_legend().remove()

fig.tight_layout()
fig.savefig(f"measurements/plot.svg")
