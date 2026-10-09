# 开发与贡献规范

本项目提供独立的 Livox Gazebo／ROS 2 传感器实现。功能边界见 [支持矩阵](docs/SUPPORT.md)，接口与父项目接入见 [接入说明](docs/INTEGRATION.md)。

## 代码与依赖

- 一个提交围绕一个目的，格式化与功能修改分开。
- 复用 RGL 能力，只增加必要适配；上游版本及本地补丁记录在 [UPSTREAM.md](third_party/rgl_gazebo/UPSTREAM.md)。
- 第三方代码保留原格式、版权与许可证，不做无关的批量重排。
- 构建、运行与测试只依赖公开声明的依赖和本仓库资源，不使用个人绝对路径或搜索相邻工作空间作为备用依赖。
- 下载资源存入忽略的缓存；不提交编译产物、运行日志、凭据或模型制作中间文件。

## 父项目边界

仓库根目录是一个 ROS 包，支持独立构建，也支持作为 Git 子模块放入父工作空间的 `src/`，不假设固定目录层级。

通用传感器功能在本仓库维护；安装位姿、机器人控制、场地、整机启动和话题重映射由父项目负责。传感器接入入口不应强制启动世界、RViz 或重复发布公共 TF。父项目锁定子模块提交，更新后重新构建并执行自己的集成测试。

## 代码格式

项目原创 C++ 使用 clang-format 18：Google 风格、2 空格缩进、100 列、C++20。现有插件位于 `third_party/`，由 `.clang-format-ignore` 排除，修改时保持上游格式。

文本遵循 `.editorconfig`：UTF-8、LF、空格缩进，Python 为 4 空格。文档以中文为主，同时维护英文 README 中的使用方式和功能边界。

## 测试

按 README 准备依赖并构建后，在仓库根目录执行：

```bash
bash scripts/check.sh --unit
# NVIDIA GPU 运行回归：单实例、双实例、混合型号、移动与复位
bash scripts/check.sh --gpu
# 在运行回归基础上增加 MID-360 300 秒、Avia 60 秒稳定性测试
bash scripts/check.sh --endurance
python3 scripts/release_check.py
git diff --check
```

普通 CTest 执行 Python 单元测试和无 GPU 的 C++ 初始化故障注入；GPU 运行测试包含临时独立父工作空间的构建与实际接入，且独立执行，结果写入忽略的 `run/`。检查脚本需要本仓库的本地构建；父工作空间可使用其构建目录执行 CTest，并在加载父安装环境后直接运行 `test/*_runtime.py`。

| 变更 | 验证要求 |
|---|---|
| 文档与工程配置 | 链接、命令、资源安装清单与忽略规则 |
| 构建与依赖 | 干净构建、下载失败行为、版本与哈希校验 |
| 扫描与接口 | 消息字段、仿真时钟、TF、GPU 求交及复位 |
| 模型与配置 | 尺寸、轴向、法线、材质、碰撞包络、外参与资源加载 |

CPU CI 使用 Dockerfile 构建并运行单元测试，不代替 GPU、GUI 或性能测试。没有 GPU 时应明确标记运行测试未执行。环境检查与发布元信息检查也不代表仿真已运行通过。

## Avia 专项验证

```bash
# 需要 GPU；检查近远端截断、空点云、视场及普通物体遮挡
python3 test/avia_runtime.py
# 真实 Gazebo 相机采集前后视图；图片写入 run，不作为渲染一致性的自动证明
python3 test/avia_visual_runtime.py --format dae --output run/avia_visual/dae
python3 test/avia_visual_runtime.py --format glb --output run/avia_visual/glb
# 10 分钟静态稳定性；移动夹具只运行短轨迹
python3 test/release_runtime.py --model avia --seconds 600 --output run/avia_endurance
python3 test/release_runtime.py --model avia --moving --seconds 6 --output run/avia_moving
```

可视测试需要 Gazebo 的 Ogre2 渲染后端和 `python3-pil`。截图须人工检查外壳、窗口、法线和朝向；不能以颜色不同推断扫描失败，也不能将普通物体遮挡测试等同于雷达外壳之间的遮挡。

## 型号与资产

新增型号需提供参数与预设来源、版本和哈希、可分发的模型、材质、碰撞体、安装与测量坐标、IMU 外参、示例和回归测试。缺少实物依据的参数标为近似；预设存在不等于型号完整支持。

运行资产保留 DAE、可选 GLB、精简的几何校验信息和来源声明。模型制作源及转换工具独立维护，不作为构建或测试前提。更新网格时同步更新哈希与几何数据，并检查 Gazebo 和 RViz 的显示效果。

## 提交与许可

本项目在 `main` 分支开发。提交标题使用 `type(scope): 描述`，scope 可省略；类型包括 feat、fix、docs、refactor、test、build、chore。提交说明包含验证结果及未执行项。

`python3 scripts/release_check.py --install-prefix "$(ros2 pkg prefix livox_lidar_simulation_gz)"` 检查安装资源和技术元信息。正式发行前运行 `python3 scripts/release_check.py --release`；`dependencies/distribution.json` 中未解决的分发审查会阻止通过。批准记录必须包含实际审查依据，不得为通过检查而改状态。

原创代码采用 [Apache-2.0](LICENSE)。引入第三方内容时更新 [来源清单](THIRD_PARTY_NOTICES.md)，保留适用声明；公开发行前核实资产分发条件与 `package.xml` 中的维护者信息。
