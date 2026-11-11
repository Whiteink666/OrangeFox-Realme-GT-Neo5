#!/system/bin/sh
# Whiteink recovery 诊断脚本 —— 在马达/帧率反馈时用，收集一次性证据。
# 用法：adb push diag_device.sh /tmp/ && adb shell sh /tmp/diag_device.sh
# 只读 + 一次振动测试，不改任何持久状态。

echo "===== 1. 当前是哪个构建（v3=r14 / v4=r16） ====="
for lib in /system/lib64/libminuitwrp.so /sbin/libminuitwrp.so; do
    if [ -f "$lib" ]; then
        echo "lib: $lib"
        # v4 的日志格式含 gain=%d；v3 没有
        echo -n "  v4 marker (gain=%d): "
        strings "$lib" 2>/dev/null | grep -c 'gain=%d'
        echo -n "  v3 marker (used=%d amp=): "
        strings "$lib" 2>/dev/null | grep -c 'used=%d amp=%.2f drive_ms'
        echo -n "  gain 文件开关: "
        strings "$lib" 2>/dev/null | grep -c 'fox_haptics_gain'
    fi
done
echo "twres 版本: $(grep -m1 -o 'OrangeFox Recovery R[0-9.]*' /twres/changelog.txt 2>/dev/null)"

echo
echo "===== 2. 振动设备节点清单 ====="
echo "-- /sys/class/leds/vibrator/ --"
ls -l /sys/class/leds/vibrator/ 2>/dev/null || echo "  (不存在)"
for a in max_brightness brightness duration activate trigger gain vmax rtp mode; do
    p="/sys/class/leds/vibrator/$a"
    [ -e "$p" ] && echo "  $a = $(cat $p 2>/dev/null)"
done
echo "-- /sys/class/timed_output/ --"
ls -l /sys/class/timed_output/ 2>/dev/null || echo "  (不存在)"
echo "-- awinic 相关 class --"
ls -d /sys/class/*aw* /sys/class/*haptic* 2>/dev/null || echo "  (无)"
for d in /sys/class/*aw* /sys/class/*haptic*; do
    [ -d "$d" ] && { echo "  [$d]"; ls "$d" 2>/dev/null | tr '\n' ' '; echo; }
done
echo -n "-- /dev/awinic_haptic: "; ls -l /dev/awinic_haptic 2>/dev/null || echo "无"
echo -n "-- HAL 进程: "; ps -A 2>/dev/null | grep -c realme.vibrator

echo
echo "===== 3. HAL 日志与最近一次点击路径 ====="
tail -6 /tmp/fox_haptics.log 2>/dev/null || echo "  (没有 /tmp/fox_haptics.log，说明还没触发过振动)"

echo
echo "===== 4. 直接写 sysfs 拉满振幅测试（会震一下） ====="
V=/sys/class/leds/vibrator
if [ -d "$V" ]; then
    MB=$(cat $V/max_brightness 2>/dev/null)
    echo "  max_brightness=$MB"
    TGT=${MB:-255}
    echo "  trigger 当前: $(cat $V/trigger 2>/dev/null | head -c 200)"
    echo "  写 brightness=$TGT (满振幅)..."
    echo "$TGT" > $V/brightness 2>/dev/null && echo "    brightness 写入成功 -> $(cat $V/brightness)" || echo "    brightness 写入失败"
    echo "  写 duration=60 + activate=1 ..."
    echo 60 > $V/duration 2>/dev/null && echo "    duration ok -> $(cat $V/duration)" || echo "    duration 写入失败"
    echo 1 > $V/activate 2>/dev/null && echo "    activate ok -> $(cat $V/activate)" || echo "    activate 写入失败"
    echo "  >>> 请记录：这一下的力度 vs 你在 recovery 里点按钮的力度"
    sleep 1
    echo "  恢复 brightness=0"
    echo 0 > $V/brightness 2>/dev/null
else
    echo "  /sys/class/leds/vibrator 不存在，无法测试"
fi

echo
echo "===== 5. 显示 / 帧率相关 ====="
echo "-- /sys/class/graphics/fb0 --"
for a in virtual_size bpp modes dynamic_fps msm_fb_panel_info; do
    p="/sys/class/graphics/fb0/$a"
    [ -e "$p" ] && echo "  $a = $(cat $p 2>/dev/null | head -c 300)"
done
echo "-- DRM DSI 模式 --"
cat /sys/class/drm/card0-DSI-1/modes 2>/dev/null | head -5 || echo "  (无)"
echo -n "  dynamic_fps = "; cat /sys/class/drm/card0-DSI-1/dynamic_fps 2>/dev/null || echo "(无)"
echo "-- 运行时刷新脚本结果 --"
cat /tmp/fox_refresh.log 2>/dev/null | tail -8 || echo "  (没有 /tmp/fox_refresh.log)"
echo "-- governor --"
for c in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo "  $c = $(cat $c 2>/dev/null)"
done | head -4
echo -n "  当前最大核频率: "; cat /sys/devices/system/cpu/cpu7/cpufreq/scaling_max_freq 2>/dev/null || echo "?"
echo "-- 图形后端（recovery 启动日志）--"
grep -i "using drm\|using fbdev\|double buffered\|single buffered\|overlay" /tmp/recovery.log 2>/dev/null | head -5 || echo "  (无 /tmp/recovery.log)"

echo
echo "===== 完成，把上面全部输出发给我 ====="
