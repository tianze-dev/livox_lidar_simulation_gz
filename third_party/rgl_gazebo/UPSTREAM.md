# RGL Gazebo 来源与本地改动

来源：RobotecAI/RGLGazeboPlugin，提交 `d4bf3cf36fe4a363a56df1bec2ce3809720db563`。
引入范围：RGLServerPlugin 的 7 个源文件、4 个头文件及上游 LICENSE。
保留原始格式与版权；本项目使用自己的 ament 构建入口，不引入上游 GUI 插件。

RGL Core 使用 v0.21.0。运行库、API 头和 MID-360／Avia 预设通过公开来源下载并按
`dependencies/lock.json` 校验；不从任何其他工作空间提取运行依赖。
Core 与本插件该版本的 LICENSE 文本相同，随安装保留本目录 LICENSE。

本地补丁记录：

- `Lidar.cc`：校验频率和量程、处理空点云及复位调度；初始化失败立即停用，按连通分量释放已创建节点（含未连接的预设分组）；输出传感器就绪信息。
- `LidarPatternLoader.cc`：拒绝空文件、负长度和不完整读取；`pattern_preset_path` 支持 `pattern_count` 与 `rays_per_frame` 属性并校验布局。套件使用锁文件生成这两个值，上游预设映射仍保留供兼容使用。
- Manager 与 Instance 的源码／头文件：实现 Gazebo ISystemReset，复位时保留传感器图并重建场景；实体删除时只在并行 PostUpdate 标记待清理，在串行 PreUpdate 释放图，避免多个传感器并发调用 RGL 清理接口。

这些是基础健壮性修复，不引入逐点时间、历史位姿或运动畸变。
