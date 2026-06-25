/**
 * Jest configuration via `next/jest`, which wires up the same SWC transform
 * Next.js uses (so TypeScript and JSX "just work" in tests) and loads
 * environment variables and path aliases automatically.
 */
const nextJest = require("next/jest");

const createJestConfig = nextJest({ dir: "./" });

/** @type {import('jest').Config} */
const customJestConfig = {
  testEnvironment: "jest-environment-jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
  },
};

module.exports = createJestConfig(customJestConfig);
