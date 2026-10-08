#!/usr/bin/env bash
# Read-only development prerequisite check. Does not install or start simulation.
set -eo pipefail

if [[ ! -r /opt/ros/jazzy/setup.bash ]]; then
  echo 'FAIL: ROS 2 Jazzy setup is missing.'
  exit 1
fi
source /opt/ros/jazzy/setup.bash
set -u

failures=0
for tool in cmake c++ colcon ros2 gz python3 timeout; do
  if command -v "$tool" >/dev/null 2>&1; then
    echo "OK: $tool"
  else
    echo "FAIL: $tool is missing"
    failures=$((failures + 1))
  fi
done

if command -v ros2 >/dev/null 2>&1; then
  for package in ament_cmake ament_cmake_python gz_cmake_vendor gz_plugin_vendor gz_sim_vendor gz_msgs_vendor ros_gz_sim ros_gz_bridge xacro robot_state_publisher rviz2; do
    if ros2 pkg prefix "$package" >/dev/null 2>&1; then
      echo "OK: ROS package $package"
    else
      echo "FAIL: ROS package $package is missing"
      failures=$((failures + 1))
    fi
  done
fi

if command -v gz >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
  if version=$(timeout 15s gz sim --versions 2>&1); then
    echo "Gazebo Sim version: $version"
    if [[ ! "$version" =~ (^|[[:space:]])8\. ]]; then
      echo 'FAIL: Gazebo Sim 8 (Harmonic) was not detected'
      failures=$((failures + 1))
    fi
  else
    echo 'FAIL: Unable to query Gazebo Sim version'
    failures=$((failures + 1))
  fi
fi

if command -v nvidia-smi >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
  if ! timeout 15s nvidia-smi --query-gpu=name,driver_version --format=csv,noheader; then
    echo 'FAIL: NVIDIA driver query failed'
    failures=$((failures + 1))
  fi
else
  echo 'FAIL: NVIDIA driver query is unavailable'
  failures=$((failures + 1))
fi

echo 'Scope: prerequisite discovery only; not a compile, CUDA/OptiX, RGL or runtime compatibility test.'
echo 'Run from a fresh terminal without other workspace overlays for an isolated check.'
if (( failures > 0 )); then
  echo "FAILED: $failures prerequisite checks"
  exit 1
fi
echo 'PASS: prerequisite discovery'
