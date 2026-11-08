#
#	This file is part of the OrangeFox Recovery Project
# 	Copyright (C) 2023 The OrangeFox Recovery Project
#
#	OrangeFox is free software: you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or
#	any later version.
#
#	OrangeFox is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
# 	This software is released under GPL version 3 or any later version.
#	See <http://www.gnu.org/licenses/>.
#
# 	Please maintain this if you use this script or any part of it
#

# OrangeFox settings
OF_HIDE_NOTCH := 1
OF_USE_GREEN_LED := 0
OF_FLASHLIGHT_ENABLE := 1
OF_ALLOW_DISABLE_NAVBAR := 0
OF_QUICK_BACKUP_LIST := /data;/boot;
OF_SKIP_MULTIUSER_FOLDERS_BACKUP := 1
OF_ENABLE_USB_STORAGE := 1
OF_IGNORE_LOGICAL_MOUNT_ERRORS := 1
OF_BIND_MOUNT_SDCARD_ON_FORMAT := 1
OF_NO_SPLASH_CHANGE := 1
OF_FORCE_CASEFOLDING := 1
OF_DONT_KEEP_LOG_HISTORY := 1
OF_FORCE_CASEFOLDING := 1

# OrangeFox GUI settings
OF_SCREEN_H := 2412
OF_STATUS_H := 106
OF_STATUS_INDENT_LEFT := 48
OF_STATUS_INDENT_RIGHT := 48
OF_HIDE_NOTCH := 1
OF_CLOCK_POS := 1
OF_OPTIONS_LIST_NUM := 6
OF_SPLASH_MAX_SIZE := 16384

# Recovery additional features
OF_ENABLE_ALL_PARTITION_TOOLS=1
OF_USE_DMCTL :=1

OF_DISABLE_OTA_MENU := 1
OF_DYNAMIC_FULL_SIZE := 9663676416

# OTA
OF_NO_TREBLE_COMPATIBILITY_CHECK := 1
OF_PATCH_AVB20 := 1
OF_KEEP_DM_VERITY_FORCED_ENCRYPTION := 1

# Maintainer specific settings
OF_MAINTAINER := Whiteink

# ============================================================
# Whiteink (白墨) customizations
# Base: MisterZtr/recovery_device_realme_RMXTARO (OrangeFox R11.3, fox_12.1)
# Device: realme GT Neo5 / GT3 (codename RMXTARO, aka senna) - SM8475
# Plan: keep R11.3 base building, then upgrade UI layer to OrangeFox R12.0
# ============================================================
FOX_MAINTAINER_PATCH_VERSION := Whiteink-1.0

# R12 UI upgrade checklist (apply when moving bootable/recovery +
# vendor/recovery onto the R12 branch):
#   - TW_THEME -> new R12 theme engine (Fox White / Fox Dark)
#   - enable Inter font + gesture nav via OF flags (R12 default)
#   - swap SVG icon set into vendor/recovery images/
# Current build stays on R11.3 portrait_hdpi until R12 branch is wired in.

