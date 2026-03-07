import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],

  server: {
    port: 5173,
    host: true,
    origin: "http://demo.local:5173",

    proxy: {
      "/api": {
        // IP használata: demo.local DNS (mDNS) másodpercekig tarthat, 127.0.0.1 azonnali
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
        secure: false,
        configure: (proxy) => {
          proxy.on("proxyReq", (proxyReq) => {
            proxyReq.setHeader("Host", "demo.local:8001");
          });
        },
      },
    },
  },
});
