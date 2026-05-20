#!/bin/bash
# =============================================================================
# Email Capture Plugin — Ubuntu Auto Installer
# =============================================================================
# Usage:
#   chmod +x install.sh
#   sudo ./install.sh
# =============================================================================

set -e

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Config ────────────────────────────────────────────────────────────────────
APP_NAME="email-plugin"
INSTALL_DIR="/opt/email-plugin"
VENV_DIR="$INSTALL_DIR/venv"
LOG_DIR="/var/log/email-plugin"
LOG_FILE="$LOG_DIR/server.log"
PID_FILE="/var/run/email-plugin.pid"
SERVICE_USER="$(logname 2>/dev/null || echo $SUDO_USER || echo root)"
PORT=8000

# ── Helpers ───────────────────────────────────────────────────────────────────
print_banner() {
  echo -e "${CYAN}"
  echo "  ╔══════════════════════════════════════════════╗"
  echo "  ║       Email Capture Plugin — Installer       ║"
  echo "  ╚══════════════════════════════════════════════╝"
  echo -e "${NC}"
}

log()     { echo -e "${GREEN}[✔]${NC} $1"; }
info()    { echo -e "${BLUE}[→]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
error()   { echo -e "${RED}[✘]${NC} $1"; exit 1; }
section() { echo -e "\n${BOLD}${CYAN}── $1 ──${NC}"; }

prompt() {
  local var_name=$1
  local prompt_text=$2
  local default=$3
  local secret=$4

  if [ -n "$secret" ]; then
    read -rsp "${YELLOW}?${NC} ${prompt_text} [${default}]: " input
    echo
  else
    read -rp "$(echo -e "${YELLOW}?${NC} ${prompt_text} [${default}]: ")" input
  fi
  eval "$var_name=\"${input:-$default}\""
}

# ── Root check ────────────────────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
  error "Please run as root: sudo ./install.sh"
fi

print_banner

# =============================================================================
# STEP 1 — Collect configuration interactively
# =============================================================================
section "Configuration"
echo -e "${YELLOW}Please provide the following details. Press Enter to use defaults.${NC}\n"

prompt BASE_URL      "Your server public URL (no trailing slash)" "http://localhost:$PORT"
prompt PORT          "Port to run on"                             "$PORT"
prompt LINK_EXPIRE   "Download link expiry (hours)"               "24"
prompt SMTP_HOST     "SMTP host"                                  "smtp.gmail.com"
prompt SMTP_PORT     "SMTP port"                                  "587"
prompt SMTP_USER     "SMTP username (your email)"                 ""
prompt SMTP_PASSWORD "SMTP password / App password" ""            secret
prompt FROM_EMAIL    "From email address"                         "$SMTP_USER"

echo ""
log "Configuration collected."

# =============================================================================
# STEP 2 — System packages
# =============================================================================
section "System Packages"

info "Updating apt..."
apt-get update -qq

info "Installing Python3, pip, venv, curl..."
apt-get install -y -qq \
  python3 \
  python3-pip \
  python3-venv \
  curl \
  cron \
  lsof

log "System packages installed."

# =============================================================================
# STEP 3 — Create install directory and copy files
# =============================================================================
section "Installing Application"

info "Creating directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR/files"
mkdir -p "$LOG_DIR"

# Copy all plugin files from current directory to install dir
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for f in main.py plugin.js demo.html requirements.txt; do
  if [ -f "$SCRIPT_DIR/$f" ]; then
    cp "$SCRIPT_DIR/$f" "$INSTALL_DIR/$f"
    log "Copied $f"
  else
    warn "$f not found in $SCRIPT_DIR — skipping (place it in $INSTALL_DIR manually)"
  fi
done

# Place a placeholder file in /files if empty
if [ -z "$(ls -A "$INSTALL_DIR/files" 2>/dev/null)" ]; then
  echo "Place your downloadable files here." > "$INSTALL_DIR/files/README.txt"
  warn "No files found. Add your files to $INSTALL_DIR/files/"
fi

log "Application files installed to $INSTALL_DIR"

# =============================================================================
# STEP 4 — Python virtual environment + dependencies
# =============================================================================
section "Python Environment"

info "Creating virtual environment at $VENV_DIR..."
python3 -m venv "$VENV_DIR"

info "Installing Python packages..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install \
  fastapi \
  "uvicorn[standard]" \
  "pydantic[email]" \
  python-multipart \
  -q

log "Python environment ready."

# =============================================================================
# STEP 5 — Write .env file
# =============================================================================
section "Environment Config"

cat > "$INSTALL_DIR/.env" <<EOF
# Auto-generated by install.sh on $(date)
BASE_URL=$BASE_URL
PORT=$PORT
LINK_EXPIRE_HRS=$LINK_EXPIRE
SMTP_HOST=$SMTP_HOST
SMTP_PORT=$SMTP_PORT
SMTP_USER=$SMTP_USER
SMTP_PASSWORD=$SMTP_PASSWORD
FROM_EMAIL=$FROM_EMAIL
EOF

chmod 600 "$INSTALL_DIR/.env"
log ".env file written to $INSTALL_DIR/.env"

# =============================================================================
# STEP 6 — Patch main.py to load .env automatically
# =============================================================================
section "Patching Application Config"

# Inject dotenv loader at top of main.py if not already present
if ! grep -q "dotenv" "$INSTALL_DIR/main.py" 2>/dev/null; then
  "$VENV_DIR/bin/pip" install python-dotenv -q

  # Prepend dotenv loading lines
  TMP=$(mktemp)
  cat > "$TMP" <<'PYEOF'
import os
from pathlib import Path as _P
_env = _P(__file__).parent / '.env'
if _env.exists():
    for _line in _env.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _v = _line.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip())

