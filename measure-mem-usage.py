#!/usr/bin/env python3

import os
import subprocess
import shutil
import re
import pandas as pd
from dataclasses import dataclass
from sys import stderr
from tempfile import TemporaryDirectory
from pathlib import Path
from typing import Callable, Optional
from datetime import datetime, timezone

LINUX_VM_IMAGE = "result/nixos.qcow2"

HERMIT_LOADER_EXECUTABLE = "../loader/target/release/hermit-loader-x86_64"
HERMIT_EXECUTABLE = "target/x86_64-unknown-hermit/release/dyn_mem"

AMP_EXECUTABLE = "target/release/artificial-mem-pressure"

NICENESS = 10

QEMU_COMMON_ARGS = [
    "-enable-kvm",
    "-cpu",
    "host",
    "-smp",
    "1",
    "-m",
    "6G",
    "-display",
    "none",
    "-serial",
    "stdio",
]
QEMU_BALLOON_ARGS = [
    "-device",
    "virtio-balloon-pci,disable-legacy=on,free-page-reporting=on",
]
QEMU_HERMIT_ARGS = [
    "-device",
    "isa-debug-exit,iobase=0xf4,iosize=0x04",
]
QEMU_LINUX_ARGS = [
    # Another serial device for /dev/ttyS1 which we tell Linux to open a console on
    # We don't really want the output. We just want Linux to also log events to be fair.
    "-serial",
    "null",
]

PS_KEYS = ["pid", "uss", "rss", "pss", "min_flt", "maj_flt", "oom", "oomadj"]


@dataclass(frozen=True)
class Paths:
    nice: Path
    taskset: Path
    qemu: Path
    ps: Path

    def __init__(self):
        executables = {
            "qemu": "qemu-system-x86_64",
            **{n: n for n in ["nice", "taskset", "ps"]},
        }

        for attribute_name, executable_name in executables.items():
            path = shutil.which(executable_name)
            if path is None:
                raise Exception(f"Could not find {executable_name}")
            path = Path(path)
            self.__dict__[attribute_name] = path


def start_linux_vm(
    paths: Paths,
    tmp_dir: Path,
    unique_id: int,
    with_balloon: bool,
) -> subprocess.Popen[bytes]:
    image_file = tmp_dir / f"linux-vm-{unique_id}.qcow2"
    shutil.copyfile(LINUX_VM_IMAGE, image_file, follow_symlinks=True)

    process = subprocess.Popen(
        [
            paths.nice,
            "-n",
            str(NICENESS),
            paths.taskset,
            "-c",
            f"{1 + unique_id}",
            paths.qemu,
            *QEMU_COMMON_ARGS,
            *QEMU_LINUX_ARGS,
            *(QEMU_BALLOON_ARGS if with_balloon else []),
            "-drive",
            f"file={image_file}",
        ],
        stdout=subprocess.PIPE,
    )

    print(f"Started Linux VM with pid {process.pid}", file=stderr)

    return process


def start_hermit_vm(
    paths: Paths,
    tmp_dir: Path,
    unique_id: int,
    with_balloon: bool,
) -> subprocess.Popen[bytes]:

    process = subprocess.Popen(
        [
            paths.nice,
            "-n",
            str(NICENESS),
            paths.taskset,
            "-c",
            f"{1 + unique_id}",
            paths.qemu,
            *QEMU_COMMON_ARGS,
            *QEMU_HERMIT_ARGS,
            *(QEMU_BALLOON_ARGS if with_balloon else []),
            "-kernel",
            HERMIT_LOADER_EXECUTABLE,
            "-initrd",
            HERMIT_EXECUTABLE,
        ],
        stdout=subprocess.PIPE,
    )

    print(f"Started Hermit VM with pid {process.pid}", file=stderr)

    return process


def parse_ps_output(now: float, ps_stdout: bytes) -> pd.DataFrame:
    # strip column header line
    lines = ps_stdout.splitlines()[1:]
    assert len(lines) >= 1

    return pd.DataFrame.from_records(
        [(now, *(int(column) for column in line.split())) for line in lines],
        columns=["elapsed_s", *PS_KEYS],
        index=["elapsed_s", "pid"],
    )


