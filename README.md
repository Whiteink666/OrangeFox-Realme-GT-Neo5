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

- **OrangeFox R12.0 新 UI**：`fox_12.1` manifest 拉取的 `bootable/recovery` 中
  `FOX_INTERNAL_RELEASE := R12.0`，即 Material You Expressive 界面、SVG 图标引擎、
  Fox White/Dark 双主题、Inter 字体、手势导航**已在本次构建中**，无需再迁移分支。
- 设备树的 `TW_THEME := portrait_hdpi` 仅影响旧主题兼容；R12 的界面资源由
  `vendor/recovery` + `bootable/recovery` 提供。
- 已修复：把 10 个 OPLUS `my_*` 逻辑分区补进 `AB_OTA_PARTITIONS`，消除 OTA 时报
  “logical partition not found” 的隐患（此前靠 `OF_IGNORE_LOGICAL_MOUNT_ERRORS` 掩盖）。
- **云端编译已跑通**：Actions run `42509233113`（head `86bd1f5`）成功产出
  `OrangeFox-R12.0-Unofficial-RMXTARO.img` / `.zip`，编译耗时 1h57m，`mka_rc=0`。

## 构建

### 方式一：GitHub Actions 云端编译（推荐，免密钥）

本仓库已内置 `.github/workflows/build.yml`：

1. 把本仓库 **公开** 推送到你的 GitHub（OrangeFox 为 GPL-3.0，要求公开修改过的设备树）。
2. 在仓库 **Actions** 页点 **Run workflow**（或 push 到 `main`/`master`/`fox-12.1` 分支）。
3. 编译成功后 workflow 会自动创建 **Pre-release**（tag `ofox-RMXTARO-r<run号>`），
   在 **Releases → Assets** 直接下载 `recovery.img`、已签名的 `OrangeFox-*.zip` 与
   `.md5` 校验文件——无需登录、走 CDN。Actions **Artifacts** 里也保留同样一份
   （保留 30 天），但匿名下载会 401、速度也慢，仅供备用。
4. 先 `fastboot flash recovery`，进 recovery 后再刷 zip 完成持久化安装。

> 云端编译使用 GitHub 自带的 `GITHUB_TOKEN`，**无需你提供任何个人密钥**。
> workflow 只监听 `push` / `workflow_dispatch`；发布 Release **不会**再触发一轮编译。
> 若免费 runner 磁盘/内存吃紧，可换用大磁盘或自托管 runner。

### 方式二：本地 WSL2 编译

```bash
# 1. 拉取 OrangeFox 源码（fox_12.1 基底）
git clone https://gitlab.com/OrangeFox/sync.git ~/ofsync && cd ~/ofsync
./orangefox_sync.sh --branch 12.1 --path ~/fox_12.1

# 2. 放入设备树
mkdir -p ~/fox_12.1/device/realme
git clone -b main <本仓库地址> ~/fox_12.1/device/realme/RMXTARO

# 3. 编译
cd ~/fox_12.1
export ALLOW_MISSING_DEPENDENCIES=true LC_ALL=C FOX_BUILD_DEVICE=RMXTARO
. build/envsetup.sh
lunch twrp_RMXTARO-eng
mka recoveryimage -j$(nproc)
```

产物：`out/target/product/RMXTARO/recovery.img`、
`OrangeFox-R12.0-Unofficial-RMXTARO.zip`（已签名，含 `META-INF` / `magiskboot`）及对应 `.md5`。

## 刷入

前置条件：bootloader 已解锁、`fastboot devices` 能识别设备、已备份 `/data`，
且**当前固件版本与镜像匹配**（本镜像 `kernel_size=0`，不含内核，直接用机器的 5.10 内核）。

### 最小验证流程（只需 `recovery.img`，不动 vbmeta、不清数据）

Windows PowerShell，路径换成你的实际位置：

```powershell
fastboot devices
fastboot flash recovery "C:\Users\Lenovo\WorkBuddy\2026-11-08-23-12-29\build-output\recovery.img"
fastboot reboot recovery
```

刷完校验一下：

```powershell
Get-FileHash .\build-output\recovery.img -Algorithm SHA256
```

若 `fastboot reboot recovery` 无响应（部分 realme 机型不实现该命令），用
`fastboot reboot` 并在震动的瞬间按住 **音量下**，或直接用电源 + 音量下组合键。

