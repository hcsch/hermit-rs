#!/usr/bin/env python3

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import itertools

CONFIGS_KIND = ["hermit", "linux"]
CONFIGS_NUM_PARALLEL = [1, 2, 4]

fig, ax_grid = plt.subplots(
    figsize=(12, 8),
    nrows=len(CONFIGS_KIND) * 2,
    ncols=len(CONFIGS_NUM_PARALLEL),
    sharey=True,
    sharex=True,
)

for (kind, balloon_name), ax_row in zip(
    itertools.product(
        CONFIGS_KIND,
        ["without-balloon", "with-balloon"],
    ),
    ax_grid,
):
    for n, ax in zip(CONFIGS_NUM_PARALLEL, ax_row):
        ax.set_title(
            f"{kind} ×{n} {balloon_name}",
            loc="left",
            fontstyle="oblique",
            fontsize="medium",
        )

        measurements = pd.read_csv(f"measurements/{kind}-{balloon_name}-{n}.csv")
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

plt.savefig(f"measurements/plot.svg")
