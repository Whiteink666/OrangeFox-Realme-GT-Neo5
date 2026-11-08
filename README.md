# OrangeFox Recovery for realme GT Neo5 / GT3 (RMXTARO · senna)

一款面向 **realme GT Neo5 / GT3** 的第三方 Recovery，基于 OrangeFox（橙狐）构建，
由 **Whiteink（白墨）** 维护与定制。

| 项目 | 信息 |
| --- | --- |
| 设备 | realme GT Neo5 / GT3 |
| 代号 | `RMXTARO`（realme 内部平台名，别名 `senna`） |
| 型号 | RMX3706（150W / 5000mAh）、RMX3708（240W / 4600mAh）、RMX3709（海外 GT3） |
| SoC | 高通 SM8475 骁龙 8+ Gen 1 |
| 架构 | arm64（内核 5.10，非 GKI，来自机器 boot/vendor_boot） |
| 分区 | Virtual A/B + 独立 recovery 分区 + 动态分区（super） |

## 状态

- 当前基线：**OrangeFox R11.3**（fox_12.1 基底），主题仍为旧版 `portrait_hdpi`。
- 下一步：将 `bootable/recovery` + `vendor/recovery` 切到 **R12.0** 分支，启用全新 UI
  （Material You Expressive、SVG 图标引擎、Fox White/Dark 双主题、Inter 字体、手势导航）。
- 已修复：把 10 个 OPLUS `my_*` 逻辑分区补进 `AB_OTA_PARTITIONS`，消除 OTA 时报
  “logical partition not found” 的隐患（此前靠 `OF_IGNORE_LOGICAL_MOUNT_ERRORS` 掩盖）。

## 构建

### 方式一：GitHub Actions 云端编译（推荐，免密钥）

本仓库已内置 `.github/workflows/build.yml`：

1. 把本仓库 **公开** 推送到你的 GitHub（OrangeFox 为 GPL-3.0，要求公开修改过的设备树）。
2. 在仓库 **Actions** 页点 **Run workflow**（或 push 到 `main`/`master`/`fox-12.1` 分支）。
3. 编译完成后，在 **Artifacts** 下载 `recovery.img`。

> 云端编译使用 GitHub 自带的 `GITHUB_TOKEN`，**无需你提供任何个人密钥**。
> 若免费 runner 磁盘/内存吃紧，可换用大磁盘或自托管 runner。

### 方式二：本地 WSL2 编译

```bash
# 1. 拉取 OrangeFox 源码（fox_12.1 基底）
git clone https://gitlab.com/OrangeFox/sync.git ~/ofsync && cd ~/ofsync
./orangefox_sync.sh --branch 12.1 --path ~/fox_12.1

# 2. 放入设备树
mkdir -p ~/fox_12.1/device/realme
git clone -b fox-12.1 <本仓库地址> ~/fox_12.1/device/realme/RMXTARO

# 3. 编译
cd ~/fox_12.1
export ALLOW_MISSING_DEPENDENCIES=true LC_ALL=C FOX_BUILD_DEVICE=RMXTARO
. build/envsetup.sh
lunch twrp_RMXTARO-eng
mka adbd recoveryimage -j$(nproc)
```

产物：`out/target/product/RMXTARO/recovery.img`

## 刷入

```bash
fastboot --disable-verity --disable-verification flash vbmeta vbmeta.img
fastboot flash recovery out/target/product/RMXTARO/recovery.img
fastboot reboot recovery
# 进 recovery 后，再刷一次 OrangeFox 的 zip 完成完整安装
```

⚠️ **禁止 `fastboot boot recovery.img`**：本机为 Virtual A/B 动态分区设备，临时启动
环境不完整，会导致解密失败甚至变砖。必须 `flash` 进分区再重启。

## 自定义元素（加自己的东西）

| 想改的东西 | 文件 |
| --- | --- |
| 署名 / 版本 | `fox_RMXTARO.mk` 的 `OF_MAINTAINER` / `FOX_MAINTAINER_PATCH_VERSION` |
| 配色 / 字体 / 图标 | `bootable/recovery` 的 `ui.xml` + `themes/` + `images/`（R12 用 SVG） |
| 自定义页面 / 按钮（工作室、QQ群、酷安、GitHub） | `pages/*.xml` + `portrait.xml` |
| 状态栏 / 挖孔 / 圆角 | `fox_RMXTARO.mk`：`OF_SCREEN_H 2412`、`OF_STATUS_H 106`、`OF_STATUS_INDENT_* 48`、`OF_HIDE_NOTCH 1` |
| 开机图 | ⚠️ 本树设了 `OF_NO_SPLASH_CHANGE := 1`，**开机图必须编译进 recovery**，运行时换无效 |
| 中文字体 | R12 起可用 `FOX_USE_MISANS_FONTS := 1` |

## 已知注意事项

1. **解密**：`BoardConfig.mk` 里 `PLATFORM_VERSION := 99.87.36` 是骗过 Keymaster TA 的
   版本覆盖，删除会导致 `/data` 解密失败。升级到 realme UI 7 / Android 16 后必须在对应
   固件版本上重测。
2. **内核非 GKI**：recovery.img 不含内核（`BOARD_EXCLUDE_KERNEL_FROM_RECOVERY_IMAGE := true`），
   直接用机器 5.10 内核。刷错 150W↔240W 或 A13↔A16 固件会起不来。
3. **OPLUS 私有分区**：已补 `my_*` 到 `AB_OTA_PARTITIONS`，OTA 不再报逻辑分区缺失。
4. **FRP**：`twrp.flags` 已加 `/frp` 备份入口；刷完若无法设置密码/指纹，进 fastboot 清 FRP。

## Credits

- 设备树基于 [MisterZtr/recovery_device_realme_RMXTARO](https://github.com/MisterZtr/recovery_device_realme_RMXTARO)（OrangeFox R11.3）
- OrangeFox Recovery Project（TeamWin TWRP 衍生）
- 原始贡献：Bot-cd-Crypton、hoangzk9as、Ctapchuk、Kychera22

## License

GPL-3.0。详见 [LICENSE](LICENSE)。
