#!/system/bin/sh
# Whiteink / OrangeFox R12 on RMXTARO (realme GT Neo5 / GT3, SM8475)
#
# Best-effort 144 Hz panel mode for recovery.
#
# Recovery has no SurfaceFlinger / DisplayManager / SettingsProvider, so
# "settings put system peak_refresh_rate 144" does NOT work here. The panel
# scanout mode is chosen by the kernel DRM/panel driver; the only thing a
# device tree can do is write a refresh-rate sysfs node early in boot.
#
# Deliberately conservative:
#   * writes only when the kernel advertises a 144 Hz mode, OR when the node
#     is demonstrably a live refresh-rate control (current value >= 60)
#   * verifies the new value by reading it back
#   * restores the old value if the write is rejected
#   * ALWAYS exits 0, so a missing node can never block the boot
# This changes the PANEL rate, not the UI redraw rate (TW_FRAMERATE).
#
# To disable: set ENABLE=0 below, or remove "start fox_refresh" from
# init.recovery.qcom.rc and rebuild.

ENABLE=1
LOG=/tmp/fox_refresh.log

[ "$ENABLE" -eq 1 ] || exit 0
: > "$LOG" 2>/dev/null || LOG=/dev/null

echo "fox_refresh: probing panel refresh nodes" >> "$LOG"

# Evidence that 144 Hz is a real mode on this panel. Match a standalone 144,
# not resolutions such as 1440 / 1240.
SUPPORTS144=0
for p in /sys/class/graphics/fb0/modes \
         /sys/class/graphics/fb0/msm_fb_panel_info \
         /sys/class/graphics/fb0/dynamic_fps \
         /sys/class/drm/card0-DSI-1/modes; do
    [ -r "$p" ] || continue
    if grep -q -E '(^|[^0-9])144([^0-9]|$)' "$p" 2>/dev/null; then
        echo "fox_refresh: 144 advertised by $p" >> "$LOG"
        SUPPORTS144=1
        break
    fi
done

CANDIDATES="/sys/class/graphics/fb0/dynamic_fps
/sys/class/graphics/fb0/msm_fb_dfps_mode
/sys/class/drm/card0-DSI-1/dynamic_fps"

for node in $CANDIDATES; do
    [ -w "$node" ] || continue
    old=$(cat "$node" 2>/dev/null) || continue
    cur=$(printf '%s\n' "$old" | grep -o '[0-9][0-9]*' | head -1)

    if [ "$SUPPORTS144" -eq 0 ]; then
        if [ -z "$cur" ] || [ "$cur" -lt 60 ] 2>/dev/null; then
            continue
        fi
        echo "fox_refresh: no 144 advertisement; $node is a live fps control ($cur)" >> "$LOG"
    fi

    echo 144 > "$node" 2>/dev/null || {
        echo "fox_refresh: write rejected by $node" >> "$LOG"
        continue
    }
    new=$(cat "$node" 2>/dev/null | grep -o '[0-9][0-9]*' | head -1)
    if [ "$new" = "144" ]; then
        echo "fox_refresh: OK $node: $old -> 144 Hz" >> "$LOG"
        exit 0
    fi
    echo "fox_refresh: $node did not accept 144 (readback=$new); restoring $old" >> "$LOG"
    [ -n "$old" ] && echo "$old" > "$node" 2>/dev/null
done

echo "fox_refresh: no usable 144 Hz node; panel left at kernel default" >> "$LOG"
exit 0
