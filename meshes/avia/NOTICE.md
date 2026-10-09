# Avia 模型来源与参数

本目录提供官方 CAD 衍生的 Avia 外观模型及几何校验信息。公开再分发条件尚待确认；官方公开下载不等于任意再分发许可。项目 Apache-2.0 不覆盖 Livox 原始 CAD、标识或商标，MID-360 的分发确认不自动适用于 Avia。

## 来源

- [Livox Avia 官方下载页](https://www.livoxtech.com/avia/downloads)，Avia 3D Model。
- [官方 STEP 文件](https://terra-1-g.djicdn.com/65c028cd298f4669a7f0e40e50ba1131/Download/Avia/Livox_Avia_shell_FOV.stp)。
- 原 STEP SHA256：`a1254e83f44ed1a16f47a70995a206ff5f9c6a73c1bb701bb9e8b1e937f87745`。
- [官方外观参考图](https://www.livoxtech.com/dps/757afa3728b8a229d78167ed65407f47.png)。

原 STEP 使用毫米单位；网格化后统一转换为米。运行资产包含雷达实体的 193139 个三角形，不含 FOV 示意体。原 STEP、参考图及模型制作工程不随运行资源分发。

## 外观与坐标

外观为银灰金属外壳、青绿色不透明光学窗口及深灰标识，使用三组 COLLADA Phong 材质。标识面向前偏移 0.03 mm 以避免共面闪烁；主体形状与尺寸保持 CAD 几何。材质为视觉近似，不是实测光学参数或 LiDAR 反射率，也没有外部纹理依赖。

可选的 `avia.glb` 来自同一上色版本，保留 193139 个三角形和三组 PBR 材质。GLB 采用 Y-up，Gazebo 加载时需 `mesh_rpy="1.5707963267948966 0 0"`，补偿后与 DAE 的安装坐标一致；默认仍使用 DAE。GLB 不改变 CAD 的来源与公开再分发限制，文件哈希见 `geometry_report.json`。

网格 +X 朝前窗、+Z 朝上、+Y 满足右手系，原点位于主体底面包围盒中心。CAD 转换关系（米）：`x=-CAD_x+0.0653, y=CAD_z+0.0385, z=CAD_y-0.0159`，为刚体变换，无非均匀缩放。最终网格哈希、包围盒及单位见 `geometry_report.json`。

主体尺寸为 x=91、y=61.2、z=64.8 mm，含侧面接口的整体宽度约 75.550 mm。碰撞使用主体和接口两个包络盒体，测试检查它们覆盖全部可视顶点，不用精细网格参与物理碰撞。

安装原点是本包的几何约定；测量中心和 IMU 原点近似置于主体中心 `(0, 0, 0.0324)` m，不是厂商标定外参。质量为 0.498 kg，惯量为均匀主体盒体近似。
