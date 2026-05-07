#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
#  BUTCHER — Updater v1.0
#  Pulls the latest changes from Git and refreshes the installation.
# ─────────────────────────────────────────────────────────────────────

set -e

RED="\033[91m"
GRN="\033[92m"
CYN="\033[96m"
YLW="\033[93m"
RST="\033[0m"
BLD="\033[1m"

info()    { echo -e "${CYN}[*]${RST} $1"; }
success() { echo -e "${GRN}${BLD}[✓]${RST} $1"; }
warn()    { echo -e "${YLW}[!]${RST} $1"; }
error()   { echo -e "${RED}[✗]${RST} $1"; stop_animation; exit 1; }

# ── Animator Logic (Cinematic) ────────────────────────────────────────────────
ANIM_PID=0

start_animation() {
    local label="$1"
    stop_animation
    
    python3 -c "
import math, time, sys
label = \"$label\"
def wave(label, t):
    res = ''
    for i, c in enumerate(label):
        if not c.isalpha(): res += c; continue
        v = math.sin(t * 10 + i * 0.4)
        if v > 0: res += f'\033[91m\033[1m{c.upper()}\033[0m'
        else: res += f'\033[31m{c.lower()}\033[0m'
    return res
def braille(t):
    chars = '⡀⡄⡆⡇⣇⣧⣷⣿'
    bar = ''
    for i in range(40):
        idx = int((math.sin(t * 5 + i * 0.2) + 1) / 2 * (len(chars) - 1))
        bar += f'\033[91m{chars[idx]}\033[0m'
    return bar
start = time.time()
try:
    while True:
        t = time.time() - start
        sys.stdout.write(f'\r  {wave(label, t):<30} {braille(t)} ')
        sys.stdout.flush()
        time.sleep(0.05)
except:
    pass
" &
    ANIM_PID=$!
    disown $ANIM_PID 2>/dev/null || true
}

stop_animation() {
    if [ "$ANIM_PID" -ne 0 ]; then
        kill -9 "$ANIM_PID" &>/dev/null || true
        wait "$ANIM_PID" 2>/dev/null || true
        printf "\r\b\b\033[K"
        ANIM_PID=0
    fi
}

trap "stop_animation" EXIT INT TERM

# ── Pull latest changes ───────────────────────────────────────────────────────
start_animation "SYNCING REPOSITORY"
if [ ! -d ".git" ]; then
    stop_animation
    error "Not a git repository."
fi

git pull origin $(git rev-parse --abbrev-ref HEAD) || warn "Pull failed. Proceeding with local refresh..."
stop_animation

# ── Run installer ─────────────────────────────────────────────────────────────
info "Refreshing installation..."
chmod +x install.sh
./install.sh --yes

echo ""
echo -e "  ${GRN}${BLD}Update complete.${RST} Butcher is now surgical.\n"
echo ""