def parse_vm_output(pid: int, vm_stdout: bytes) -> pd.DataFrame:
    # strip column header line
    match = re.search(b"<dyn-mem> end -- \\{elapsed: ([^}]+)\\}", vm_stdout)
    assert match is not None

    return pd.DataFrame.from_records(
        [(pid, float(match.group(1)))],
        columns=["pid", "workload_runtime_s"],
        index="pid",
    )


StartFn = Callable[[Paths, Path, int, bool], subprocess.Popen[bytes]]


@dataclass(frozen=True, slots=True, kw_only=True)
class MeasurementResult:
    measurements: pd.DataFrame
    timings: pd.DataFrame


def run_measurement(
    paths: Paths,
    tmp_dir: Path,
    num_parallel: int,
    start_fn: StartFn,
    success_returncode: int,
    with_balloon: bool,
    with_amp: bool,
) -> MeasurementResult:
    print(f"Running measurement with {num_parallel} VMs")

    start = datetime.now(timezone.utc).timestamp()

    vm_processes = []

    amp_process: Optional[subprocess.Popen[bytes]] = None

    try:
        measurements: Optional[pd.DataFrame] = None

        vm_processes = [
            start_fn(paths, tmp_dir, i, with_balloon) for i in range(num_parallel)
        ]

        while any(map(lambda p: p.poll() is None, vm_processes)):
            now = datetime.now(timezone.utc).timestamp() - start

            if with_amp and (amp_process is None or amp_process.poll() is not None):
                if amp_process is not None and amp_process.returncode != 0:
                    raise Exception(
                        f"Artificial memory pressure process failed with non-zero exit code {amp_process.returncode}"
                    )

                amp_process = subprocess.Popen([AMP_EXECUTABLE])

            # Run ps and artificial-mem-pressure concurrently
            ps_process = subprocess.Popen(
                [
                    paths.ps,
                    "--pid",
                    ",".join(map(lambda p: f"{p.pid}", vm_processes)),
                    "-o",
                    ",".join(PS_KEYS),
                ],
                stdout=subprocess.PIPE,
            )

            ps_stdout, _ = ps_process.communicate(timeout=1)
            if ps_process.returncode != 0:
                print(
                    f"ps exited with non-zero exit code {ps_process.returncode}",
                    file=stderr,
                )
                raise Exception("ps failed")

            if measurements is None:
                measurements = parse_ps_output(now, ps_stdout)
            else:
                measurements = pd.concat(
                    [measurements, parse_ps_output(now, ps_stdout)]
                )

        timings: Optional[pd.DataFrame] = None
        for vm_process in vm_processes:
            vm_stdout, _ = vm_process.communicate(timeout=1)
            if vm_process.returncode != success_returncode:
                print(
                    f"ps exited with non-success (!={success_returncode}) exit code {vm_process.returncode}",
                    file=stderr,
                )
                raise Exception("a VM process failed")

            vm_timing = parse_vm_output(vm_process.pid, vm_stdout)

            print(vm_timing)

            if timings is None:
                timings = vm_timing
            else:
                timings = pd.concat([timings, vm_timing])
    finally:
        processes_for_cleanup = vm_processes
        if amp_process is not None:
            processes_for_cleanup.append(amp_process)

        for process in processes_for_cleanup:
            if process.poll() is None:
                print(
                    f"Process {process.args} was left running after run scope, killing..."
                )
                process.kill()

    assert measurements is not None
    assert timings is not None

    return MeasurementResult(measurements=measurements, timings=timings)


CONFIGS_NUM_PARALLEL = [1, 2, 4]
CONFIGS_KIND = {"hermit": (start_hermit_vm, 3), "linux": (start_linux_vm, 0)}
CONFIGS_BALLOON = {"without-balloon": False, "with-balloon": True}
CONFIGS_AMP = {"without-amp": False, "with-amp": True}


