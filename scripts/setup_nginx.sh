#!/usr/bin/env bash
set -euo pipefail

# Configure Nginx as the public reverse proxy for Calimara.
#
# Default mode is Cloudflare:
#   Browser -> Cloudflare HTTPS -> Nginx HTTPS -> http://127.0.0.1:8000
#
# Before running the default mode, create a Cloudflare Origin Certificate for:
#   calimara.ro
#   *.calimara.ro
#
# Save it on the VM as:
#   /etc/ssl/calimara/cloudflare-origin.pem
#   /etc/ssl/calimara/cloudflare-origin.key
#
# Optional environment overrides:
#   DOMAIN=calimara.ro
#   APP_HOST=127.0.0.1
#   APP_PORT=8000
#   SSL_MODE=cloudflare|certbot|http
#   CLOUDFLARE_ORIGIN_CERT=/etc/ssl/calimara/cloudflare-origin.pem
#   CLOUDFLARE_ORIGIN_KEY=/etc/ssl/calimara/cloudflare-origin.key
#   CERTBOT_EMAIL=you@example.com
#   CERTBOT_DOMAINS=calimara.ro,www.calimara.ro,gocandan.calimara.ro
#
# Notes:
#   - Cloudflare mode supports arbitrary first-level author subdomains when
#     Cloudflare DNS has a proxied wildcard A record: * -> your VM IP.
#   - Certbot mode can issue certificates only for explicit names listed in
#     CERTBOT_DOMAINS unless you separately configure a DNS challenge.

DOMAIN="${DOMAIN:-calimara.ro}"
APP_HOST="${APP_HOST:-127.0.0.1}"
APP_PORT="${APP_PORT:-8000}"
SITE_NAME="${SITE_NAME:-calimara}"
CLIENT_MAX_BODY_SIZE="${CLIENT_MAX_BODY_SIZE:-100M}"
ENABLE_HTTPS="${ENABLE_HTTPS:-1}"
SSL_MODE="${SSL_MODE:-}"
CLOUDFLARE_ORIGIN_CERT="${CLOUDFLARE_ORIGIN_CERT:-/etc/ssl/calimara/cloudflare-origin.pem}"
CLOUDFLARE_ORIGIN_KEY="${CLOUDFLARE_ORIGIN_KEY:-/etc/ssl/calimara/cloudflare-origin.key}"
INSTALL_CERTBOT="${INSTALL_CERTBOT:-1}"
RUN_CERTBOT_DRY_RUN="${RUN_CERTBOT_DRY_RUN:-0}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"
CERTBOT_DOMAINS="${CERTBOT_DOMAINS:-${DOMAIN},www.${DOMAIN},gocandan.${DOMAIN},mireasufletului.${DOMAIN},vanatordecuvinte.${DOMAIN},filedintramvai.${DOMAIN}}"

log() {
    printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"
}

die() {
    printf '\nError: %s\n' "$*" >&2
    exit 1
}

apt_install() {
    "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
}

if [[ -z "${SSL_MODE}" ]]; then
    if [[ "${ENABLE_HTTPS}" == "0" ]]; then
        SSL_MODE="http"
    else
        SSL_MODE="cloudflare"
    fi
fi

case "${SSL_MODE}" in
    cloudflare|certbot|http) ;;
    *) die "SSL_MODE must be one of: cloudflare, certbot, http" ;;
esac

if [[ "${EUID}" -eq 0 ]]; then
    SUDO=()
else
    command -v sudo >/dev/null 2>&1 || die "sudo is required when not running as root."
    SUDO=(sudo)
fi

command -v apt-get >/dev/null 2>&1 || die "This script expects an Ubuntu/Debian VM with apt-get."

if [[ -z "${DOMAIN}" || "${DOMAIN}" == *"://"* || "${DOMAIN}" == *"/"* ]]; then
    die "DOMAIN must be a bare domain, e.g. calimara.ro"
fi

if ! [[ "${APP_PORT}" =~ ^[0-9]+$ ]]; then
    die "APP_PORT must be numeric."
fi

if [[ "${SSL_MODE}" == "cloudflare" ]]; then
    if [[ ! -f "${CLOUDFLARE_ORIGIN_CERT}" || ! -f "${CLOUDFLARE_ORIGIN_KEY}" ]]; then
        cat >&2 <<EOF

Cloudflare origin certificate files are missing.

Create an Origin Certificate in Cloudflare:
  SSL/TLS -> Origin Server -> Create Certificate

Include these hostnames:
  ${DOMAIN}
  *.${DOMAIN}

Then save the certificate and private key on the VM:
  sudo mkdir -p /etc/ssl/calimara
  sudo nano ${CLOUDFLARE_ORIGIN_CERT}
  sudo nano ${CLOUDFLARE_ORIGIN_KEY}
  sudo chmod 644 ${CLOUDFLARE_ORIGIN_CERT}
  sudo chmod 600 ${CLOUDFLARE_ORIGIN_KEY}

Then rerun:
  ./scripts/setup_nginx.sh

EOF
        exit 1
    fi
fi

AVAILABLE="/etc/nginx/sites-available/${SITE_NAME}"
ENABLED="/etc/nginx/sites-enabled/${SITE_NAME}"

