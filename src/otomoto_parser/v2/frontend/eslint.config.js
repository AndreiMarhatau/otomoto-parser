import js from "@eslint/js";
import globals from "globals";

const maintainabilityRules = {
  "complexity": ["error", 30],
  "max-depth": ["error", 4],
  "max-lines": ["error", { max: 200, skipBlankLines: true, skipComments: true }],
  "max-params": ["error", 4],
  "no-unused-vars": "off",
};

export default [
  {
    ignores: ["dist/**", "node_modules/**"],
  },
  {
    files: ["src/**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    rules: {
      ...js.configs.recommended.rules,
      ...maintainabilityRules,
    },
  },
  {
    files: ["src/**/*.test.{js,jsx}", "src/test-helpers.jsx"],
    rules: {
      "complexity": "off",
      "max-depth": "off",
      "max-lines": "off",
      "max-params": "off",
    },
  },
];
