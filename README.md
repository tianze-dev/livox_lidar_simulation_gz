# Livox LiDAR Simulation for Gazebo

基于 RGL 的非官方 Livox 多型号 Gazebo／ROS 2 仿真套件。独立维护通用传感器功能，父项目通过 Git 子模块接入，不依赖其他机器人工作空间。

当前版本为 **0.1.0 预发布版**。MID-360 提供精细模型与名义外参；Avia 提供官方 CAD 衍生的精细外观、非重复扫描／标准接口预览，测量与 IMU 外参仍为近似值。已包含静态、双实例和移动滑台演示。型号和平台限制见 [支持矩阵](docs/SUPPORT.md)。另见 [English](README.en.md)、[接入说明](docs/INTEGRATION.md)、[MID-360 来源](meshes/mid360/NOTICE.md)、[Avia 来源与待确认的公开再分发条件](meshes/avia/NOTICE.md)。

## 环境与构建

目标环境为 Ubuntu 24.04 x86_64、ROS 2 Jazzy、Gazebo Harmonic，需要支持 RGL 的 NVIDIA GPU／驱动。已验证硬件为 RTX 4060；不提供 CPU 后端。请在未加载其他项目 overlay 的新终端操作。

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

源码来自固定 RGL 上游，仅携带基础健壮性／复位补丁，记录见 [UPSTREAM](third_party/rgl_gazebo/UPSTREAM.md)。构建与运行不借用其他工作空间的安装产物；脚本不自动安装宿主系统依赖。

## 运行

```bash
ros2 launch livox_lidar_simulation_gz demo.launch.py
# 无界面：
ros2 launch livox_lidar_simulation_gz demo.launch.py gui:=false rviz:=false
# 在 RViz 中近距离查看精细模型（隐藏点云，仍正常发布）：
ros2 launch livox_lidar_simulation_gz demo.launch.py model_view:=true
# 移动滑台／转台，动态 TF 来自实际 Gazebo 关节反馈：
bash scripts/run.sh moving:=true
# Avia 扫描／接口预览：
bash scripts/run.sh model:=avia name:=avia
# 聚焦 Avia 外观（RViz）：
bash scripts/run.sh model:=avia name:=avia model_view:=true
```

默认演示包含地面、墙面和静止雷达。单实例参数：`model`（mid360／avia）、`name`、`namespace`、`xyz`、`rpy`、`visual_mesh`、`mesh_rpy`；公共参数为 `gui`、`rviz`、`model_view`。移动示例额外支持 `moving`、`linear_velocity`、`angular_velocity`，只允许一个传感器，滑台行程 ±2.5 m。运行多个独立仿真时自行设置不同 `GZ_PARTITION` 和 `ROS_DOMAIN_ID`；演示不修改其他实例。

`scripts/run.sh` 在未指定环境变量时使用 ROS domain 119 和独立 Gazebo partition，避免默认混入 domain 0；已有显式设置会保留。直接使用 `ros2 launch` 则由使用者选择隔离环境。运行前确认目标 domain 没有实机或其他同话题实例。

双雷达演示共用一个世界，使用不同的话题、TF 名称和安装朝向：

```bash
ros2 launch livox_lidar_simulation_gz demo.launch.py \
  sensors_file:="$(ros2 pkg prefix --share livox_lidar_simulation_gz)/config/demos/dual_mid360.yaml" \
  gui:=false rviz:=false
```

指定 `sensors_file` 后，实例 YAML 替代单实例参数。名称必须全局唯一，即使 namespace 不同也不能重名；启动前会拒绝未知字段和非有限位姿。多实例 demo 只桥接一次 `/clock`，RViz 为每路点云和模型生成独立显示项。`model_view:=true` 聚焦第一台模型；不指定 visual_mesh 时使用内置精细 DAE。`visual_mesh:=primitive` 仅适用于 MID-360，Avia 不提供简化外观回退。

