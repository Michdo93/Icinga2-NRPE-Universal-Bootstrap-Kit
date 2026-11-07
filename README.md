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
* **Interactive Prompts (`y/n`):** Step-by-step assistant guiding you through configuration choices.
* **Universal Standard Checks:** Instantly provisions essential metrics (`check_load`, `check_disk`, `check_swap`, `check_users`).
* **Smart Auto-Discovery (Ports & Services):** 
  * Automatically scans active listening TCP ports (`ss`) to generate dynamic port checks.
  * Optionally inspects running `systemd` daemons to auto-configure process monitoring.
* **Secure Setup:** Automatically binds `allowed_hosts` to your Icinga2 Master IP and enables argument passing (`dont_blame_nagios=1`).

---

## Quick Start (One-Liner Execution)

You can download and execute the script directly on your target host using Python 3:

```bash
wget -qO- https://raw.githubusercontent.com/Michdo93/Icinga2-NRPE-Universal-Bootstrap-Kit/main/install.sh | sh
```

*(Alternatively, clone the repository and run `./install.sh` locally).*

---

## Interactive Wizard Flow

When running the script, you will be prompted with the following configuration steps:

1. **Icinga2 Master IP:** Enter the IP address of your monitoring server to whitelist it in NRPE.
2. **Standard Checks:** Choose whether to install default resource monitoring (`y/N`).
3. **SSH Monitoring:** Quick toggle to check if the `sshd` process is running (`y/N`).
4. **Port Auto-Discovery:** Scans local listening ports (e.g., HTTP, databases, custom app ports) and builds NRPE commands (`y/N`).
5. **Service Auto-Discovery:** Inspects active systemd services and provisions process checks (`y/N`).

---

## License

MIT License. Feel free to use, modify, and expand for your infrastructure!
