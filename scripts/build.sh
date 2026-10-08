#!/usr/bin/env bash
# Build only this checkout, with outputs rooted here. No dependency downloads.
set -eo pipefail
project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source /opt/ros/jazzy/setup.bash
set -u
cd "$project_root"
colcon --log-base "$project_root/log" build --base-paths "$project_root" \
  --packages-select livox_lidar_simulation_gz \
  --build-base "$project_root/build" --install-base "$project_root/install" \
  --executor sequential --event-handlers console_direct+ \
  --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo "$@"
