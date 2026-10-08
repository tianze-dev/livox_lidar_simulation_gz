# 第三方来源与许可状态

本清单区分已引入、已参考和待确认内容，不代表整个项目已完成公开发行审查。已引入固定版本 RGL Gazebo 插件源码及其原 LICENSE；运行库、API 头和扫描预设从公开来源下载到忽略的缓存，构建时校验、安装时打包必要运行资源。精细 MID-360 模型已按所有者确认收录，详见模型 NOTICE。

| 来源 | 当前用途与状态 | 后续要求 |
|---|---|---|
| 本机 `scut-uav` 工程规范 | 参考格式、忽略规则和开发流程；本项目重新整理贡献说明 | 该工程总 LICENSE 为 GPL-3.0 文本；未复制其总许可证或功能代码，不以此确定本项目许可 |
| [RGLGazeboPlugin](https://github.com/RobotecAI/RGLGazeboPlugin/tree/d4bf3cf36fe4a363a56df1bec2ce3809720db563) | 已引入 third_party/rgl_gazebo，7 个源文件和 4 个头文件 | 保留原版权和 Apache-2.0 LICENSE；改动标注在文件头及 UPSTREAM.md |
| [RGL Core v0.21.0](https://github.com/RobotecAI/RobotecGPULidar/tree/v0.21.0) | 下载官方 core-linux-x64 发行库和 API 头，按 lock.json 校验 | Core 与插件此版本的 LICENSE 文本一致，安装时保留；预编译资产及其依赖的正式再分发审查仍待完成 |
| [Livox 官方仿真仓库](https://github.com/Livox-SDK/livox_laser_simulation/tree/1cce1073633a062b92e30243a4c2920e45551bb5) | 型号与扫描轨迹来源；原 CSV 不重复收录 | 原仓库 MIT License（Copyright 2021 livox）保存在 third_party/livox_scan/LICENSE，并随安装保留 |
| RGL 收录的 Livox `.mat3x4f` | MID-360／Avia 预设从固定上游下载并校验，随本地安装提供 | 原数据为 Livox 官方扫描配置，转换来自上游 PR #52；固定来源见 lock.json，保留 Robotec 与 Livox 的声明，不称为原创 |
| 本机哨兵 MID-360 组件 | 登记提交和 57 个文件指纹，供差异核查 | 上游代码与本地增量分别追溯，不把包根许可证当作所有资产的权属证明 |
| MID-360 精细模型 | 所有者于 2026-10-09 确认原 STL 为官方模型且可以公开发布；已收录整理后的 Blender 制作源、DAE 和报告 | 来源、发布确认、转换及外参依据见 [模型 NOTICE](meshes/mid360/NOTICE.md)；不自动套用项目候选许可证，不将品牌或资产宣称为原创 |

## 引入记录要求

每批第三方内容至少记录源 URL／仓库、版本或提交、文件范围、内容哈希、适用许可证和声明、本地修改，以及是否允许随发行包分发。

本清单不替代上游 LICENSE／NOTICE。正式引入时附带要求保留的原文件；来源不明或权利未核实的资产不进入公开发行包。

所有者于 2026-10-09 确认本项目原创代码采用 [Apache-2.0](LICENSE)，范围和第三方归属见 [NOTICE](NOTICE)。此选择不替代模型来源说明或为第三方商标授予权利。

简化外观回退与测试世界由本项目使用基础几何体描述；默认精细外观来自上述模型处理流程。测量原点和 IMU 外参采用手册名义值，均匀盒体惯量及外观材质仍为近似。官网 STEP 和手册没有随运行资源重新分发。本次只提交本地仓库，不创建远程仓库或执行公开发布。

Avia 使用本项目制作的基础几何体外观，未复制／分发官方 Avia CAD。尺寸、质量和扫描参数来源为官方规格页；Avia 的测量／IMU 外参是已标注的近似值，与 MID-360 手册名义外参分开管理。
