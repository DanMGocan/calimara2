import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import viewportZoom from "./postcss-viewport-zoom.js";

export default defineConfig({
  plugins: [react()],
  css: {
    postcss: {
      plugins: [viewportZoom()]
    }
  },
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          minSize: 20 * 1024,
          maxSize: 260 * 1024,
          groups: [
            {
              name: "react",
              test: /node_modules[\\/](react|react-dom)[\\/]/,
              priority: 40
            },
            {
              name: "editor",
              test: /node_modules[\\/](@tiptap|prosemirror-[^\\/]+|orderedmap|rope-sequence|w3c-keyname)[\\/]/,
              priority: 35,
              maxSize: 900 * 1024
            },
            {
              name: "icons",
              test: /node_modules[\\/]react-icons[\\/]/,
              priority: 30,
              maxSize: 180 * 1024
            },
            {
              name: "vendor",
              test: /node_modules[\\/]/,
              priority: 10,
              maxSize: 220 * 1024
            }
          ]
        }
      }
    }
  },
  server: {
    port: Number(process.env.VITE_DEV_PORT || 5173),
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true
      },
      "/autentificare": {
        target: process.env.VITE_API_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true
      }
    }
  }
});
