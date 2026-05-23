# ♟️ ГВИНТ — Telegram Bot (PvP)

Карточная игра «Гвинт» из «Ведьмака 3» для Telegram.  
Два реальных игрока, 2 фракции, 3 раунда, полная игровая механика.

---

## 🗂 Структура проекта

```
gwent-bot/
├── index.py          ← Flask-сервер + весь игровой движок
├── data/
│   └── data.json     ← Карты, фракции, лидеры (без перeдеплоя)
├── requirements.txt
├── vercel.json
├── set_webhook.py    ← Запустить 1 раз после деплоя
├── .env.example
└── .gitignore
```

---

## ⚙️ Переменные окружения

| Переменная       | Где взять                                      |
|-----------------|------------------------------------------------|
| `BOT_TOKEN`      | [@BotFather](https://t.me/BotFather) → `/newbot` |
| `WEBHOOK_SECRET` | Любая строка (например: `mygwentsecret2024`)   |
| `UPSTASH_URL`    | [console.upstash.com](https://console.upstash.com) → Redis → REST API → Endpoint |
| `UPSTASH_TOKEN`  | Там же → REST Token                            |

---

## 🚀 Пошаговый деплой

### Шаг 1 — Создай бота

Открой [@BotFather](https://t.me/BotFather) в Telegram:
```
/newbot
```
Скопируй токен.

---

### Шаг 2 — Redis (Upstash, бесплатно)

1. Зайди на [console.upstash.com](https://console.upstash.com)
2. Create Database → тип **Redis** → регион ближайший
3. Вкладка **REST API**:
   - Скопируй `UPSTASH_URL` (строка `UPSTASH_REDIS_REST_URL`)
   - Скопируй `UPSTASH_TOKEN` (строка `UPSTASH_REDIS_REST_TOKEN`)

---

### Шаг 3 — Установка зависимостей

```bash
pip install -r requirements.txt
```

---

### Шаг 4 — GitHub

```bash
git init
git add .
git commit -m "init gwent bot"
```

Создай репозиторий на [github.com](https://github.com/new):
- Имя: только `_` и `-` (без пробелов и спецсимволов)
- Visibility: Public или Private

```bash
git branch -M main
git remote add origin https://github.com/ВАШ_НИК/ИМЯ_РЕПО.git
git push -u origin main
```

> При SSL-ошибке: `git config --global http.sslVerify false`

---

### Шаг 5 — Vercel

1. Зайди на [vercel.com](https://vercel.com) → **Add New Project**
2. Импортируй репозиторий с GitHub
3. **Framework Preset → Other** (не Python, не Node!)
4. Нажми **Deploy**

После деплоя добавь переменные:  
`Settings → Environment Variables`

| Name             | Value              |
|-----------------|--------------------|
| BOT_TOKEN        | твой токен         |
| WEBHOOK_SECRET   | любая строка       |
| UPSTASH_URL      | из Upstash         |
| UPSTASH_TOKEN    | из Upstash         |

Нажми **Redeploy** (обязательно после добавления переменных!).

Проверь: открой `https://твой-проект.vercel.app/` — должен вернуть:
```json
{"status": "ok"}
```

---

### Шаг 6 — Webhook (PowerShell, каждую строку ОТДЕЛЬНО)

```powershell
$env:BOT_TOKEN="123456:ABC-токен"
$env:BASE_URL="https://твой-проект.vercel.app"
$env:WEBHOOK_SECRET="mygwentsecret2024"
python set_webhook.py
```

Проверка:
```
https://api.telegram.org/bot{ТОКЕН}/getWebhookInfo
```
Поле `"url"` должно содержать твой адрес.

---

## 🎮 Как играть

| Команда  | Действие                    |
|---------|-----------------------------|
| `/start` | Главное меню                |
| `/game`  | Посмотреть текущее поле     |
| `/rules` | Правила игры                |
| `/cancel`| Выйти из очереди поиска     |

**Порядок игры:**
1. `/start` → ⚔️ Найти игру
2. Дождись соперника (или пригласи по ссылке)
3. Оба выбирают фракцию и лидера
4. Муллиган (замена до 2 карт)
5. Поочерёдные ходы — нажми карту → выбери ряд
6. Пасуй кнопкой ✋ Пас
7. Побеждает тот, кто выиграет 2 из 3 раундов

---

## 📐 Архитектура

```
Telegram ←→ Vercel (Flask webhook)
                ↓
         Game Engine (Python)
                ↓
         Upstash Redis (сессии, очередь)
                ↓
         data/data.json (карты, фракции)
```

- **Stateless** сервер: каждый запрос — новый event loop (`asyncio.run()`)
- **Redis TTL**: игровые сессии живут 2 часа, очередь — 5 минут
- **Без БД**: все состояния в Redis, статика в JSON

---

## 🃏 Реализованные механики

- ✅ 2 фракции: Северные Королевства, Нильфгаард
- ✅ Лидеры (3 на фракцию)
- ✅ Типы карт: обычные, герои, шпионы, погода, рог, чучело
- ✅ Способности: Медик, Прилив сил, Прочная связь, Казнь
- ✅ Погода на 3 ряда + Ясная погода
- ✅ Командирский рог
- ✅ 3 раунда, 2 победы
- ✅ Муллиган (до 2 замен)
- ✅ Пас
- ✅ Особенность Нильфгаарда (победа при ничье)
- ✅ Matchmaking + приглашение по ссылке

---

## ✅ Чеклист деплоя

- [ ] `pip install -r requirements.txt` прошёл без ошибок
- [ ] Репозиторий виден на github.com
- [ ] `https://твой-проект.vercel.app/` возвращает `{"status":"ok"}`
- [ ] Переменные добавлены в Vercel + Redeploy сделан
- [ ] `/start` в боте работает и бот отвечает
