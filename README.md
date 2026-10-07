# Асинхронный процессинг платежей

Сервис принимает запрос на оплату, сохраняет его вместе с событием в одной транзакции и сразу отвечает `202 Accepted`. Отдельный процесс читает очередь, проводит платёж через эмулятор шлюза и отправляет результат на webhook.

## Стек

FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), PostgreSQL, RabbitMQ, FastStream, Alembic, Docker Compose.

## Слои

Запрос идёт сверху вниз. Роутер не пишет SQL и не публикует в брокер. Сервис держит сценарий и транзакцию. Репозиторий — единственное место с запросами. Политики не импортируют фреймворки.

| Каталог | Ответственность |
| --- | --- |
| `app/api` | HTTP, ключ API, схемы ответа |
| `app/services` | создание платежа, обработка, relay outbox |
| `app/repositories` | SQL |
| `app/policies` | идемпотентность, retry, маршруты очередей |
| `app/integrations` | эмулятор шлюза и HTTP webhook |
| `app/messaging` | брокер, топология, publisher, consumer |
| `app/models` | таблицы |

## Поток

1. `POST /api/v1/payments` в одной транзакции пишет платёж со статусом `pending` и строку в `outbox`. В RabbitMQ из запроса ничего не уходит.
2. Relay в процессе API забирает пачку строк (`pending` → `publishing`), коммитит её и только потом публикует событие. Блокировка строки не держится на время сети.
3. Consumer читает `payments.new` по одному сообщению. До шлюза и webhook он увеличивает `processing_attempts` и коммитит это число. Если процесс убьют во время ожидания шлюза или отправки webhook, повторная доставка увидит уже записанную попытку. Четвёртая такая доставка шлюз не вызывает и сразу кладёт сообщение в `payments.dlq`.
4. Если платёж ещё `pending`, шлюз ждёт 2–5 секунд и возвращает `succeeded` (90%) или `failed` (10%). Это бизнес-результат: статус сохраняется, сообщение не уходит в DLQ.
5. Webhook отправляется на `webhook_url`. Первая попытка сразу, дальше паузы 1, 2 и 4 секунды.
6. Технический сбой (нет строки, ошибка БД, webhook так и не доставлен) публикует сообщение в delay-очередь. После третьей неудачи оно попадает в `payments.dlq`.

Повторная доставка не переигрывает шлюз: статус меняется условным `UPDATE ... WHERE status = 'pending'`. После успешного webhook пишется `webhook_sent_at`, и повторная доставка больше не уведомляет клиента.

## Очереди

Обменники и очереди объявляют и API, и consumer.

- `payments.events` (topic) → очередь `payments.new`, routing key `payments.new`
- `payments.retry` → `payments.retry.1` (TTL 2 с) и `payments.retry.2` (TTL 4 с). После TTL сообщение возвращается в `payments.new`. Счётчик попыток — заголовок `x-retry-count`
- `payments.dlx` → `payments.dlq`

`x-death` не используется: на цепочке delay-очередей он считается непредсказуемо. Публикация ждёт подтверждения брокера. Исходное сообщение подтверждается только после этого. `nack` с возвратом в очередь применяется, только если не удалось запланировать retry.

Пользователь `guest` из другого контейнера к RabbitMQ не подключается, поэтому compose поднимает пользователя `payments`.

## Запуск

```bash
docker compose up --build
```

- API: http://localhost:8000
- OpenAPI: http://localhost:8000/docs
- RabbitMQ Management: http://localhost:15672 (`payments` / `payments`)
- PostgreSQL: `localhost:5432`, база `payments`, пользователь и пароль `postgres`
- Ключ API: `dev-api-key`, заголовок `X-API-Key`

Миграции выполняет контейнер API до старта uvicorn. Consumer ждёт, пока API станет healthy.

Остановить:

```bash
docker compose down
```

## Примеры

Создание платежа:

```bash
curl -s -D - \
  -X POST http://localhost:8000/api/v1/payments \
  -H "X-API-Key: dev-api-key" \
  -H "Idempotency-Key: order-1001" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": "1500.00",
    "currency": "RUB",
    "description": "Order 1001",
    "metadata": {"order_id": "1001"},
    "webhook_url": "https://webhook.site/your-id"
  }'
```

Ответ `202 Accepted`:

