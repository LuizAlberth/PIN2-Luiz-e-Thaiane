#!/bin/sh
set -eu

BACKEND="${API_PROXY_TARGET:-http://api:8000}"

if [ "$BACKEND" != "http://api:8000" ]; then
  sed -i "s|__API_PROXY_TARGET__|$BACKEND|g" /etc/nginx/conf.d/default.conf
else
  sed -i "s|__API_PROXY_TARGET__|$BACKEND|g" /etc/nginx/conf.d/default.conf
fi

exec nginx -g 'daemon off;'
