# Changelog

## 0.1.1 (unreleased)

- Refresh all Python runtime, development, and build dependencies and the complete uv lockfile, including FastAPI 0.161.0, SQLAlchemy 2.1.6, and cryptography 50.0.2.
- Update Next.js 16.4.2, React 19.3.1, React Query 5.104.5, Lucide 1.61.0, Orval 8.44.0, Vitest 5.0.5, pnpm 12.15.0, and the frontend lockfile.
- Use SQLAlchemy's native typing after removal of its obsolete mypy plugin. Derive the OpenAPI version from installed package metadata and regenerate the client.
- Keep ESLint 9.39.5 and TypeScript 6.0.3 while current Next.js lint plugins require ESLint 9 and TypeScript below 6.1. These are upstream compatibility constraints; strict peer validation stays enabled.
- Bound the development-only braces parser using the reviewed MIT-licensed local patch and regression tests for CVE-2026-93687, which still has no published upstream fix.
