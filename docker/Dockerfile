# Pinned ROS Jazzy base; no host workspaces or installation trees are mounted.
FROM ros:jazzy-ros-base@sha256:066420e07f60aa18262f2479981def87ebcfcec42eefb0c0c57c4a46098348ca
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git python3-colcon-common-extensions python3-pytest python3-numpy \
    ros-jazzy-ros-gz ros-jazzy-rviz2 ros-jazzy-xacro ros-jazzy-robot-state-publisher \
    ros-jazzy-sensor-msgs-py ros-jazzy-ament-cmake-pytest \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace/src/livox_lidar_simulation_gz
COPY . .
RUN python3 scripts/fetch_dependencies.py && \
    source /opt/ros/jazzy/setup.bash && CMAKE_BUILD_PARALLEL_LEVEL=2 bash scripts/build.sh && \
    source install/local_setup.bash && ctest --test-dir build/livox_lidar_simulation_gz --output-on-failure
ENV NVIDIA_VISIBLE_DEVICES=all NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics
ENTRYPOINT ["/bin/bash", "-c", "source /opt/ros/jazzy/setup.bash && source install/local_setup.bash && exec \"$@\"", "--"]
CMD ["ros2", "launch", "livox_lidar_simulation_gz", "demo.launch.py", "gui:=false", "rviz:=false"]
