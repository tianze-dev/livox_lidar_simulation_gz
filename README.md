# Livox LiDAR Simulation for Gazebo

基于 RGL 的非官方 Livox 多型号 Gazebo／ROS 2 仿真套件。独立维护通用传感器功能，父项目通过 Git 子模块接入，不依赖任何哨兵或无人机工作空间。

当前为 **MID-360 基础开发版**，不是正式开源发行版。已提供独立 ROS 包、GPU 快照扫描、PointCloud2／IMU、Xacro 挂载宏、独立演示与无界面测试。外观使用明确标注的简化模型，精细网格分发与其他型号尚未完成。验证记录见 [VALIDATION](docs/VALIDATION.md)，接入方式见 [INTEGRATION](docs/INTEGRATION.md)。

## 环境与构建

目标环境为 Ubuntu 24.04 x86_64、ROS 2 Jazzy、Gazebo Harmonic，需要支持 RGL 的 NVIDIA GPU／驱动。当前本机使用 RTX 4060；不提供 CPU 后端。请在未加载其他项目 overlay 的新终端操作。

在仓库根目录执行：

```bash
source /opt/ros/jazzy/setup.bash
# 系统依赖未齐时，由使用者审阅并安装 package.xml 声明的依赖：
# rosdep install --from-paths . --ignore-src -r -y
bash scripts/check_environment.sh
python3 scripts/fetch_dependencies.py
bash scripts/build.sh
source install/local_setup.bash
```

下载器只获取 `dependencies/lock.json` 指定的公开资源，全部校验 SHA256；CMake 配置阶段不联网。缓存默认为 `.deps/rgl`，缓存完备后可执行 `python3 scripts/fetch_dependencies.py --offline` 验证。自定义缓存用 `--cache-dir /path/to/cache`，构建时对应传入 `bash scripts/build.sh -DLIVOX_RGL_CACHE=/path/to/cache`。

源码来自固定 RGL 上游，仅携带基础健壮性／复位补丁，记录见 [UPSTREAM](third_party/rgl_gazebo/UPSTREAM.md)。不借用原工程的库、模型或安装产物，不自动安装系统依赖。

## 运行

```bash
ros2 launch livox_lidar_simulation_gz demo.launch.py
# 无界面：
ros2 launch livox_lidar_simulation_gz demo.launch.py gui:=false rviz:=false
```

演示包含地面、已知位置的墙面和静止雷达。单实例参数：`model`（目前仅 mid360）、`name`、`namespace`、`xyz`、`rpy`、`visual_mesh`、`mesh_rpy`；公共参数为 `gui` 和 `rviz`。运行多个独立仿真时自行设置不同的 `GZ_PARTITION` 和 `ROS_DOMAIN_ID`；演示不会更改其他运行实例。

双雷达演示共用一个世界，使用不同的话题、TF 名称和安装朝向：

```bash
ros2 launch livox_lidar_simulation_gz demo.launch.py \
  sensors_file:="$(ros2 pkg prefix --share livox_lidar_simulation_gz)/config/demos/dual_mid360.yaml" \
  gui:=false rviz:=false
```

指定 `sensors_file` 后，实例 YAML 替代单实例参数。名称必须全局唯一，即使 namespace 不同也不能重名；启动前会拒绝未知字段和非有限位姿。多实例 demo 只桥接一次 `/clock`，RViz 配置会为每路点云生成独立显示项（配置已测试，GUI 视觉尚未验收）。

| 默认话题 | 类型 | 仿真时间频率与坐标 |
|---|---|---|
| `/livox/mid360/points` | PointCloud2 | 10 Hz，`mid360_lidar`；x/y/z/intensity 为 float32 |
| `/livox/mid360/imu` | Imu | 200 Hz，`mid360_imu` |
| `/clock` | Clock | 来自 Gazebo，由 demo 桥接 |
| `/tf_static` | TFMessage | demo 的 robot_state_publisher 发布 |

每帧发射 20000 条射线，只输出命中点；输出点数随场景变化，不保证每帧 20000 个有效点。`intensity` 来自 Gazebo `laser_retro`，不是经过标定的 Livox 反射率。

## 验证

```bash
source /opt/ros/jazzy/setup.bash
source install/local_setup.bash
ctest --test-dir build/livox_lidar_simulation_gz --output-on-failure
python3 test/smoke_runtime.py
# 双雷达、障碍物改位、暂停／单步／复位：
python3 test/multi_runtime.py
```

运行测试创建独立 Gazebo partition，检查实际点云／IMU、时钟、TF、墙面几何及复位恢复，结束后仅清理它启动的进程。默认 ROS domain 单实例为 117、双实例为 118，可设置其他未使用的 `ROS_DOMAIN_ID`。日志与结果写入被忽略的 `run/`，GPU 测试不自动加入普通 CTest。

## 子模块使用

仓库根目录就是 ROS 包。以后作为子模块放入父工作空间的 `src/livox_lidar_simulation_gz`，准备依赖后从父工作空间正常使用 colcon 构建。挂载宏、世界插件和桥接方式见 [接入说明](docs/INTEGRATION.md)。

`sensor.launch.py` 不启动 Gazebo、RViz、机器人或公共 TF，默认不桥接时钟。父项目负责安装位姿、场地、整机启动和话题重映射；通用实现只在本仓库维护。父项目固定子模块提交，更新后重新构建，不自动跟随本仓库 `main`。当前没有远程仓库，未修改任何父项目。

## 已知边界

- 快照扫描，不模拟逐点时间或帧内运动畸变。CustomMsg、FAST-LIVO2 和 CSV 转换继续暂缓。
- 外观为按外形尺寸制作的几何近似，惯量为均匀长方体近似，测量原点与 IMU 外参未标定。`visual_mesh` 可接收显式提供的网格，但格式、原点和轴向需核验。
- 默认量程是 0.1–40 m 固定裁剪，不模拟反射率依赖探测概率、硬件噪声、限幅或多回波；IMU 当前为理想 Gazebo 输出。
- 双 MID-360 的并行输出、话题／TF 隔离、障碍物改位后的稳定几何、暂停／步进／复位已通过本机测试。超过两台的运行规模、连续运动误差和移动雷达动态 TF 尚未验收；demo 的传感器安装是固定的。
- RGL 当前共用场景会排除所有已注册雷达自身链接的外观，不能用于验证雷达外壳之间的相互遮挡。
- GUI／RViz 显示、精细彩色网格和异机安装仍须继续验收；不能以这些测试宣称全系列或实机等效。

## 开发与许可

直接在 `main` 开发。见 [贡献规范](CONTRIBUTING.md)、[开发计划](DEVELOPMENT_PLAN.md) 和 [历史准备记录](docs/DEVELOPMENT_READINESS.md)。

本项目不代表 Livox 或 Robotec 官方发布。[LICENSE](LICENSE) 目前仅记录项目总许可待确认状态，不是正式开源授权。已引入的 RGL 文件保留其 Apache-2.0 许可，模型、数据和二进制发行条件分别登记于 [第三方来源清单](THIRD_PARTY_NOTICES.md)。未经确认不公开发布。
