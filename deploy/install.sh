#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo bash deploy/install.sh" >&2
  exit 1
fi
project_root="$(cd "$(dirname "$0")/.." && pwd)"
if [ "$project_root" != "/opt/viju-ticketbooth" ]; then
  echo "Clone this repository to /opt/viju-ticketbooth first." >&2
  exit 1
fi
apt-get update
apt-get install -y python3 python3-venv python3-pip network-manager bluez obexftp nginx sudo fonts-dejavu-core
if ! nmcli -g GENERAL.STATE device show wlan0 >/dev/null 2>&1 || nmcli -g GENERAL.STATE device show wlan0 | grep -qi unmanaged; then
  echo "NetworkManager must manage wlan0 before enabling the recovery AP." >&2
  exit 1
fi
if ! command -v npm >/dev/null || ! command -v node >/dev/null; then
  echo "Install Node.js 18+ and npm before running this installer." >&2
  exit 1
fi
node_major="$(node --version | cut -d. -f1 | tr -d v)"
if [ "$node_major" -lt 18 ]; then
  echo "Node.js 18+ is required." >&2
  exit 1
fi
if ! id viju >/dev/null 2>&1; then
  useradd --system --user-group --home-dir /opt/viju-ticketbooth --shell /usr/sbin/nologin viju
fi
if getent group bluetooth >/dev/null; then usermod -aG bluetooth viju; fi
install -d -m 0750 -o viju -g viju /var/lib/viju-ticketbooth
install -d -m 0700 /etc/viju-ticketbooth
if [ ! -f /etc/viju-ticketbooth/access.env ]; then
  ap_password="$(python3 -c 'import secrets,string; print("".join(secrets.choice(string.ascii_letters+string.digits) for _ in range(20)))')"
  printf 'SETUP_AP_PASSWORD=%s\n' "$ap_password" > /etc/viju-ticketbooth/access.env
  chmod 0600 /etc/viju-ticketbooth/access.env
fi
if [ ! -f /etc/viju-ticketbooth/app.env ]; then
  printf 'VIJU_DATA_DIR=/var/lib/viju-ticketbooth\nPRINTER_BACKEND=mock\nVIJU_NETWORK_HELPER=/usr/local/libexec/viju-network\n' > /etc/viju-ticketbooth/app.env
  chmod 0600 /etc/viju-ticketbooth/app.env
fi
sed -i '/^VIJU_ADMIN_TOKEN=/d' /etc/viju-ticketbooth/access.env /etc/viju-ticketbooth/app.env
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
(cd frontend && npm ci && npm run build)
chown -R viju:viju backend/.venv frontend/dist
install -d -m 0755 /usr/local/libexec
install -m 0755 deploy/network/viju-network /usr/local/libexec/viju-network
install -m 0755 deploy/bluetooth/viju-bluetooth /usr/local/libexec/viju-bluetooth
printf 'viju ALL=(root) NOPASSWD: /usr/local/libexec/viju-network status, /usr/local/libexec/viju-network connect\n' > /etc/sudoers.d/viju-network
printf 'viju ALL=(root) NOPASSWD: /usr/local/libexec/viju-bluetooth pair *, /usr/local/libexec/viju-bluetooth trust *, /usr/local/libexec/viju-bluetooth forget *\n' > /etc/sudoers.d/viju-bluetooth
chmod 0440 /etc/sudoers.d/viju-network
chmod 0440 /etc/sudoers.d/viju-bluetooth
visudo -cf /etc/sudoers.d/viju-network
visudo -cf /etc/sudoers.d/viju-bluetooth
install -m 0644 deploy/systemd/*.service /etc/systemd/system/
install -m 0644 deploy/nginx/viju-ticketbooth.conf /etc/nginx/sites-available/viju-ticketbooth
ln -sfn /etc/nginx/sites-available/viju-ticketbooth /etc/nginx/sites-enabled/viju-ticketbooth
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl daemon-reload
systemctl enable --now NetworkManager bluetooth nginx viju-ticketbooth-api.service viju-ticketbooth-worker.service viju-ticketbooth-network.service
systemctl reload nginx
echo "Installation complete. Setup WLAN credentials are in /etc/viju-ticketbooth/access.env (root-only)."
echo "Configure /etc/viju-ticketbooth/app.env for TMDB and the actual printer, then restart API and worker."