| 默认话题 | 类型 | 仿真时间频率与坐标 |
|---|---|---|
| `/livox/mid360/points` | PointCloud2 | 10 Hz，`mid360_lidar`；x/y/z/intensity 为 float32 |
| `/livox/mid360/imu` | Imu | 200 Hz，`mid360_imu` |
| `/clock` | Clock | 来自 Gazebo，由 demo 桥接 |
| `/tf_static` | TFMessage | demo 的 robot_state_publisher 发布 |

MID-360 每帧发射 20000 条射线，Avia 为 24000 条，只输出命中点；输出点数随场景变化。`intensity` 来自 Gazebo `laser_retro`，不是经过标定的 Livox 反射率。

## 验证

```bash
source /opt/ros/jazzy/setup.bash
source install/local_setup.bash
ctest --test-dir build/livox_lidar_simulation_gz --output-on-failure
python3 test/smoke_runtime.py
# 双雷达、障碍物改位、暂停／单步／复位：
python3 test/multi_runtime.py
# 完整运行回归与稳定性检查：
bash scripts/check.sh --gpu
bash scripts/check.sh --endurance
python3 scripts/release_check.py
```

运行测试创建独立 Gazebo partition，检查实际点云／IMU、时钟、TF、墙面几何及复位恢复，结束后仅清理它启动的进程。默认 ROS domain 单实例为 117、双实例为 118，可设置其他未使用的 `ROS_DOMAIN_ID`。日志与结果写入被忽略的 `run/`，GPU 测试不自动加入普通 CTest。

## 子模块使用

仓库根目录就是 ROS 包。可作为子模块放入父工作空间的 `src/livox_lidar_simulation_gz`，准备依赖后从父工作空间正常使用 colcon 构建。挂载宏、世界插件和桥接方式见 [接入说明](docs/INTEGRATION.md)。

`sensor.launch.py` 不启动 Gazebo、RViz、机器人或公共 TF，默认不桥接时钟。父项目负责安装位姿、场地、整机启动和话题重映射；通用实现只在本仓库维护。父项目固定子模块提交，更新后重新构建，不自动跟随本仓库 `main`。

## 已知边界

- 快照扫描，不模拟逐点时间或帧内运动畸变。不提供 CustomMsg、FAST-LIVO2 接入和 CSV 转换。
- 精细模型已校正安装轴向与尺寸；MID-360 使用官方手册名义外参，Avia 使用近似测量与 IMU 原点，均不代替逐台实物标定。惯量为均匀长方体近似，外观材质不是光学标定。`visual_mesh` 可接收自定义网格，但其原点和轴向需自行核验。
- MID-360 量程为 0.1–40 m，Avia 为 0.1–190 m，均为固定裁剪，不模拟反射率依赖探测概率、硬件噪声、限幅或多回波；IMU 为理想 Gazebo 输出。
- 双实例的话题／TF 隔离、障碍物改位、暂停／步进／复位，以及移动滑台的点云／关节反馈／动态 TF／理想 IMU 已通过限定场景测试。移动演示不是导航或定位算法，不代表任意机器人运动精度。
- RGL 当前共用场景会排除所有已注册雷达自身链接的外观，不能用于验证雷达外壳之间的相互遮挡。
- 本机 Gazebo／RViz 的精细模型与材质已做视觉检查；异机、其他渲染后端和全系列仍须继续验收，不能宣称实机等效。

## 开发与许可

开发方式、测试和资产维护要求见 [贡献规范](CONTRIBUTING.md)。

本项目不代表 Livox 或 Robotec 官方发布。原创代码采用 [Apache-2.0](LICENSE)；[NOTICE](NOTICE) 和 [第三方来源清单](THIRD_PARTY_NOTICES.md) 保留上游与模型的独立说明，不把品牌／CAD 统一宣称为本项目原创。排错见 [TROUBLESHOOTING](docs/TROUBLESHOOTING.md)。