> ⚠️ 只刷 `recovery.img` 是**非持久安装**：重启进一次系统后，原厂 recovery 可能被
> 启动链/OTA 还原。长期使用必须做下面的完整安装。首次进入会要求输入锁屏密码解密
> `/data`；解密失败不要 format data，先退回排查固件版本与 Keymaster 覆盖。

### 完整安装（需要 OrangeFox 签名 zip）

进 recovery 后刷 `OrangeFox-R12.0-Unofficial-RMXTARO.zip`。这是 OrangeFox 官方
R12.0 的**必要步骤**——官方明确写「do NOT just flash the recovery image in the zip
and stop there」，只刷 img 不算安装完成。zip 会把 OrangeFox 固化到启动链（含写入
非活动 slot，切槽后仍在）。

⚠️ 本树是 `FOX_VANILLA_BUILD=1` 的 vanilla 构建。按官方 build_vars 文档，该模式会
跳过全部 OrangeFox patches 并自动启用 `OF_SKIP_ORANGEFOX_PROCESS`，且
`OF_PATCH_AVB20` 在 vanilla 下被忽略（对 A/B 设备本来也不生效）。**不要指望 zip
替你处理 vbmeta / dm-verity**，请保持 vbmeta 与当前固件一致。
官方还要求：刷任何 ROM 之后都要立刻重刷一次 OrangeFox，并始终先做完整备份。

**只有确认系统因 dm-verity 校验起不来时**，才需要另刷 `vbmeta.img`（需自行从与当前
固件同版本的官方线刷包提取，本仓库不提供）：

```bash
fastboot --disable-verity --disable-verification flash vbmeta vbmeta.img
```

⚠️ 这条命令会改变 AVB 状态，通常伴随**清空 data**，务必先备份；不要在最小验证流程里执行。

⚠️ **禁止 `fastboot boot recovery.img`**：本机为 Virtual A/B 动态分区设备，临时启动
环境不完整，会导致解密失败甚至变砖。必须 `flash` 进分区再重启。

## 白墨工作室自定义页面

进入方式：**高级（Advanced）→ 自定义设置（Custom settings）**。这个入口是 OrangeFox
官方预留的维护者 hook，不是我们改出来的：

- `ui.xml` 里已有 `<xml name="/sbin/maintainer.xml" default="/twres/pages/dummy.xml"/>`
- `pages/advanced.xml` 的按钮带 `<condition var1="fileexists" var2="/sbin/maintainer.xml"/>`

所以只要设备树提供 `/sbin/maintainer.xml`，入口就自动出现，**不需要 fork 或修改上游
`bootable/recovery` 源码**，云编译每次重新同步源码也不会丢失。

| 内容 | 位置 |
| --- | --- |
| 页面 / 按钮 / 文案 | `recovery/root/sbin/maintainer.xml`（5 个页面：`maintainer`、`whiteink_qq`、`whiteink_coolapk`、`whiteink_github`、`whiteink_about`） |
| 作者横幅 / 头像 / 二维码 / 开机叠加图 | `recovery/root/twres/images/Whiteink/*.png` |
| **开机启动画面** | `recovery/root/twres/splash.xml`（保留原狐头 logo 与 `OrangeFox` / `Recovery` 英文，叠加白墨头像 + 工作室名） |
| 云编译注入（防止 twres 生成顺序覆盖资源） | `.github/workflows/build.yml` → `Inject Whiteink UI overlay into theme source`（同时覆盖主题源的 `splash.xml`） |
| 默认语言 | `BoardConfig.mk` → `TW_DEFAULT_LANGUAGE := zh_CN`（仍可在 设置 → 语言 切换） |
| 署名 / 版本 | `fox_RMXTARO.mk` → `OF_MAINTAINER := Whiteink`、`FOX_MAINTAINER_PATCH_VERSION := 1` |

作者署名是 **🐾白墨🐾Whiteink🐾丨白墨(Whiteink)工作室**。内置中文字体
`wqy-microhei.ttf` 不含 U+1F43E，直接写进 `<text>` 会显示豆腐块，因此横幅用
Segoe UI Emoji 渲染真实爪印并统一染成狐橙 `#ed6f02`，作为 PNG 放进 `twres/images/Whiteink/`。

