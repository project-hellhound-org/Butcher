#!/usr/bin/env bash
# install.sh — Surgical Installer for Butcher [HELLHOUND-class]

set -e

# Branding Colors
BR='\033[91m' # Bright Red
Y='\033[33m'  # Yellow
W='\033[97m'  # White
GR='\033[90m' # Grey
C='\033[36m'  # Cyan
B='\033[1m'   # Bold
D='\033[2m'   # Dim
RST='\033[0m' # Reset

# Markers
INFO="${W}[${C}#${W}]${RST}"
SUCCESS="${W}[${Y}✓${W}]${RST}"
ERROR="${W}[${BR}✗${W}]${RST}"

log() { echo -e "  ${INFO} ${GR}$1${RST}"; }
success() { echo -e "  ${SUCCESS} ${B}${W}$1${RST}"; }
error() { echo -e "  ${ERROR} ${BR}$1${RST}"; exit 1; }

# Center Banner Logic
TW=$(tput cols || echo 80)
print_centered() {
    local text="$1"
    local color="$2"
    local clean_text=$(echo -e "$text" | sed 's/\033\[[0-9;]*m//g')
    local padding=$(( (TW - 2 - ${#clean_text}) / 2 ))
    printf "${W}│${RST}%${padding}s${color}%s${RST}%$(( TW - 2 - ${#clean_text} - padding ))s${W}│${RST}\n" "" "$text" ""
}

# Banner
echo -e "\n${W}┌$(printf '─%.0s' $(seq 1 $((TW - 2))))┐${RST}"
print_centered "_____________  ______________________  __________________ " "${BR}"
print_centered "___  __ )_  / / /__  __/_  ____/__  / / /__  ____/__  __ \\" "${BR}"
print_centered "__  __  |  / / /__  /  _  /    __  /_/ /__  __/  __  /_/ /" "${Y}"
print_centered "_  /_/ // /_/ / _  /   / /___  _  __  / _  /___  _  _, _/ " "${Y}"
print_centered "/_____/ \____/  /_/    \____/  /_/ /_/  /_____/  /_/ |_|  " "${Y}"
print_centered "" ""
print_centered "[ Surgical Installation Matrix ]" "${D}${W}"
echo -e "${W}└$(printf '─%.0s' $(seq 1 $((TW - 2))))┘${RST}\n"

# 1. Environment Check
log "Initializing deployment sequence..."
if ! command -v python3 &>/dev/null; then
    error "Python 3 required but not found."
fi

# 2. Isolation
log "Carving virtual environment (.venv)..."
python3 -m venv .venv || error "Failed to create isolation layer."

# 3. Dependencies
log "Mounting core dependencies..."
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt || error "Dependency carving failed."

# 4. Surgical Engine
log "Mounting Playwright Chromium cores..."
./.venv/bin/python3 -m playwright install chromium || true
if [ "$EUID" -ne 0 ]; then
    log "Requesting system permissions for engine patches..."
    sudo ./.venv/bin/python3 -m playwright install-deps chromium >/dev/null 2>&1 || true
else
    ./.venv/bin/python3 -m playwright install-deps chromium >/dev/null 2>&1 || true
fi

# 5. Global Link
log "Finalizing system-wide deployment..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER_PATH="/usr/local/bin/butcher"

# Create a clean wrapper
cat <<EOF > butcher_tmp
#!/usr/bin/env bash
exec "${SCRIPT_DIR}/.venv/bin/python3" "${SCRIPT_DIR}/butcher.py" "\$@"
EOF

if [ -w "/usr/local/bin" ]; then
    mv butcher_tmp "${WRAPPER_PATH}"
    chmod 755 "${WRAPPER_PATH}"
else
    WRAPPER_PATH="${HOME}/.local/bin/butcher"
    mkdir -p "${HOME}/.local/bin"
    mv butcher_tmp "${WRAPPER_PATH}"
    chmod 755 "${WRAPPER_PATH}"
fi

success "Butcher successfully deployed to ${WRAPPER_PATH}"
echo -e "  ${GR}Usage: butcher <target>${RST}\n"
