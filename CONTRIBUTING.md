# Git Workflow

- `main` — стабильная ветка (история релизов)
- `dev` — основная интеграционная ветка; все задачи мержим сюда перед релизом
- `deploy` — продакшн-ветка, на неё смотрит GitHub Actions деплоя
- Feature-ветки создаём от `dev`: `git checkout dev && git checkout -b feature/<task>`
- После завершения задачи: merge feature → `dev`, тесты, затем при готовности релиза merge `dev` → `deploy` (и при необходимости → `main`)