def measure_qualitative_overview(
    paths: Paths,
):
    os.makedirs("measurements/qualitative", exist_ok=True)

    print(f"Running qualitative overview measurements...", file=stderr)
    for kind_name, (start_fn, success_returncode) in CONFIGS_KIND.items():
        print(f"Running {kind_name} measurements...", file=stderr)
        for balloon_name, with_balloon in CONFIGS_BALLOON.items():
            print(f"Running measurements {balloon_name}...", file=stderr)
            for amp_name, with_amp in CONFIGS_AMP.items():
                print(f"Running measurements {amp_name}...", file=stderr)
                for num_parallel in CONFIGS_NUM_PARALLEL:
                    print(f"Running measurement for {num_parallel} VMs...", file=stderr)
                    with TemporaryDirectory(suffix="mem-usage-linux") as tmp_dir:
                        result = run_measurement(
                            paths,
                            Path(tmp_dir),
                            num_parallel,
                            start_fn,
                            success_returncode,
                            with_balloon,
                            with_amp,
                        )

                        result.measurements.to_csv(
                            f"measurements/qualitative/{kind_name}-{balloon_name}-{amp_name}-{num_parallel}-measurements.csv"
                        )
                        result.timings.to_csv(
                            f"measurements/qualitative/{kind_name}-{balloon_name}-{amp_name}-{num_parallel}-timings.csv"
                        )
                    print(
                        f"Done running measurement for {num_parallel} VMs", file=stderr
                    )
                print(f"Done running measurements {amp_name}", file=stderr)
            print(f"Done running measurements {balloon_name}", file=stderr)
        print(f"Done running {kind_name} measurements", file=stderr)
    print(f"Done running qualitative overview measurements", file=stderr)


CONFIGS_FOR_QUANTITATIVE_MEASUREMENTS = [
    ("hermit", "without-balloon", "without-amp", 1),
    ("hermit", "with-balloon", "without-amp", 1),
    ("linux", "without-balloon", "without-amp", 1),
    ("linux", "with-balloon", "without-amp", 1),
    ("hermit", "without-balloon", "with-amp", 1),
    ("hermit", "with-balloon", "with-amp", 1),
    ("linux", "without-balloon", "with-amp", 1),
    ("linux", "with-balloon", "with-amp", 1),
]
QUANTITATIVE_NUM_SAMPLES = 20


def measure_quantitative_details(paths: Paths):
    os.makedirs("measurements/quantitative", exist_ok=True)

    print(f"Running quantitative detail measurements...", file=stderr)
    for (
        kind_name,
        balloon_name,
        amp_name,
        num_parallel,
    ) in CONFIGS_FOR_QUANTITATIVE_MEASUREMENTS:
        start_fn, success_returncode = CONFIGS_KIND[kind_name]
        with_balloon = CONFIGS_BALLOON[balloon_name]
        with_amp = CONFIGS_AMP[amp_name]

        print(
            f"Running measurements with config {{{kind_name=}, {balloon_name=}, {amp_name=}, {num_parallel=}}}...",
            file=stderr,
        )
        for i in range(QUANTITATIVE_NUM_SAMPLES):
            with TemporaryDirectory(suffix="mem-usage-linux") as tmp_dir:
                result = run_measurement(
                    paths,
                    Path(tmp_dir),
                    num_parallel,
                    start_fn,
                    success_returncode,
                    with_balloon,
                    with_amp,
                )

                result.measurements.to_csv(
                    f"measurements/quantitative/{kind_name}-{balloon_name}-{amp_name}-{num_parallel}-i{i}-measurements.csv"
                )
                result.timings.to_csv(
                    f"measurements/quantitative/{kind_name}-{balloon_name}-{amp_name}-{num_parallel}-i{i}-timings.csv"
                )
        print(
            f"Done running measurement with config {{{kind_name=}, {balloon_name=}, {amp_name=}, {num_parallel=}}}",
            file=stderr,
        )
    print(f"Done running quantitative detail measurements", file=stderr)


def main():
    paths = Paths()

    measure_quantitative_details(paths)
    measure_qualitative_overview(paths)


if __name__ == "__main__":
    main()
