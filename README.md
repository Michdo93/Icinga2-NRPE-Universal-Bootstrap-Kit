# Icinga2 NRPE Universal Bootstrap Kit

An interactive, automated bootstrap script designed for Debian-based Linux distributions to seamlessly install, configure, and provision **Nagios Remote Plugin Executor (NRPE)** for **Icinga2** monitoring integration.

## Supported Operating Systems
* **Ubuntu** (Server & Desktop)
* **Debian**
* **Kali Linux** & **Kali Purple**
* **DietPi OS**
* **Raspberry Pi OS**

---

## Features
* **Interactive Prompts (`y/n`):** Step-by-step assistant guiding you through configuration choices – or no questions at all with command-line options.
* **Universal Standard Checks:** `check_load` (per CPU), `check_disk_root`, `check_swap` (OK on hosts without swap), `check_users`, `check_zombie_procs`, `check_total_procs`.
* **SSH Check:** `check_ssh` against the configured sshd port – also works with socket activation (Ubuntu ≥ 22.10, no `sshd` process until someone connects).
* **Smart Auto-Discovery (Ports & Services):**
  * Scans listening TCP ports (`ss`) and checks each one on the address the service is bound to.
  * Optionally adds a check per running systemd service (`systemctl is-active`, via a small plugin in `/usr/local/lib/nagios/plugins/`).
* **Secure Setup:** `allowed_hosts` = localhost + your Icinga2 master(s). Command arguments (`dont_blame_nrpe=1`) are off unless you enable them. With an active UFW, TCP 5666 is opened for the master(s) only.
* **Lean:** installs `nagios-nrpe-server` and `monitoring-plugins-basic`. `nagios-plugins-contrib` is optional (it pulls in a mail server and many libraries).
* **Re-runnable:** the generated commands live in `/etc/nagios/nrpe.d/icinga2-bootstrap.cfg`, which is rewritten on every run (no duplicates; same-named defaults in `nrpe.cfg` are overridden).
* **Icinga2 side:** `/etc/nagios/icinga2-services.conf.example` contains matching `object Service` definitions (`check_command = "nrpe"`).
* **Rollout over SSH:** [ssh-icinga2-nrpe-manager](https://github.com/Michdo93/ssh-icinga2-nrpe-manager) runs the kit on all hosts of an IPv4 range.

---

## Quick Start (One-Liner Execution)

As root or as a user with `sudo` (works with `| sh` and `| bash`):

```bash
wget -qO- https://raw.githubusercontent.com/Michdo93/Icinga2-NRPE-Universal-Bootstrap-Kit/main/install.sh | sh
```

Without questions (options are passed to `nrpe-bootstrap.py`):

```bash
wget -qO- https://raw.githubusercontent.com/Michdo93/Icinga2-NRPE-Universal-Bootstrap-Kit/main/install.sh \
  | sh -s -- --master 192.168.1.10 --defaults --ssh --ports --no-services --yes
```

*(Alternatively, clone the repository and run `sudo python3 nrpe-bootstrap.py`).*

---

## Interactive Wizard Flow

1. **Icinga2 Master IP(s):** one or more addresses, comma separated (IPv4/IPv6, CIDR or host names), whitelisted in NRPE.
2. **Standard Checks:** default resource monitoring (`Y/n`).
3. **SSH Monitoring:** `check_ssh` on the local sshd port (`Y/n`).
4. **Port Auto-Discovery:** listening TCP ports (e.g. HTTP, databases, custom app ports) (`Y/n`).
5. **Service Auto-Discovery:** running systemd services (`y/N`).
6. **Extras:** `nagios-plugins-contrib` (`y/N`) and command arguments `dont_blame_nrpe=1` (`y/N`).

## Command-Line Options

| Option | Meaning |
|---|---|
| `--master ADDR[,ADDR…]` | Icinga2 master/satellite address(es) |
| `--defaults` / `--no-defaults` | standard checks |
| `--ssh` / `--no-ssh` | SSH check |
| `--ports` / `--no-ports` | port auto-discovery |
| `--services` / `--no-services` | service auto-discovery |
| `--contrib` / `--no-contrib` | install `nagios-plugins-contrib` |
| `--arguments` / `--no-arguments` | `dont_blame_nrpe=1` |
| `--yes` | no questions; options not given use the defaults above |

Without a terminal the script runs as with `--yes`; `--master` is then required.
`NRPE_BOOTSTRAP_URL` makes `install.sh` download `nrpe-bootstrap.py` from another location (fork, mirror).

## Test

From the Icinga2 master (package `nagios-nrpe-plugin` / `monitoring-plugins-nrpe`):

```bash
/usr/lib/nagios/plugins/check_nrpe -H <host> -c check_load
```

---

## License

MIT License. Feel free to use, modify, and expand for your infrastructure!
