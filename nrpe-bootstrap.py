#!/usr/bin/env python3
"""Icinga2 NRPE Universal Bootstrap Kit - install and configure NRPE on Debian-based hosts.

Interactive by default. Every question can be answered on the command line, which makes the
script usable without a terminal (e.g. from a rollout over SSH):

    nrpe-bootstrap.py --master 192.168.1.10 --defaults --ssh --ports --no-services --yes

Re-running is safe: the generated commands live in their own file
(/etc/nagios/nrpe.d/icinga2-bootstrap.cfg) which is rewritten on every run.
"""
import argparse
import ipaddress
import os
import re
import shutil
import subprocess
import sys

GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
NC = "\033[0m"
if not sys.stdout.isatty():
    GREEN = RED = YELLOW = NC = ""

PLUGINS = "/usr/lib/nagios/plugins"
NRPE_CONF = "/etc/nagios/nrpe.cfg"
NRPE_DIR = "/etc/nagios/nrpe.d"
BOOTSTRAP_CFG = os.path.join(NRPE_DIR, "icinga2-bootstrap.cfg")
UNIT_PLUGIN = "/usr/local/lib/nagios/plugins/check_systemd_unit"
ICINGA_EXAMPLE = "/etc/nagios/icinga2-services.conf.example"

# Units that are either always running or not useful as an individual check.
IGNORED_SERVICES = re.compile(
    r"^(getty@|serial-getty@|user@|systemd-|dbus|polkit|udisks|rsyslog|cron|ssh|sshd|networking|"
    r"nagios-nrpe-server|ModemManager|wpa_supplicant|accounts-daemon|rtkit|upower|packagekit|"
    r"unattended-upgrades|multipathd|irqbalance|snapd|lvm2|blk-availability|console-setup|keyboard-setup|"
    r"apparmor|plymouth|setvtrgb|kmod|ufw|e2scrub|fwupd|thermald|power-profiles|switcheroo|colord|cups-browsed|"
    r"avahi-daemon|bluetooth|triggerhappy|hciuart|dphys-swapfile|rpi-|raspi-)")


def info(msg):
    print(f"{GREEN}>> {msg}{NC}", flush=True)


def warn(msg):
    print(f"{YELLOW}Warning: {msg}{NC}", flush=True)


def die(msg):
    print(f"{RED}Error: {msg}{NC}", file=sys.stderr, flush=True)
    sys.exit(1)


def print_banner():
    print(f"{GREEN}======================================================{NC}")
    print(f"{GREEN}      Icinga2 NRPE Universal Bootstrap Kit            {NC}")
    print(f"{GREEN}======================================================{NC}")
    print("Supports: Ubuntu, Debian, Kali Linux, DietPi, Raspberry Pi OS\n")


def check_os():
    if os.geteuid() != 0:
        die("This script must be run as root (use install.sh or sudo).")
    if not os.path.exists("/etc/os-release"):
        die("/etc/os-release not found. Unsupported system.")
    os_info = {}
    with open("/etc/os-release") as f:
        for line in f:
            if "=" in line:
                key, val = line.rstrip().split("=", 1)
                os_info[key] = val.strip('"')
    print(f"Detected OS: {YELLOW}{os_info.get('PRETTY_NAME', 'Unknown')}{NC}")
    if not shutil.which("apt-get"):
        die("'apt-get' not found. This script requires a Debian-based system.")


def systemd_running():
    return os.path.isdir("/run/systemd/system") and shutil.which("systemctl") is not None


def prompt(question, interactive):
    if not interactive:
        return ""
    try:
        return input(question).strip()
    except EOFError:
        return ""


def prompt_yes_no(question, default, interactive):
    if not interactive:
        return default
    default_str = "Y/n" if default else "y/N"
    while True:
        try:
            choice = input(f"{question} [{default_str}]: ").strip().lower()
        except EOFError:
            return default
        if not choice:
            return default
        if choice in ("y", "yes"):
            return True
        if choice in ("n", "no"):
            return False
        print(f"{YELLOW}Please answer with 'y' or 'n'.{NC}")


