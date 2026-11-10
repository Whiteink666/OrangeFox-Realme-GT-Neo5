# OrangeFox Recovery for realme GT Neo5 / GT3 (RMXTARO · senna)

**R12.0 新 UI** · **默认简体中文** · **GPL-3.0** · 最新构建 `ofox-RMXTARO-r10`

一款面向 **realme GT Neo5 / GT3** 的第三方 Recovery，基于 OrangeFox（橙狐）R12.0 构建，
由 **🐾白墨🐾Whiteink🐾丨白墨(Whiteink)工作室** 维护与定制。

> [!NOTE]
> 最新可刷产物在 **[`ofox-RMXTARO-r10`](https://github.com/Whiteink666/OrangeFox-Realme-GT-Neo5/releases/tag/ofox-RMXTARO-r10)**，
> 含高性能 governor、60 fps 转圈动画与全部自定义页面。刷入前请先读
> [刷入](#刷入) 与 [已知注意事项](#已知注意事项)。

| 项目 | 信息 |
| --- | --- |
| 设备 | realme GT Neo5 / GT3 |
| 代号 | `RMXTARO`（realme 内部平台名，别名 `senna`） |
| 型号 | RMX3706（150W / 5000mAh）、RMX3708（240W / 4600mAh）、RMX3709（海外 GT3） |
| SoC | 高通 SM8475 骁龙 8+ Gen 1 |
| 架构 | arm64（内核 5.10，非 GKI，来自机器 boot/vendor_boot） |
| 分区 | Virtual A/B + 独立 recovery 分区 + 动态分区（super） |
| 维护 | [酷安 @白墨Whiteink](https://www.coolapk.com/u/30264531) · [GitHub Whiteink666](https://github.com/Whiteink666) · QQ 群 287398984 |

---

## 目录

**开始使用** · [状态](#状态) · [刷入](#刷入) · [验证产物](#验证产物)

**构建与维护** · [构建](#构建) · [维护约定](#维护约定) · [常见问题](#常见问题)

**定制内容** · [白墨工作室自定义页面](#白墨工作室自定义页面) · [UI 流畅度](#ui-流畅度) · [硬件适配](#硬件适配)

**其他** · [已知注意事项](#已知注意事项) · [Credits](#credits) · [License](#license)

---

## 状态

| 项目 | 说明 |
| --- | --- |
| OrangeFox 版本 | **R12.0**（`fox_12.1` manifest，`FOX_INTERNAL_RELEASE := R12.0`） |
| 界面 | Material You Expressive、SVG 图标引擎、Fox White / Fox Dark 双主题、Inter 字体、手势导航 |
| 默认语言 | **简体中文**（`TW_DEFAULT_LANGUAGE := zh_CN`，可在 设置 → 语言 切换） |
| 定制内容 | 白墨维护者页面、QQ 群 / 酷安 / GitHub 二维码、开机画面吉祥物头像 |
| 最新成功构建 | Actions **run 10**（`42743206972`，head `6ef4601`）成功，15 步全绿，`mka_rc=0`，耗时约 **2h20m** |
| 典型产物 | `recovery.img`（100 MiB）+ 已签名 `OrangeFox-R12.0-Unofficial-RMXTARO.zip` + 两个 `.md5` |

- `fox_12.1` manifest 拉取的 `bootable/recovery` 已是 R12.0 新 UI，**无需再迁移分支**；
  从镜像解出的 `twres/changelog.txt` 首段即 `OrangeFox Recovery R12.0 Changelog`。
- 设备树的 `TW_THEME := portrait_hdpi` 仅影响旧主题兼容；R12 的界面资源由
  `vendor/recovery` + `bootable/recovery` 提供。
- 已修复：把 10 个 OPLUS `my_*` 逻辑分区补进 `AB_OTA_PARTITIONS`，消除 OTA 时报
  “logical partition not found” 的隐患（此前靠 `OF_IGNORE_LOGICAL_MOUNT_ERRORS` 掩盖）。

---

## 构建

### 方式一：GitHub Actions 云端编译（推荐，免密钥）

本仓库已内置 `.github/workflows/build.yml`：

1. 把本仓库 **公开** 推送到你的 GitHub（OrangeFox 为 GPL-3.0，要求公开修改过的设备树）。
2. 在仓库 **Actions** 页点 **Run workflow**（或 push 到 `main` / `master` / `fox-12.1` 分支）。
3. 编译成功后 workflow 会自动创建 **Pre-release**（tag `ofox-RMXTARO-r<run号>`），
   在 **Releases → Assets** 直接下载 `recovery.img`、已签名的 `OrangeFox-*.zip` 与
   `.md5` 校验文件——无需登录、走 CDN。Actions **Artifacts** 里也保留同样一份
   （保留 30 天），但匿名下载会 401、速度也慢，仅供备用。
4. 先 `fastboot flash recovery`，进 recovery 后再刷 zip 完成持久化安装。

> [!NOTE]
> 云端编译使用 GitHub 自带的 `GITHUB_TOKEN`，**无需你提供任何个人密钥**。
> workflow 只监听 `push` / `workflow_dispatch`；发布 Release **不会**再触发一轮编译。

#### 耗时与资源

| 项目 | 值 |
| --- | --- |
| 单次全量编译 | 约 **2 小时**（基线 run：整个 run 124.5 分钟，build step 约 117 分钟） |
| 编译规模 | 约 **28030** 个 ninja target（整个 AOSP / OrangeFox 基底，不只是 recovery） |
| 并行度 | `mka recoveryimage -j1`（为低内存 runner 设的，代价是慢） |
| 超时 | build step 150 分钟，整个 job 180 分钟 |
| runner | `ubuntu-22.04`，约 15 GiB 内存 / 146 GiB 磁盘，额外 8 GiB swapfile |
| 缓存 | 每次都是全新 runner，**无跨 run 的 ccache 复用**，重跑即完整两小时 |

> [!TIP]
> 想缩短等待可把 `-j1` 提到 `-j2`（15 GiB 内存通常扛得住），但需自行验证稳定性；
> 文档与 UI 小改建议统一带 `[skip ci]`，攒够一批再编，避免反复等两小时。

#### CI 产物与日志

| 内容 | 位置 |
| --- | --- |
| 可刷镜像 / 签名 zip / 校验文件 | Pre-release `ofox-RMXTARO-r<run号>` 的 Assets（推荐） |
| 同样一份备用 | Actions Artifacts → `OrangeFox-RMXTARO-<run号>`（30 天） |
| **完整编译日志** | Actions Artifacts → `build-log-<run号>`（步骤结束后上传） |
| 实时进度 | Actions 页面实时日志中的 `HEARTBEAT` 与 `-- ninja progress: xx% xxxx/28030 --` |

ninja 的全量输出（约 4 MiB / 28000 行）会被写进 runner 上的 `ofox_build.log`，
**不经过实时日志流**；实时日志里只有每分钟一组心跳，含采样进度、输出空闲秒数、
内存 / 磁盘 / 负载。连续 20 分钟无构建输出时会打印一次 `STALL` 进程状态用于取证。

#### CI 已知问题：实时日志管道冻结

历史上有两次构建在 **41–42% 进度** 处冻结：流出的实时日志分别停在
`2,110,272` 与 `2,110,393` 字节（**仅差 121 字节，约 2.011 MiB**），ninja、`tee`
和心跳这些写 stdout 的进程**同时**停止，而内存（可用 12 GiB）、磁盘（剩余 67 GiB）、
load（1.0）都正常。这是 GitHub runner 的 live-log 上传管道 wedged 后把 stdout 写操作
全部阻塞，**不是编译内容、不是 DIY 资源、也不是 OOM**。

当前 workflow 的规避方式就是把 ninja 输出全部重定向到文件，让实时日志体积保持在
约 200 KiB / 2 小时，远离触发点。由此带来一个副作用：

> [!NOTE]
> 运行中的 job 用 `GET /actions/jobs/<id>/logs` 下载归档日志可能返回
> `BlobNotFound` / 404 —— 因为 stdout 量太小，尚未触发归档分片上传。
> **这不是失败信号**，完整日志会在步骤结束后作为 `build-log-<run号>` artifact 出现。

判断编译是否还活着，看 Actions 页面实时日志里 `===== HEARTBEAT =====` 有没有每分钟
刷新、`ninja progress` 有没有往上涨；不要依赖归档日志 API。若自托管 runner 或
本地编译，则完全不受此问题影响。

### 方式二：本地 WSL2 编译

本地没有 runner 的日志管道限制，也不会被 150 分钟超时打断。建议 WSL2 分配
≥16 GiB 内存、≥120 GiB 可用磁盘；首次同步源码约 40–60 GiB。

```bash
# 1. 拉取 OrangeFox 源码（fox_12.1 基底）
git clone https://gitlab.com/OrangeFox/sync.git ~/ofsync && cd ~/ofsync
./orangefox_sync.sh --branch 12.1 --path ~/fox_12.1

# 2. 放入设备树
mkdir -p ~/fox_12.1/device/realme
git clone -b main https://github.com/Whiteink666/OrangeFox-Realme-GT-Neo5.git \
  ~/fox_12.1/device/realme/RMXTARO

# 3. 编译
cd ~/fox_12.1
export ALLOW_MISSING_DEPENDENCIES=true LC_ALL=C FOX_BUILD_DEVICE=RMXTARO
. build/envsetup.sh
lunch twrp_RMXTARO-eng
mka recoveryimage -j$(nproc)
```

本地用 `-j$(nproc)` 会明显快于云端的 `-j1`；若出现 OOM，把并行度降到 `-j2` / `-j1`。
另外本地编译时也要把 `recovery/root/twres/splash.xml` 与 `twres/images/Whiteink/`
覆盖到 `bootable/recovery/gui/theme/portrait_hdpi/`，否则主题打包顺序可能用回上游
splash（云端的 `Inject Whiteink UI overlay into theme source` 步骤就是干这件事）。

产物：`out/target/product/RMXTARO/recovery.img`、
`OrangeFox-R12.0-Unofficial-RMXTARO.zip`（已签名，含 `META-INF` / `magiskboot`）及对应 `.md5`。

---

## 刷入

前置条件：bootloader 已解锁、`fastboot devices` 能识别设备、已备份 `/data`，
且**当前固件版本与镜像匹配**（本镜像 `kernel_size=0`，不含内核，直接用机器的 5.10 内核）。

### 最小验证流程（只需 `recovery.img`，不动 vbmeta、不清数据）

Windows PowerShell，路径换成你把镜像解压到的实际位置：

```powershell
fastboot devices
fastboot flash recovery "C:\path\to\recovery.img"
fastboot reboot recovery
```

刷前先校验文件完整性，与 Release 里的 `.img.md5` / `.zip.md5` 内容比对：

```powershell
Get-FileHash .\recovery.img -Algorithm MD5
Get-FileHash .\recovery.img -Algorithm SHA256
```

若 `fastboot reboot recovery` 无响应（部分 realme 机型不实现该命令），用
`fastboot reboot` 并在震动的瞬间按住 **音量下**，或直接用电源 + 音量下组合键。

> [!WARNING]
> 只刷 `recovery.img` 是**非持久安装**：重启进一次系统后，原厂 recovery 可能被
> 启动链 / OTA 还原。长期使用必须做下面的完整安装。首次进入会要求输入锁屏密码解密
> `/data`；解密失败不要 format data，先退回排查固件版本与 Keymaster 覆盖。

### 完整安装（需要 OrangeFox 签名 zip）

进 recovery 后刷 `OrangeFox-R12.0-Unofficial-RMXTARO.zip`。这是 OrangeFox 官方
R12.0 的**必要步骤**——官方明确写「do NOT just flash the recovery image in the zip
and stop there」，只刷 img 不算安装完成。zip 会把 OrangeFox 固化到启动链（含写入
非活动 slot，切槽后仍在）。

> [!WARNING]
> 本树是 `FOX_VANILLA_BUILD=1` 的 vanilla 构建。按官方 build_vars 文档，该模式会
> 跳过全部 OrangeFox patches 并自动启用 `OF_SKIP_ORANGEFOX_PROCESS`，且
> `OF_PATCH_AVB20` 在 vanilla 下被忽略（对 A/B 设备本来也不生效）。**不要指望 zip
> 替你处理 vbmeta / dm-verity**，请保持 vbmeta 与当前固件一致。
> 官方还要求：刷任何 ROM 之后都要立刻重刷一次 OrangeFox，并始终先做完整备份。

**只有确认系统因 dm-verity 校验起不来时**，才需要另刷 `vbmeta.img`（需自行从与当前
固件同版本的官方线刷包提取，本仓库不提供）：

```bash
fastboot --disable-verity --disable-verification flash vbmeta vbmeta.img
```

> [!WARNING]
> 这条命令会改变 AVB 状态，通常伴随**清空 data**，务必先备份；不要在最小验证流程里执行。

> [!IMPORTANT]
> **禁止 `fastboot boot recovery.img`**：本机为 Virtual A/B 动态分区设备，临时启动
> 环境不完整，会导致解密失败甚至变砖。必须 `flash` 进分区再重启。

---

## 验证产物

刷之前建议先确认自定义 UI 真的进了镜像，两种方式：

**实机**（最直接）：开机画面应同时出现原狐头 logo、`OrangeFox` / `Recovery` 两行英文，
以及上方的白墨吉祥物头像和「白墨(Whiteink)工作室」；进入后
**高级（Advanced）→ 自定义设置（Custom settings）** 应能看到 5 个页面和简体中文界面。

**离线解包**：`recovery.img` 是 Android boot image v4，偏移 4096 起是 LZ4-legacy
**多 block** 压缩的 cpio。注意别把整段当单个 LZ4 block 解压（会得到乱码），
需要逐 4 字节读取 block size 逐块解压再拼成 `ramdisk.cpio`，或直接用
`magiskboot unpack` / `unpack_bootimg` 解包。展开后应存在：

```text
/sbin/maintainer.xml
/twres/splash.xml
/twres/images/Whiteink/*.png      # 8 张：banner / 3 张二维码 / 4 种头像尺寸
/twres/languages/zh_CN.xml
```

> [!WARNING]
> 不要手工解包再重打包 `recovery.img` 拿去刷，容易破坏签名与 AVB 结构；
> 离线解包只用于检查内容。

---

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

想换链接 / 群号：用 `qrcode` 重新生成对应 PNG 覆盖同名文件即可，参数保持
`ERROR_CORRECT_M` + 4 模块静区 + 480×480 整数倍模块尺寸，避免缩放糊掉；
改完记得按 [验证产物](#验证产物) 检查一遍。

### 白墨头像与开机画面

蓝白 Q 版吉祥物已抠掉白底（连通域法，只清除与画布边缘相连的白色，角色身上的
白色围巾 / 绒毛保留），导出为多尺寸透明 PNG：

| 文件 | 尺寸 | 用在哪 |
| --- | --- | --- |
| `splash_avatar.png` | 1080×1920 透明 | 启动画面：头像 + `白墨(Whiteink)工作室`，与狐头 logo 共用中心锚点 |
| `avatar_card.png` | 984×300 | 「关于此 Recovery」页顶部：头像 + 署名 + 三个入口摘要 |
| `avatar_small.png` | 150×137 | QQ 群 / 酷安 / GitHub 三个二维码页右侧 |
| `avatar_mini.png` | 96×88 | 维护者主页右下角 |

`splash.xml` 是上游文件的完整副本，只多了一个 `<image>` 资源和一个 `<image>`
元素，**原有狐头 logo 和 `OrangeFox` / `Recovery` 两行英文原样保留**。中文工作室名
直接画进 PNG，因为 splash 用的 Inter 字体没有中文字形。

> [!NOTE]
> `OF_NO_SPLASH_CHANGE := 1` 的准确含义（官方 build_vars）：
> "set this to 1 to disable changing the splash image" —— 只禁用**在 recovery 里运行时**
> 更换开机图，不阻止编译期覆盖。所以自定义 splash 必须编译进 recovery，运行后在
> 设置里是换不了的，这是预期行为。

后续还能加的（尚未做）：`themes/accent.xml` 改专属配色、`FOX_USE_MISANS_FONTS := 1`
换中文字体、整套 SVG 图标替换、`twres/credits.txt` 追加白墨署名。

---

## UI 流畅度

Recovery 里没有 Android 的 SurfaceFlinger / HWUI / vsync 合成：界面由 CPU 软件渲染到
framebuffer，**按需重绘**——静止时一帧都不画，只有触摸跟手、页面切换和转圈动画时逐帧
重绘。所以不存在「恒定 60fps」，体感卡顿来自单帧耗时过长。R12 的 SVG 图标、阴影与圆角
在 1240×2772 全屏上光栅化，一帧约 13.7 MB（`RGBX_8888`），CPU 降频时尤其明显。

本构建做了三件事，开箱即默认高性能：

| 改动 | 位置 | 作用 |
| --- | --- | --- |
| 开机锁定 `performance` governor | `recovery/root/init.recovery.qcom.rc` 的 `fox_perf` 服务，`on boot` 与解密完成后各触发一次 | 避免默认「均衡」把 UI 线程压到小核低频 |
| 默认「Recovery 性能模式」改为**高性能** | 云端编译时 patch 上游 `pages/settings.xml` 的两处兜底默认值 | 让 OrangeFox 自身的启动逻辑也用高性能 |
| 转圈动画 30 → 60 fps | 云端编译时 patch 上游 `pages/{files,main,templates/base}.xml` 共 4 处 | 只影响进度条不确定动画，**不是全局帧率上限** |

> [!NOTE]
> 主题里那 4 处 `fps="30"` 的条件都是 `ui_progress`，只控制进度条转圈；全局 UI 没有
> 帧率常量。所以「没有 60 帧」无法靠改一个数字解决。

首次进入后建议再确认两处（一次设置即可持久生效）：

1. **设置 → 性能 → Recovery 性能模式**：应显示「高性能」。若之前在 `/sdcard/Fox/`
   保存过「均衡」，旧的持久化设置会覆盖编译期默认值，手动改一次并重启 recovery。
2. **设置 → 自定义 → 手势导航 → 关闭「开启手势」**：R12 默认开启，手势跟随手指是
   连续全屏重绘，比点击操作重得多；改回导航栏通常最立竿见影。

临时判定（recovery 里连着 adb，立即生效、不改任何设置）：

```powershell
adb shell cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
adb shell /sbin/setgovernor performance
```

---

## 硬件适配

这两套驱动**设备树里本来就有**，做的是把它们接进启动链，而不是移植驱动：

| 组件 | 设备树里已有的文件 | 接线方式 |
| --- | --- | --- |
| X 轴线性马达 | `vendor/lib/modules/1.1/aw8697.ko`（Awinic AW8697）、`/dev/awinic_haptic`、`system/bin/realme.vibrator.service`（AIDL `IVibrator` V2）、`aac_richtap.config` + 809/815 波形、`IVibrator/default` VINTF manifest | 加进 `TW_LOAD_VENDOR_MODULES` 显式 insmod；init 里 `wait /dev/awinic_haptic 2` 之后再 `start realme.vibrator`；**UI 调用路径由 `scripts/patch_minuitwrp_haptics.py` 改成 `perform(CLICK)`**，见下 |
| 屏幕面板 | `vendor/lib/modules/1.1/panel_event_notifier.ko`、`vendor.display.config@1.0/2.0`、`TW_BRIGHTNESS_PATH` | 加进 `TW_LOAD_VENDOR_MODULES`；新增 `sbin/fox_refresh.sh` 做保守的 144 Hz 探测 |

### 为什么 r11 仍是「转子震感 + 滑动卡」

> [!IMPORTANT]
> **r11 及更早版本的马达接线没有打中根因。** 从 r10 成品解出的
> `system/lib64/libminuitwrp.so` 中含有 `IVibrator/default`、
> `AServiceManager_getService`、`fromBinder`，却**完全没有 `perform` / `Effect`**——
> 马达 HAL 一直在，但 UI 一次都没调用过设备里预置的 RichTap 波形。

上游 `bootable/recovery/minuitwrp/events.cpp` 的 `vibrate(int timeout_ms)` 在 AIDL 分支做的是：

```cpp
std::shared_ptr<IVibrator> vib = IVibrator::fromBinder(
    ndk::SpAIBinder(AServiceManager_getService(kVibratorInstance.c_str())));
vib->on((uint32_t)timeout_ms, nullptr);   // 固定振幅、按毫秒长震
```

两个症状其实同源：

| 现象 | 真正原因 |
| --- | --- |
| 转子马达那种「嗡嗡」感 | `on(ms)` 只给一个**恒定振幅**；线性马达需要预渲染波形。`vendor/odm/etc/vibrator/809/def/effect_*.bin` 里 300+ 个 RichTap 波形一次都没被用上。 |
| 点击 / 滑动发涩 | 每次虚拟按键都同步走一次 binder `getService()` + `fromBinder()`；设备树原来还开了 `TW_SUPPORT_INPUT_AIDL_HAPTICS_FIX_OFF`，会为每次点击新建一个 detached `std::thread` + `usleep(ms)` + `off()`。 |

`scripts/patch_minuitwrp_haptics.py` 在每次云端 sync 后对 `vibrate()` 做函数级重写：

1. **缓存 HAL 代理**（mutex 保护；服务晚启动时最多每 500 ms 重试一次），不再每次触摸查 binder；
2. 调 `perform(Effect::CLICK, EffectStrength::MEDIUM, nullptr, &played_ms)` 触发 RichTap 波形；HAL 没有 CLICK 波形时才退回 20 ms 短 `on()`，**振动不会丢**；
3. 35 ms 节流，手势导航的连续事件不会把马达与输入线程打满；
4. 移除 `FIX_OFF` 的 `<thread>` / `vib_on_count` 脚手架。patch 带精确匹配计数与后置断言，失效就直接让 CI 失败，不会白白编 2 小时。

> [!NOTE]
> `TW_SUPPORT_INPUT_AIDL_HAPTICS_FQNAME := "IVibrator/default"` 与
> `TW_SUPPORT_INPUT_AIDL_HAPTICS_FIX_OFF := true` 都已从 `BoardConfig.mk` 删除。
> 前者本就是上游默认实例名（`IVibrator::descriptor + "/default"`，与本机 VINTF
> manifest 一致），补它等于没改；后者正是「每击建线程」的元凶。

> [!TIP]
> 验证 r12 是否真的生效：解出 `system/lib64/libminuitwrp.so`，
> `strings` 里应能找到 `perform` / `Effect`，而不是像 r10/r11 那样只有 `on()`。

> [!IMPORTANT]
> **144 Hz 不是靠 `BoardConfig.mk` 声明出来的。** recovery 没有 SurfaceFlinger /
> DisplayManager / SettingsProvider，`settings put system peak_refresh_rate 144`
> 在这里完全无效；面板扫描模式由内核 DRM / panel 驱动决定。`TW_FRAMERATE` 是
> TWRP 的 **UI 动画抽帧节拍**（`gui/animation.cpp` 里的 `TW_FRAMERATE / mFPS`），
> 和面板刷新率是两套东西。

> [!NOTE]
> **「144 Hz 看不出来」和「滑动卡」都不等于面板没跑在 144 Hz。** recovery 没有
> SurfaceFlinger / HWUI / vsync，是 CPU 按需重绘到 framebuffer：1240×2772、
> `RGBX_8888` 一帧约 13.7 MB。即使面板扫描率是 144 Hz，UI 也只在发生事件时画一帧，
> **不存在恒定 144 fps**。r12 修掉的是每次触摸同步走 binder + 新建线程这段输入延迟
> （见上），配合已固化的 `performance` governor；全屏软渲染本身仍是上限。想更跟手，
> 进设置关掉手势导航通常最有效。

构建把 `TW_FRAMERATE` 设为 `60`：TWRP 在 `gui/objects.hpp` 里默认写死 `30`，而上一轮
已把主题 4 处转圈动画 patch 成 `fps="60"`，`30/60 == 0`（整数除法）两边是错配的，
同步到 60 才自洽。**刻意不设 144**：1240×2772 的 CPU 软渲染一帧约 13.7 MB，UI 主循环
根本达不到 144 Hz，把节拍写成 144 只会让动画抽帧变稀、反而更卡。

`fox_refresh.sh` 是 oneshot 服务，在 `on boot`、模块加载完成、解密完成后各尝试一次，
策略是「宁可不生效，也不能让 recovery 起不来」：

1. 先找内核是否**明确广告** 144 Hz 模式（`fb0/modes`、`msm_fb_panel_info`、DRM `modes`）；
   没有广告时，只有当节点当前值 ≥ 60、能确认它确实是刷新率控制才继续。
2. 只在可写节点上 `echo 144`，并**回读校验**；读回不是 144 就恢复原值。
3. 任何环节失败都静默跳过并以 `exit 0` 结束，不阻塞启动。日志在 `/tmp/fox_refresh.log`。

> [!WARNING]
> 强制改变面板扫描率在个别固件上可能引发花屏 / 黑屏 / 额外耗电。脚本已做回读与
> 回滚，但若真出现异常：进 fastboot 重刷上一版 `recovery.img` 即可恢复；想彻底关闭，
> 把 `fox_refresh.sh` 里的 `ENABLE=1` 改成 `0`，或删掉 `init.recovery.qcom.rc` 里的
> 三处 `start fox_refresh` 后重编。

回家接上 adb 后可用下面几条确认是否真的生效（**不需要**为了改代码而先跑）：

```powershell
adb shell "service list | grep -i vibra"
adb shell "lsmod | grep -i aw8697; ls -l /dev/awinic_haptic"
adb shell "cat /tmp/fox_refresh.log"
adb shell "cat /sys/class/graphics/fb0/dynamic_fps 2>/dev/null"
```

---

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
6. **CI 实时日志**：约 2 MiB 处可能 wedged，详见
   [CI 已知问题](#ci-已知问题实时日志管道冻结)；这是 runner 侧限制，不影响本地编译。

---

## 常见问题

| 现象 | 说明 |
| --- | --- |
| 用 7-Zip / WinRAR 打开 `recovery.img`，看到 KernelSU 的 `.ko` 文件 | 正常。层级是 `recovery.img → LZ4 ramdisk(cpio) → FFiles/KernelSU/KernelSU_Installer.zip → .ko`；那是安装包里的嵌套文件，不是镜像坏了。ramdisk 中真正独立的 `.ko` 在 `vendor/lib/modules/1.1/` 下的高通驱动模块。 |
| 进 recovery 后觉得 UI "不像新版" | R12.0 是渐进式界面升级，主色仍是 `#ed6f02`、底部导航仍是橙狐风格；Fox White / Fox Dark 主题可能需要手动切换。也可能根本没进 OrangeFox——确认看到 Fox logo、底部导航栏、版本号 `R12.0_1` 和解密 `/data` 提示。 |
| Actions Artifact 匿名下载 401 / 特别慢 | 用 **Releases → Assets** 的直链，走 CDN、免登录。Artifact 只是备用。 |
| 编译卡在 41–42% 长时间无输出 | 先看实时日志里的 `HEARTBEAT` 是否还在跳。若心跳也停了，属于 [CI 已知问题](#ci-已知问题实时日志管道冻结)，取消该 run 后用最新 workflow 重跑，或改用本地 WSL2 编译。 |
| 运行中下载日志返回 `BlobNotFound` / 404 | 归档分片尚未上传，不是失败；完整日志在 `build-log-<run号>` artifact 里。 |
| `fastboot flash` 后重启又变回原厂 recovery | 只刷 img 是非持久安装，必须进 recovery 后再刷签名 zip，见 [完整安装](#完整安装需要-orangefox-签名-zip)。 |
| 界面操作起来卡、感觉没有 60 帧 | 见 [UI 流畅度](#ui-流畅度)：recovery 是按需重绘、本就没有恒定帧率；已默认锁高性能，再关掉手势导航通常最有效。r12 起还去掉了每次触摸的 binder 查找与新建线程。 |
| 线性马达摸起来还是转子那种「嗡嗡」感 | r11 及更早版本只调了 `on(ms)`，从没调过 `perform(CLICK)` 波形；见 [硬件适配](#硬件适配)。r12 已重写 `vibrate()`，可在 `libminuitwrp.so` 里检查 `perform` / `Effect` 字符串确认。 |
| 144 Hz 没看出来 / 面板刷新率不生效 | 面板刷新率 ≠ UI 帧率；recovery 按需重绘，`fox_refresh.sh` 也只在内核明确广告 144 Hz 时才写，节点不存在就静默跳过。见 [硬件适配](#硬件适配)。 |

---

## 维护约定

- **触发编译**：push 到 `main` / `master` / `fox-12.1`，或在 Actions 页 `Run workflow`。
  commit message 里带 `[skip ci]` 可跳过编译。
- **不触发编译**：文档、UI 资源、二维码这类小改统一带 `[skip ci]`，攒够一批再编一次，
  每次完整编译约 2 小时。
- **发 Release 不会触发编译**：workflow 只监听 `push` / `workflow_dispatch`，
  Pre-release 由构建成功后的步骤自行创建，避免「编译 → 发版 → 又编译一轮」。
- **产物发布**：构建成功后由 `Collect build outputs` 归集到 `dist/`，再同时上传为
  Artifact 和 Pre-release Assets。`~` 不会被 upload-artifact / gh-release 的 glob 展开，
  所以路径一律用 `dist/*` 或 `${{ github.workspace }}/dist/*`。
- **密钥安全**：云端编译只用 `GITHUB_TOKEN`；本地推送若用 PAT，一律通过一次性
  `git -c http.extraHeader=...` 传入，**绝不写进仓库或文档**，用完及时 revoke。
- **自定义资源**：所有 DIY 文件都在 `recovery/root/` 下，云编译会注入主题源；
  不要直接改 `bootable/recovery`，否则下次同步源码会被覆盖。

---

## Credits

- 设备树基于 [MisterZtr/recovery_device_realme_RMXTARO](https://github.com/MisterZtr/recovery_device_realme_RMXTARO)（`fox-12.1` 分支）
- OrangeFox Recovery Project（TeamWin TWRP 衍生）
- 原始贡献：Bot-cd-Crypton、hoangzk9as、Ctapchuk、Kychera22
- 维护与定制：白墨 Whiteink · [酷安](https://www.coolapk.com/u/30264531) ·
  [GitHub](https://github.com/Whiteink666) · QQ 群 287398984

---

## License

GPL-3.0。详见 [LICENSE](LICENSE)。
