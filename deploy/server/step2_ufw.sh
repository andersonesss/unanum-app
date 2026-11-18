#!/bin/bash
# Шаг 2: ufw — 22/80/443 allow, остальное deny. Правило 22 — ДО enable.
set -uo pipefail

ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status verbose
