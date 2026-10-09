#!/usr/bin/env bash
set -eo pipefail
project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source /opt/ros/jazzy/setup.bash
if [[ ! -f "$project_root/install/local_setup.bash" ]]; then
  echo 'Build first: bash scripts/build.sh' >&2
  exit 1
fi
source "$project_root/install/local_setup.bash"
set -u
cd "$project_root"
mode=${1:---unit}
case "$mode" in --unit|--gpu|--endurance) ;; *) echo 'Usage: bash scripts/check.sh [--unit|--gpu|--endurance]' >&2; exit 2;; esac
python3 scripts/fetch_dependencies.py --offline
ctest --test-dir build/livox_lidar_simulation_gz --output-on-failure
if [[ "$mode" != --unit ]]; then
  python3 test/avia_runtime.py --output run/check/avia_specification
  python3 test/robot_integration_runtime.py --output run/check/robot_integration
  python3 test/smoke_runtime.py --output run/check/single
  python3 test/multi_runtime.py --output run/check/dual
  python3 test/multi_runtime.py --mixed --output run/check/mixed
  python3 test/release_runtime.py --moving --seconds 10 --output run/check/moving
  python3 test/release_runtime.py --model avia --seconds 6 --output run/check/avia
  python3 test/release_runtime.py --model avia --moving --seconds 6 --output run/check/avia_moving
fi
if [[ "$mode" == --endurance ]]; then
  python3 test/release_runtime.py --seconds 300 --output run/check/endurance_mid360
  python3 test/release_runtime.py --model avia --seconds 60 --output run/check/endurance_avia
fi
