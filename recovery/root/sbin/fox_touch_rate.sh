#!/system/bin/sh
# Whiteink / OrangeFox R12 on RMXTARO (realme GT Neo5 / GT3, SM8475)
#
# Pair the touch controller's report rate with the 144 Hz panel.
#
# Measured in recovery with adb root on 2026-11-14:
#   /sys/kernel/oplus_display/dynamic_te          = 144   (panel really at 144 Hz)
#   /tmp/fox_drm.log                              = "vrefresh=144 modeset_ok=1"
#   /proc/touchpanel/game_switch_enable           = "0, high_frame_support:1, high_frame_value:0"
#   dmesg: "report_rate_limit not specified,we will set it 60hz"
#          "default rate 60 / default game value 1"
#          "fps_report_rate is: 60 / 90 / 120"      (supported ladder)
#          "extreme_game_report_rate 0"             (no 240 Hz tier on this IC)
#
# The panel side is handled in source by scripts/patch_minuitwrp_drm_hz.py.
# The TOUCH side was never touched: the Synaptics S3910 boots at 60 Hz while
# the screen scans out at 144 Hz, so drags only get ~60 position updates per
# second no matter how fast the GUI redraws. That is the "30 fps / not
# following my finger" feel.
#
# Driver probes (all runtime proc switches, fully reversible):
#   echo 1 > /proc/touchpanel/game_switch_enable
#       -> "syna_tcm_set_game_mode: enable[1]", "set report_rate:1"
#   echo 0 > /proc/touchpanel/game_switch_enable
#       -> "syna_report_refresh_switch: refresh_switch: 60 HZ success!"
#   echo 2 > /proc/touchpanel/report_rate_white_list
#       -> "syna_rate_white_list_ctrl: DC_SET_REPORT_FRE: 3  success!"  (top tier)
#   echo 1 -> DC_SET_REPORT_FRE: 2, echo 0 -> DC_SET_REPORT_FRE: 1
#   values >= 3 are ignored by the driver.
#
# IMPORTANT: the driver drops back to 60 Hz on its own when it enters
# normal_mode (self-test / resume / re-init):
#       "syna_tcm_normal_mode : enter"
#       "syna_report_refresh_switch: refresh_switch: 60 HZ success!"
# A single early write is therefore not enough. This is a small resident
# watchdog: it re-asserts only when the values drift, every 5 seconds. It
# does NOT spin, writes no logs when nothing changed, and touches nothing
# outside two /proc nodes.
#
# Safety:
#   * never writes a partition / image, never deletes anything
#   * missing nodes just make it idle (other firmwares / device variants)
#   * every write is verified by readback on the next pass
# To disable: set ENABLE=0 below, or remove "start fox_touch_rate" from
# init.recovery.qcom.rc and rebuild.

ENABLE=1
LOG=/tmp/fox_touch.log
GAME=/proc/touchpanel/game_switch_enable
WLIST=/proc/touchpanel/report_rate_white_list
TE=/sys/kernel/oplus_display/dynamic_te

GAME_VALUE=1     # non-zero = high report-rate mode
WLIST_VALUE=2    # highest tier -> DC_SET_REPORT_FRE: 3
INTERVAL=5

[ "$ENABLE" -eq 1 ] || exit 0

log() { echo "fox_touch: $*" >> "$LOG"; }

log "watchdog start; panel dynamic_te=$(cat "$TE" 2>/dev/null || echo unknown)"

while true; do
    if [ ! -f "$GAME" ] || [ ! -f "$WLIST" ]; then
        sleep "$INTERVAL"
        continue
    fi

    g=$(cat "$GAME" 2>/dev/null)
    g=${g%%,*}
    g=$(printf '%s' "$g" | tr -d ' ')
    w=$(cat "$WLIST" 2>/dev/null | tr -d ' \n')

    if [ "$g" != "$GAME_VALUE" ] || [ "$w" != "$WLIST_VALUE" ]; then
        if [ "$g" != "$GAME_VALUE" ]; then
            echo "$GAME_VALUE" > "$GAME" 2>/dev/null
        fi
        if [ "$w" != "$WLIST_VALUE" ]; then
            echo "$WLIST_VALUE" > "$WLIST" 2>/dev/null
        fi
        g2=$(cat "$GAME" 2>/dev/null)
        w2=$(cat "$WLIST" 2>/dev/null | tr -d ' \n')
        log "re-assert game=$g->$g2 whitelist=$w->$w2 te=$(cat "$TE" 2>/dev/null)"
    fi

    sleep "$INTERVAL"
done
