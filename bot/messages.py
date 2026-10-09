"""All user-facing texts (Hebrew). Messages are sent with HTML parse mode.

Keep wording changes here so handlers stay free of text. Any value interpolated
from user input or files must be passed through `html.escape`.
"""

from __future__ import annotations

from html import escape

from bot import currencies
from bot.rates import Conversion


def unauthorized(user_id: int, admin_name: str) -> str:
    return (
        "שלום! הבוט הזה פתוח למשתמשים מורשים בלבד.\n\n"
        f"כדי לקבל גישה, שלח/י ל{escape(admin_name)} את המזהה שלך בטלגרם:\n"
        f"<code>{user_id}</code>"
    )


def help_text(name: str | None, target: str) -> str:
    greeting = f"היי {escape(name)}! " if name else "היי! "
    return (
        f"{greeting}אני ממיר מחירים למטבע שבחרת "
        f"(כרגע: <b>{target}</b>).\n\n"
        "<b>איך משתמשים:</b>\n"
        "• שלחו סכום ומטבע, למשל: <code>100 USD</code>, <code>€25</code>, "
        "<code>12.50 יורו</code>\n"
        "• או שלחו תמונה של תווית מחיר (אפשר להוסיף בכיתוב את המטבע, למשל <code>EUR</code>)\n\n"
        "<b>פקודות:</b>\n"
        "/set &lt;מטבע&gt; - קביעת מטבע היעד, למשל <code>/set USD</code>\n"
        "/currency - הצגת מטבע היעד הנוכחי\n"
        "/help - ההודעה הזו"
    )


def missing_currency(amount: float) -> str:
    return (
        f"קיבלתי את הסכום {amount:,.2f}, אבל לא ציינת מטבע.\nנסו למשל: <code>{amount:g} USD</code>"
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


def current_currency(target: str) -> str:
    return f"מטבע היעד שלך: <b>{target}</b>\nלשינוי: <code>/set USD</code> (או כל קוד מטבע אחר)"


def currency_set(target: str) -> str:
    return f"✅ מטבע היעד עודכן ל-<b>{target}</b>"


def unknown_currency(token: str) -> str:
    return (
        f"לא מכיר את המטבע <code>{escape(token)}</code>.\n"
        "השתמשו בקוד בן 3 אותיות (USD, EUR, GBP, ILS...) או בשם כמו דולר / יורו / שקל."
    )


RATES_UNAVAILABLE = "😕 לא הצלחתי לקבל שערי חליפין כרגע. נסו שוב בעוד כמה דקות."
VISION_UNAVAILABLE = "😕 שירות זיהוי התמונות לא זמין כרגע. אפשר לשלוח את המחיר כטקסט."
NO_PRICE_IN_IMAGE = "לא מצאתי מחיר בתמונה 🤔\nנסו תמונה ברורה וקרובה יותר, או שלחו את המחיר כטקסט."


def image_missing_currency(amount: float) -> str:
    return (
        f"זיהיתי בתמונה את הסכום <b>{amount:,.2f}</b> אבל לא את המטבע.\n"
        "שלחו שוב את התמונה עם המטבע בכיתוב (למשל <code>EUR</code>), "
        f"או כתבו: <code>{amount:g} EUR</code>"
    )
