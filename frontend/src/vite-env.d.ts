/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Origin of the public API; empty means same-origin (proxied by Vite in development). */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
