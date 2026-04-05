/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_TEMPORAL_UI_URL?: string;
  readonly VITE_GRAFANA_URL?: string;
  readonly VITE_PROMETHEUS_URL?: string;
}

interface Window {
  __ROUTEFORGE_CONFIG__?: {
    temporalUiUrl?: string;
    grafanaUrl?: string;
    prometheusUrl?: string;
  };
}
