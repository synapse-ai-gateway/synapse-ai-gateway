/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_GATEWAY_URL?: string;
  readonly VITE_USE_MOCK?: string;
  readonly VITE_DEV_PORT?: string;
  readonly VITE_DEV_HOST?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
