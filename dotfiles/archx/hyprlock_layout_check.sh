#!/usr/bin/env bash
layout=$(
  hyprctl devices -j \
    | jq -r '.keyboards[] | select(.main == true) | .active_keymap' \
    | cut -d" " -f1
)

short=$(echo "$layout" | tr 'a-z' 'A-Z')

if [ "$short" != "ENGLISH" ]; then
  echo "<span>Incorrect keyboard layout.</span>"
else
  echo ""
fi
