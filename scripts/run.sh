#!/usr/bin/env bash
set -eo pipefail
project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source /opt/ros/jazzy/setup.bash
if [[ ! -f "$project_root/install/local_setup.bash" ]]; then
  echo 'Build first: bash scripts/build.sh' >&2
  exit 1
fi
source "$project_root/install/local_setup.bash"
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-119}
export GZ_PARTITION=${GZ_PARTITION:-livox_standalone_$$}
exec ros2 launch livox_lidar_simulation_gz demo.launch.py "$@"
