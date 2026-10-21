import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The live mode reads the existing backend through a same-origin proxy (/api -> 127.0.0.1:8765),
// so the page never makes a cross-origin or non-local request.
const backend = { "/api": { target: "http://127.0.0.1:8765", rewrite: (p: string) => p.replace(/^\/api/, "") } };

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true, host: "127.0.0.1", proxy: backend },
  preview: { port: 4173, strictPort: true, host: "127.0.0.1", proxy: backend },
  test: { include: ["src/**/*.test.ts"], environment: "node" },
});
