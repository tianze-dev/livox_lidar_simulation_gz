# Livox LiDAR Simulation for Gazebo

基于 RGL 的非官方 Livox 激光雷达仿真套件，支持 **MID-360、Avia、ROS 2 Jazzy 与 Gazebo Harmonic**。

提供精细外观、GPU 点云、IMU 和 TF，支持单雷达、双雷达及移动演示，可作为独立 ROS 包或 Git 子模块使用。当前版本：0.1.0 预发布版。

[English](README.en.md) · [接入指南](docs/INTEGRATION.md) · [支持范围](docs/SUPPORT.md) · [常见问题](docs/TROUBLESHOOTING.md)

## 效果预览

Gazebo 中的默认 DAE 模型：

| MID-360 | Avia |
|:---:|:---:|
| ![MID-360 在 Gazebo 中的外观](docs/images/mid360-gazebo.png) | ![Avia 在 Gazebo 中的外观](docs/images/avia-gazebo.png) |

Avia 扫描点云在 RViz 中的显示效果，颜色表示高度：

![Avia 点云在 RViz 中的显示效果](docs/images/avia-pointcloud.png)

| 型号 | 射线数／帧 | 点云频率 | IMU 频率 | 仿真量程 |
|---|---:|---:|---:|---:|
| MID-360 | 20,000 | 10 Hz | 200 Hz | 0.1–40 m |
| Avia | 24,000 | 10 Hz | 200 Hz | 0.1–190 m |

频率按仿真时间计算；点云仅包含命中点。外观默认使用 DAE，也提供[可选 PBR GLB](docs/INTEGRATION.md#可选-glb-外观)。

## 快速开始

**环境：Ubuntu 24.04 x86_64、ROS 2 Jazzy、Gazebo Harmonic、NVIDIA GPU。** 不提供 CPU 仿真后端。

```bash
git clone https://github.com/tianze-dev/livox_lidar_simulation_gz.git
cd livox_lidar_simulation_gz
source /opt/ros/jazzy/setup.bash

# 安装 package.xml 声明的依赖（需已初始化 rosdep）
rosdep install --from-paths . --ignore-src -r -y
bash scripts/check_environment.sh
python3 scripts/fetch_dependencies.py
bash scripts/build.sh
source install/local_setup.bash

# 启动 MID-360，打开 Gazebo 和 RViz
bash scripts/run.sh
```

RGL 依赖按固定版本下载并校验 SHA256，缓存位于 `.deps/rgl`。离线使用、自定义缓存和安装问题见[排错说明](docs/TROUBLESHOOTING.md)。

## 演示

在仓库根目录执行，每次启动一个演示：

```bash
# Avia
bash scripts/run.sh model:=avia name:=avia
# 模型近景
bash scripts/run.sh model_view:=true
# 移动滑台与转台
bash scripts/run.sh moving:=true
# MID-360 + Avia
bash scripts/run.sh sensors_file:=config/demos/mixed.yaml
# 无界面
bash scripts/run.sh gui:=false rviz:=false
```

默认话题为 `/livox/<name>/points`（PointCloud2）和 `/livox/<name>/imu`（Imu）。演示同时提供 `/clock` 与 TF。`run.sh` 默认使用 ROS domain 119；自定义时设置 `ROS_DOMAIN_ID`，避免与实机或其他仿真冲突。

## 接入机器人

将本包放入父工作空间的 `src/` 后用 colcon 构建，在机器人 Xacro 中挂载雷达。父项目负责世界、机器人 TF 和启动编排，`sensor.launch.py` 只提供消息桥接。完整示例见[接入指南](docs/INTEGRATION.md)。

本包采用整帧快照扫描和理想 IMU，暂不提供逐点时间、运动畸变、CustomMsg 或 FAST-LIVO2 接入。MID-360 外参采用手册名义值，Avia 外参为近似值；详细参数与限制见[支持范围](docs/SUPPORT.md)。

## 测试与贡献

```bash
bash scripts/check.sh --unit       # 单元测试
bash scripts/check.sh --gpu        # GPU 运行回归
bash scripts/check.sh --endurance  # 稳定性检查
```

开发规范见 [CONTRIBUTING.md](CONTRIBUTING.md)。原创代码采用 [Apache-2.0](LICENSE)，第三方代码和模型见[来源声明](THIRD_PARTY_NOTICES.md)；Avia CAD 衍生资产的公开再分发条件仍待确认。
