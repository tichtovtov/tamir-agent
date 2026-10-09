"""All user-facing texts (Hebrew). Messages are sent with HTML parse mode.

Keep wording changes here so handlers stay free of text. Any value interpolated
from user input or files must be passed through `html.escape`.
"""

from __future__ import annotations

from html import escape

from bot import catalog, currencies
from bot.rates import Conversion


def unauthorized(user_id: int, admin_name: str) -> str:
    return (
        "שלום! הבוט הזה פתוח למשתמשים מורשים בלבד.\n\n"
        f"כדי לקבל גישה, שלח/י ל{escape(admin_name)} את המזהה שלך בטלגרם:\n"
        f"<code>{user_id}</code>"
    )


def help_text(name: str | None, target: str, source: str | None) -> str:
    greeting = f"היי {escape(name)}! " if name else "היי! "
    return (
        f"{greeting}אני ממיר מחירים למטבע שבחרת.\n"
        f"{_settings_line(target, source)}\n\n"
        "<b>איך משתמשים:</b>\n"
        "• שלחו סכום ומטבע, למשל: <code>100 USD</code>, <code>€25</code>, "
        "<code>12.50 יורו</code>\n"
        "• או שלחו תמונה של תווית מחיר (אפשר להוסיף בכיתוב את המטבע, למשל <code>EUR</code>)\n"
        "• בנסיעה? קבעו מטבע מקור עם <code>/from EUR</code> ואז אפשר לשלוח רק מספר\n\n"
        "<b>פקודות:</b>\n"
        "/set &lt;מטבע&gt; - קביעת מטבע היעד, למשל <code>/set USD</code>\n"
        "/from &lt;מטבע&gt; - מטבע מקור כשנשלח רק מספר (<code>/from off</code> לביטול)\n"
        "/currencies - רשימת מטבעות והקודים שלהם\n"
        "/currency - הצגת ההגדרות הנוכחיות\n\n"
        "לא יודעים את הקוד? כתבו שם מדינה או מטבע: <code>/from וייטנאם</code>, "
        "<code>/set פסו</code>\n"
        "/help - ההודעה הזו"
    )


def _settings_line(target: str, source: str | None) -> str:
    line = f"מטבע יעד: <b>{catalog.describe(target)}</b>"
    if source:
        line += f"\nמטבע מקור ברירת מחדל: <b>{catalog.describe(source)}</b>"
    return line


def missing_currency(amount: float) -> str:
    return (
        f"קיבלתי את הסכום {amount:,.2f}, אבל לא ציינת מטבע.\n"
        f"נסו למשל: <code>{amount:g} USD</code>\n"
        "טיפ: <code>/from USD</code> יקבע את USD כמטבע המקור, ואז אפשר לשלוח רק מספרים."
    )


def conversion(c: Conversion) -> str:
    text = (
        f"{currencies.format_amount(c.amount, c.source)} ≈ "
        f"<b>{currencies.format_amount(c.result, c.target)}</b>"
    )
    if c.source == c.target:
        return text
    updated = c.updated_at.strftime("%d/%m/%Y %H:%M UTC")
    text += f"\n<i>שער: 1 {c.source} = {c.rate:.4f} {c.target} · עודכן {updated}</i>"
    if c.stale:
        text += "\n⚠️ לא הצלחתי לרענן שערים, מוצג שער שמור"
    return text


def current_settings(target: str, source: str | None) -> str:
    text = f"{_settings_line(target, source)}\nלשינוי מטבע היעד: <code>/set USD</code>"
    if source:
        text += "\nלביטול מטבע המקור: <code>/from off</code>"
    else:
        text += "\nלקביעת מטבע מקור (למספר בלי מטבע): <code>/from EUR</code>"
    return text


def currency_set(target: str) -> str:
    return f"✅ מטבע היעד עודכן ל-<b>{catalog.describe(target)}</b>"


def source_set(source: str) -> str:
    return (
        f"✅ מטבע המקור נקבע ל-<b>{catalog.describe(source)}</b>\n"
        f"מעכשיו מספר בלי מטבע (בטקסט או בתמונה) יומר מ-{source}.\n"
        "לביטול: <code>/from off</code>"
    )


SOURCE_CLEARED = "✅ מטבע המקור בוטל. מעכשיו צריך לציין מטבע עם כל סכום."


def unknown_currency(token: str) -> str:
    return (
        f"לא מכיר את המטבע <code>{escape(token)}</code>.\n"
        "אפשר לכתוב קוד בן 3 אותיות (USD, EUR...), שם מטבע (דולר, באט) או שם מדינה "
        "(תאילנד, וייטנאם).\n"
        "לרשימה המלאה: /currencies"
    )


def choose_currency(kind: str) -> str:
    """Prompt above the quick-pick buttons. `kind` is "set" (target) or "from" (source)."""
    what = "מטבע היעד" if kind == "set" else "מטבע המקור (למספרים בלי מטבע)"
    return (
        f"בחרו {what}:\n"
        f"לא ברשימה? כתבו <code>/{kind}</code> ואחריו שם מדינה או מטבע, "
        f"למשל <code>/{kind} וייטנאם</code>. רשימה מלאה: /currencies"
    )


def multiple_matches(token: str) -> str:
    return f"מצאתי כמה מטבעות שמתאימים ל-<code>{escape(token)}</code>, בחרו אחד:"


def currency_list() -> str:
    """All catalog currencies grouped by region: flag, code and Hebrew name."""
    lines = ["<b>מטבעות נפוצים</b> (קוד · שם):"]
    for region in catalog.REGIONS:
        lines.append(f"\n<b>{region}</b>")
        lines += [
            f"{c.flag} <code>{c.code}</code> {c.name_he}"
            for c in catalog.CATALOG
            if c.region == region
        ]
    lines.append(
        "\nשימוש: <code>/set VND</code> או <code>/from וייטנאם</code>.\n"
        "כל קוד מטבע תקני אחר (ISO 4217) נתמך גם אם אינו ברשימה."
    )
    return "\n".join(lines)


RATES_UNAVAILABLE = "😕 לא הצלחתי לקבל שערי חליפין כרגע. נסו שוב בעוד כמה דקות."
VISION_UNAVAILABLE = "😕 שירות זיהוי התמונות לא זמין כרגע. אפשר לשלוח את המחיר כטקסט."
NO_PRICE_IN_IMAGE = "לא מצאתי מחיר בתמונה 🤔\nנסו תמונה ברורה וקרובה יותר, או שלחו את המחיר כטקסט."


def image_missing_currency(amount: float) -> str:
    return (
        f"זיהיתי בתמונה את הסכום <b>{amount:,.2f}</b> אבל לא את המטבע.\n"
        "שלחו שוב את התמונה עם המטבע בכיתוב (למשל <code>EUR</code>), "
        f"או כתבו: <code>{amount:g} EUR</code>\n"
        "טיפ: <code>/from EUR</code> יקבע מטבע מקור קבוע לתמונות ומספרים בלי מטבע."
    )
