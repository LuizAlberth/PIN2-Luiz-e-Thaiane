import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(() => {
  const proxyTarget = process.env.API_PROXY_TARGET || "http://localhost:8000";

  return {
    plugins: [react()],
    server: { proxy: { "/api": proxyTarget } },
    preview: { proxy: { "/api": proxyTarget } },
  };
});
