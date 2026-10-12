# Architecture

A version with diagrams: [ARCHITECTURE.html](ARCHITECTURE.html) (open it in a browser). Keep the two files in sync.

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
Any other input (sticker, voice, unknown command) → help message.

**Free text that `parser.parse` doesn't recognize** goes to `nlu.OllamaNLU.interpret` (a language model in Ollama), which returns an `Interpretation`:
```
text ── parser.parse ──► clear price ──────────────────────────► conversion
             │
             └─ not recognized / bare number while a question is pending
                       ▼
             nlu.interpret(text, conversation memory, user settings)
                       ▼
   convert ─────────► (validate currency in our code) ──► conversion / question
   set_target/source ► confirmation button ("✅ כן" / "❌ לא") ──► saved only on press
   clear_source ─────► confirmation button
   clarify ──────────► the model's question (HTML-escaped) + saved to memory
   show_settings / list_currencies / help ──► the existing response
```
Principles:
- **The model only interprets; the code decides.** Every currency the model returns goes through `_resolve` (aliases + catalog + the rates provider's list). An unrecognized currency → question to the user. A settings change → only after a button press.
- **Conversation memory**: when the bot asks a question (the model's question, "which currency?" for a bare number, or an image without a currency), the exchange is stored in `context.user_data` (in memory only, not on disk). The next message is sent to the model together with the memory, so an answer like `יורו` or `50` is understood in context. The memory is cleared after a successful action, or after `CONVERSATION_TTL_SECONDS` (10 minutes), and holds at most `CONVERSATION_MAX_MESSAGES` messages.
- **If Ollama is down**: unrecognized text gets the help message (same as before the feature). Regular conversions aren't affected.

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
| `auth.py` | `AllowList`: reads `allowed_users.json` (reloads on mtime change) merged with `BotUsers` |
| `storage.py` | Files the bot writes, atomically: `UserPrefs` (each user's currencies in `user_prefs.json`) and `BotUsers` (users added with `/add_user`, in `bot_users.json`) |
| `parser.py` | Parses text into `ParsedPrice(amount, currency)`, including magnitude suffixes (`10k`, `1.5m`, `5 אלף`) |
| `currencies.py` | Map of symbols/names → ISO code (for parsing free text), and display formatting |
| `catalog.py` | Catalog of ~50 common currencies: Hebrew/English name, flag, region, countries. Used for `/currencies`, search, and buttons |
| `rates.py` | `RatesClient`: fetches USD-based rates, cache, conversion via cross rate |
| `ollama.py` | `OllamaClient`: shared Ollama client (chat with a JSON schema, startup check of models) |
| `vision.py` | `OllamaVision`: sends an image to the model and returns `ParsedPrice` |
| `nlu.py` | `OllamaNLU`: interprets free text into an `Interpretation` (action + fields), given the user's settings and first name. Includes `SYSTEM_PROMPT` with examples |
| `messages.py` | All user-facing texts (Hebrew, HTML) |

Services are created once in `__main__.py` and stored in `application.bot_data["services"]` (a `Services` object).

## Data files (`data/`, not in git)
| File | Who writes it | Format |
|---|---|---|
| `allowed_users.json` | Admin, by hand | `{"<telegram_id>": {"name": "<name>"}}` |
| `bot_users.json` | The bot (admin's `/add_user`, `/remove_user`) | `{"<telegram_id>": {"name": "<name>", "added_by": <admin id>, "added_at": "<ISO time>"}}` |
| `user_prefs.json` | The bot | `{"<telegram_id>": {"name": "<Telegram name>", "currency": "USD", "source": "EUR"}}` |

`currency` = target currency (default `DEFAULT_CURRENCY`). `source` = default source currency from `/from`, optional; `/from off` removes the field.

The split is intentional: the bot never writes to the file the admin edits, so there's no risk of overwriting manual edits. The allow-list is the union of `allowed_users.json` and `bot_users.json`; if a user is in both, the name from `allowed_users.json` wins.

**Admins** (`ADMIN_IDS` in `.env`) always pass the gate and can run `/add_user`, `/remove_user` and `/users`. For anyone else these commands fall through to the help message, like an unknown command. The admin commands are added to the Telegram command menu only in admins' private chats (`BotCommandScopeChat`).

## Design decisions
- **Polling, not a webhook**: no public address or SSL certificate needed. Works behind a home NAT.
- **Local Ollama**: images and text never leave the machine, and there's no per-use cost. The JSON schema in `format` forces structured output.
- **Parser first, model second**: common messages (`100 USD`) are answered immediately and deterministically; only what isn't recognized pays the ~6 seconds of the language model.
- **Rates via USD**: a single API call gives the rate between any pair of currencies (`rate = rates[target] / rates[source]`).
- **Stale cache when the API fails**: better to return an old rate, with a warning, than to fail.
- **A broken allowed_users.json doesn't lock out users**: the previous list is kept.

## How to extend
- **New way to write a currency in free text** (e.g. a nickname): add an entry to `ALIASES` in `currencies.py` (lowercase key), plus a test in `tests/test_parser.py`. Only unambiguous names (e.g. not "דינר"; those are handled by search with buttons). An alias must not be exactly a magnitude suffix (`k`, `m`, `b`, `bn`, `אלף`, `מיליון`...), because the parser reads those as multipliers first.
- **Currency in the list / search by country**: add `_c(...)` to `CATALOG` in `catalog.py` (code, Hebrew name, English name, flag, region, search keywords). For a quick-pick button, also add it to `POPULAR`.
- **Currency display symbol**: `DISPLAY_SYMBOLS` in `currencies.py`.
- **Changing text wording**: `messages.py` only.
- **Improving recognition from images**: change `PROMPT` in `vision.py`, or the model in `.env`. Use `LOG_LEVEL=DEBUG` to see the model's raw output.
- **Improving free-text understanding**: add an example to the `Examples` section of `SYSTEM_PROMPT` in `nlu.py`. Check with real phrases (see `tests/test_nlu.py` for the format), not just the ones in the examples.
- **New action for the language model**: add it to `ACTIONS` and to the prompt in `nlu.py`, handle it in `_understand` in `handlers.py`, and add a test in `tests/test_handlers.py`.
- **New admin command**: like a new command, but start the handler with the `_is_admin` check (fall back to `help_cmd`) and add it to `ADMIN_COMMANDS` instead of `COMMANDS`, plus a line in `messages.ADMIN_HELP`.
- **New command**: a function in `handlers.py` + registration in `register()` + an entry in `COMMANDS` in `__main__.py` (so it shows in Telegram's menu) + a line in the help text.
- **Different rates provider**: replace `_fetch` in `rates.py` (keep `self._rates` relative to one base currency).

## Tests
`tests/` covers the logic without network access: parsing, conversion and cache (`httpx.MockTransport`),
the allow-list and preferences (temp directory), the vision and language modules (a mocked Ollama), and the handlers' logic, including the clarifying-question and confirmation flow (`test_handlers.py`, with stub Telegram objects).
