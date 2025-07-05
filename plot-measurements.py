#!/usr/bin/env python3

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

CONFIGS_KIND = ["hermit", "linux"]
CONFIGS_NUM_PARALLEL = [1, 2, 4]

fig, ax_grid = plt.subplots(
    figsize=(12, 8),
    nrows=len(CONFIGS_KIND),
    ncols=len(CONFIGS_NUM_PARALLEL),
    sharey=True,
    sharex=True,
)

for kind, ax_row in zip(CONFIGS_KIND, ax_grid):
    for n, ax in zip(CONFIGS_NUM_PARALLEL, ax_row):
        ax.set_title(f"{kind} ×{n}", loc="left", fontstyle="oblique", fontsize="medium")

        for with_balloon, balloon_name in [
            (False, "without-balloon"),
            (True, "with-balloon"),
        ]:
            measurements = pd.read_csv(f"measurements/{kind}-{balloon_name}-{n}.csv")
            # Convert RSS from kibibytes to Gibibytes
            measurements.rss = measurements.rss.astype("float64") / (1024 * 1024)

            measurements.groupby("pid").plot(
                "elapsed_s", "rss", ax=ax, xlabel="t [s]", ylabel="RSS [GiB]"
            )

plt.savefig(f"measurements/plot.svg")
