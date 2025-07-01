#!/usr/bin/env bash

set -o errexit -o nounset -o pipefail

# Build the executable and get its path from `cargo build`'s output
echo "Building the executable..."
EXECUTABLE="$(cargo build -Z build-std=std,core,alloc,panic_abort --release --target x86_64-unknown-linux-musl --message-format json | jq -sr '.[-2].executable')"

echo "Building image..."
virt-builder fedora-42 \
    --format qcow2 \
    --output dyn-mem-f42.qcow2 \
    --selinux-relabel \
    --root-password password:root \
    --upload "$EXECUTABLE:/usr/local/bin/dyn_mem" \
    --upload "dyn-mem.service:/etc/systemd/system/dyn-mem.service" \
    --run-command 'ln -s /etc/systemd/system/dyn-mem.service /etc/systemd/system/multi-user.target.wants/'

echo "Done"
