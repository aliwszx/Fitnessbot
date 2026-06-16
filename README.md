# Telegram AI Bot

FastAPI + python-telegram-bot v21 + Supabase + OpenAI ilə qurulmuş async Telegram botu.

## Texnologiyalar

| Texnologiya | Versiya |
|---|---|
| Python | 3.11.11 |
| FastAPI | 0.111.0 |
| python-telegram-bot | 21.3 |
| Supabase Python SDK | 2.4.6 |
| OpenAI SDK | 1.30.5 |
| Pydantic | 2.7.1 |

## Quruluş

```
telegram-bot/
├── app/
│   ├── api/
│   │   ├── health.py       # Health check endpoint
│   │   └── webhook.py      # Telegram webhook endpoint
│   ├── bot/
│   │   ├── application.py  # PTB Application builder
│   │   └── handlers.py     # Command & message handlers
│   ├── core/
│   │   ├── config.py       # Pydantic Settings
│   │   └── logging.py      # Logging setup
│   ├── db/
│   │   ├── client.py       # Supabase async client
│   │   ├── models.py       # Pydantic models
│   │   └── repository.py   # DB repository layer
│   ├── services/
│   │   └── openai_service.py  # OpenAI chat service
│   └── main.py             # FastAPI app + lifespan
├── supabase/
│   └── migrations/
│       └── 001_initial.sql # DB schema
├── main.py                 # Entry point
├── requirements.txt
├── runtime.txt             # python-3.11.11
├── render.yaml             # Render.com config
└── .env.example
```

## Başlamaq

### 1. Mühit dəyişənləri

```bash
cp .env.example .env
# .env faylını doldurun
```

### 2. Supabase Migration

Supabase Dashboard → SQL Editor-də `supabase/migrations/001_initial.sql` icra edin.

### 3. Lokal işlətmək

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Webhook üçün lokal testdə [ngrok](https://ngrok.com/) istifadə edin:

```bash
ngrok http 8000
# TELEGRAM_WEBHOOK_URL=https://xxxx.ngrok.io olaraq təyin edin
```

### 4. Render.com Deploy

1. GitHub-a push edin
2. Render Dashboard → New Web Service
3. Repo seçin, `render.yaml` avtomatik aşkarlanacaq
4. Environment Variables-i əlavə edin
5. Deploy edin — webhook avtomatik qurulacaq

## Bot Əmrləri

| Əmr | Funksiya |
|---|---|
| `/start` | Salamlama mesajı |
| `/help` | Kömək |
| `/clear` | Söhbət tarixçəsini sil |

## API Endpointlər

| Method | Path | Təsvir |
|---|---|---|
| GET | `/` | Root check |
| GET | `/health` | Health check |
| POST | `/webhook/{secret_token}` | Telegram webhook |
