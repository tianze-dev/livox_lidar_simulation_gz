# 独立包接口与父项目接入

本包提供模型、扫描及标准消息桥接。父项目负责机器人、世界、安装位姿和启动编排，不能反向成为本包的构建依赖。

## 包与运行环境

根目录为 `livox_lidar_simulation_gz` ROS 包。完成依赖下载后，可在父工作空间使用 colcon 构建；运行前加载父工作空间自己的安装环境。安装钩子设置本包插件搜索路径、资源路径及 `RGL_PATTERNS_DIR`，不写入系统配置。

子模块由父项目锁定提交，更新后重新构建；避免在一个工作空间同时保留同名旧包。当前尚无远程地址，因此这里不提供虚构的 `git submodule add` 命令。

## 在机器人中挂载

父项目的 URDF/Xacro 中包括：

```xml
<xacro:include filename="$(find livox_lidar_simulation_gz)/urdf/livox.xacro"/>
<xacro:livox_lidar parent="base_link" name="front_lidar" model="mid360"
  xyz="0.1 0 0.4" rpy="0 0 0"
  points_topic="/robot/front_lidar/points"
  imu_topic="/robot/front_lidar/imu"/>
```

安装参考为简化外壳底面中心，米／弧度。此处位姿只是示例，不是机器人的标定值。名称生成 `front_lidar_body`、`front_lidar_lidar`、`front_lidar_imu` 等 frame；多雷达必须使用全局不冲突的 `name`，ROS namespace 本身不会给 TF frame 加前缀。

Xacro 和 launch 都读取安装包的 `config/models/mid360.yaml`。默认外观为几何体，碰撞为盒体；标称总质量 0.265 kg，采用均匀盒体惯量及极小的数值传感器链接质量，不是 CAD 标定惯性。测量中心和 IMU 中心暂近似设在底面以上 0.035 m。

雷达外观位于其传感器链接下，由 RGL 自链接过滤排除，避免外壳遮挡所有射线；机器人其他部件仍参与遮挡。碰撞体用于物理碰撞，RGL 求交使用场景可视几何。

多实例使用共用 RGL 场景，所有已注册雷达自身链接的外观都会被排除，因此本实现不会模拟雷达外壳之间的相互遮挡。普通机器人部件不受此例外影响。

可选 `visual_mesh` 指定使用者自己的网格 URI，`mesh_rpy` 调整网格朝向。网格应采用米单位且以安装参考为原点；只替换外观，不自动推断尺寸、碰撞、质量或测量原点，也不自动赋予分发权。

## 世界插件

父世界必须且只应包含一个 RGL 场景管理器，并启用 Gazebo IMU 系统：

```xml
<plugin filename="RGLServerPluginManager" name="rgl::RGLServerPluginManager">
  <do_ignore_entities_in_lidar_link>true</do_ignore_entities_in_lidar_link>
</plugin>
<plugin filename="gz-sim-imu-system" name="gz::sim::systems::Imu"/>
```

父项目仍需正常配置 Physics、UserCommands 等世界系统。传感器插件由挂载宏提供，无需在模型层重复添加。参考 `worlds/demo.sdf`，不要把 demo 世界强行嵌入整机启动。

## 消息桥接与 TF 所有权

```bash
ros2 launch livox_lidar_simulation_gz sensor.launch.py \
  name:=front_lidar namespace:=robot bridge_clock:=false
```

生成 Gazebo→ROS 单向桥接 `/robot/front_lidar/points` 与 `/robot/front_lidar/imu`，必须与 Xacro 中话题一致。可在父 launch 中包含该入口，再按需施加 ROS remapping。此入口不创建机器人、不发布 TF、不启动世界或 RViz。

父 robot_state_publisher 发布挂载宏的固定关节；全局 `/clock` 由父项目唯一桥接，只有独立使用时才选择 `bridge_clock:=true`。本包节点使用仿真时间。

PointCloud2 为小端紧凑布局，x/y/z/intensity 都是 float32，偏移 0/4/8/12，point_step=16；坐标是该帧传感器坐标，时间戳为整帧快照仿真时间。未命中射线不输出，没有 offset_time、line、tag 或 CustomMsg。

IMU 使用 Gazebo 原生 Imu，单位为 rad/s 和 m/s²。静止水平放置时本机测试 z 比力约 +9.80665 m/s²；当前没有硬件噪声、偏置、量程限幅或外参标定。协方差和方向数据以 Gazebo 消息为准，不宣称与 Livox 驱动完全一致。

## 更新与兼容性

核心改动在本仓库提交；父项目主动更新到验证过的提交或标签，并提交子模块指针。每个父工作空间仍需构建与验证，尤其是 TF 唯一性、话题隔离和机器人自遮挡。本次不修改现有哨兵或无人机仓库。

## 多实例演示配置

`demo.launch.py sensors_file:=/path/to/sensors.yaml` 可在同一世界放置多个固定传感器。文件仅包含 `sensors` 列表，每项支持 model、name、namespace、xyz、rpy、visual_mesh 和 mesh_rpy，单位仍为米／弧度。完整示例为 `config/demos/dual_mid360.yaml`。

```yaml
sensors:
  - name: front
    namespace: robot_a
    xyz: [0, 0, 1]
    rpy: [0, 0, 0]
  - name: side
    namespace: robot_b
    xyz: [1, 0, 1]
    rpy: [0, 0, 1.5707963267948966]
```

默认型号是 mid360。话题按 `/<namespace>/<name>/points` 和 `/<namespace>/<name>/imu` 生成；六个子 frame 使用 front／side 前缀，公共父 frame 为 world。重名即使跨 namespace 也会被拒绝。当前只实测了两个实例，不宣称任意数量实时运行。

各实例分别使用 robot_state_publisher 和传感器桥接，只有第一路桥接时钟。所有传感器从一开始就写入初始世界，支持全场景复位。RViz 配置随实例列表生成，不再只显示默认话题。

这是一种固定安装验证场景，不是整机运动控制器。不要在该 demo 中任意移动雷达模型后继续信任其静态 TF；真实移动机器人由父项目维护动态 TF，本轮仅验证了障碍物离散改位后的稳定扫描结果。
