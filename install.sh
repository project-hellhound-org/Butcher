#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
#  BUTCHER — Installer (v1.0)
#  Installs the `butcher` command with an isolated virtual environment.
# ─────────────────────────────────────────────────────────────────────

set -e

RED='\033[91m'
GRN='\033[92m'
CYN='\033[96m'
YLW='\033[93m'
RST='\033[0m'
BLD='\033[1m'

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
    for i in range(50):
        idx = int((math.sin(t * 5 + i * 0.2) + 1) / 2 * (len(chars) - 1))
        bar += f'\033[91m{chars[idx]}\033[0m'
    return bar
start = time.time()
try:
    while True:
        t = time.time() - start
        sys.stdout.write(f'\r  {wave(label, t):<35}  {braille(t)} ')
        sys.stdout.flush()
        time.sleep(0.06)
except KeyboardInterrupt:
    pass
" &
    ANIM_PID=$!
}

stop_animation() {
    if [ "$ANIM_PID" -ne 0 ]; then
        kill "$ANIM_PID" &>/dev/null || true
        wait "$ANIM_PID" 2>/dev/null || true
        printf "\r\b\b\033[K"
        ANIM_PID=0
    fi
}

trap "stop_animation" EXIT INT TERM

# Parse flags
NON_INTERACTIVE=false
for arg in "$@"; do
    if [[ "$arg" == "--yes" || "$arg" == "-y" || "$arg" == "--non-interactive" ]]; then
        NON_INTERACTIVE=true
    fi
done

# ── Check Python version ───────────────────────────────────────────────────────
start_animation "PREPARING BUTCHER"
if ! command -v python3 &>/dev/null; then
    stop_animation
    error "Python 3 not found. Install Python 3.10+ and try again."
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    error "Python 3.10+ required. Found: $PY_VERSION"
fi
stop_animation
success "Python $PY_VERSION found"

# ── Virtual Environment Setup ────────────────────────────────────────────────
start_animation "ISOLATING CORE"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR" || error "Failed to create virtual environment."
fi
VENV_PYTHON="$VENV_DIR/bin/python3"
stop_animation
success "Virtual environment ready: $VENV_DIR"

# ── Install pip dependencies ───────────────────────────────────────────────────
start_animation "CARVING DEPENDENCIES"
"$VENV_PYTHON" -m pip install --quiet --upgrade pip
"$VENV_PYTHON" -m pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
stop_animation
success "Core dependencies installed"

# ── Playwright ───────────────────────────────────────────────────────
start_animation "MOUNTING SURGICAL ENGINE"
"$VENV_PYTHON" -m pip install --quiet --upgrade playwright
"$VENV_PYTHON" -m playwright install chromium 2>&1 | grep --line-buffered -vE "BEWARE|fallback" || true
if command -v sudo &>/dev/null && [ "$EUID" -ne 0 ]; then
    sudo "$VENV_PYTHON" -m playwright install-deps chromium 2>&1 | grep --line-buffered -vE "BEWARE|fallback" || true
else
    "$VENV_PYTHON" -m playwright install-deps chromium 2>&1 | grep --line-buffered -vE "BEWARE|fallback" || true
fi
stop_animation
success "Playwright Engine ready"

# ── Install the butcher command ─────────────────────────────────────────────────
start_animation "FINALIZING DEPLOYMENT"

BUTCHER_SRC="$SCRIPT_DIR/butcher.py"
WRAPPPER_TMP=$(mktemp)
cat <<'EOW' > "$WRAPPPER_TMP"
#!/usr/bin/env bash
SELF="$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || realpath "${BASH_SOURCE[0]}" 2>/dev/null || echo "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$SELF")" && pwd)"
EOW
cat <<EOW >> "$WRAPPPER_TMP"
VENV_PYTHON="$VENV_PYTHON"
BUTCHER_SRC="$BUTCHER_SRC"
EOW
cat <<'EOW' >> "$WRAPPPER_TMP"
if [ ! -x "$VENV_PYTHON" ]; then
    echo "[!] Butcher venv not found at: $VENV_PYTHON" >&2
    exit 1
fi
exec "$VENV_PYTHON" "$BUTCHER_SRC" "$@"
EOW

if [ -w "/usr/local/bin" ]; then
    INSTALL_DIR="/usr/local/bin"
elif sudo -n true 2>/dev/null; then
    INSTALL_DIR="/usr/local/bin"
    USE_SUDO=true
else
    INSTALL_DIR="$HOME/.local/bin"
    mkdir -p "$INSTALL_DIR"
fi

INSTALL_PATH="$INSTALL_DIR/butcher"

if [ "${USE_SUDO:-false}" = true ]; then
    sudo cp "$WRAPPPER_TMP" "$INSTALL_PATH"
    sudo chmod 755 "$INSTALL_PATH"
else
    cp "$WRAPPPER_TMP" "$INSTALL_PATH"
    chmod 755 "$INSTALL_PATH"
fi
rm -f "$WRAPPPER_TMP"
stop_animation
success "Installed to $INSTALL_PATH"

echo ""
echo -e "  ${GRN}${BLD}Installation complete.${RST}\n"
echo -e "  Usage:"
echo -e "    ${CYN}butcher${RST} https://target.com"
echo -e "    ${CYN}butcher${RST} --help"
echo ""
