# 独立包接口与父项目接入

本包提供模型、扫描及标准消息桥接。父项目负责机器人、世界、安装位姿和启动编排，不能反向成为本包的构建依赖。

## 包与运行环境

根目录为 `livox_lidar_simulation_gz` ROS 包。完成依赖下载后，可在父工作空间使用 colcon 构建；运行前加载父工作空间自己的安装环境。安装钩子设置本包插件搜索路径、资源路径及 `RGL_PATTERNS_DIR`，不写入系统配置。

子模块由父项目锁定提交，更新后重新构建；避免在一个工作空间同时保留同名旧包。

不要同时加载两套同名 RGL 插件／共享库；父项目只启用一套扫描实现和一个场景管理器。安装位姿以本包模型坐标为准，不沿用其他模型的轴向补偿。

## 在机器人中挂载

父项目的 URDF/Xacro 中包括：

```xml
<xacro:include filename="$(find livox_lidar_simulation_gz)/urdf/livox.xacro"/>
<xacro:livox_lidar parent="base_link" name="front_lidar" model="mid360"
  xyz="0.1 0 0.4" rpy="0 0 0"
  points_topic="/robot/front_lidar/points"
  imu_topic="/robot/front_lidar/imu"/>
```

安装参考为外壳底面中心，米／弧度。此处位姿只是示例，不是机器人的标定值。名称生成 `front_lidar_body`、`front_lidar_lidar`、`front_lidar_imu` 等 frame；多雷达必须使用全局不冲突的 `name`，ROS namespace 本身不会给 TF frame 加前缀。

Xacro 和 launch 都读取安装包的 `config/models/mid360.yaml`。默认外观为内置精细 DAE，碰撞为主体盒体加接口圆柱；标称总质量 0.265 kg，仍采用均匀盒体惯量及极小的数值传感器链接质量，不是 CAD 标定惯性。测量中心位于安装原点以上 0.047 m，IMU 相对安装原点为 `(0.011, 0.02329, 0.00288)` m，轴向一致，采用官方手册名义外参。来源、变换和尺寸报告见 [模型说明](../meshes/mid360/NOTICE.md)。

雷达外观位于其传感器链接下，由 RGL 自链接过滤排除，避免外壳遮挡所有射线；机器人其他部件仍参与遮挡。碰撞体用于物理碰撞，RGL 求交使用场景可视几何。

多实例使用共用 RGL 场景，所有已注册雷达自身链接的外观都会被排除，因此本实现不会模拟雷达外壳之间的相互遮挡。普通机器人部件不受此例外影响。

可选 `visual_mesh` 指定使用者自己的网格 URI，`mesh_rpy` 调整网格朝向。不指定时使用内置 DAE；特殊值 `primitive` 仅在 MID-360 上提供简化外观，Avia 不再接受此参数。网格应采用米单位且以安装参考为原点；只替换外观，不自动推断尺寸、碰撞、质量或测量原点，也不自动赋予分发权。

## 可选 GLB 外观

两款型号同时提供 DAE 与 GLB，默认仍为已验证的 DAE。GLB 保留 PBR 金属度／粗糙度，当前 Gazebo 默认光照下金属外壳较暗；完整镀膜扩展效果与 RViz GLB 视觉一致性尚未验收。

例如只切换 Avia 外观：

```bash
bash scripts/run.sh model:=avia name:=avia \
  visual_mesh:=package://livox_lidar_simulation_gz/meshes/avia/avia.glb \
  mesh_rpy:="1.5707963267948966 0 0"
```

MID-360 对应 `model:=mid360 name:=mid360` 和 `meshes/mid360/mid360.glb`，旋转参数相同。GLB 的 Y-up 到安装坐标 Z-up 补偿只传给 `mesh_rpy`，不要放进安装参数 `rpy`，否则会改变传感器的实际扫描朝向。碰撞、质量、测量原点及 IMU 外参均不因格式切换而改变。

双型号 GLB 示例使用安装包中的相对资源，不依赖制作目录：

```bash
bash scripts/run.sh \
  sensors_file:="$(ros2 pkg prefix --share livox_lidar_simulation_gz)/config/demos/mixed_glb.yaml" \
  rviz:=false
```

恢复 DAE 时省略 `visual_mesh` 与 `mesh_rpy`；不要将 GLB 的 90° 补偿沿用到 DAE。Gazebo 短时实测两种格式都正常发布 10 Hz 点云和 200 Hz IMU，不代表更换格式能改善测量精度。

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

IMU 使用 Gazebo 原生 Imu，单位为 rad/s 和 m/s²。默认地球重力下静止水平放置时，z 比力约 +9.80665 m/s²；当前没有硬件噪声、偏置、量程限幅或外参标定。协方差和方向数据以 Gazebo 消息为准，不宣称与 Livox 驱动完全一致。

## 更新与兼容性

核心改动在本仓库提交；父项目主动更新到验证过的提交或标签，并提交子模块指针。每个父工作空间仍需构建与验证，尤其是 TF 唯一性、话题隔离和机器人自遮挡。

## 移动载体验证入口

`demo.launch.py moving:=true` 使用世界锚定的滑台和转台，不使用位姿瞬移伪装物理运动。Gazebo JointController 驱动两个实际关节，JointStatePublisher 的反馈通过 ros_gz_bridge 发布到 `/fixture/<name>/joint_states`，robot_state_publisher 据此发布动态 TF。原有传感器挂载宏和固定外参不变。

默认直线速度 0.1 m/s、角速度 0.15 rad/s，参数绝对值限制 0.5，滑台行程 ±2.5 m。可通过 `/fixture/<name>/linear_velocity` 与 `/fixture/<name>/angular_velocity` 的 std_msgs/Float64 命令控制；该入口仅是验证夹具，不替代父项目控制器。一次只支持一个雷达，不能与多实例 sensors_file 同时启用。

动态 TF 的 world→slide、slide→platform 来自关节反馈；platform→雷达固定外参由 URDF 定义。扫描仍是一帧一个位姿，不含逐点时间或畸变补偿。运动验收将点云按独立关节反馈还原到测试墙面，并核对陀螺仪和向心加速度；这不是对任意动作的全面物理校准。

## Avia 预览

`model:=avia name:=avia` 复用同一插件、挂载宏与桥接代码，选择不同配置和预设。Avia 使用 `meshes/avia/avia.dae`，含银灰外壳、青绿色前窗和深灰标识，不提供简化外观回退。FOV 示意体不参与渲染、碰撞或 RGL 求交。主体和侧接口使用盒体碰撞，仅供物理计算。扫描为非重复模式、单几何返回、10 Hz／24000 射线，其他模式未实现。原点、IMU 外参和惯量为近似值，详见支持矩阵和模型 NOTICE。

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

各实例分别使用 robot_state_publisher 和传感器桥接，只有第一路桥接时钟。所有传感器从一开始就写入初始世界，支持全场景复位。demo 将描述话题隔离到 `/<namespace>/<name>/robot_description`，RViz 配置随实例列表生成模型和点云显示项。父项目自有 robot_state_publisher 不需要采用此 demo 话题约定。

此多实例入口是一种固定安装验证场景，不是整机运动控制器。不要任意移动静态模型后继续信任其固定 TF；运动验证使用前述 `moving:=true` 单实例入口，真实移动机器人由父项目维护动态 TF。
