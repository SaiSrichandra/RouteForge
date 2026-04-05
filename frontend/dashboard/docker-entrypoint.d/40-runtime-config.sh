#!/bin/sh
set -eu

cat > /usr/share/nginx/html/runtime-config.js <<EOF
window.__ROUTEFORGE_CONFIG__ = {
  temporalUiUrl: "${TEMPORAL_UI_PUBLIC_URL}",
  grafanaUrl: "${GRAFANA_PUBLIC_URL}",
  prometheusUrl: "${PROMETHEUS_PUBLIC_URL}"
};
EOF