PYEOF
  cat "$INSTALL_DIR/main.py" >> "$TMP"
  mv "$TMP" "$INSTALL_DIR/main.py"
  log "dotenv loader injected into main.py"
fi

# =============================================================================
# STEP 7 — Create start/stop/status helper scripts
# =============================================================================
section "Helper Scripts"

# ── start.sh ──────────────────────────────────────────────────────────────────
cat > "$INSTALL_DIR/start.sh" <<STARTEOF
#!/bin/bash
INSTALL_DIR="$INSTALL_DIR"
VENV_DIR="$VENV_DIR"
LOG_FILE="$LOG_FILE"
PID_FILE="$PID_FILE"
PORT="$PORT"

if [ -f "\$PID_FILE" ] && kill -0 \$(cat "\$PID_FILE") 2>/dev/null; then
  echo "Already running (PID \$(cat \$PID_FILE))"
  exit 0
fi

cd "\$INSTALL_DIR"
nohup "\$VENV_DIR/bin/uvicorn" main:app \\
  --host 0.0.0.0 \\
  --port "\$PORT" \\
  >> "\$LOG_FILE" 2>&1 &

echo \$! > "\$PID_FILE"
echo "Started (PID \$!). Logs: \$LOG_FILE"
STARTEOF

# ── stop.sh ───────────────────────────────────────────────────────────────────
cat > "$INSTALL_DIR/stop.sh" <<STOPEOF
#!/bin/bash
PID_FILE="$PID_FILE"
if [ -f "\$PID_FILE" ]; then
  PID=\$(cat "\$PID_FILE")
  if kill -0 "\$PID" 2>/dev/null; then
    kill "\$PID"
    rm -f "\$PID_FILE"
    echo "Stopped (PID \$PID)"
  else
    echo "Process not running. Cleaning PID file."
    rm -f "\$PID_FILE"
  fi
else
  echo "Not running."
fi
STOPEOF

# ── status.sh ─────────────────────────────────────────────────────────────────
cat > "$INSTALL_DIR/status.sh" <<STATUSEOF
#!/bin/bash
PID_FILE="$PID_FILE"
PORT="$PORT"
if [ -f "\$PID_FILE" ] && kill -0 \$(cat "\$PID_FILE") 2>/dev/null; then
  echo -e "\033[0;32m[RUNNING]\033[0m PID: \$(cat \$PID_FILE) | Port: \$PORT"
  echo "URL: $BASE_URL"
  echo "Logs: $LOG_FILE"