write_proxy_location() {
    cat <<NGINX
    client_max_body_size ${CLIENT_MAX_BODY_SIZE};

    location / {
        proxy_pass http://${APP_HOST}:${APP_PORT};
        proxy_http_version 1.1;

        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;

        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_read_timeout 300;
        proxy_send_timeout 300;
    }
NGINX
}

write_http_config() {
    cat <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN} www.${DOMAIN} *.${DOMAIN};

$(write_proxy_location)
}
NGINX
}

write_cloudflare_config() {
    cat <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN} www.${DOMAIN} *.${DOMAIN};

    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${DOMAIN} www.${DOMAIN} *.${DOMAIN};

    ssl_certificate ${CLOUDFLARE_ORIGIN_CERT};
    ssl_certificate_key ${CLOUDFLARE_ORIGIN_KEY};
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;

$(write_proxy_location)
}
NGINX
}

log "Installing Nginx"
"${SUDO[@]}" apt-get update
apt_install \
    nginx \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz-subset0 \
    libfontconfig1 \
    libcairo2 \
    fonts-dejavu-core
"${SUDO[@]}" systemctl enable --now nginx

if command -v ufw >/dev/null 2>&1; then
    log "Opening firewall ports with UFW"
    "${SUDO[@]}" ufw allow OpenSSH || true
    "${SUDO[@]}" ufw allow 'Nginx Full' || true
else
    log "UFW not installed; skipping local firewall changes"
fi

log "Writing Nginx reverse proxy config for ${DOMAIN} using SSL_MODE=${SSL_MODE}"
TMP_CONFIG="$(mktemp)"
if [[ "${SSL_MODE}" == "cloudflare" ]]; then
    write_cloudflare_config > "${TMP_CONFIG}"
else
    write_http_config > "${TMP_CONFIG}"
fi

"${SUDO[@]}" install -m 0644 "${TMP_CONFIG}" "${AVAILABLE}"
rm -f "${TMP_CONFIG}"
"${SUDO[@]}" ln -sfn "${AVAILABLE}" "${ENABLED}"
"${SUDO[@]}" rm -f /etc/nginx/sites-enabled/default
"${SUDO[@]}" nginx -t
"${SUDO[@]}" systemctl reload nginx

log "Nginx is proxying ${DOMAIN} to http://${APP_HOST}:${APP_PORT}"

if [[ "${SSL_MODE}" == "certbot" ]]; then
    if [[ "${INSTALL_CERTBOT}" == "1" ]]; then
        log "Installing Certbot"
        apt_install snapd
        "${SUDO[@]}" systemctl enable --now snapd.socket
        "${SUDO[@]}" snap install core || true
        "${SUDO[@]}" snap refresh core || true
        "${SUDO[@]}" snap install --classic certbot || true
        "${SUDO[@]}" ln -sfn /snap/bin/certbot /usr/local/bin/certbot
    fi

    command -v certbot >/dev/null 2>&1 || die "certbot is not installed. Set INSTALL_CERTBOT=1 or install certbot manually."

    log "Requesting HTTPS certificate with Certbot"
    IFS=',' read -r -a DOMAIN_LIST <<< "${CERTBOT_DOMAINS}"
    DOMAIN_ARGS=()
    for item in "${DOMAIN_LIST[@]}"; do
        item="${item#"${item%%[![:space:]]*}"}"
        item="${item%"${item##*[![:space:]]}"}"
        [[ -n "${item}" ]] && DOMAIN_ARGS+=("-d" "${item}")
    done

    [[ "${#DOMAIN_ARGS[@]}" -gt 0 ]] || die "CERTBOT_DOMAINS did not contain any domains."

    EMAIL_ARGS=()
    if [[ -n "${CERTBOT_EMAIL}" ]]; then
        EMAIL_ARGS=(--email "${CERTBOT_EMAIL}")
    else
        EMAIL_ARGS=(--register-unsafely-without-email)
    fi

    "${SUDO[@]}" certbot --nginx \
        --non-interactive \
        --agree-tos \
        --redirect \
        "${EMAIL_ARGS[@]}" \
        "${DOMAIN_ARGS[@]}"

    "${SUDO[@]}" nginx -t
    "${SUDO[@]}" systemctl reload nginx

    if [[ "${RUN_CERTBOT_DRY_RUN}" == "1" ]]; then
        log "Testing certificate auto-renewal"
        "${SUDO[@]}" certbot renew --dry-run
    fi
elif [[ "${SSL_MODE}" == "cloudflare" ]]; then
    log "Cloudflare mode enabled"
    log "Set Cloudflare SSL/TLS mode to Full (strict), with DNS records proxied."
else
    log "HTTP-only mode enabled"
fi

cat <<DONE

Done.

Start the app in a separate terminal/tmux session:
  cd /home/projects/calimara2
  source .venv/bin/activate
  python run.py

Then test:
  https://${DOMAIN}
  https://gocandan.${DOMAIN}

If Cloudflare mode is active, DNS lookups should return Cloudflare IPs:
  dig +short ${DOMAIN}
  dig +short gocandan.${DOMAIN}

DONE
