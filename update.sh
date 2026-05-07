#!/usr/bin/env bash
# update.sh — Surgical Updater for Butcher [HELLHOUND-class]

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
print_centered "[ Surgical Update Matrix ]" "${D}${W}"
echo -e "${W}└$(printf '─%.0s' $(seq 1 $((TW - 2))))┘${RST}\n"

# 1. Fetch
log "Synchronizing with origin/main..."
git fetch --all --quiet
git reset --hard origin/main --quiet

# 2. Rebuild
log "Rebuilding isolation layer..."
if [ -d ".venv" ]; then
    ./.venv/bin/pip install --quiet --upgrade pip
    ./.venv/bin/pip install --quiet -r requirements.txt
else
    python3 -m venv .venv
    ./.venv/bin/pip install --quiet -r requirements.txt
fi

# 3. Redeploy
log "Redeploying surgical command..."
bash install.sh > /dev/null

success "Butcher successfully synchronized and updated."
echo ""
