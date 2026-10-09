# 安装与运行排错

## 干净环境

使用新的终端，仅加载 `/opt/ros/jazzy/setup.bash` 与本工作空间安装环境。不要加载其他机器人工作空间解决本包缺失依赖。父工作空间不得存在两份同名包。

系统依赖在 package.xml 声明，可由使用者审阅 `rosdep install --from-paths . --ignore-src -r -y` 后安装；本仓库脚本不自动修改宿主系统。Dockerfile 中的 apt 安装只发生在容器内。

## 下载或哈希失败

先运行 `python3 scripts/fetch_dependencies.py`，再构建。网络失败和哈希错误会明确退出；不要删除校验或改用未经核实的库。下载临时文件校验通过后才替换缓存，已有文件不因半次下载被覆盖。

离线环境需提前准备完整 `.deps/rgl`，然后运行 `python3 scripts/fetch_dependencies.py --offline`。也可使用自定义缓存：下载器 `--cache-dir /path/cache` 对应构建 `-DLIVOX_RGL_CACHE=/path/cache`。CMake 不联网，不从其他工程寻找库。

本包使用锁定版本的 Linux x86_64 预编译 RGL。自行编译其他平台的 RGL 属于未验收路线，遵循上游 CUDA／OptiX 工具链与许可要求，不将替换共享库视为已支持。

## 没有点云

1. 检查 NVIDIA 驱动查询、RGL 初始化日志及 GPU 是否暴露给容器；容器运行需要 NVIDIA Container Toolkit 和 `--gpus all`。
2. 确认世界有且仅有一个 RGL 场景管理器，插件搜索路径与预设环境钩子已加载。
3. 确认传感器话题与桥接配置一致，RViz Fixed Frame 可通过 TF 连到雷达 frame。
4. 检查是否暂停、场景中是否有可命中的可视几何、是否被自身外壳挡住。RGL 使用可视几何而非碰撞几何。

找不到型号时会拒绝启动，不静默降级到 MID-360。Avia 视野较窄，转离墙面后没有墙面点是正确结果，不应通过伪造点云修补。

插件初始化成功时输出 `RGL sensor ready`（Gazebo 日志级别 `-v 3` 或更高）；初始化失败会停止该传感器并释放已创建资源。看不到点云时，先确认这条就绪信息，再检查 Gazebo 话题和桥接参数是否一致。点云存在但为空，也可能只是量程内没有命中物体。

## GUI 问题

先用 `gui:=false rviz:=false` 区分渲染问题与传感器问题。不要因为 GUI 的 OpenGL 错误就断言 RGL 扫描失效，也不要以 headless 测试替代视觉验收。模型看见内部时检查面绕序，不要用双面渲染掩盖反向面。

## 多实例与移动验证

name 必须全局唯一，namespace 不会自动隔离 TF frame。不同独立仿真使用不同 GZ_PARTITION／ROS_DOMAIN_ID；同一世界只桥接一次 /clock。

`moving:=true` 是单雷达滑台／转台示例，滑台行程 ±2.5 m，默认速度 0.1 m/s、角速度 0.15 rad/s。不是无限行驶机器人，不能撞到行程终点后继续按匀速期望验证。父项目自己的移动机器人负责动态 TF 和控制，不能使用静态 demo 的固定 TF 假装移动。

Gazebo 全复位可能移除启动后生成的模型；本包 demo 把传感器放入初始世界，父项目的生成／重建由父项目负责。
