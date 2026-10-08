# 第三方来源与许可状态

本清单区分已引入、已参考和待确认内容，不代表整个项目已完成公开发行审查。已引入固定版本 RGL Gazebo 插件源码及其原 LICENSE；运行库、API 头和扫描预设从公开来源下载到忽略的缓存，构建时校验、安装时打包必要运行资源。未引入原工程的精细模型。

| 来源 | 当前用途与状态 | 后续要求 |
|---|---|---|
| 本机 `scut-uav` 工程规范 | 参考格式、忽略规则和开发流程；本项目重新整理贡献说明 | 该工程总 LICENSE 为 GPL-3.0 文本；未复制其总许可证或功能代码，不以此确定本项目许可 |
| [RGLGazeboPlugin](https://github.com/RobotecAI/RGLGazeboPlugin/tree/d4bf3cf36fe4a363a56df1bec2ce3809720db563) | 已引入 third_party/rgl_gazebo，7 个源文件和 4 个头文件 | 保留原版权和 Apache-2.0 LICENSE；改动标注在文件头及 UPSTREAM.md |
| [RGL Core v0.21.0](https://github.com/RobotecAI/RobotecGPULidar/tree/v0.21.0) | 下载官方 core-linux-x64 发行库和 API 头，按 lock.json 校验 | Core 与插件此版本的 LICENSE 文本一致，安装时保留；预编译资产及其依赖的正式再分发审查仍待完成 |
| [Livox 官方仿真仓库](https://github.com/Livox-SDK/livox_laser_simulation/tree/1cce1073633a062b92e30243a4c2920e45551bb5) | 型号和扫描轨迹来源参考，未迁入 | 引入时保存适用许可，确认代码与数据的覆盖范围 |
| RGL 收录的 Livox `.mat3x4f` | MID-360 预设已从固定上游下载并校验，随本地安装提供 | 原数据为 Livox 官方扫描配置，转换来自上游 PR #52；固定来源见 lock.json，不称为原创，公开发行前完成数据条件审查 |
| 本机哨兵 MID-360 组件 | 登记提交和 57 个文件指纹，供差异核查 | 上游代码与本地增量分别追溯，不把包根许可证当作所有资产的权属证明 |
| MID-360 STL、彩色 GLB、Blender 工程及官网 CAD 参考 | 仍在原工程中，未迁入；许可审查待完成 | 分别核实几何、配色、标识及参考资产来源，登记修改；可下载不等于可以再分发 |

## 引入记录要求

每批第三方内容至少记录源 URL／仓库、版本或提交、文件范围、内容哈希、适用许可证和声明、本地修改，以及是否允许随发行包分发。

本清单不替代上游 LICENSE／NOTICE。正式引入时附带要求保留的原文件；来源不明或权利未核实的资产不进入公开发行包。

本项目总许可仍待所有者确认，见 [LICENSE](LICENSE)。

当前简化外观和测试世界由本项目使用基础几何体描述，并非官方 CAD。标称尺寸、质量等参数参考 Livox MID-360 规格页；测量原点、IMU 外参和均匀盒体惯量明确标为近似。原有精细网格、彩色 GLB 和 Blender 工程仍未迁入或分发。
