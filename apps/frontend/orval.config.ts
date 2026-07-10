import { defineConfig } from "orval";

export default defineConfig({
  flaremailer: {
    input: process.env.ORVAL_INPUT ?? "http://127.0.0.1:8000/openapi.json",
    output: {
      target: "./src/generated/flaremailer.ts",
      schemas: "./src/generated/models",
      client: "react-query",
      mode: "tags-split",
      clean: true,
      override: {
        mutator: {
          path: "./src/lib/orval-fetcher.ts",
          name: "orvalFetcher",
        },
        query: {
          useQuery: true,
          useMutation: true,
          signal: true,
        },
      },
    },
  },
});
