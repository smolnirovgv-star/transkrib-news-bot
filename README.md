# transkrib-news-bot

Автоматический генератор и публикатор контента для @video_transkrib.

## Архитектура

- Каждый день в 10:30 МСК генерится draft через Claude Sonnet 4
- Картинка через Pollinations.ai (бесплатно)
- Draft отправляется админу в @TranskribAdmin_Bot
- Админ нажимает Publish/Regenerate/Reject
- На Publish — пост уходит в @video_transkrib

## Установка

1. Создать нового бота через @BotFather, получить токен
2. Добавить бота в @video_transkrib как админа с правом постить
3. SQL: выполнить sql/news_posts.sql в Supabase
4. Railway: создать новый сервис, подключить repo, задать env переменные
5. Deploy

## Команды

- `/start` — приветствие
- `/generate` — сгенерить draft вручную (для тестов)

## Стоимость

~$15-30/год (Claude API + Railway worker, Pollinations бесплатно).
