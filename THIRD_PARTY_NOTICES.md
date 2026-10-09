# 第三方来源与许可

原创代码采用 [Apache-2.0](LICENSE)。第三方代码、扫描数据、模型及品牌标识保留各自适用的归属和条件，根目录许可证不自动重新授权这些内容。

| 来源 | 使用内容 | 归属与分发说明 |
|---|---|---|
| [RGLGazeboPlugin](https://github.com/RobotecAI/RGLGazeboPlugin/tree/d4bf3cf36fe4a363a56df1bec2ce3809720db563) | `third_party/rgl_gazebo/` 中的 7 个源文件和 4 个头文件 | 保留上游 Apache-2.0 LICENSE；本地修改见文件头及 [UPSTREAM.md](third_party/rgl_gazebo/UPSTREAM.md) |
| [RGL Core v0.21.0](https://github.com/RobotecAI/RobotecGPULidar/tree/v0.21.0) | 官方 Linux x64 发行库与 API 头 | URL、版本和哈希由 `dependencies/lock.json` 锁定；此版本 Core 与插件 LICENSE 文本一致，安装时保留。预编译资产及其依赖的正式再分发审查尚未完成 |
| [Livox 官方仿真仓库](https://github.com/Livox-SDK/livox_laser_simulation/tree/1cce1073633a062b92e30243a4c2920e45551bb5) | 型号与扫描轨迹来源，原 CSV 不重复收录 | 原 MIT License（Copyright 2021 livox）保存在 [third_party/livox_scan/LICENSE](third_party/livox_scan/LICENSE)，并随安装保留 |
| RGL 收录的 Livox 扫描预设 | MID-360／Avia 的 `.mat3x4f` 文件 | 原数据来自 Livox，转换来源为 [RGLGazeboPlugin PR 52](https://github.com/RobotecAI/RGLGazeboPlugin/pull/52)；从固定上游下载并校验，保留 Robotec 与 Livox 声明 |
| MID-360 模型 | 官方 STL 衍生的彩色 DAE 和可选 PBR GLB | 所有者确认的分发依据、原文件哈希和外参来源见 [模型 NOTICE](meshes/mid360/NOTICE.md) |
| Avia 模型 | 官方 STEP 衍生的彩色 DAE 和可选 PBR GLB | [模型 NOTICE](meshes/avia/NOTICE.md) 记录来源与变换；公开再分发条件尚待确认，不适用 MID-360 的既有确认 |

简化外观与测试世界由本项目使用基础几何体描述。模型颜色和惯量是近似值；两款 IMU 相对雷达的位移采用手册名义值；Avia 雷达原点按手册图示与 CAD 前窗配准，不代替实物标定。原始 CAD、参考照片和手册不随运行资源分发。

可机读审查状态见 `dependencies/distribution.json`。`scripts/release_check.py --release` 在未解决或没有审查依据时返回失败；普通技术检查通过不代表分发许可已确认。

引入第三方内容时记录源 URL、版本或提交、文件范围、内容哈希、适用许可证、本地修改及分发条件；不得以本清单替代上游 LICENSE／NOTICE。公开下载不等于无限制再分发。未确认的资产条件应在公开发行前解决。
