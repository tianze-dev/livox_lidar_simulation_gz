# 开发准备与首批实施任务

核查日期：2026-10-08。项目定位：基于 RGL 的非官方 Livox 多型号 Gazebo／ROS 2 仿真套件。

当前已完成基础环境探测、主要源码差异核查、源文件指纹登记及少量相关测试。尚未完成 M0 全部验收，尚无可构建的新 ROS 包，也未完成 GPU 求交运行验证。原哨兵和无人机工程保持不变。

后续按独立仓库开发，仓库根目录作为单一 ROS 包；哨兵、无人机项目未来通过子模块消费已验证版本。下文外部路径和既有测试结果仅是历史来源记录，不是新包开发或验收的前置步骤。后续测试只使用本包、公开依赖及独立的最小测试工作空间。

## 环境与基线

| 项目 | 核查结果 |
|---|---|
| 操作系统 | Ubuntu 24.04.5 LTS |
| ROS | Jazzy；基础开发及 ros_gz、Xacro、robot_state_publisher、RViz 包可发现 |
| Gazebo Sim | 8.15.0，Harmonic 系列 |
| GPU 与驱动 | NVIDIA RTX 4060，580.178.04；可查询，不代表 RGL 已运行通过 |
| 本地参考 | `/home/tianze/sentry_simulation/src/mid360_simulation` |
| 哨兵提交 | `04c0c934d4b0254407408990c082908938a69579`；核查时该包工作树干净 |
| RGL 插件参考 | `d4bf3cf36fe4a363a56df1bec2ce3809720db563` |
| RGL Core 参考 | `v0.21.0` |
| 新目录 | 已初始化本地 Git，主分支为 `main`，直接在该分支开发；无远程仓库、功能源码或安装产物 |

`dependencies/sentry_baseline.sha256` 登记原组件除 `maps/` 外的 57 个文件，包含待排除代码以便追溯，并不是迁入清单。后续读取基线前可在原组件目录执行 `sha256sum -c /home/tianze/livox_lidar_simulation_gz/dependencies/sentry_baseline.sha256`。文件指纹不代替源代码备份；当前保留原工程及其提交，不额外复制大型地图。

基础环境可复查：

```bash
bash /home/tianze/livox_lidar_simulation_gz/scripts/check_environment.sh
```

该脚本仅探测，不安装依赖、不启动仿真、不修改系统设置；建议使用未加载其他工作空间的终端。完整构建依赖及运行兼容性仍须通过新包构建和运行测试确认。

本次已通过 Bash 语法检查，并在清空继承环境、仅保留系统 PATH 的独立 shell 中运行，基础环境检查通过。57 项源文件指纹复查全部一致，原组件 Git 状态仍干净。

## 上游差异与迁入边界

逐文件比较了上游 `RGLServerPlugin` 的 7 个 `.cc` 和 4 个 `.hh` 与本机对应文件。

| 内容 | 已确认差异或现状 | 首版处理 |
|---|---|---|
| Mesh、Scene、Utils、Manager、PatternLoader 的对应源码及未列出的头文件 | 上述比较范围内与固定上游一致 | 直接复用，不另写实现 |
| `Lidar.cc` | 增加逐点字段、时间和历史扫描，也包含频率、空预设校验 | 以基础上游路径为准；必要输入校验独立保留并测试，不迁入时间增强 |
| `RGLServerPluginInstance.cc/.hh` | 增加历史位姿更新、历史扫描调用、相关状态 | 使用基础快照实现 |
| `MotionDistortion.hh` | 本地新增 | 本期不迁入 |
| CMake 与 package.xml | 强制查找并依赖 `livox_ros_driver2`，构建 CustomMsg 转换；GUI 与核心一起构建 | 重整最小构建目标和依赖，不整份复制 |
| demo launch | 即使 `fast_livo=false` 仍启动 CustomMsg 转换节点 | 删除新套件中的转换节点、算法选项和历史扫描选项 |
| 标准输出 | 插件已有 Gazebo PointCloudPacked，现有 demo 使用 ros_gz_bridge 转为 PointCloud2 | 复用该路径，不开发新的 ROS 点云发布器 |
| RGL Core 下载 | 固定版本但库与头文件下载缺少内容哈希核验；已有自定义库入口 | 补状态检查、可信来源哈希与缓存验证 |
| MID-360 预设下载 | 已固定提交及哈希，但每次配置都调用下载 | 后续增加已验证缓存复用与离线入口 |
| 单元测试 | 原资源测试文件混有导航和算法配置检查 | 仅提取核心相关断言，不把整份测试搬入新包 |

