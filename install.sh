#!/bin/sh
set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "${GREEN}=== Icinga2 NRPE Bootstrap Launcher ===${NC}"

# 1. Root / Sudo Privilege Check
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        echo "${YELLOW}>> Re-running script with sudo...${NC}"
        exec sudo sh "$0" "$@"
    else
        echo "${RED}Error: This script must be run as root. Sudo is not available.${NC}"
        exit 1
    fi
fi

# 2. Check for Python 3 (install if missing on lightweight systems like DietPi)
if ! command -v python3 >/dev/null 2>&1; then
    echo "${YELLOW}>> Python 3 not found. Installing Python 3 via apt...${NC}"
    apt-get update -qq
    apt-get install -y python3
fi

# 3. Define raw GitHub URLs (Adjust to your actual repository branch/name)
REPO_RAW_URL="https://raw.githubusercontent.com/Michdo93/Icinga2-NRPE-Universal-Bootstrap-Kit/main"
SCRIPT_NAME="nrpe-bootstrap.py"
TEMP_PATH="/tmp/$SCRIPT_NAME"

echo "${GREEN}>> Downloading setup logic (${SCRIPT_NAME})...${NC}"
if command -v curl >/dev/null 2>&1; then
    curl -sSL "$REPO_RAW_URL/$SCRIPT_NAME" -o "$TEMP_PATH"
elif command -v wget >/dev/null 2>&1; then
    wget -qO "$TEMP_PATH" "$REPO_RAW_URL/$SCRIPT_NAME"
else
    echo "${RED}Error: Neither curl nor wget is available to download the payload.${NC}"
    exit 1
fi

if [ ! -f "$TEMP_PATH" ]; then
    echo "${RED}Error: Failed to download setup script from GitHub.${NC}"
    exit 1
fi

# 4. Execute the Python logic (passing interactive terminal back via /dev/tty)
echo "${GREEN}>> Launching setup wizard...${NC}\n"
python3 "$TEMP_PATH" < /dev/tty

# Cleanup
rm -f "$TEMP_PATH"
