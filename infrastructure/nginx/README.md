# NEX — Production TLS Deployment Checklist
#
# TLS is NOT configured in the current nginx.conf.
# This file documents what must be completed before production traffic.
#
# ─────────────────────────────────────────────────────────────────────────────
# Option A: Let's Encrypt + Certbot (self-managed)
# ─────────────────────────────────────────────────────────────────────────────
#
# 1. Point your public domain's A/AAAA record to the server IP.
# 2. Install Certbot: https://certbot.eff.org
# 3. Obtain a certificate:
#      certbot certonly --standalone -d your.domain.com
# 4. Mount certificate files into the Nginx container:
#      /etc/letsencrypt/live/your.domain.com/fullchain.pem
#      /etc/letsencrypt/live/your.domain.com/privkey.pem
# 5. Update nginx.conf to listen on 443 ssl:
#      ssl_certificate     /etc/nginx/certs/fullchain.pem;
#      ssl_certificate_key /etc/nginx/certs/privkey.pem;
#      ssl_protocols       TLSv1.2 TLSv1.3;
#      ssl_ciphers         ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:...;
# 6. Add HTTP → HTTPS redirect on port 80.
# 7. Configure certificate auto-renewal (certbot renew cron or systemd timer).
# 8. Test: https://www.ssllabs.com/ssltest/
#
# ─────────────────────────────────────────────────────────────────────────────
# Option B: Managed TLS (recommended for production)
# ─────────────────────────────────────────────────────────────────────────────
#
# Place a TLS-terminating load balancer in front of this Nginx instance:
#   - AWS Application Load Balancer (ACM certificates)
#   - GCP HTTPS Load Balancer (Google-managed certificates)
#   - Cloudflare (edge TLS + DDoS protection)
#
# In this model, Nginx sees HTTP internally and does not need certificate files.
# Ensure X-Forwarded-Proto is passed correctly and Django's SECURE_PROXY_SSL_HEADER
# is configured (already done in production.py).
#
# ─────────────────────────────────────────────────────────────────────────────
# Security requirements before go-live
# ─────────────────────────────────────────────────────────────────────────────
#
# [ ] TLS certificate provisioned and validated
# [ ] HTTP → HTTPS redirect active
# [ ] HSTS header enabled (already in Django production.py)
# [ ] Certificate auto-renewal tested
# [ ] SSL Labs grade A or A+
# [ ] DJANGO_ALLOWED_HOSTS set to exact production domain(s) only
# [ ] DJANGO_SECRET_KEY is a 50+ character random value (not "change-me")
# [ ] PostgreSQL and Redis not reachable from public interfaces
# [ ] Container images rebuilt from production Dockerfiles (not dev)

