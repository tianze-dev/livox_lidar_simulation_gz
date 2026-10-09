# Livox LiDAR Simulation for Gazebo

An unofficial, standalone Livox simulation suite using RGL, ROS 2 Jazzy and Gazebo Harmonic.
The repository root is one ROS package, suitable for a pinned Git submodule in a parent workspace.
No other robot workspace is used as a dependency.

## Supported features

- MID-360: detailed colored mesh, lightweight collision, manufacturer nominal extrinsics, standard PointCloud2/IMU, static and moving demos.
- Avia: official CAD-derived detailed appearance, lightweight collision, non-repetitive scan-pattern and standard-interface preview. Measurement/IMU origins remain approximations. See [asset provenance and pending public redistribution terms](meshes/avia/NOTICE.md).
- One geometric return per ray, whole-frame snapshots, finite scan-pattern replay. No per-point timestamps, motion distortion, CustomMsg, FAST-LIVO2, CSV conversion or hardware protocol emulation.

Version 0.1.0 is a prerelease. See [support matrix](docs/SUPPORT.md), [integration](docs/INTEGRATION.md) and [contributing](CONTRIBUTING.md).

Both models include optional PBR GLB assets; DAE remains the default. For GLB, set
`visual_mesh:=package://livox_lidar_simulation_gz/meshes/<model>/<model>.glb`
and `mesh_rpy:="1.5707963267948966 0 0"` (Y-up to Z-up, visual only).
`config/demos/mixed_glb.yaml` provides both models with this correction.
Metal surfaces appear darker under the current Gazebo lighting; full material-extension
fidelity and RViz GLB appearance have not been validated. Collision and sensor frames are unchanged.

## Build

Target: Ubuntu 24.04 x86_64, ROS 2 Jazzy, Gazebo Harmonic, supported NVIDIA GPU/driver.
System dependencies are declared in package.xml. Review and install them with rosdep if needed.

```bash
source /opt/ros/jazzy/setup.bash
python3 scripts/fetch_dependencies.py
bash scripts/build.sh
source install/local_setup.bash
```

Downloads are pinned and SHA256-checked. Configure/build never downloads dependencies implicitly.
Use `--offline` to validate a complete cache. A custom download `--cache-dir PATH` corresponds to `-DLIVOX_RGL_CACHE=PATH` in CMake.

## Run and test

```bash
bash scripts/run.sh gui:=false rviz:=false
bash scripts/run.sh model:=avia name:=avia gui:=false rviz:=false
bash scripts/run.sh moving:=true
bash scripts/run.sh model_view:=true
bash scripts/check.sh --unit
bash scripts/check.sh --gpu
bash scripts/check.sh --endurance
python3 scripts/release_check.py
```

Each default sensor publishes `/livox/<name>/points` and `/livox/<name>/imu` at 10 Hz and 200 Hz in simulation time. PointCloud2 has float32 x/y/z/intensity, point_step=16. Only hits are returned. Intensity is Gazebo laser_retro, not calibrated reflectivity.

The moving fixture uses actual Gazebo joint states to drive dynamic TF; its rail travel is limited to ±2.5 m. Defaults are 0.1 m/s and 0.15 rad/s. It is a validation fixture, not a navigation stack.

`sensor.launch.py` only creates bridges and does not own a world, GUI, robot or TF. The parent owns integration-specific transforms and lifecycle. Keep sensor names unique even across namespaces.

## Container

```bash
docker build -f docker/Dockerfile -t livox-gz:0.1.0 .
docker run --rm --gpus all livox-gz:0.1.0 python3 test/smoke_runtime.py
```

The image builds and runs unit tests without a GPU; runtime tests require NVIDIA Container Toolkit and a GPU. The container does not mount host workspaces. CPU CI does not claim GPU tests passed. The base image is digest-pinned, but apt packages are resolved at build time.

## License

Original project code: Apache-2.0. Upstream code and assets retain their notices and applicable terms; see LICENSE, NOTICE and THIRD_PARTY_NOTICES.md. The MID-360 asset redistribution basis is separately recorded in meshes/mid360/NOTICE.md. No official endorsement is implied.
