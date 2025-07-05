#!/usr/bin/env python3

import os
import subprocess
import shutil
import csv
from sys import stderr
from tempfile import TemporaryDirectory
from pathlib import Path
from typing import Any, Callable, List, Tuple
from datetime import datetime, timezone

LINUX_VM_IMAGE = "result/nixos.qcow2"

HERMIT_LOADER_EXECUTABLE = "../loader/target/release/hermit-loader-x86_64"
HERMIT_EXECUTABLE = "target/x86_64-unknown-hermit/release/dyn_mem"

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

PS_KEYS = ["pid", "uss", "rss", "pss", "min_flt", "maj_flt", "oom", "oomadj"]

CONFIGS_NUM_PARALLEL = [1, 2, 4]


def start_linux_vm(
    qemu_path: Path,
    tmp_dir: Path,
    unique_id: int,
    with_balloon: bool,
) -> subprocess.Popen[bytes]:
    image_file = tmp_dir / f"linux-vm-{unique_id}.qcow2"
    shutil.copyfile(LINUX_VM_IMAGE, image_file, follow_symlinks=True)

    process = subprocess.Popen(
        [
            qemu_path,
            *QEMU_COMMON_ARGS,
            *(QEMU_BALLOON_ARGS if with_balloon else []),
            "-drive",
            f"file={image_file}",
        ],
        stdout=subprocess.DEVNULL,
    )

    print(f"Started Linux VM with pid {process.pid}", file=stderr)

    return process


def start_hermit_vm(
    qemu_path: Path,
    tmp_dir: Path,
    unique_id: int,
    with_balloon: bool,
) -> subprocess.Popen[bytes]:

    process = subprocess.Popen(
        [
            qemu_path,
            *QEMU_COMMON_ARGS,
            *QEMU_HERMIT_ARGS,
            *(QEMU_BALLOON_ARGS if with_balloon else []),
            "-kernel",
            HERMIT_LOADER_EXECUTABLE,
            "-initrd",
            HERMIT_EXECUTABLE,
        ],
        stdout=subprocess.DEVNULL,
    )

    print(f"Started Hermit VM with pid {process.pid}", file=stderr)

    return process


StartFn = Callable[[Path, Path, int, bool], subprocess.Popen[bytes]]


def run_measurement(
    qemu_path: Path,
    ps_path: Path,
    tmp_dir: Path,
    num_parallel: int,
    start_fn: StartFn,
    success_returncode: int,
    with_balloon: bool,
) -> List[Tuple[Any, ...]]:
    print(f"Running measurement with {num_parallel} VMs")

    start = datetime.now(timezone.utc).timestamp()

    vm_processes = [
        start_fn(qemu_path, tmp_dir, i, with_balloon) for i in range(num_parallel)
    ]

    measurements: List[Tuple[Any, ...]] = []

    while any(map(lambda p: p.poll() is None, vm_processes)):
        result = subprocess.run(
            [
                ps_path,
                "--pid",
                ",".join(map(lambda p: f"{p.pid}", vm_processes)),
                "-o",
                ",".join(PS_KEYS),
            ],
            capture_output=True,
        )

        now = datetime.now(timezone.utc).timestamp() - start

        if result.returncode != 0:
            print(result, file=stderr)
            raise Exception("ps failed")

        measurements.extend(
            (
                (now, *(int(column) for column in line.split()))
                for line in result.stdout.splitlines()[1:]
            )
        )

        print(result.stdout, file=stderr)

    if any(map(lambda p: p.returncode != success_returncode, vm_processes)):
        print(vm_processes, file=stderr)
        raise Exception("a VM process failed")

    return measurements


def main():
    qemu_path = shutil.which("qemu-system-x86_64")
    if qemu_path is None:
        raise Exception("Could not find qemu-system-x86_64")
    qemu_path = Path(qemu_path)

    ps_path = shutil.which("ps")
    if ps_path is None:
        raise Exception("Could not find ps")
    ps_path = Path(ps_path)

    os.makedirs("measurements", exist_ok=True)

    for start_fn, name, success_returncode in [
        (start_hermit_vm, "hermit", 3),
        (start_linux_vm, "linux", 0),
    ]:
        print(f"Running {name} measurements...", file=stderr)
        for with_balloon, balloon_name in [
            (False, "without-balloon"),
            (True, "with-balloon"),
        ]:
            print(f"Running measurements {balloon_name}...", file=stderr)
            for n in CONFIGS_NUM_PARALLEL:
                print(f"Running measurement for {n} VMs...", file=stderr)
                with TemporaryDirectory(suffix="mem-usage-linux") as tmp_dir:
                    measurements = run_measurement(
                        qemu_path,
                        ps_path,
                        Path(tmp_dir),
                        n,
                        start_fn,
                        success_returncode,
                        with_balloon,
                    )

                    with open(
                        f"measurements/{name}-{balloon_name}-{n}.csv",
                        "w",
                        encoding="utf-8",
                    ) as f:
                        writer = csv.writer(f)
                        writer.writerow(["elapsed_s"] + PS_KEYS)
                        writer.writerows(measurements)
                print(f"Done running measurement for {n} VMs", file=stderr)
            print(f"Done running measurements {balloon_name}", file=stderr)
        print(f"Done running {name} measurements", file=stderr)


if __name__ == "__main__":
    main()
