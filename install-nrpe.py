#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
import re

# Colors for terminal output
GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
NC = "\033[0m"  # No Color

def print_banner():
    print(f"{GREEN}======================================================{NC}")
    print(f"{GREEN}      Icinga2 NRPE Universal Bootstrap Kit            {NC}")
    print(f"{GREEN}======================================================{NC}")
    print("Supports: Ubuntu, Debian, Kali Linux, DietPi, Raspberry Pi OS\n")

def check_root():
    if os.geteuid() != 0:
        print(f"{RED}Error: This script must be run as root (sudo python3 install-nrpe.py){NC}")
        sys.exit(1)

def check_os():
    if not os.path.exists("/etc/os-release"):
        print(f"{RED}Error: /etc/os-release not found. Unsupported system.{NC}")
        sys.exit(1)
    
    os_info = {}
    with open("/etc/os-release") as f:
        for line in f:
            if "=" in line:
                key, val = line.rstrip().split("=", 1)
                os_info[key] = val.strip('"')
    
    print(f"Detected OS: {YELLOW}{os_info.get('PRETTY_NAME', 'Unknown')}{NC}")
    
    if not shutil.which("apt-get"):
        print(f"{RED}Error: 'apt-get' not found. This script requires a Debian-based system.{NC}")
        sys.exit(1)

def prompt_yes_no(question, default="y"):
    default_str = "Y/n" if default.lower() == "y" else "y/N"
    while True:
        choice = input(f"{question} [{default_str}]: ").strip().lower()
        if not choice:
            choice = default
        if choice in ["y", "yes"]:
            return True
        elif choice in ["n", "no"]:
            return False
        print(f"{YELLOW}Please answer with 'y' or 'n'.{NC}")

def scan_listening_ports():
    ports = []
    try:
        # Run 'ss' to find listening TCP ports
        result = subprocess.run(["ss", "-tulpn", "state", "listening"], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            if "127.0.0.1" in line or "0.0.0.0" in line or "[::]" in line:
                parts = line.split()
                if len(parts) >= 4:
                    local_address = parts[3]
                    port_match = re.search(r':(\d+)$', local_address)
                    if port_match:
                        port = port_match.group(1)
                        if int(port) < 65535 and port not in [str(p['port']) for p in ports]:
                            # Try to extract process name
                            proc_match = re.search(r'users:\(\("([^"]+)"', line)
                            proc_name = proc_match.group(1) if proc_match else "unknown"
                            ports.append({"port": port, "process": proc_name})
    except Exception as e:
        print(f"{YELLOW}Warning: Port scanning failed: {e}{NC}")
    return ports

def scan_active_services():
    services = []
    ignored = {"getty", "systemd", "rsyslog", "dbus", "policykit", "udev", "cron", "ssh", "networking"}
    try:
        result = subprocess.run(["systemctl", "list-units", "--type=service", "--state=running", "--no-legend"], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            parts = line.split()
            if parts:
                svc_name = parts[0].replace(".service", "")
                if not any(svc_name.startswith(ign) for ign in ignored):
                    services.append(svc_name)
    except Exception as e:
        print(f"{YELLOW}Warning: Service scanning failed: {e}{NC}")
    return services

def main():
    check_root()
    print_banner()
    check_os()

    print("\n" + "="*35 + "\n 1. Configuration & Master IP\n" + "="*35)
    master_ip = input("Enter Icinga2 Master / Monitoring Server IP (required): ").strip()
    if not master_ip:
        print(f"{RED}Error: Master IP cannot be empty. Aborting.{NC}")
        sys.exit(1)

    print("\n" + "="*35 + "\n 2. Standard System Checks\n" + "="*35)
    setup_defaults = prompt_yes_no("Install standard checks (Load, Disk, Swap, Users)?", "y")
    setup_ssh = prompt_yes_no("Monitor SSH service status?", "y")

    print("\n" + "="*35 + "\n 3. Dynamic Auto-Discovery Options\n" + "="*35)
    auto_ports = prompt_yes_no("Scan and automatically add checks for open listening network ports?", "y")
    auto_services = prompt_yes_no("Scan and automatically add checks for active systemd services?", "n")

    print(f"\n{GREEN}>> Updating package lists and installing NRPE + Plugins...{NC}")
    subprocess.run(["apt-get", "update", "-qq"], check=True)
    subprocess.run(["apt-get", "install", "-y", "nagios-nrpe-server", "monitoring-plugins", "nagios-plugins-contrib"], check=True)

    nrpe_conf = "/etc/nagios/nrpe.cfg"
    print(f"{GREEN}>> Configuring NRPE in {nrpe_conf}...{NC}")

    # Read and update allowed_hosts and dont_blame_nagios
    with open(nrpe_conf, "r") as f:
        content = f.read()

    # Update allowed_hosts
    content = re.sub(r'^allowed_hosts=.*$', f'allowed_hosts=127.0.0.1, ::1, {master_ip}', content, flags=re.MULTILINE)
    # Enable argument passing (dont_blame_nagios)
    content = re.sub(r'^dont_blame_nagios=.*$', 'dont_blame_nagios=1', content, flags=re.MULTILINE)

    with open(nrpe_conf, "w") as f:
        f.write(content)

    # Append custom commands
    custom_commands = "\n\n# --- Automatically Added Bootstrap Checks ---\n"

    if setup_defaults:
        custom_commands += 'command[check_load]=/usr/lib/nagios/plugins/check_load -w 5.0,4.0,3.0 -c 10.0,8.0,6.0\n'
        custom_commands += 'command[check_users]=/usr/lib/nagios/plugins/check_users -w 5 -c 10\n'
        custom_commands += 'command[check_swap]=/usr/lib/nagios/plugins/check_swap -w 20% -c 10%\n'
        custom_commands += 'command[check_disk_root]=/usr/lib/nagios/plugins/check_disk -w 20% -c 10% -p /\n'

    if setup_ssh:
        custom_commands += 'command[check_ssh]=/usr/lib/nagios/plugins/check_procs -c 1:1 -w 1:1 -u root -C sshd\n'

    if auto_ports:
        print(f"{GREEN}>> Scanning open ports...{NC}")
        ports = scan_listening_ports()
        custom_commands += '\n# --- Dynamic Port Checks ---\n'
        for p in ports:
            port = p['port']
            proc = p['process']
            print(f" -> Found port {port} ({proc})")
            custom_commands += f'command[check_port_{port}]=/usr/lib/nagios/plugins/check_tcp -H 127.0.0.1 -p {port}\n'

    if auto_services:
        print(f"{GREEN}>> Scanning active systemd services...{NC}")
        services = scan_active_services()
        custom_commands += '\n# --- Dynamic Service Checks ---\n'
        for svc in services:
            print(f" -> Found service: {svc}")
            custom_commands += f'command[check_svc_{svc}]=/usr/lib/nagios/plugins/check_procs -c 1:1 -w 1:1 -C {svc}\n'

    with open(nrpe_conf, "a") as f:
        f.write(custom_commands)

    print(f"{GREEN}>> Restarting NRPE service...{NC}")
    subprocess.run(["systemctl", "enable", "nagios-nrpe-server"], check=True)
    subprocess.run(["systemctl", "restart", "nagios-nrpe-server"], check=True)

    print(f"\n{GREEN}=== Installation & Configuration Successfully Completed! ==={NC}")
    print(f"NRPE is running and authorized for Icinga Master: {YELLOW}{master_ip}{NC}")

if __name__ == "__main__":
    main()