本次未逐行审查整个 RGL Core、GUI 或所有上游构建文件；最小补丁清单在实际接入时进一步收敛。

## 模型与资源

本机已有 MID-360 STL、配色后的 GLB／Blender 工程及原 Xacro 中的简化碰撞体。无需默认重新建模，但必须验证以下事项：

- 彩色模型坐标、尺寸和材质在目标 Gazebo／RViz 中是否正确；GLB 已存在不等于兼容验收通过。
- 当前 Xacro 质量为 0.0525946221106936 kg，质量、质心与惯量需要成套核验。
- 当前 IMU 安装位置沿用雷达测量中心，需核对硬件外参，而非直接当作精确实物值。
- 源网格、上色资产和 CAD 参考的来源及分发条件，尚未完成发布审查。
- 其他型号的专用网格与模型包不在本次已确认资产范围内。

本地现有资源指纹如下，库文件哈希仅是本机指纹，不冒充官方发布校验值：

| 文件 | SHA256 |
|---|---|
| `LivoxMid360.mat3x4f` | `d7b3322f303f9a83268180931e730b5f361592ef1ab6f1d56c166aadf47153fd` |
| `libRobotecGPULidar.so` | `e0e68d0b96e3b90bd9923c7c93af9ca75e55a687e77c87058a288b47e909ad52` |
| `mid360_base_link.STL` | `1fad48d70c34846e32dc2376782c875bea04b9ae0c2969515592469e4fab3e02` |
| `mid360_colored.glb` | `2815513499b275212d89ce6b6e1bc0b5ae524103c34da2002afd8fba767c9ca0` |

库与预设位于原组件 build 目录，本次没有复制，也不能以链接旧 build/install 的方式交付新套件。

## 本次测试

在清空继承环境的独立 shell 中，仅加载 ROS Jazzy，并为测试临时设置原组件源码的 Python 搜索路径，未加载实车或哨兵安装空间：IMU 限幅测试及 demo 资源路径单项测试共 6 个测试用例通过。初次直接运行因原组件未安装到该环境而导入失败；指定源码路径后通过，不将此结果视为独立安装验收。以下命令供干净终端复查：

```bash
source /opt/ros/jazzy/setup.bash
PYTHONPATH=/home/tianze/sentry_simulation/src/mid360_simulation${PYTHONPATH:+:$PYTHONPATH} \
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  /home/tianze/sentry_simulation/src/mid360_simulation/test/test_imu_range_limiter.py \
  /home/tianze/sentry_simulation/src/mid360_simulation/test/test_launch_resources.py::test_demo_exports_its_gazebo_resource_path
```

没有重跑暂缓范围的 CustomMsg、历史扫描、定位或导航测试，没有启动 Gazebo，也没有对新套件作性能或精度承诺。

## 首批实施顺序

1. 完成最小发行资产的许可初审，以及依赖来源校验；记录仍待核对的模型参数。
2. 按开发计划的单包结构建立构建入口，接入锁定的上游基础扫描代码；保留来源和必要的小型补丁，不引入暂缓功能。
3. 接入 MID-360 专用模型、简化碰撞体与快照扫描配置；为缺乏依据的参数明确标注近似。
4. 整理标准 PointCloud2／IMU 桥接、TF、独立演示和机器人挂载入口，分离可选 GUI 构建依赖。
5. 在不加载旧工作空间的条件下新建 build/install，执行构建、资源安装、标准接口和实际 GPU 扫描验收。

第一批结束标准：MID-360 可以在独立工作空间构建、显示对应模型、发布标准点云和 IMU，且不依赖 CustomMsg、FAST-LIVO2、历史位姿增强或个人目录。未达到该标准前不扩展 Avia，也不标记 M0–M3 完成。

来源入口：[RGL 固定上游](https://github.com/RobotecAI/RGLGazeboPlugin/tree/d4bf3cf36fe4a363a56df1bec2ce3809720db563)、本地原组件的 `resources/RGL_UPSTREAM.md`、CMake、launch、Xacro 和测试源码。
