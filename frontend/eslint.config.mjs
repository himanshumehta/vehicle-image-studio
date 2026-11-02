import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    // Every image here is a blob: URL or an API-served file at its original
    // resolution; next/image's resizing would defeat a pixel editor.
    rules: { "@next/next/no-img-element": "off" },
  },
  {
    // Tests mock modules freely; `any` keeps the mocks readable.
    files: ["src/__tests__/**"],
    rules: { "@typescript-eslint/no-explicit-any": "off" },
  },
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
