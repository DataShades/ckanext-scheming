import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

// Bundles src/main.tsx (React + RJSF) into a single self-contained IIFE
// file dropped straight into ../assets/js, next to the other vendored
// scripts. CKAN's webassets.yml references it by that fixed name.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../assets/js",
    emptyOutDir: false,
    rollupOptions: {
      input: "src/main.tsx",
      output: {
        format: "iife",
        entryFileNames: "schema-editor-react.min.js",
        assetFileNames: "schema-editor-react.[ext]",
      },
    },
  },
});