```json
{
  "payment_id": "6f1c0c3e-1b2a-4d5e-9f10-0a1b2c3d4e5f",
  "status": "pending",
  "created_at": "2026-10-07T12:00:00Z"
}
```

Повтор с тем же ключом и тем же телом возвращает тот же платёж. Другое тело с тем же ключом — `409`. Без ключа или с неверным `X-API-Key` — `401`.

Чтение:

```bash
curl -s http://localhost:8000/api/v1/payments/{payment_id} \
  -H "X-API-Key: dev-api-key"
```

Валюта: `RUB`, `USD`, `EUR`. Сумма больше нуля, не больше 18 цифр и 2 знаков после запятой. `webhook_url` — `http` или `https`.

Webhook, который получит клиент:

```json
{
  "payment_id": "6f1c0c3e-1b2a-4d5e-9f10-0a1b2c3d4e5f",
  "status": "succeeded",
  "amount": "1500.00",
  "currency": "RUB",
  "processed_at": "2026-10-07T12:00:04Z"
}
```

Чтобы увидеть `payments.dlq`, укажите URL, который не отвечает. Сообщение окажется там после трёх технических неудач. Consumer сохранит его в таблицу `dead_letters`.

Просмотр сохранённых сообщений:

```bash
curl -s http://localhost:8000/api/v1/dead-letters \
  -H "X-API-Key: dev-api-key"
```

События outbox, которые не удалось опубликовать после 10 попыток, остаются в базе со статусом `failed`. Их можно вернуть в обработку:

```bash
curl -s http://localhost:8000/api/v1/outbox/failed \
  -H "X-API-Key: dev-api-key"

curl -s -X POST http://localhost:8000/api/v1/outbox/{event_id}/retry \
  -H "X-API-Key: dev-api-key"
```

Повтор отвечает `202` и ставит строке статус `pending`. Relay подхватит её заново. Если событие не `failed`, ответ `409`. Если записи нет — `404`.

## Доработки сверх задания

Задание описывает приём платежа, outbox, один consumer, три попытки и DLQ. Ниже то, что добавлено поверх этого.

- `GET /health` без API-ключа. По нему Docker понимает, что миграции прошли и API принимает запросы. Платёжные методы по-прежнему требуют `X-API-Key`.
- Тот же `Idempotency-Key` с другим телом возвращает `409`. Сравнение идёт по каноническому hash: сумма нормализуется до копеек, ключи JSON сортируются.
- Исход шлюза записывается условным `UPDATE ... WHERE status = 'pending'`. Повторная доставка не перебрасывает 90/10. Десять процентов отказа — это статус `failed` и webhook, а не сообщение в DLQ.
- После успешного webhook пишется `webhook_sent_at`. Следующая доставка того же сообщения только подтверждается и клиенту повторно не уходит.
- Relay переводит строку outbox в `publishing` и коммитит до вызова RabbitMQ, поэтому блокировка не держится на время сети. Строка в `publishing` дольше 30 секунд снова становится `pending`.
- Публикация ждёт подтверждения брокера. Consumer читает по одному сообщению.
- Webhook пробует доставку сразу и ещё три раза с паузами 1, 2 и 4 секунды. Если все четыре вызова неуспешны, сообщение обрабатывается брокером заново: вторая попытка через 2 секунды, третья через 4 секунды, затем `payments.dlq`.
- Номер попытки хранится в колонке `payments.processing_attempts`, а не только в заголовке RabbitMQ. Заголовок пропадает, если процесс убить до подтверждения сообщения. Колонка записывается до долгой работы, поэтому три обрыва обработки тоже заканчиваются в DLQ.
- Сообщение из `payments.dlq` сохраняется в `dead_letters`. Повторная доставка той же пары платёж и номер попытки не создаёт вторую строку. Список доступен через `GET /api/v1/dead-letters`.
- Для outbox, который так и не опубликовался, есть `GET /api/v1/outbox/failed` и `POST /api/v1/outbox/{event_id}/retry`. Задание такую команду не описывает: без неё окончательно сбойная строка оставалась бы только в базе.

## Проверки без Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Тесты покрывают идемпотентность, маршрутизацию retry/DLQ, эмулятор шлюза, паузы webhook и сценарии обработки без брокера и базы.

## Переменные

См. [.env.example](.env.example). В compose они уже заданы. Для локального запуска без Docker поднимите PostgreSQL и RabbitMQ и положите свои значения в `.env`.