else
  echo -e "\033[0;31m[STOPPED]\033[0m"
fi
STATUSEOF

chmod +x "$INSTALL_DIR/start.sh" "$INSTALL_DIR/stop.sh" "$INSTALL_DIR/status.sh"
log "start.sh / stop.sh / status.sh created"

# =============================================================================
# STEP 8 — Cron job for auto-start on reboot + keep-alive every 5 min
# =============================================================================
section "Cron Jobs"

CRON_START="@reboot $INSTALL_DIR/start.sh >> $LOG_FILE 2>&1"
CRON_ALIVE="*/5 * * * * $INSTALL_DIR/start.sh >> $LOG_FILE 2>&1"

# Get current crontab, remove old entries, add new ones
(
  crontab -l 2>/dev/null | grep -v "email-plugin" | grep -v "$INSTALL_DIR/start.sh"
  echo "# email-plugin: auto-start on reboot"
  echo "$CRON_START"
  echo "# email-plugin: keep-alive check every 5 minutes"
  echo "$CRON_ALIVE"
) | crontab -

log "Cron jobs added:"
info "  @reboot     → auto-start server on system reboot"
info "  */5 * * * * → keep-alive check every 5 minutes"

# =============================================================================
# STEP 9 — Open firewall port (ufw if available)
# =============================================================================
section "Firewall"

if command -v ufw &>/dev/null; then
  ufw allow "$PORT/tcp" > /dev/null 2>&1 && log "ufw: port $PORT opened" || warn "ufw rule failed (may already exist)"
else
  warn "ufw not found — open port $PORT manually if needed"
fi

# =============================================================================
# STEP 10 — Start the server now
# =============================================================================
section "Starting Server"

info "Starting server on port $PORT..."
bash "$INSTALL_DIR/start.sh"

sleep 2

if bash "$INSTALL_DIR/status.sh" | grep -q "RUNNING"; then
  log "Server is running!"
else
  warn "Server may not have started. Check logs: $LOG_FILE"
fi

# =============================================================================
# DONE
# =============================================================================
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║              Installation Complete!                      ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Server URL:${NC}       $BASE_URL"
echo -e "  ${BOLD}Demo page:${NC}        $BASE_URL/demo"
echo -e "  ${BOLD}Admin panel:${NC}      $BASE_URL/admin/subscribers?secret=admin"
echo -e "  ${BOLD}Files list:${NC}       $BASE_URL/api/files"
echo -e "  ${BOLD}Install dir:${NC}      $INSTALL_DIR"
echo -e "  ${BOLD}Files folder:${NC}     $INSTALL_DIR/files/"
echo -e "  ${BOLD}Logs:${NC}             $LOG_FILE"
echo ""
echo -e "  ${BOLD}Commands:${NC}"
echo -e "    Start:   ${CYAN}$INSTALL_DIR/start.sh${NC}"
echo -e "    Stop:    ${CYAN}$INSTALL_DIR/stop.sh${NC}"
echo -e "    Status:  ${CYAN}$INSTALL_DIR/status.sh${NC}"
echo ""
echo -e "  ${BOLD}Embed on your website:${NC}"
echo -e "    ${CYAN}<script src=\"$BASE_URL/plugin.js\""
echo -e "            data-file=\"yourfile.pdf\""
echo -e "            data-website=\"https://yoursite.com\"></script>${NC}"
echo ""
echo -e "  ${YELLOW}Next steps:${NC}"
echo -e "    1. Drop your files into ${BOLD}$INSTALL_DIR/files/${NC}"
echo -e "    2. Paste the script tag on your website with the correct ${BOLD}data-file${NC} name"
echo -e "    3. Check subscribers at ${BOLD}$BASE_URL/admin/subscribers?secret=admin{NC}"
echo -e "    4. Download links expire after ${BOLD}${LINK_EXPIRE_HRS}h${NC} — set via LINK_EXPIRE_HRS env var"
echo ""