def parse_masters(text):
    """Comma/space separated IPs, networks (CIDR) or host names -> list, or None if invalid."""
    items = [x for x in re.split(r"[,\s]+", text.strip()) if x]
    if not items:
        return None
    for item in items:
        try:
            ipaddress.ip_network(item, strict=False)
        except ValueError:
            if not re.fullmatch(r"(?=.{1,253}$)[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*", item):
                return None
    return items


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def apt_install(packages):
    env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
    run(["apt-get", "update", "-qq"], env=env, stdin=subprocess.DEVNULL)
    run(["apt-get", "install", "-y", "-q", "--no-install-recommends",
         "-o", "Dpkg::Options::=--force-confdef", "-o", "Dpkg::Options::=--force-confold", *packages],
        env=env, stdin=subprocess.DEVNULL)


def scan_listening_ports():
    """TCP listeners -> [{port, host, process}], one entry per port.

    The check connects to the address the service is bound to (127.0.0.1 for wildcard
    binds), so services listening on a single LAN address or only on IPv6 are found too.
    """
    ports = {}
    try:
        out = subprocess.run(["ss", "-Htlnp"], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        warn(f"Port scanning failed: {e}")
        return []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        local = parts[3]
        addr, _, port = local.rpartition(":")
        if not port.isdigit():
            continue
        addr = addr.strip("[]").split("%")[0]
        if addr.startswith("127.0.0.5") and port == "53":  # systemd-resolved stub, local only
            continue
        if addr in ("*", "0.0.0.0", ""):
            host = "127.0.0.1"
        elif addr == "::":
            host = "::1"
        else:
            host = addr
        proc = re.search(r'users:\(\("([^"]+)"', line)
        entry = {"port": int(port), "host": host, "process": proc.group(1) if proc else "unknown"}
        known = ports.get(entry["port"])
        # prefer 127.0.0.1 (a wildcard IPv4 bind) over other addresses for the same port
        if known is None or (entry["host"] == "127.0.0.1" and known["host"] != "127.0.0.1"):
            ports[entry["port"]] = entry
    return [ports[p] for p in sorted(ports)]


def scan_active_services():
    if not systemd_running():
        warn("systemd is not running - service auto-discovery skipped.")
        return []
    try:
        out = subprocess.run(["systemctl", "list-units", "--type=service", "--state=running",
                              "--no-legend", "--plain"], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        warn(f"Service scanning failed: {e}")
        return []
    services = []
    for line in out.splitlines():
        parts = line.split()
        if parts and parts[0].endswith(".service"):
            name = parts[0][: -len(".service")]
            if not IGNORED_SERVICES.match(name):
                services.append(name)
    return services


def safe_name(text):
    return re.sub(r"[^A-Za-z0-9_-]", "_", text)


def sshd_port():
    try:
        out = subprocess.run(["sshd", "-T"], capture_output=True, text=True).stdout
        m = re.search(r"^port (\d+)", out, re.MULTILINE)
        if m:
            return int(m.group(1))
    except OSError:
        pass
    return 22


def write_unit_plugin():
    os.makedirs(os.path.dirname(UNIT_PLUGIN), exist_ok=True)
    with open(UNIT_PLUGIN, "w") as f:
        f.write("""#!/bin/sh
# check_systemd_unit <unit> - OK if the systemd unit is active (Icinga2 NRPE Bootstrap Kit)
[ -n "$1" ] || { echo "UNKNOWN - no unit given"; exit 3; }
state=$(systemctl is-active "$1" 2>/dev/null)
case "$state" in
  active)       echo "OK - $1 is active"; exit 0 ;;
  activating|reloading) echo "WARNING - $1 is $state"; exit 1 ;;
  "")           echo "UNKNOWN - systemctl not available"; exit 3 ;;
  *)            echo "CRITICAL - $1 is $state"; exit 2 ;;
esac
""")
    os.chmod(UNIT_PLUGIN, 0o755)


def set_option(content, key, value):
    """Set key=value in nrpe.cfg (replaces an active or commented line, else appends)."""
    pattern = re.compile(rf"^[ \t]*#?[ \t]*{re.escape(key)}=.*$", re.MULTILINE)
    active = re.compile(rf"^[ \t]*{re.escape(key)}=.*$", re.MULTILINE)
    line = f"{key}={value}"
    if active.search(content):
        return active.sub(line, content, count=1)
    if pattern.search(content):
        return pattern.sub(line, content, count=1)
    return content.rstrip("\n") + f"\n{line}\n"


def restart_nrpe():
    if systemd_running():
        run(["systemctl", "enable", "nagios-nrpe-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        run(["systemctl", "restart", "nagios-nrpe-server"])
    elif shutil.which("service"):
        run(["service", "nagios-nrpe-server", "restart"])
    else:
        die("Neither systemd nor 'service' found - start NRPE manually.")


def open_firewall(masters):
    if not shutil.which("ufw"):
        return
    status = subprocess.run(["ufw", "status"], capture_output=True, text=True).stdout
    if "Status: active" not in status:
        return
    for m in masters:
        try:
            ipaddress.ip_network(m, strict=False)
        except ValueError:
            warn(f"UFW: '{m}' is a host name - open TCP 5666 for it manually.")
            continue
        info(f"UFW: allowing TCP 5666 from {m}")
        run(["ufw", "allow", "from", m, "to", "any", "port", "5666", "proto", "tcp"], stdout=subprocess.DEVNULL)


def parse_args():
    p = argparse.ArgumentParser(description="Install and configure NRPE for Icinga2.")
    p.add_argument("--master", help="Icinga2 master/satellite address(es), comma separated (IP, CIDR or host name)")
    p.add_argument("--yes", "-y", action="store_true", help="do not ask; use the given options or the defaults")
    for name, help_text in (("defaults", "standard checks: load, disk, swap, users, procs"),
                            ("ssh", "check the SSH server"),
                            ("ports", "auto-discover listening TCP ports"),
                            ("services", "auto-discover running systemd services"),
                            ("contrib", "also install nagios-plugins-contrib (large, pulls in a mail server)"),
                            ("arguments", "allow command arguments (dont_blame_nrpe=1, less secure)")):
        p.add_argument(f"--{name}", dest=name, action="store_true", default=None, help=help_text)
        p.add_argument(f"--no-{name}", dest=name, action="store_false")
    return p.parse_args()


def main():
    args = parse_args()
    interactive = not args.yes and sys.stdin.isatty()
    print_banner()
    check_os()

    print("\n" + "=" * 35 + "\n 1. Configuration & Master IP\n" + "=" * 35)
    masters = parse_masters(args.master) if args.master else None
    if args.master and masters is None:
        die(f"Invalid master address(es): {args.master}")
    while masters is None:
        answer = prompt("Enter Icinga2 Master / Monitoring Server IP (required, comma separated for several): ", interactive)
        if not answer and not interactive:
            die("Master IP cannot be empty (use --master). Aborting.")
        masters = parse_masters(answer)
        if masters is None:
            print(f"{YELLOW}Please enter IPv4/IPv6 addresses, networks (CIDR) or host names.{NC}")

    def ask(value, question, default):
        return value if value is not None else prompt_yes_no(question, default, interactive)

    print("\n" + "=" * 35 + "\n 2. Standard System Checks\n" + "=" * 35)
    setup_defaults = ask(args.defaults, "Install standard checks (Load, Disk, Swap, Users, Processes)?", True)
    setup_ssh = ask(args.ssh, "Monitor SSH service status?", True)

    print("\n" + "=" * 35 + "\n 3. Dynamic Auto-Discovery Options\n" + "=" * 35)
    auto_ports = ask(args.ports, "Scan and automatically add checks for open listening network ports?", True)
    auto_services = ask(args.services, "Scan and automatically add checks for active systemd services?", False)

    print("\n" + "=" * 35 + "\n 4. Extras\n" + "=" * 35)
    contrib = ask(args.contrib, "Install extra plugins (nagios-plugins-contrib, large, pulls in a mail server)?", False)
    allow_args = ask(args.arguments, "Allow command arguments from Icinga (dont_blame_nrpe=1, less secure)?", False)

    info("Updating package lists and installing NRPE + Plugins...")
    packages = ["nagios-nrpe-server", "monitoring-plugins-basic"]
    if contrib:
        packages.append("nagios-plugins-contrib")
    apt_install(packages)

    info(f"Configuring NRPE in {NRPE_CONF}...")
    with open(NRPE_CONF) as f:
        content = f.read()
    content = set_option(content, "allowed_hosts", ",".join(["127.0.0.1", "::1", *masters]))
    content = set_option(content, "dont_blame_nrpe", "1" if allow_args else "0")
    if not re.search(rf"^include_dir={re.escape(NRPE_DIR)}/?\s*$", content, re.MULTILINE):
        content = content.rstrip("\n") + f"\ninclude_dir={NRPE_DIR}/\n"
    with open(NRPE_CONF, "w") as f:
        f.write(content)

    # Commands go into their own file: a re-run replaces them instead of appending duplicates.
    # Files in nrpe.d are read after nrpe.cfg, so same-named defaults there are overridden.
    lines = ["# Generated by Icinga2 NRPE Universal Bootstrap Kit - rewritten on every run.", ""]
    commands = []

    def add(name, cmdline, description):
        lines.append(f"command[{name}]={cmdline}")
        commands.append((name, description))

    if setup_defaults:
        swap_opt = "-n ok " if "--no-swap" in subprocess.run([f"{PLUGINS}/check_swap", "--help"],
                                                             capture_output=True, text=True).stdout else ""
        add("check_load", f"{PLUGINS}/check_load -r -w 1.5,1.2,1.0 -c 3.0,2.5,2.0", "Load (per CPU)")
        add("check_users", f"{PLUGINS}/check_users -w 5 -c 10", "Users")
        add("check_swap", f"{PLUGINS}/check_swap {swap_opt}-w 20% -c 10%", "Swap")
        add("check_disk_root", f"{PLUGINS}/check_disk -w 20% -c 10% -p /", "Disk /")
        add("check_zombie_procs", f"{PLUGINS}/check_procs -w 5 -c 10 -s Z", "Zombie processes")
        add("check_total_procs", f"{PLUGINS}/check_procs -w 400 -c 600", "Total processes")

    if setup_ssh:
        # check_ssh talks to the port - unlike a process check it also works with socket
        # activation (Ubuntu >= 22.10: no sshd process until somebody connects).
        add("check_ssh", f"{PLUGINS}/check_ssh -H 127.0.0.1 -p {sshd_port()}", "SSH")

    if auto_ports:
        info("Scanning open ports...")
        lines.append("\n# --- Dynamic Port Checks ---")
        for p in scan_listening_ports():
            if p["port"] == 5666:
                continue  # NRPE itself
            print(f" -> Found port {p['port']} ({p['process']}) on {p['host']}")
            add(f"check_port_{p['port']}", f"{PLUGINS}/check_tcp -H {p['host']} -p {p['port']}",
                f"Port {p['port']} ({p['process']})")

    if auto_services:
        info("Scanning active systemd services...")
        write_unit_plugin()
        lines.append("\n# --- Dynamic Service Checks (systemctl is-active) ---")
        for svc in scan_active_services():
            print(f" -> Found service: {svc}")
            add(f"check_svc_{safe_name(svc)}", f"{UNIT_PLUGIN} {svc}.service", f"Service {svc}")

    os.makedirs(NRPE_DIR, exist_ok=True)
    with open(BOOTSTRAP_CFG, "w") as f:
        f.write("\n".join(lines) + "\n")
    info(f"{len(commands)} NRPE commands written to {BOOTSTRAP_CFG}")

    open_firewall(masters)
    info("Restarting NRPE service...")
    restart_nrpe()

    # Example for the Icinga2 side (check_command "nrpe" from the ITL).
    host = os.uname().nodename
    example = [f'// Icinga2 services for {host} (NRPE) - generated by the NRPE Bootstrap Kit',
               f'// Host object needs: address = "<ip of {host}>"', ""]
    for name, desc in commands:
        example += [f'object Service "{desc}" {{', f'  host_name = "{host}"', '  check_command = "nrpe"',
                    f'  vars.nrpe_command = "{name}"', "}", ""]
    with open(ICINGA_EXAMPLE, "w") as f:
        f.write("\n".join(example))

    print(f"\n{GREEN}=== Installation & Configuration Successfully Completed! ==={NC}")
    print(f"NRPE is running and authorized for Icinga Master: {YELLOW}{', '.join(masters)}{NC}")
    print(f"Commands: {', '.join(n for n, _ in commands) or '-'}")
    print(f"Icinga2 service example: {ICINGA_EXAMPLE}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        die(f"Command failed ({e.returncode}): {' '.join(map(str, e.cmd))}")
    except KeyboardInterrupt:
        die("Aborted.")
