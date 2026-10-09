# Architecture

## Message flow
```
Telegram update
      │
      ▼
 gate (auth.AllowList) ── not in list ──► "send your ID <id> to Elad" (stop)
      │ authorized
      ▼
 ┌────────────┬────────────────┬────────────────────┬──────────────┐
 │ /start     │ /set <cur>     │ text               │ photo/image  │
 │ /help      │ /from <cur>    │                    │              │
 │            │ /currency      │                    │              │
 ▼            ▼                ▼                    ▼              │
 help     storage.UserPrefs   parser.parse()   vision.extract_price()
                               │                    │ (+ currency from caption)
                               │  (no currency? → /from default)
                               └────────┬───────────┘
                                       ▼
                         rates.RatesClient.convert()
                                       ▼
                         messages.conversion() → reply
```
Any other input (sticker, voice, unknown command, text that isn't a price) → help message.

**Choosing a currency in `/set` and `/from`** (`_choose_currency` in `handlers.py`):
1. No argument → quick-pick buttons (`catalog.POPULAR`); in `/from`, also a cancel button.
2. Code / symbol / alias (`currencies.normalize`) that the rates provider supports → saved directly.
3. Otherwise `catalog.search` by name or country: one match → saved; several → selection buttons; none → error plus a pointer to `/currencies`.

A button press arrives as a callback query with data `set:<code>` / `from:<code>` / `from:off`, handled by `currency_button`, which validates the code again before saving.

**Determining the source currency** (first one found):
- Text: currency written in the message → user's `source` (`/from`) → otherwise ask for a currency.
- Image: currency in the caption → currency the model saw in the image → user's `source` → otherwise ask for a currency.

## Modules (`bot/`)
| File | Responsibility |
|---|---|
| `__main__.py` | Entry point: loads config, startup checks (data dir, Ollama), builds the services, starts polling |
| `config.py` | Reads `.env` into a `Config` object. **The only place** that reads environment variables or holds fixed constants |
| `handlers.py` | Telegram handlers. Thin layer: calls the other modules and returns texts from `messages.py` |
| `auth.py` | `AllowList`: reads `allowed_users.json`, reloads on mtime change |
| `storage.py` | `UserPrefs`: each user's target currency in `user_prefs.json`, atomic writes |
| `parser.py` | Parses text into `ParsedPrice(amount, currency)` |
| `currencies.py` | Map of symbols/names → ISO code (for parsing free text), and display formatting |
| `catalog.py` | Catalog of ~50 common currencies: Hebrew/English name, flag, region, countries. Used for `/currencies`, search, and buttons |
| `rates.py` | `RatesClient`: fetches USD-based rates, cache, conversion via cross rate |
| `vision.py` | `OllamaVision`: sends an image to Ollama with a JSON schema and returns `ParsedPrice` |
| `messages.py` | All user-facing texts (Hebrew, HTML) |

Services are created once in `__main__.py` and stored in `application.bot_data["services"]` (a `Services` object).

## Data files (`data/`, not in git)
| File | Who writes it | Format |
|---|---|---|
| `allowed_users.json` | Admin, by hand | `{"<telegram_id>": {"name": "<name>"}}` |
| `user_prefs.json` | The bot | `{"<telegram_id>": {"name": "<Telegram name>", "currency": "USD", "source": "EUR"}}` |

`currency` = target currency (default `DEFAULT_CURRENCY`). `source` = default source currency from `/from`, optional; `/from off` removes the field.

The split is intentional: the bot never writes to the file the admin edits, so there's no risk of overwriting manual edits.

## Design decisions
- **Polling, not a webhook**: no public address or SSL certificate needed. Works behind a home NAT.
- **Local Ollama**: images never leave the machine, and there's no per-use cost. The JSON schema in `format` forces structured output.
- **Rates via USD**: a single API call gives the rate between any pair of currencies (`rate = rates[target] / rates[source]`).
- **Stale cache when the API fails**: better to return an old rate, with a warning, than to fail.
- **A broken allowed_users.json doesn't lock out users**: the previous list is kept.

## How to extend
- **New way to write a currency in free text** (e.g. a nickname): add an entry to `ALIASES` in `currencies.py` (lowercase key), plus a test in `tests/test_parser.py`. Only unambiguous names (e.g. not "דינר"; those are handled by search with buttons).
- **Currency in the list / search by country**: add `_c(...)` to `CATALOG` in `catalog.py` (code, Hebrew name, English name, flag, region, search keywords). For a quick-pick button, also add it to `POPULAR`.
- **Currency display symbol**: `DISPLAY_SYMBOLS` in `currencies.py`.
- **Changing text wording**: `messages.py` only.
- **Improving recognition from images**: change `PROMPT` in `vision.py`, or the model in `.env`. Use `LOG_LEVEL=DEBUG` to see the model's raw output.
- **New command**: a function in `handlers.py` + registration in `register()` + an entry in `COMMANDS` in `__main__.py` (so it shows in Telegram's menu) + a line in the help text.
- **Different rates provider**: replace `_fetch` in `rates.py` (keep `self._rates` relative to one base currency).

## Tests
`tests/` covers the logic without network access: parsing, conversion and cache (`httpx.MockTransport`),
the allow-list and preferences (temp directory), the vision module (a mocked Ollama), and the handlers' logic (`test_handlers.py`, with stub Telegram objects).
