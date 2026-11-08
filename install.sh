#!/bin/sh
#
# Icinga2 NRPE Bootstrap Launcher - downloads nrpe-bootstrap.py and runs it as root.
#
#   wget -qO- https://raw.githubusercontent.com/Michdo93/Icinga2-NRPE-Universal-Bootstrap-Kit/main/install.sh | sh
#
# Arguments after "sh -s --" are passed to nrpe-bootstrap.py (see --help), e.g. without
# questions:
#   wget -qO- .../install.sh | sh -s -- --master 192.168.1.10 --defaults --ssh --ports --yes
#
# Works as root or as a sudo user, with "| sh" and "| bash". Everything is inside main(),
# which is only called on the last line, so the piped script is read completely first.

set -eu

main() {
    if [ -t 1 ]; then GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
    else GREEN=''; RED=''; YELLOW=''; NC=''; fi

    printf "${GREEN}=== Icinga2 NRPE Bootstrap Launcher ===${NC}\n"

    # 1. Root / sudo
    if [ "$(id -u)" -eq 0 ]; then
        SUDO=""
    elif command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
        printf "${YELLOW}>> Not running as root - using sudo.${NC}\n"
    else
        printf "${RED}Error: This script must be run as root. Sudo is not available.${NC}\n" >&2
        exit 1
    fi

    # 2. Python 3 (missing on lightweight systems like DietPi)
    if ! command -v python3 >/dev/null 2>&1; then
        printf "${YELLOW}>> Python 3 not found. Installing Python 3 via apt...${NC}\n"
        $SUDO env DEBIAN_FRONTEND=noninteractive apt-get update -qq </dev/null
        $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends python3 </dev/null >/dev/null
    fi

    # 3. Download the setup logic (NRPE_BOOTSTRAP_URL overrides the source, e.g. for a fork)
    URL="${NRPE_BOOTSTRAP_URL:-https://raw.githubusercontent.com/Michdo93/Icinga2-NRPE-Universal-Bootstrap-Kit/main/nrpe-bootstrap.py}"
    TEMP_PATH="$(mktemp)"
    trap 'rm -f "$TEMP_PATH"' EXIT INT TERM

    printf "${GREEN}>> Downloading setup logic (%s)...${NC}\n" "${URL##*/}"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$URL" -o "$TEMP_PATH"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$TEMP_PATH" "$URL"
    else
        printf "${RED}Error: Neither curl nor wget is available to download the payload.${NC}\n" >&2
        exit 1
    fi
    [ -s "$TEMP_PATH" ] || { printf "${RED}Error: Failed to download %s.${NC}\n" "$URL" >&2; exit 1; }

    # 4. Run it. The pipe is stdin, so questions are answered on the terminal (/dev/tty);
    #    without a terminal the script runs non-interactively (--master is then required).
    printf "${GREEN}>> Launching setup wizard...${NC}\n\n"
    if (exec </dev/tty) 2>/dev/null; then
        $SUDO python3 "$TEMP_PATH" "$@" </dev/tty
    else
        $SUDO python3 "$TEMP_PATH" --yes "$@" </dev/null
    fi
}

main "$@"
