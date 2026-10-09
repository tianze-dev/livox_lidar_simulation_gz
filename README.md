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

以下示例把一台 MID-360 挂到现有机器人的 `base_link`。机器人应已有可运行的 Gazebo 世界、生成流程和 `robot_state_publisher`；本包不替代整机启动。

### 1 安装到机器人工作空间

从机器人工作空间根目录执行；如果已通过子模块引入，跳过克隆：

```bash
git clone https://github.com/tianze-dev/livox_lidar_simulation_gz.git src/livox_lidar_simulation_gz
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -r -y
python3 src/livox_lidar_simulation_gz/scripts/fetch_dependencies.py
colcon build --symlink-install
source install/setup.bash
```

在引用雷达宏的机器人描述包 `package.xml` 中声明 `<exec_depend>livox_lidar_simulation_gz</exec_depend>`。后续启动 Gazebo、机器人和桥接的终端都需加载同一工作空间环境，并使用相同的 `ROS_DOMAIN_ID` 和 `GZ_PARTITION`。

### 2 在机器人 Xacro 中挂载

将下面内容放到已有机器人的 `<robot xmlns:xacro="http://www.ros.org/wiki/xacro">` 内：

```xml
<xacro:include filename="$(find livox_lidar_simulation_gz)/urdf/livox.xacro"/>

<xacro:livox_lidar
  parent="base_link"
  name="front"
  namespace="robot"
  model="mid360"
  xyz="0.1 0 0.4"
  rpy="0 0 0"/>
```

| 参数 | 示例含义 |
|---|---|
| `parent` | 机器人已有的父链接 `base_link` |
| `name` | 实例名 `front`，同时作为链接和 TF 前缀；多个雷达必须使用不同名称 |
| `namespace` | 话题命名空间；示例生成 `/robot/front/points` 和 `/robot/front/imu` |
| `model` | 型号，可选 `mid360` 或 `avia` |
| `xyz`、`rpy` | 雷达安装底面中心相对父链接的位姿，单位米／弧度；按实际安装位置修改 |
| `points_topic`、`imu_topic` | Gazebo 输出话题，必须与下一步桥接的话题一致 |

宏包含外观、碰撞、惯性、固定关节、雷达和 IMU。默认话题由 `namespace/name` 生成。需要自定义时，宏和桥接同时传入 `points_topic`、`imu_topic`，例如桥接参数 `points_topic:=/sensors/cloud imu_topic:=/sensors/imu`。

### 3 在 Gazebo 世界中启用传感器系统

在机器人使用的 SDF 世界的 `<world>` 内加入以下插件；已有的 Physics、UserCommands 等世界系统保持不变。同一世界各保留一份，不要为每台雷达重复添加：

```xml
<plugin filename="RGLServerPluginManager"
        name="rgl::RGLServerPluginManager">
  <do_ignore_entities_in_lidar_link>true</do_ignore_entities_in_lidar_link>
</plugin>

<plugin filename="gz-sim-imu-system"
        name="gz::sim::systems::Imu"/>
```

用机器人原有的启动流程加载这个世界、展开修改后的 Xacro 并生成机器人；`robot_state_publisher` 也应使用同一份完整机器人描述。无需启动本包的 `demo.launch.py`。

### 4 桥接到 ROS 2

在已加载父工作空间环境的新终端执行：

```bash
ros2 launch livox_lidar_simulation_gz sensor.launch.py \
  model:=mid360 name:=front namespace:=robot bridge_clock:=false
```

这会将 Gazebo 的 `/robot/front/points` 和 `/robot/front/imu` 单向桥接到同名 ROS 2 话题。若父项目没有桥接 `/clock`，将 `bridge_clock` 改为 `true`；整个仿真只保留一个时钟桥接。

自行桥接时钟时，建议加上 `clock_topic:=/world/你的世界名/clock`，ROS 端仍输出 `/clock`。

| ROS 2 话题 | 类型 | frame_id | 频率 |
|---|---|---|---:|
| `/robot/front/points` | `sensor_msgs/msg/PointCloud2` | `front_lidar` | 10 Hz |
| `/robot/front/imu` | `sensor_msgs/msg/Imu` | `front_imu` | 200 Hz |

机器人自己的 `robot_state_publisher` 发布 `base_link → front_body`、`front_body → front_lidar/front_imu` 的固定关系。机器人运动所需的 `odom → base_link` 等动态 TF 由父项目提供；RViz 和算法节点设置 `use_sim_time:=true`。

接入后可在 RViz 添加 PointCloud2，选择 `/robot/front/points`，将 Fixed Frame 设为 `base_link` 或已有的 `odom`。切换 Avia 时，将挂载宏和桥接命令的 `model` 都改为 `avia`。自定义外观、GLB 和更多参数见[接入指南](docs/INTEGRATION.md)。

本包采用整帧快照扫描和理想 IMU，暂不提供逐点时间、运动畸变、CustomMsg 或 FAST-LIVO2 接入。MID-360 外参采用手册名义值，Avia 外参为近似值；详细参数与限制见[支持范围](docs/SUPPORT.md)。

## 测试与贡献

```bash
bash scripts/check.sh --unit       # 单元测试与初始化故障注入
bash scripts/check.sh --gpu        # GPU 运行回归
bash scripts/check.sh --endurance  # 稳定性检查
```

`--gpu` 包含独立父机器人工作空间的挂载、桥接、TF 和复位回归。技术检查使用 `python3 scripts/release_check.py`；正式发行检查使用 `--release`，未完成的分发审查会返回失败。

开发规范见 [CONTRIBUTING.md](CONTRIBUTING.md)。原创代码采用 [Apache-2.0](LICENSE)，第三方代码和模型见[来源声明](THIRD_PARTY_NOTICES.md)；Avia CAD 衍生资产的公开再分发条件仍待确认。
