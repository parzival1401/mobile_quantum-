#!/bin/bash
# start_quantum_dance.sh - boot launcher for the VERTICAL build (quantum_optimized.py)
#
# Called from ~/.config/labwc/autostart. Rotates both screens to portrait,
# waits until the rotation is really applied, THEN starts the game - the game
# measures the screens once at startup, so starting it while they are still
# landscape leaves the windows cut off and shifted up.

GAME_DIR=/home/quantummobile/mobile_quantum-/dance_dance
PYTHON=/home/quantummobile/mobile_quantum-/.venv/bin/python
LOG=/tmp/quantum_dance.log
ROT=90            # use 270 if the picture is upside down

export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
export WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0}

exec > "$LOG" 2>&1
echo "start $(date)"

rotate() {
    wlr-randr --output HDMI-A-1 --mode 1024x768 --transform $ROT --pos 0,0 \
              --output HDMI-A-2 --mode 1024x768 --transform $ROT --pos 768,0
}

portrait_ok() {
    out=$(wlr-randr 2>/dev/null)
    [ "$(echo "$out" | grep -c "Transform: $ROT")" -ge 2 ] &&
        echo "$out" | grep -q "Position: 768,0"
}

# 1. Wait (up to 30 s) until labwc has brought up both monitors.
for i in $(seq 1 30); do
    [ "$(wlr-randr 2>/dev/null | grep -c '^HDMI-A-')" -ge 2 ] && break
    sleep 1
done

# 2. Rotate, and retry until both really report portrait.
for i in $(seq 1 10); do
    rotate
    sleep 1
    portrait_ok && break
done

# 3. Let the desktop finish re-laying out before the game measures it.
sleep 2
wlr-randr
echo "env: DISPLAY=$DISPLAY WAYLAND_DISPLAY=$WAYLAND_DISPLAY SDL_VIDEODRIVER=$SDL_VIDEODRIVER"

# 4. Start the game from dance_dance/ (music/ paths are relative).
cd "$GAME_DIR" || exit 1
exec "$PYTHON" quantum_optimized.py
