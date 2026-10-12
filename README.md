# tamir-agent: Telegram currency-conversion bot

A Telegram bot that converts prices into each user's preferred currency.
Send it an amount and a currency as text (`100 USD`, `€25`, `50 יורו`), or a **photo of a price tag**,
and it replies with the value in the target currency (default: ILS ₪).

- Each user picks a target currency with `/set USD` (or any other currency).
- Travelling? `/from EUR` sets a default source currency, so you can send just a number (`12.5`) for the whole trip.
- No need to know codes: `/from וייטנאם`, quick-pick buttons, and `/currencies` for the full list.
- Prices are read from images by a **local vision model through Ollama**, with no external cloud service.
- **Free-form writing**: a message the regular parser doesn't recognize ("כמה זה 30 יורו בדולרים?", "אני טס ליפן") goes to a local language model. It understands the request, and **asks a clarifying question** if something is missing or unclear. Settings changes from free text are saved only after a confirmation button.
- Exchange rates come from [open.er-api.com](https://open.er-api.com) (free, no key needed), with a one-hour cache.
- Access is limited to a list of authorized users. An unauthorized user gets their Telegram ID and is told to send it to the admin.

## Contents
- [Requirements](#requirements)
- [Setup on a new machine](#setup-on-a-new-machine)
- [Running](#running)
- [Managing users](#managing-users)
- [Using the bot](#using-the-bot)
- [Configuration](#configuration)
- [Moving to another machine and backup](#moving-to-another-machine-and-backup)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

Architecture details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (with diagrams: [docs/ARCHITECTURE.html](docs/ARCHITECTURE.html)) · Change history: [CHANGELOG.md](CHANGELOG.md)

---

## Requirements
| Component | Version | Notes |
|---|---|---|
| Python | 3.11+ (recommended 3.12) | Only for running locally without Docker |
| [Ollama](https://ollama.com/download) | Recent | Runs the vision model. Needs about 8GB of free RAM |
| Docker + Docker Compose | Optional | For running in a container |
| `make` | Optional | Built into Mac/Linux. On Windows, use the commands that appear next to each `make` command |

## Setup on a new machine

### 1. Clone the project
```bash
git clone <repo-url> tamir-agent
cd tamir-agent
```

### 2. Install Ollama and pull the model
Install Ollama from https://ollama.com/download, start it (the Ollama app or `ollama serve`), then:
```bash
ollama pull gemma3:12b          # or: make model
```
> The same model handles both images and text understanding (about 8GB). You can use different models. See [Configuration](#configuration).

### 3. Create a bot in Telegram
1. Open a chat with [@BotFather](https://t.me/BotFather) and send `/newbot`.
2. Pick a name and a username (must end in `bot`).
3. Copy the **token** you get (looks like `123456789:AA...`).

### 4. Configuration files
```bash
make setup
```
This command creates a Python virtual environment (`.venv`), installs the dependencies, creates `.env` from `.env.example`,
and creates an empty `data/allowed_users.json`.

<details><summary>Without make (Windows, for example)</summary>

```bash
python -m venv .venv
.venv\Scripts\activate            # Mac/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env            # Mac/Linux: cp .env.example .env
echo {} > data\allowed_users.json
```
</details>

Open `.env` and set `TELEGRAM_BOT_TOKEN=` to the token from BotFather.

### 5. Add yourself as an authorized user
Start the bot ([Running](#running)) and send it any message. You'll get a reply with your ID.
Add it to `data/allowed_users.json` (see [Managing users](#managing-users)).
Also put it in `ADMIN_IDS=` in `.env` so you can add other users from Telegram with `/add_user`.

## Running

**Locally:**
```bash
make run                 # or: .venv/bin/python -m bot
```

**In Docker** (Ollama keeps running on the host machine and uses its GPU):
```bash
make docker-up           # or: docker compose up -d --build
make docker-logs         # follow the logs
make docker-down         # stop
```
The container restarts automatically (`restart: unless-stopped`). The `data/` directory is mounted as a volume, so data survives rebuilding the image.

On startup the bot checks that Ollama is reachable and the model is pulled. If not, it prints a warning with what to do.
Text conversions keep working; only images will fail.

## Managing users
The `data/allowed_users.json` file is **edited by hand**:
```json
{
  "123456789": {"name": "תמיר"},
  "987654321": {"name": "דנה"}
}
```
- The key is the Telegram ID (the number the bot shows to an unauthorized user).
- `name` is used to address the user personally: in the greeting ("Hi Tamir!"), in setting confirmations ("✅ Tamir, the target currency was updated…"), and by the language model in its clarifying questions (first name only). Conversion replies stay short, without a name.
- **No restart needed.** The bot detects the change automatically on the next message.
- If the file has a JSON error, the bot keeps the previous list and logs an error.

**From Telegram (admins only).** Put your Telegram ID in `ADMIN_IDS=` in `.env` (several IDs: comma separated) and restart. Then:
- `/add_user 123456789 דנה`: allows the user and sends them a "you have access" message. If they never wrote to the bot, Telegram doesn't let the bot message them first, but access is active anyway.
- `/remove_user 123456789`: removes a user added this way.
- `/users`: lists all authorized users, by source.

Users added from Telegram are saved in a separate file, `data/bot_users.json`. The bot **never writes `allowed_users.json`**, so your manual edits are safe, and `/remove_user` can't remove someone listed there (edit the file instead). Admins can always use the bot, even if they're not in either file. For anyone else, the admin commands act like an unknown command, and they don't appear in their command menu.

The bot manages a separate file, `data/user_prefs.json`, where it stores each user's target currency and default source currency (`/from`). There's no need to edit it.

## Using the bot
| Action | Example |
|---|---|
| Convert text | `100 USD`, `$12.5`, `12,50€`, `1,299.90 EUR`, `50 יורו`, `30 ש"ח` |
| Thousands / millions | `10k`, `$1.5m`, `2M ₪`, `5 אלף דולר`, `3 מיליון יורו`, `1bn EUR` (`k`/`אלף`, `m`/`מיליון`, `b`/`bn`/`מיליארד`) |
| Convert from an image | Send a photo of a price tag. If the tag has no currency symbol, add it in the caption: `EUR` (or set `/from`) |
| Change target currency | `/set USD`, `/set יורו`, or `/set` alone for quick-pick buttons |
| Default source currency (trips) | `/from EUR`, then just send `12.5`. Cancel with `/from off` |
| Don't know the code? | Search by country or currency name: `/from וייטנאם`, `/set dong`. Several matches (`/set פסו`) → selection buttons |
| Currency list | `/currencies`: about 50 common currencies with a flag, Hebrew name and code |
| Show current settings | `/currency` |
| Free-form writing | `כמה זה 30 יורו בדולרים?`, `2 בירות ב-150 באט`, `אני בלונדון השבוע` (proposes a source-currency change with a confirmation button), `חזרתי הביתה` |
| Clarifying questions | If something is missing, the bot asks, e.g. `כמה עולה?` → "איזה סכום להמיר?". You can answer just `50` or `יורו` and it understands in context |
| Help | `/help`, or any unsupported message |

## Configuration
All settings are in `.env`. Every variable has a comment in [.env.example](.env.example).

| Variable | Default | Meaning |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | (required) | Token from BotFather |
| `ADMIN_NAME` | `אלעד` | Name shown to unauthorized users |
| `ADMIN_IDS` | (empty) | Telegram IDs of admins, comma separated. Enables `/add_user`, `/remove_user`, `/users`; admins always pass the allow-list |
| `DEFAULT_CURRENCY` | `ILS` | Target currency for new users |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama address (overridden automatically in Docker) |
| `OLLAMA_MODEL` | `gemma3:12b` | Vision model (reading prices from images) |
| `OLLAMA_TEXT_MODEL` | Same as `OLLAMA_MODEL` | Language model for understanding free text and clarifying questions |
| `OLLAMA_TIMEOUT` | `90` | Max seconds per request to Ollama |
| `DATA_DIR` | `data` | Data directory |
| `RATES_TTL` | `3600` | Rates cache duration, in seconds |
| `LOG_LEVEL` | `INFO` | `DEBUG` also shows the model's raw output |

**Changing models:** `ollama pull <model>`, update `OLLAMA_MODEL` / `OLLAMA_TEXT_MODEL` in `.env`, and restart the bot.

Tested models:
| Model | Images | Hebrew text | Response time (text, M-series Mac) |
|---|---|---|---|
| `gemma3:12b` | ✅ | ✅ 18/19 sample phrases understood correctly | ~6 seconds |
| `qwen2.5:7b-instruct` | (no image support) | ⚠️ confuses target and source currency | ~1.5 seconds |

## Moving to another machine and backup
Everything specific to a deployment lives in two places, which are **not in git**:
- `.env`: the token and settings
- `data/`: the authorized-users list and preferences

To move: clone the repo on the new machine, copy `.env` and `data/` into it, pull the model in Ollama, and run.
For backup, back up those two items.

## Development
```bash
make test      # tests (pytest)
make lint      # lint and formatting check (ruff)
make format    # automatic fixes
make help      # list of all commands
```
The code structure and how to extend it (new currency, changing the prompt, and so on) are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
Every change is recorded in [CHANGELOG.md](CHANGELOG.md).

## Troubleshooting
| Symptom | Fix |
|---|---|
| `Configuration error: TELEGRAM_BOT_TOKEN is missing` | No `.env`, or no token in it. See step 4 |
| `InvalidToken: ... rejected by the server` | Wrong token. Copy it again from BotFather (`/mybots` → API Token) |
| `Ollama is not reachable` on startup | Start Ollama (`ollama serve` or the app). In Docker, make sure Ollama is running on the **host** |
| `Model ... is not pulled` | `ollama pull <model>` |
| Bot replies "image recognition service is unavailable" | As above. Check with `curl localhost:11434/api/tags` |
| Free text gets the help message instead of an answer | The language model isn't available (Ollama not running or model not pulled). See the startup warning in the log |
| The model misunderstood a phrase | Run with `LOG_LEVEL=DEBUG` to see what it returned, and add a matching example to `SYSTEM_PROMPT` in `bot/nlu.py` |
| Image / free text takes a long time / timeout | First run loads the model into memory (can take ~30 seconds). Raise `OLLAMA_TIMEOUT` or use a smaller model |
| A user was added but still gets "unauthorized" | Check that the ID in the file is correct and that the JSON is valid (look at the log) |
| In Docker on Linux: `Permission denied` on `data/` | The container runs as uid 1000: `sudo chown -R 1000 data` |
| Docker on Linux: Ollama isn't reachable from the container | Ollama listens only on localhost by default. Set `OLLAMA_HOST=0.0.0.0` in the Ollama service |