三个入口用二维码落地（recovery 里没有浏览器，扫码是最实用的跳转方式）：

| 入口 | 二维码内容 |
| --- | --- |
| QQ 群 | `mqqapi://card/show_pslcard?...uin=287398984&card_type=group...`（QQ 扫一扫直接开群资料卡），页面同时显示群号 |
| 酷安 | `https://www.coolapk.com/u/30264531` |
| GitHub | `https://github.com/Whiteink666/OrangeFox-Realme-GT-Neo5`（**就是本仓库**） |

想换链接/群号：改 PNG 里的二维码内容后覆盖同名文件即可；生成脚本用的参数是
`qrcode` 的 `ERROR_CORRECT_M` + 4 模块静区，输出 480×480 整数倍模块尺寸，避免缩放糊掉。

### 白墨头像与开机画面

用户提供的蓝白 Q 版形象已抠掉白底（连通域法，只清除与画布边缘相连的白色，
角色身上的白色围巾/绒毛保留），导出为多尺寸透明 PNG：

| 文件 | 尺寸 | 用在哪 |
| --- | --- | --- |
| `splash_avatar.png` | 1080×1920 透明 | 启动画面：头像 + `白墨(Whiteink)工作室`，与狐头 logo 共用中心锚点 |
| `avatar_card.png` | 984×300 | 「关于此 Recovery」页顶部：头像 + 署名 + 三个入口摘要 |
| `avatar_small.png` | 150×137 | QQ群 / 酷安 / GitHub 三个二维码页右侧 |
| `avatar_mini.png` | 96×88 | 维护者主页右下角 |

`splash.xml` 是上游文件的完整副本，只多了一个 `<image>` 资源和一个 `<image>`
元素，**原有狐头 logo 和 `OrangeFox` / `Recovery` 两行英文原样保留**。中文工作室名
直接画进 PNG，因为 splash 用的 Inter 字体没有中文字形。

> `OF_NO_SPLASH_CHANGE := 1` 的准确含义（官方 build_vars）：
> "set this to 1 to disable changing the splash image" —— 只禁用**在 recovery 里运行时**
> 更换开机图，不阻止编译期覆盖。所以自定义 splash 必须编译进 recovery，运行后在
> 设置里是换不了的，这是预期行为。

后续还能加的（尚未做）：`themes/accent.xml` 改专属配色、`FOX_USE_MISANS_FONTS := 1`
换中文字体、整套 SVG 图标替换、`twres/credits.txt` 追加白墨署名。

## 已知注意事项

1. **解密**：`BoardConfig.mk` 里 `PLATFORM_VERSION := 99.87.36` 是骗过 Keymaster TA 的
   版本覆盖，删除会导致 `/data` 解密失败。升级到 realme UI 7 / Android 16 后必须在对应
   固件版本上重测。
2. **内核非 GKI**：recovery.img 不含内核（`BOARD_EXCLUDE_KERNEL_FROM_RECOVERY_IMAGE := true`），
   直接用机器 5.10 内核。刷错 150W↔240W 或 A13↔A16 固件会起不来。
3. **OPLUS 私有分区**：已补 `my_*` 到 `AB_OTA_PARTITIONS`，OTA 不再报逻辑分区缺失。
4. **FRP**：`twrp.flags` 已加 `/frp` 备份入口；刷完若无法设置密码/指纹，进 fastboot 清 FRP。
5. **Vanilla 构建**：`vendorsetup.sh` 设了 `FOX_VANILLA_BUILD=1`，构建日志会出现
   “skip all OrangeFox patches / Deleting AromaFM”。即本包**不含 AromaFM 与部分 OrangeFox
   附加 patch**（zip 内仍带 `sdcard/Fox/FoxFiles/Magisk.zip`）。R12.0 新 UI 属于
   `bootable/recovery`，不受此项影响；若需要 AromaFM 等功能，去掉该变量后重编。

## Credits

- 设备树基于 [MisterZtr/recovery_device_realme_RMXTARO](https://github.com/MisterZtr/recovery_device_realme_RMXTARO)（`fox-12.1` 分支）
- OrangeFox Recovery Project（TeamWin TWRP 衍生）
- 原始贡献：Bot-cd-Crypton、hoangzk9as、Ctapchuk、Kychera22

## License

GPL-3.0。详见 [LICENSE](LICENSE)。
