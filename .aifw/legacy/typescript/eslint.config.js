import eslint from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  {
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    ignores: ["dist/**", "coverage/**", "fixtures/**"],
  },
  {
    files: ["tests/**/*.ts"],
    rules: {
      "@typescript-eslint/no-floating-promises": "off",
      "@typescript-eslint/require-await": "off",
      "@typescript-eslint/restrict-template-expressions": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
      "@typescript-eslint/no-unsafe-assignment": "off",
    },
  },
  {
    // Runtime YAML/JSON boundaries intentionally re-check values after parsing.
    files: [
      "src/core/charter-file.ts",
      "src/core/conformance.ts",
      "src/core/gate-runner.ts",
      "src/core/policy-loader.ts",
      "src/core/routing-file.ts",
      "src/core/workspace.ts",
    ],
    rules: {
      "@typescript-eslint/no-unnecessary-condition": "off",
      "@typescript-eslint/no-unnecessary-type-parameters": "off",
    },
  },
);
