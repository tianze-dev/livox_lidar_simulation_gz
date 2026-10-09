# Livox LiDAR Simulation for Gazebo

An unofficial RGL-based Livox simulator for **MID-360, Avia, ROS 2 Jazzy and Gazebo Harmonic**.

Detailed models, GPU point clouds, IMU and TF, with single-sensor, dual-sensor and moving demos. Use it as a standalone ROS package or a Git submodule. Version: 0.1.0 prerelease.

[中文](README.md) · [Integration](docs/INTEGRATION.md) · [Supported features](docs/SUPPORT.md) · [Troubleshooting](docs/TROUBLESHOOTING.md)

## Preview

Default DAE models rendered in Gazebo:

| MID-360 | Avia |
|:---:|:---:|
| ![MID-360 rendered in Gazebo](docs/images/mid360-gazebo.png) | ![Avia rendered in Gazebo](docs/images/avia-gazebo.png) |

Avia scan pattern displayed in RViz, colored by height:

![Avia point cloud in RViz](docs/images/avia-pointcloud.png)

| Model | Rays per frame | Point cloud rate | IMU rate | Simulated range |
|---|---:|---:|---:|---:|
| MID-360 | 20,000 | 10 Hz | 200 Hz | 0.1–40 m |
| Avia | 24,000 | 10 Hz | 200 Hz | 0.1–190 m |

Rates use simulation time; only ray hits are published. DAE is the default appearance format; [optional PBR GLB assets](docs/INTEGRATION.md#可选-glb-外观) are also included.

## Quick start

**Ubuntu 24.04 x86_64, ROS 2 Jazzy, Gazebo Harmonic and an NVIDIA GPU are required.** There is no CPU simulation backend.

```bash
git clone https://github.com/tianze-dev/livox_lidar_simulation_gz.git
cd livox_lidar_simulation_gz
source /opt/ros/jazzy/setup.bash

# Install declared dependencies; rosdep must already be initialized
rosdep install --from-paths . --ignore-src -r -y
bash scripts/check_environment.sh
python3 scripts/fetch_dependencies.py
bash scripts/build.sh
source install/local_setup.bash

# Launch MID-360 with Gazebo and RViz
bash scripts/run.sh
```

RGL dependencies are version-pinned and SHA256-checked, with a local cache in `.deps/rgl`. See [troubleshooting](docs/TROUBLESHOOTING.md) for offline use, custom cache paths and installation issues.

## Demos

Run from the repository root, one demo at a time:

```bash
# Avia
bash scripts/run.sh model:=avia name:=avia
# Close-up model view
bash scripts/run.sh model_view:=true
# Moving rail and turntable
bash scripts/run.sh moving:=true
# MID-360 + Avia
bash scripts/run.sh sensors_file:=config/demos/mixed.yaml
# Headless
bash scripts/run.sh gui:=false rviz:=false
```

Default topics are `/livox/<name>/points` (PointCloud2) and `/livox/<name>/imu` (Imu), alongside `/clock` and TF. The wrapper defaults to ROS domain 119; set `ROS_DOMAIN_ID` to avoid conflicts with other simulations or hardware.

## Robot integration

Place this package under the parent workspace's `src/`, build with colcon and attach the sensor through Xacro. The parent owns the world, robot TF and launch orchestration; `sensor.launch.py` only creates message bridges. See the [integration guide](docs/INTEGRATION.md) for examples.

The simulator uses whole-frame snapshots and an ideal IMU. Per-point timing, motion distortion, CustomMsg and FAST-LIVO2 integration are not provided. MID-360 extrinsics use manufacturer nominal values; Avia extrinsics are approximations. See [support details](docs/SUPPORT.md) for parameters and limitations.

## Tests and contributions

```bash
bash scripts/check.sh --unit       # Unit tests
bash scripts/check.sh --gpu        # GPU runtime regression
bash scripts/check.sh --endurance  # Stability checks
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines. Original code is licensed under [Apache-2.0](LICENSE); third-party code and models retain their [own notices](THIRD_PARTY_NOTICES.md). Public redistribution terms for the Avia CAD-derived assets remain unconfirmed.
