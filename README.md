# OrangeFox Recovery for realme GT Neo5 / GT3 (RMXTARO · senna)

**R12.0 新 UI** · **默认简体中文** · **GPL-3.0** · 最新构建 `ofox-RMXTARO-r20`

> [!IMPORTANT]
> **`ofox-RMXTARO-r20` 已出包（patch v6）**：run 20 十五步全绿，`mka_rc=0`，`0 FAILED`，
> build 步骤 `01:33:55`，可下载 `recovery.img` / zip。
>
> 这一轮改的是**拖动时的帧周期**，不是面板：GUI 主循环是
> `loopTimer() → Update() → Render() → flip()` 一条串行链，v5 把输入窗口设成「2 帧」
> 等于给每帧垫了 13.9 ms 的下限，叠上整屏重绘和阻塞提交就是 ~30 ms —— 也就是
> 「像 30 帧」。v6 把它降到**半帧**（3.5 ms），并加了可运行时开关的帧计时器。
> 详见 [为什么 144 Hz 之后还是「像 30 帧」](#为什么-144-hz-之后还是像-30-帧帧时间是串行的)。
>
> **刷入后请先做这两步**（不需要重编译）：
>
> ```powershell
> adb shell cat /tmp/fox_drm.log              # 期望 vrefresh=144 modeset_ok=1
> adb shell touch /tmp/fox_render_trace       # 打开帧计时器，滑动十几秒后
> adb shell cat /tmp/fox_render.log | tail -40
> ```
>
> `flip` ≈ 16000 说明面板还是 60 Hz；`flip` ≈ 6900 说明 144 Hz 生效；`render` 占大头
> 说明瓶颈在软渲染。线性马达力度已在 r16 定型，不再改动
> （见 [力度上限：为什么停在这里](#力度上限为什么停在这里)）。



一款面向 **realme GT Neo5 / GT3** 的第三方 Recovery，基于 OrangeFox（橙狐）R12.0 构建，
由 **🐾白墨🐾Whiteink🐾丨白墨(Whiteink)工作室** 维护与定制。

> [!NOTE]
> r16（patch v4）在当前 v3 基础上做三件事：**三档力度**（阈值 50 / 150，让 50、100
> 拿到原来 300 的力度，300 更强）、**波形播放前也 `setAmplitude()`**、以及运行时增益文件
> `/tmp/fox_haptics_gain`（不用重编译就能调力度）；并用 `scripts/patch_gui_framerate.py`
> 修掉真正的 30 fps 主循环天花板与 500 ms 输入窗口，见 [UI 流畅度](#ui-流畅度)。
> r17 再把主循环节拍提到 **144** 并把面板时序拉到 **144 Hz**（两条独立的改动，可分别回退）。
> 刷入前请先读 [刷入](#刷入) 与 [已知注意事项](#已知注意事项)。

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
| 上一版构建 | Actions **run 16**（`42986555580`，head `4489b2d`）成功，15 步全绿，`mka_rc=0`，build 步骤 `01:03:36`，整个 run 约 **69 min**；`recovery.img`、zip 均已下载并 SHA256 校验，离线解包确认 v4 三档映射 + gain 开关 + 159 个 `/odm/etc` 波形、4 个 60 fps 转圈动画全部在镜像内 |
| 上一轮失败 | **run 15**（`42985063405`，head `65d401e7`）在**第 9 步注入闸门 6 分钟内**失败：`patch_gui_framerate.py` 用了 Python 3.13 才有的 `Path.read_text(newline=)`，runner 是 3.10。已修（改用 `open()`，基线降到 3.8），并新增 `scripts/check_py_compat.py` 静态拦截——**第 10 步编译未启动，没有浪费 2 小时** |
| 最新构建 | Actions **run 20**（`43063419247`，head `a1c8c41`）**成功**，15 步全绿，`mka_rc=0`，`0 FAILED`，build 步骤 `01:33:55`，整个 run 约 **107 min**；release `ofox-RMXTARO-r20` 已发布 4 个 assets（`recovery.img` 100.0 MB、zip 70.4 MB、两个 `.md5`） |
| run 19 失败 | 两次尝试都挂在第 5 步 `apt`：runner 的 DNS 整体不可用（`Temporary failure resolving 'azure.archive.ubuntu.com'`）。第 5 步与 run 18 逐字节相同，属 runner 环境问题。已给第 5 步加三层镜像兜底，见 [CI 已知问题：runner DNS 故障](#ci-已知问题runner-dns-故障导致第-5-步-apt-失败) |
| 本轮改动 | **patch v6**：① `gui.cpp` 拖动窗口 `2 帧 → 半帧`（去掉 13.9 ms 的帧周期下限）；② 新增可运行时开关的 `render` / `flip` 帧计时器；③ 保留 v5 的 144 Hz DRM 时序与 `TW_FRAMERATE 144`；④ 第 5 步 `apt` 加三层镜像兜底 |
| 后端确认 | 编译日志里 `//bootable/recovery/minuitwrp:libminuitwrp clang++ graphics_drm.cpp` 与 `graphics_drm.cpp [arm]` 均在列（77% 处），**DRM 后端确实参与编译**，补丁不会挂空 |
| 编译耗时波动 | 同样的 `-j1`、同样 28030 个 target：run 14 用 **122 min**，run 16 用 **64 min**。差异来自**换了一台 runner 虚拟机**（`1000000821` → `1000000823`），与提交内容无关，不是「越编越慢」 |
| 典型产物 | `recovery.img`（100 MiB）+ 已签名 `OrangeFox-*.zip` + 两个 `.md5` |

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

#### CI 已知问题：runner DNS 故障导致第 5 步 apt 失败

GitHub 的 `ubuntu-22.04` 镜像把所有 apt 源指向
`mirror+file:/etc/apt/apt-mirrors.txt`，实际解析到 `azure.archive.ubuntu.com`。
这台机器的 DNS 偶尔会整体不可用，表现为：

```
E: Failed to fetch ... Temporary failure resolving 'azure.archive.ubuntu.com'
 5  Install build dependencies   failure
```

**这跟本仓库的代码无关**——run 18（成功）与 run 19（失败两次）的第 5 步内容逐字节相同，
连 runner 镜像版本都是同一个 `ubuntu22/20261101.347`。但一轮构建要 1–2 小时，
不该被一次 DNS 查询毁掉，所以第 5 步现在做了三层兜底：

1. 默认镜像，`Acquire::Retries=3` + 30 s 超时 + 强制 IPv4 重试；
2. 失败则把 `mirror+file:...` 直接替换成 `http://archive.ubuntu.com/ubuntu`，并
   先 `getent hosts` 轮询等待 DNS 恢复（最多 60 s）；
3. 再失败则换成 `http://mirrors.edge.kernel.org/ubuntu`。

三层都失败才退出，并明确打印「这是 runner 网络问题，重跑即可」，不再让人误以为是
代码挂了。

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

`ofox-RMXTARO-r16` 的产物指纹（已本地下载并校验，zip 内的 `recovery.img` 与单独下载的
`recovery.img` 字节一致）：

| 文件 | 大小 | SHA256 |
| --- | --- | --- |
| `recovery.img` | 104857600 | `cdee0343364f2e6469747f011d1b3665c6cd81d4a02daa3f86a009b11e6213e7` |
| `OrangeFox-R12.0-Unofficial-RMXTARO.zip` | 73776887 | `ec70e2b6a3c01a4af61fc51c9af1704c562e6ed2e5fa43fedc2759a620b304ef` |

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
重绘。R12 的 SVG 图标、阴影与圆角在 1240×2772 全屏上光栅化，一帧约 13.7 MB
（`RGBX_8888`），CPU 降频时尤其明显。

### r14 复盘：真的有一个 30 fps 硬上限

> [!IMPORTANT]
> 这里之前写「全局 UI 没有帧率常量」是**错的**。r14 实机反馈「不仅在文件页，整个页面
> 都只有 60 帧或 30 帧的样子」之后，我把 OrangeFox `fox_12.1` 源码翻了一遍，找到三处
> 真实节流：
>
> 1. `gui/objects.hpp` 里 `#ifndef TW_FRAMERATE / #define TW_FRAMERATE 30 / #endif`。
>    OrangeFox 12.1 的 `Android.mk` **不把 `TW_FRAMERATE` 转成 `-DTW_FRAMERATE=...`
>    编译宏**（只有 `TW_DEFAULT_LANGUAGE` 等少数变量会），所以我们在 `BoardConfig.mk`
>    里写的 `TW_FRAMERATE := 60` **一直是空操作**，编译进去的仍是 30。
> 2. `gui/gui.cpp::loopTimer()`：
>    `long timeout = got_event ? 500000000 : (1.0 / TW_FRAMERATE * 1000000000);`
>    无输入时每 `1/30 s ≈ 33 ms` 才返回一次（30 fps 上限）；**一读到输入事件就把窗口
>    拉到 500 ms**，拖动时重绘被压到约 2 次/秒，这正是「滑动发涩」的主因。
> 3. `gui/animation.cpp` 的 `if (++mUpdateCount > TW_FRAMERATE / mFPS)` 用 `>` 配整数
>    除法，节拍提高后动画会每 3 帧才走一帧。

`scripts/patch_gui_framerate.py` 在每次云端 sync 后对这三处做精确替换（带匹配计数与
后置断言，失效直接让 CI 失败）：`30 → 144` 的编译期节拍、`500 ms → 2 帧` 的输入窗口、
`> → >=` 的动画除法。**144 是上限不是承诺**：实际帧率仍由 CPU 软渲染一帧的耗时决定，
但 30 fps 的人为天花板被去掉了，拖动不再被 500 ms 窗口卡住。

### 144 Hz：面板一直被迫跑 60 Hz

即使把主循环节拍提到 144，**画面依然只会在垂直同步间隔上翻页**。原因不在 GUI，在
`minuitwrp/graphics_drm.cpp`：

```c
static GRSurface* drm_flip(minui_backend* backend) {
    memcpy(drm_surfaces[current_buffer]->base.data,   // 1240x2772x4 = 13.75 MB
           draw_buf->data, draw_buf->height * draw_buf->row_bytes);
    update_plane_fb();                                // 阻塞式 atomic commit
    ...
}
```

`drm_flip()` 是**同步**的：整屏 `memcpy` 之后提交一次
`drmModeAtomicCommit(..., DRM_MODE_ATOMIC_ALLOW_MODESET, NULL)`，**没有**
`DRM_MODE_ATOMIC_NONBLOCK`，所以每次提交都要等一个垂直同步间隔。也就是说每一帧都被
额外抽了一次税：

| 面板时序 | 每帧等待 | 理论帧率上限 |
| --- | --- | --- |
| 60 Hz | +16.7 ms | 60 fps（实测就是「只有 60 帧的样子」） |
| 144 Hz | +6.9 ms | 144 fps |

而 144 Hz 一直没生效，是因为选时序的这段代码：

```c
*mode_index = 0;
for (int modes = 0; modes < main_monitor_connector->count_modes; modes++) {
    if (main_monitor_connector->modes[modes].type & DRM_MODE_TYPE_PREFERRED) {
        *mode_index = modes;
        break;
    }
}
```

它**只认内核标记 `DRM_MODE_TYPE_PREFERRED` 的那一条**，而本机 kernel 标记为 preferred
的恰好是 60 Hz。实机 `modes` 列表里明明白白有 4 条：

```
1240x2772x60cmd / 1240x2772x90cmd / 1240x2772x120cmd / 1240x2772x144cmd
```

> [!NOTE]
> 这条路**没有 sysfs 捷径**。实机确认本机：
> - `/sys/class/graphics/fb0` 目录是**空的**，没有 `mode` / `refresh_rate` 之类的节点；
> - `/sys/kernel/oplus_display` 有 48 个节点，但**没有任何一个是帧率控制**；
> - `sbin/fox_refresh.sh` 在 r16 里的日志就是 `no usable 144 Hz node`。
>
> 所以必须改源码，不能靠写节点。

`scripts/patch_minuitwrp_drm_hz.py` 做三处精确插入：

1. 文件作用域：记录内核首选下标 `g_pref_mode_index` 和实际选中的刷新率 `g_selected_vrefresh`；
2. `find_main_monitor()`：保留首选下标作回退，再在**同分辨率**的模式里挑 `vrefresh` 最大的一条；
3. `drm_init()`：**黑屏保险**。`drm_blank()` 失败时会把 `current_blank_state` 留在初始的
   `true`，据此判断「144 Hz 时序被拒」，销毁并重建 mode blob、换回内核首选时序再提交一次，
   保证最坏情况是**这一次开机退回 60 Hz**，而不是黑屏。

它还会往 `/tmp/fox_drm.log` 追加一行，所以即使没有画面也能确认实际生效的刷新率：

```powershell
adb shell cat /tmp/fox_drm.log
# vrefresh=144 modeset_ok=1
```

> [!IMPORTANT]
> 两处改动是**互相独立**的，可以分别回退：面板时序在 `patch_minuitwrp_drm_hz.py`，
> 主循环节拍在 `TW_FRAMERATE`。如果 r17 出现「画面更顺但手感更飘」或其它异常，先回退
> `TW_FRAMERATE := 144` 观察，再考虑整个 DRM 补丁。


> [!IMPORTANT]
> **补丁脚本只能用 Python 3.8 就有的 API。** run 15 就是在第 9 步 6 分钟内挂掉的：
> `TypeError: Path.read_text() got an unexpected keyword argument 'newline'`——
> `read_text(newline=)` 是 **3.13 才加**的参数，本地跑的是 3.14 所以重放全过，
> 而 runner（`ubuntu-22.04`）的系统 `python3` 是 3.10。现在 `scripts/check_py_compat.py`
> 会在注入步骤最前面用 `ast.parse(feature_version=3.8)` + 新版 API 黑名单静态扫一遍全部
> 脚本，几十秒内失败，不再白等一轮。

本构建开箱即默认高性能：

| 改动 | 位置 | 作用 |
| --- | --- | --- |
| 开机锁定 `performance` governor | `recovery/root/init.recovery.qcom.rc` 的 `fox_perf` 服务，`on boot` 与解密完成后各触发一次 | 避免默认「均衡」把 UI 线程压到小核低频 |
| 默认「Recovery 性能模式」改为**高性能** | 云端编译时 patch 上游 `pages/settings.xml` 的两处兜底默认值 | 让 OrangeFox 自身的启动逻辑也用高性能 |
| 转圈动画 30 → 60 fps | 云端编译时 patch 上游 `pages/{files,main,templates/base}.xml` 共 4 处 | 只影响进度条不确定动画 |
| **去掉 30 fps 全局天花板 / 500 ms 输入窗口** | `scripts/patch_gui_framerate.py` patch `gui/objects.hpp`、`gui/gui.cpp`、`gui/animation.cpp` | 主循环节拍 30 → 144；拖动窗口从 500 ms → **半帧**（v6） |
| **面板时序 60 → 144 Hz** | `scripts/patch_minuitwrp_drm_hz.py` patch `minuitwrp/graphics_drm.cpp` | 每帧少等 9.8 ms 垂直同步，`drm_flip()` 的阻塞提交不再把帧率钉在 60 |

### 为什么 144 Hz 之后还是「像 30 帧」：帧时间是串行的

v5 把 `loopTimer()` 的输入窗口从 500 ms 降到 **2 帧**，这一步其实是个失误——它是
**帧周期的下限**，而不是修复。GUI 主循环是串行的：

```
loopTimer()  →  PageManager::Update()  →  Render()  →  flip()
```

所以拖动时的一帧耗时约等于

```
max(2 / TW_FRAMERATE,  render + flip)
```

`2 / 144 s` = **13.9 ms** 的下限，加上整屏 `gr_fill` + 全部对象重绘 + `drm_flip()` 的
13.75 MB `memcpy` 和**阻塞** atomic commit，很容易凑到 30 ms 左右——正好就是
「像 30 帧」。面板切到 144 Hz 只是把 commit 那一段从 16.7 ms 压到 6.9 ms，
**压不掉我们自己的窗口下限和重绘耗时**。

v6 把窗口改成**半帧**（144 Hz 下 3.5 ms）：`InputHandler::processInput` 每次只读一个
事件、`handleDrag()` 每个渲染周期只发一次拖动通知，半帧足够把输入队列排空，同时不再
给帧周期垫底。

> [!IMPORTANT]
> `loopTimer()` 的这条窗口只在**有输入事件时**生效。手指不动时仍然是
> `1 / TW_FRAMERATE`，所以静止画面不会无谓地空转渲染。

### 滑动不能打断：输入队列根本没被排空

实机反馈（r20，触摸已确认 234 Hz、面板 144 Hz）：

> 还是有点卡卡的，而且滑动的时候不支持打断（在往上滑的时候突然下滑没有反应，
> 要等上滑结束才行）

这条把问题从「性能」拉回到了「逻辑」。看 `gui.cpp::loopTimer()`：

```c
do {
    bool got_event = input_handler.processInput(input_timeout_ms);
    ...
    long timeout = got_event ? 500000000 : (1.0 / TW_FRAMERATE * 1000000000);
    if (diff.tv_sec || diff.tv_nsec > timeout) { ... return; }   // ← 每帧只消费 1 个事件
    input_timeout_ms = 0;
} while (1);
```

`processInput()` **一次只读一个输入事件**，而 `diff` 从上次返回时刻开始算起——
它已经包含了上一帧的渲染耗时。所以进入 `loopTimer` 后第一次 `processInput` 拿到事件，
`diff`（约 20–25 ms）立刻大于窗口，**函数当场返回，只消费了这 1 个事件**。

于是：触摸 234 Hz 每帧产生 ~5 个事件，每帧只消费 1 个 → **队列无界增长**。
`handleDrag()` 转发的是「已消费到的那一帧的位置」，不是手指当前位置，所以

- 画面滞后于手指 → 感觉「卡」；
- 反向操作要等前面几十个旧事件消费完才反映出来 → 感觉「不能打断」。

`processInput` 的返回值也有责任：`return (ret != -2);` 把「超时没数据」(`-1`)
也当成「读到事件」，所以调用方根本无法判断队列空没空。

v7 的修法：

```c
int drain_count = 0;                       // 本次 loopTimer 已消费的事件数
do {
    bool got_event = input_handler.processInput(input_timeout_ms);
    ...
    long timeout = (long)(1.0 / TW_FRAMERATE * 1000000000);
    if (got_event && ++drain_count < 64) { // 队列还有事件：先排空再画
        input_timeout_ms = 0;
        continue;
    }
    if (diff.tv_sec || diff.tv_nsec > timeout) { ... return; }
    ...
} while (1);
```

配合 `processInput()` 的返回值改成 `return (ret >= 0);`——只有真正读到事件才算事件。
排空上限 64 次是防止某个输入源卡死时饿死渲染。

这样每帧开始就把积压的事件全部吃掉，`handleDrag()` 拿到的是**手指当前位置**，
反向立刻生效；渲染仍是每帧一次，节拍不变。

#### 用内建计时器分辨「画得慢」还是「等得久」

v6 在 `gui.cpp` 里加了一个**默认关闭**的帧计时器，开关是一个文件，不用重编译：

```powershell
adb shell touch /tmp/fox_render_trace    # 打开
adb shell cat /tmp/fox_render.log        # 读（微秒）
adb shell rm /tmp/fox_render_trace       # 关闭
```

输出形如：

```
ts=1794155414.612345 render=4821 flip=16903 ret=2
```

- `render` = 整页重绘耗时（CPU 软渲染）
- `flip` = `drm_flip()` 整帧 memcpy + 阻塞 atomic commit 的等待

判断方法很直接：**`flip` 稳定在 16000 上下 → 面板仍是 60 Hz**（144 Hz 应该读到 ~6900）；
**`render` 占大头 → 瓶颈在软渲染**，得从主题/对象下手，而不是继续调面板。


> [!NOTE]
> 主题里那 4 处 `fps="30"` 的条件都是 `ui_progress`，只控制进度条转圈；**全局**节拍是
> `TW_FRAMERATE`，而且必须由 patch 改源码默认值才有效，光改 `BoardConfig.mk` 没用。
> 而**面板**刷新率既不是 `TW_FRAMERATE` 也不是任何 sysfs 节点，只能在
> `graphics_drm.cpp` 里改选模式的逻辑。

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

### 触摸：144 Hz 面板却配了 60 Hz 报点率

2026-11-14 用 adb 在 recovery（root）里实测，把这条线彻底查清了：

```
/sys/kernel/oplus_display/dynamic_te          = 144   ← 面板确实跑在 144 Hz
/tmp/fox_drm.log                              = vrefresh=144 modeset_ok=1
/proc/touchpanel/game_switch_enable           = 0, high_frame_support:1, high_frame_value:0
dmesg: report_rate_limit not specified, we will set it 60hz
       synaptics-s3910: default rate 60 / default game value 1
       synaptics-s3910: fps_report_rate is: 60 / 90 / 120
       synaptics-s3910: extreme_game_report_rate 0     ← 这颗 IC 没有 240 Hz 档
```

**面板 144 Hz、触摸只有 60 Hz。** 不管 GUI 画得多快，拖动时每秒只有 ~60 个位置
更新，这就是「滑起来像 30 帧 / 不跟手」的另一半原因。触控 IC 是 Synaptics
S3910（SPI，`/dev/input/event5`），驱动支持 60 / 90 / 120 Hz 三档，但内核没指定
`report_rate_limit`，回退到 60 Hz，`game_switch_enable` 也是 0。

两个可逆的运行时开关，逐值试出的映射：

| 节点 / 值 | 驱动响应 |
| --- | --- |
| `echo 1 > game_switch_enable` | `syna_tcm_set_game_mode: enable[1]`，`set report_rate:1` |
| `echo 0 > game_switch_enable` | `syna_report_refresh_switch: refresh_switch: 60 HZ` |
| `echo 0 > report_rate_white_list` | `DC_SET_REPORT_FRE: 1` |
| `echo 1 > report_rate_white_list` | `DC_SET_REPORT_FRE: 2` |
| **`echo 2 > report_rate_white_list`** | **`DC_SET_REPORT_FRE: 3`（最高档）** |
| `echo ≥3 > report_rate_white_list` | 驱动忽略 |

> [!IMPORTANT]
> 驱动进入 `normal_mode`（自检 / resume / 重新初始化）时会**自己把报点率打回 60 Hz**：
> `syna_tcm_normal_mode: enter → syna_report_refresh_switch: refresh_switch: 60 HZ success!`。
> 所以开机写一次是不够的——`sbin/fox_touch_rate.sh` 是一个**常驻** watchdog
> （init.rc 里故意**不加 `oneshot`**），每 5 秒检查一次，只在值漂移时重写，
> 不漂移就不写日志。它只写两个 `/proc` 节点，**不刷任何分区、不删除任何文件**。

验证是否生效：

```powershell
adb shell "cat /proc/touchpanel/game_switch_enable; cat /proc/touchpanel/report_rate_white_list"
adb shell "cat /sys/kernel/oplus_display/dynamic_te"
adb shell "cat /tmp/fox_touch.log"
adb shell "dmesg | grep -E 'DC_SET_REPORT_FRE|set report_rate'"
```

期望：`1, high_frame_support:1`、`2`、`144`，日志里有 `re-assert` 记录。

---

## 硬件适配

这两套驱动**设备树里本来就有**，做的是把它们接进启动链，而不是移植驱动：

| 组件 | 设备树里已有的文件 | 接线方式 |
| --- | --- | --- |
| X 轴线性马达 | `vendor/lib/modules/1.1/aw8697.ko`（Awinic AW8697）、`/dev/awinic_haptic`、`system/bin/realme.vibrator.service`（AIDL `IVibrator` V2）、`aac_richtap.config` + 809/815 波形、`IVibrator/default` VINTF manifest | 加进 `TW_LOAD_VENDOR_MODULES` 显式 insmod；init 里 `wait /dev/awinic_haptic 2` 之后再 `start realme.vibrator`；波形文件补进 `/odm/etc/vibrator/`；**UI 调用路径由 `scripts/patch_minuitwrp_haptics.py` 改成强度映射 + `perform()` 波形阶梯**，见下 |
| 屏幕面板 | `vendor/lib/modules/1.1/panel_event_notifier.ko`、`vendor.display.config@1.0/2.0`、`TW_BRIGHTNESS_PATH` | 加进 `TW_LOAD_VENDOR_MODULES`；新增 `sbin/fox_refresh.sh` 做保守的 144 Hz 探测 |

### 为什么 r11 仍是「转子震感 + 滑动卡」

> [!IMPORTANT]
> **r11 及更早版本的马达接线没有打中根因。** 上游 OrangeFox 12.1 的
> `bootable/recovery/minuitwrp/events.cpp` 里，`vibrate()` 的 AIDL 分支只调
> `vib->on(timeout_ms, nullptr)`，**没有任何 `perform()` 调用**；从 r10 / r11 成品解出的
> `libminuitwrp.so` 只能看到 `IVibrator/default`、`fromBinder`（HAL 查找）和
> `pthread_create` / `std::thread::detach`（每击建线程）。
> 马达 HAL 一直在，但 UI 一次都没用过设备里预置的 RichTap 波形。

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

`scripts/patch_minuitwrp_haptics.py` 在每次云端 sync 后对 `vibrate()` 做函数级重写（当前为 **v4 三档强度版**）：

1. **缓存 HAL 代理**（mutex 保护；服务晚启动时最多每 500 ms 重试一次），不再每次触摸查 binder；
2. **`timeout_ms` 当强度意图，不当时长**：`0` 不振动、`1–49` level 1、`50–149` level 2、
   `≥150` level 3；驱动 `20 / 40 / 60 ms` 的短脉冲，**永远不会出现 300 ms 长震**；
3. **波形播放前先 `setAmplitude()`**（v3 只在 `on()` 兜底里设）——这是 r14「300 档还是偏小」
   最可能的原因：波形路径一直继承 vendor HAL 的默认振幅；
4. **波形阶梯**：level 2 试 `HEAVY_CLICK + STRONG → CLICK + MEDIUM`；level 3 只用
   `HEAVY_CLICK + STRONG`，**不降级到轻波形**，失败直接走满振幅短 `on()`；
   只有 `status.isOk() && played > 0` 才算波形播放成功；
5. **运行时增益** `/tmp/fox_haptics_gain`（整数 `-3..3`，2 秒缓存）可平移力度档位，
   `/tmp/fox_haptics_double` 给最高档加一次额外脉冲——**调力度不用再编译 2 小时**；
6. 波形不可用时满振幅 + 短 `on(drive_ms)`；HAL 完全不可用时再退到 sysfs
   `/sys/class/leds/vibrator/*` 或 `timed_output`，同样是短时长，**振动不会静默丢失**；
7. 每次事件同步 `off()` 清状态（替代上游 detached thread）、35 ms 节流、移除 `FIX_OFF` 的
   `<thread>` / `vib_on_count` 脚手架。patch 带精确匹配计数与后置断言，失效就直接让 CI 失败。

> [!NOTE]
> `TW_SUPPORT_INPUT_AIDL_HAPTICS_FQNAME := "IVibrator/default"` 与
> `TW_SUPPORT_INPUT_AIDL_HAPTICS_FIX_OFF := true` 都已从 `BoardConfig.mk` 删除。
> 前者本就是上游默认实例名（`IVibrator::descriptor + "/default"`，与本机 VINTF
> manifest 一致），补它等于没改；后者正是「每击建线程」的元凶。

> [!TIP]
> **怎么验证 patch 真的编进去了**：`perform()` 是 AIDL 纯虚接口经 vtable 调用，
> `Effect` / `EffectStrength` 是编译期枚举常量，**都不会在 `.so` 里留下明文字符串**，
> 所以别用 `strings | grep perform` 判断。正确做法有两条：把 r12 与 r11 的
> `system/lib64/libminuitwrp.so` 做符号差集（r12 应**新增** `std::mutex::lock/unlock`、
> `std::chrono::steady_clock::now`、`std::shared_ptr<…IVibrator>` 析构符号，并让
> `pthread_create`、`std::thread::detach`、`__thread_struct` **消失**）；v3 起还可直接
> 检查新字面量 `/tmp/fox_haptics.log`、`/tmp/fox_haptics_force_on`、
> `/sys/class/leds/vibrator/activate` 是否出现在 `.so` 里。
> 另外别忘了**产物层面**的检查：ramdisk 里必须存在 `/odm/etc/vibrator/809/def/effect_0.bin`。

### r12 的「有振动但很弱 / 拉到 300 没用」，以及 v3 怎么改

> [!IMPORTANT]
> 实机反馈是 **「有振动，只是很小，而且还是转子的那种震动；开到 300 也没变化」**，
> 不是完全没振动。这个区别决定了修复方向：**要加的是力度与波形，不是时长**。

先厘清设置值。解出 r12 镜像里的 `twres/pages/settings.xml`：

```xml
<data variable="tw_button_vibrate"   min="0" max="300" .../>
<data variable="tw_keyboard_vibrate" min="0" max="300" .../>
<data variable="tw_action_vibrate"   min="0" max="500" .../>
```

`0–300` 是**毫秒时长**，不是力度。对 X 轴线性马达，「震 300 ms」只会变成更长的嗡嗡声，
不会变成清脆的「咔哒」。三处根因叠加：

| # | 问题 | 后果 |
| --- | --- | --- |
| 1 | patch v1 **完全丢掉了 `timeout_ms`**：`perform()` 只要 `status.isOk()` 就返回，没检查 `played_ms`；失败则固定 `on(20)` | 拉到 300 毫无变化；实际走的是 20 ms 固定振幅短震，弱且像转子 |
| 2 | `vibrator_effect.json` 里 159 个 `effect_file` 是**绝对路径 `/odm/etc/vibrator/...`**，而设备树只把波形放在 `recovery/root/vendor/odm/etc/...`；recovery 里 `/odm` 未挂载时 ramdisk 根本没有 `/odm/etc` | RichTap HAL 找不到波形，`perform()` 失败 / 返回 0 ms，被迫走 `on()` 兜底，预渲染波形一次都没播过 |
| 3 | 上游 `on(ms)` 是恒定振幅，且 `FIX_OFF` 每击建一个 detached `std::thread` | 转子感 + 输入发涩 |

按「完全没振动」误判做过的 patch v2 会把 `on(timeout_ms)` 恢复成主路径——设置 300 就真的
变成 300 ms 长嗡，**方向正好相反**，对应 run 13 已取消，未出包。

修复版（patch v3）改为强度映射：

- `timeout_ms` → level：`0` 不振动，`1–99` → level 1，`≥100` → level 2；
  短脉冲 `drive_ms = 20 + level*10`（20 / 30 / 40 ms），**绝不喂 `timeout_ms` 给 `on()`**；
- 波形阶梯 `HEAVY_CLICK + STRONG → CLICK + MEDIUM → CLICK + LIGHT`，
  只有 `isOk() && played > 0` 才算成功；
- 波形不可用时 `setAmplitude(0.55 / 0.8 / 1.0)` + 短 `on(drive_ms)`；再失败走 sysfs 短兜底；
- **`recovery/root/odm/etc/` 双保险**：把 159 个 `effect_*.bin`、`aac_richtap.config`、
  `vibrator_effect.json` 与 VINTF manifest 一并放进 ramdisk 的 `/odm/etc/`，
  让 `ENV_RICHTAP_CONFIG_PATH` 和那些绝对路径真的能解析到文件。CI 会断言 ≥150 个波形文件存在；
- 同步 `off()`、缓存 HAL 代理、35 ms 节流、无线程这些改进全部保留。

> [!TIP]
> 运行时诊断与开关（v3 起可用，**不需要重编译**）：
> ```powershell
> adb shell cat /tmp/fox_haptics.log         # mode=1 波形 / 2 setAmplitude+on() / 3 sysfs
>                                            # 同时记录 level / gain / amp / drive_ms / played_ms
> adb shell touch /tmp/fox_haptics_force_on  # 强制走 setAmplitude + 短 on()，跳过波形
> adb shell rm    /tmp/fox_haptics_force_on  # 恢复自动波形
> adb shell ls /odm/etc/vibrator/809/def/    # 波形是否真的在 ramdisk 里
> ```
> 日志只在模式变化时写一行，不会拖慢输入线程。`mode=1` 且 `played_ms>0` 即代表
> 线性马达波形真正播放成功。

### r14 实测通过，但「300 档偏小」→ v4 微调

> [!NOTE]
> r14 实机确认 **线性马达已经工作了**（不再是转子嗡嗡感）。剩下的反馈是：
> 「调到 300 震动还是有点小，现在这个力度应该适合 100 左右或 50」。
> 也就是说 **r14 的最大档放在滑块中段才合理，顶端还得再强一截**。

v3 只有 2 档（阈值 100），且 `setAmplitude()` 只在波形失败的 `on()` 兜底里调用——
波形播放成功时振幅完全由 vendor HAL 默认值决定，这是「拉满还是偏小」的最合理解释。
`DataManager::Vibrate()` 的实现也确认了滑块值确实原样传进 `vibrate(vib_value)`，
不是没生效：

```cpp
void DataManager::Vibrate(const string& varName) {
    int vib_value = 0;
    GetValue(varName, vib_value);
    if (vib_value) vibrate(vib_value);
}
```

v4 的对应关系：

| 滑块值 | v3 (r14) | v4 | 感受目标 |
| --- | --- | --- | --- |
| `0` | 不振 | 不振 | 关闭 |
| `1–49` | level 1 | level 1 · amp 0.70 · 20 ms · `CLICK+MEDIUM` | 轻 |
| `50–99` | level 1 | level 2 · amp 0.90 · 40 ms · `HEAVY_CLICK+STRONG` | 中 |
| `100–149` | level 2 | level 2 · amp 0.90 · 40 ms · `HEAVY_CLICK+STRONG` | 中（≈ r14 的 300） |
| `≥150` | level 2 | level 3 · amp 1.00 · 60 ms · `HEAVY_CLICK+STRONG`，不降级 | 强 |

如果刷完觉得还不够，先别急着再编译——用运行时增益直接试（即时生效）：

```powershell
adb shell "echo 1 > /tmp/fox_haptics_gain"   # 整体强一档
adb shell "echo 3 > /tmp/fox_haptics_gain"   # 无论滑块在哪都锁最高档
adb shell "echo 0 > /tmp/fox_haptics_gain"   # 恢复
adb shell touch /tmp/fox_haptics_double      # 最高档加一次额外脉冲
adb shell cat /tmp/fox_haptics.log           # 看 level / gain / played_ms
```

增益文件每 2 秒才读一次，不会落在输入热路径上。

### 力度上限：为什么停在这里

r16 之后**不再继续加力度**，因为三条能加力度的路都在实机上试完了，全部撞到同一堵墙。
实测基线（`/tmp/fox_haptics.log` + `qcom-haptics` 节点）：

```
mode=1 level=3 used=3 gain=0 amp=1.00 drive_ms=60 timeout_ms=300 played_ms=81
vibrator_type=809   lra_frequency_hz=174   t_lra_us=5882
vmax=1280  fifo_vmax=9100  cl_vmax=9100
```

`played_ms=81 > 0` 说明 RichTap 波形**确实播出来了**，而且是最大档、满幅度——「弱」不是
没播，是这条波形在本机 LRA 上的物理输出就这么多。三条路的结果：

| 试的杠杆 | 做法 | 结果 | 结论 |
| --- | --- | --- | --- |
| **幅度** | `fifo_vmax` 9100 → 11375（+25%） | 「更强了，但变成转子马达的震感」 | LRA 过冲进入削顶区，谐波把线性手感变成嗡嗡的 ERM 手感 |
| **时长** | 最高档加一次额外脉冲（双脉冲） | 「正常了，但好像变弱了一点…反正没有强」 | 能量摊到两次启动/刹车，单次冲击反而更小 |
| **绕过波形** | 直接 `IVibrator::on(duration)` 驱动 | 「又是转子马达那种手感」 | 去掉 RichTap 的刹车曲线就是方波激励，必然像转子 |

> [!IMPORTANT]
> **`fifo_vmax=9100` 已经是这条 LRA 的线性区上限。** 再往上加不是「更响」，而是让振子
> 撞到机械限位——能量从基频（174 Hz）漏到谐波，听感/手感就从「哒」变成「嗡」。这也解释了
> 为什么 `setAmplitude()` 对 `perform()` 路径没有效果：RichTap 波形自带包络，HAL 不接受
> 外部再缩放。
>
> 所以 v4 的三档映射 + 运行时增益就是这套硬件的实用上限。若仍想更强，只能换硬件
> （更大尺寸的 LRA）或换厂商波形（`/odm/etc/vibrator/809/` 下的 `effect_*.bin`）。

> [!IMPORTANT]
> **144 Hz 不是靠 `BoardConfig.mk` 声明出来的。** recovery 没有 SurfaceFlinger /
> DisplayManager / SettingsProvider，`settings put system peak_refresh_rate 144`
> 在这里完全无效；面板扫描模式由内核 DRM / panel 驱动决定。`TW_FRAMERATE` 管的是
> **UI 主循环重绘节拍**（`gui/gui.cpp::loopTimer()`）与动画抽帧
> （`gui/animation.cpp` 的 `TW_FRAMERATE / mFPS`），和面板扫描率是两套东西。
> 它同时也确实是一个全局帧率上限——r14 复盘已证实，见 [UI 流畅度](#ui-流畅度)。
> 面板那一侧由 `scripts/patch_minuitwrp_drm_hz.py` 改 `graphics_drm.cpp` 的选模式逻辑
> 实现，见 [144 Hz：面板一直被迫跑 60 Hz](#144-hz面板一直被迫跑-60-hz)。

> [!NOTE]
> **「144 Hz 看不出来」和「滑动卡」都不等于面板没跑在 144 Hz。** recovery 没有
> SurfaceFlinger / HWUI / vsync，是 CPU 按需重绘到 framebuffer：1240×2772、
> `RGBX_8888` 一帧约 13.7 MB。即使面板扫描率是 144 Hz，UI 也只在发生事件时画一帧，
> **不存在恒定 144 fps**。r12 修掉的是每次触摸同步走 binder + 新建线程这段输入延迟
> （见上），配合已固化的 `performance` governor；全屏软渲染本身仍是上限。想更跟手，
> 进设置关掉手势导航通常最有效。

构建把 `TW_FRAMERATE` 设为 `144`，与面板时序对齐：TWRP 在 `gui/objects.hpp` 里默认写死
`30`，主题 4 处转圈动画是 `fps="60"`，`144/60 == 2`（整数除法）两边自洽。

> [!NOTE]
> r13 时这里写过「刻意不设 144：软渲染达不到 144 Hz，节拍写高只会让动画抽帧变稀、反而更卡」。
> 那句话把两件事混在一起了：
>
> - **动画节拍**由 `TW_FRAMERATE / mFPS` 的整数除决定，`144/60 = 2` 与 `120/60 = 2`
>   完全等价，**不会抽帧**；
> - **帧率上限**从来不由节拍决定，而是由 `drm_flip()` 的阻塞提交在等垂直同步决定。
>
> 面板跑 60 Hz 时每一帧都必须等 16.7 ms，这才是「整个页面只有 60 帧的样子」的直接原因。
> 所以正确做法是**同时**把面板拉到 144 Hz、并把节拍对齐到 144（r17 / patch v5）。

`fox_refresh.sh` 是 oneshot 服务，在 `on boot`、模块加载完成、解密完成后各尝试一次，
策略是「宁可不生效，也不能让 recovery 起不来」：先找内核是否明确广告 144 Hz 模式，只在
可写节点上 `echo 144` 并回读校验，任何环节失败都静默跳过（`exit 0`），日志在
`/tmp/fox_refresh.log`。

> [!IMPORTANT]
> 实机已确认**这台机器上它永远是空转**：`/sys/class/graphics/fb0` 目录为空，
> `/sys/kernel/oplus_display` 的 48 个节点里没有帧率控制，r16 的日志就是
> `no usable 144 Hz node`。它保留只是作为「万一某个固件版本有节点」的兜底，
> **真正生效的是 `scripts/patch_minuitwrp_drm_hz.py` 对 DRM 选模式逻辑的修改**。

> [!WARNING]
> 改 DRM 时序在个别固件上可能引发花屏 / 黑屏。补丁已内置黑屏保险（提交失败会在同一次开机
> 内退回内核首选时序），但若真出现异常：进 fastboot 重刷上一版 `recovery.img` 即可恢复。
> 想彻底关闭面板改动，把 `scripts/patch_minuitwrp_drm_hz.py` 从 workflow 第 9 步移除即可，
> 主循环节拍不受影响。

回家接上 adb 后可用下面几条确认是否真的生效（**不需要**为了改代码而先跑）：

```powershell
adb shell "cat /tmp/fox_drm.log"          # vrefresh=144 modeset_ok=1 才算真的切上去了
adb shell "cat /tmp/fox_refresh.log"
adb shell "service list | grep -i vibra"
adb shell "lsmod | grep -i aw8697; ls -l /dev/awinic_haptic"
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
| 界面操作起来卡、整个页面只有 60 帧或 30 帧 | **r16 已修**。真因不是主题里那几个 `fps="30"`，而是 `gui/objects.hpp` 默认 `TW_FRAMERATE 30`（`BoardConfig.mk` 那行一直是空操作），加上 `gui.cpp` 一读到输入就把重绘窗口拉到 500 ms。`scripts/patch_gui_framerate.py` 改成 120 节拍 / 2 帧窗口。若在 r14 及更早版本上遇到，就是这个原因；另外关掉手势导航仍然最立竿见影。 |
| 刷了 r12 之后振动很弱，把设置拉到 300 也没变化 | r12（patch v1）把 `timeout_ms` 整个丢了：波形失败时固定走 20 ms `on()`。设置里的 0–300 是**毫秒时长**，不是力度。r14 起按强度意图处理，见 [硬件适配](#硬件适配)。 |
| 线性马达摸起来还是转子那种「嗡嗡」感 | 恒定振幅的 `on(ms)` 或找不到波形的短震都会是这种感觉。根因之一是 `vibrator_effect.json` 用绝对路径 `/odm/etc/vibrator/...`，而 ramdisk 里原来只有 `vendor/odm/etc/...`；r14 起已把 159 个波形补进 `/odm/etc/`。见 [硬件适配](#硬件适配)。 |
| 想知道这次点击到底走了哪条振动路径 | r14 起 `adb shell cat /tmp/fox_haptics.log`：`mode=1` 波形（含 `level` / `gain` / `played_ms`） / `mode=2` `setAmplitude` + 短 `on()` / `mode=3` sysfs 兜底；`touch /tmp/fox_haptics_force_on` 可临时强制走 `mode=2`。 |
| 刷了 r16 觉得某档力度还不对 | 先别重编译：`adb shell "echo 1 > /tmp/fox_haptics_gain"` 试更强，或 `echo 0` 试更弱；`/tmp/fox_haptics_double` 可叠第二发脉冲。都不满意再调 `scripts/patch_minuitwrp_haptics.py` 里的 `kAmp` / `kDrive` 表，见 [硬件适配](#硬件适配)。 |
| r14 已经不转子了，但拉到 300 还是偏小 | v3 只有 2 档，且波形路径没设振幅。r16（v4）改三档（50 / 150 阈值）+ 波形前 `setAmplitude()`，刷 r16 即可。 |
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
