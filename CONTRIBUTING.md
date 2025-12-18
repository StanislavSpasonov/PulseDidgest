# Git Workflow

- `main` — стабильная ветка, используется для релизов и деплоя
- `dev` — основная интеграционная ветка; все задачи мержим сюда перед релизом
- Feature-ветки создаём от `dev`: `git checkout dev && git checkout -b feature/<task>`
- После завершения задачи: merge feature → `dev`, тесты, затем при готовности релиза merge `dev` → `main`
