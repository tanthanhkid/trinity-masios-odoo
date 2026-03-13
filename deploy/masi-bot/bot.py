"""
Masi Bot v2 — Telegram bot with Odoo MCP integration.

Polling mode, per-user conversation memory, whitelist access control.
Uses python-telegram-bot v21.x (fully async).
"""

import asyncio
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from agent import MasiAgent
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_WHITELIST
from mcp_client import OdooMCPClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
mcp_client: OdooMCPClient = None
agent: MasiAgent = None
conversations: dict[int, list] = {}  # user_id -> message history

MAX_HISTORY = 20


# ---------------------------------------------------------------------------
# Conversation memory helpers
# ---------------------------------------------------------------------------
def get_history(user_id: int) -> list:
    if user_id not in conversations:
        conversations[user_id] = []
    return conversations[user_id]


def add_to_history(user_id: int, role: str, content: str):
    history = get_history(user_id)
    history.append({"role": role, "content": content})
    if len(history) > MAX_HISTORY:
        conversations[user_id] = history[-MAX_HISTORY:]


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------
async def check_whitelist(update: Update) -> bool:
    user_id = update.effective_user.id
    if user_id not in TELEGRAM_WHITELIST:
        await update.message.reply_text(
            "\U0001f6ab B\u1ea1n ch\u01b0a \u0111\u01b0\u1ee3c c\u1ea5p quy\u1ec1n truy c\u1eadp."
        )
        logger.warning(
            "Unauthorized access attempt from user %s (@%s)",
            user_id,
            update.effective_user.username,
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Message splitting (Telegram limit: 4096 chars)
# ---------------------------------------------------------------------------
async def send_long_message(update: Update, text: str):
    """Split and send messages that exceed Telegram's 4096 char limit.
    Tries MarkdownV2 first, falls back to HTML, then plain text."""
    import re

    def escape_mdv2(t: str) -> str:
        """Escape special chars for Telegram MarkdownV2, preserving **bold** and `code`."""
        # First, protect bold and code markers
        t = t.replace("**", "\x01BOLD\x01")
        t = t.replace("`", "\x01CODE\x01")
        # Escape all special chars
        special = r'_[]()~>#+=|{}.!-'
        for ch in special:
            t = t.replace(ch, f"\\{ch}")
        # Restore bold and code
        t = t.replace("\x01BOLD\x01", "*")
        t = t.replace("\x01CODE\x01", "`")
        return t

    async def send_chunk(chunk: str):
        # Try HTML first (convert markdown if needed)
        html = md_to_html(chunk)
        try:
            await update.message.reply_text(html, parse_mode="HTML")
            return
        except Exception as e:
            logger.debug("HTML parse failed, trying plain: %s", e)
        # Fallback: plain text (strip HTML tags)
        import re as _re
        plain = _re.sub(r'<[^>]+>', '', chunk)
        await update.message.reply_text(plain)

    if len(text) <= 4096:
        await send_chunk(text)
        return

    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > 4096:
            if current:
                chunks.append(current)
            while len(line) > 4096:
                chunks.append(line[:4096])
                line = line[4096:]
            current = line
        else:
            current += ("\n" if current else "") + line
    if current:
        chunks.append(current)

    for chunk in chunks:
        await send_chunk(chunk)


def md_to_html(text: str) -> str:
    """Convert Markdown to Telegram-compatible HTML.

    Telegram HTML supports: <b>, <i>, <u>, <s>, <code>, <pre>,
    <a href>, <blockquote>, <tg-spoiler>. NO tables, lists, or headers.
    """
    import re

    # --- 1. Convert Markdown tables to aligned text ---
    def convert_table(match: re.Match) -> str:
        lines = match.group(0).strip().split("\n")
        rows = []
        for line in lines:
            line = line.strip()
            if not line.startswith("|"):
                continue
            # Skip separator rows (|---|---|)
            if re.match(r'^\|[\s\-:|]+\|$', line):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            rows.append(cells)
        if not rows:
            return match.group(0)

        # Format as aligned lines
        result = []
        header = rows[0]
        for row in rows[1:]:
            parts = []
            for i, cell in enumerate(row):
                label = header[i] if i < len(header) else ""
                if label and cell:
                    parts.append(f"{label}: {cell}")
                elif cell:
                    parts.append(cell)
            result.append("• " + " | ".join(parts))

        # If only header (no data rows), show header as bold
        if not result:
            return "<b>" + " | ".join(header) + "</b>"
        return "\n".join(result)

    # Match markdown tables (lines starting with |)
    text = re.sub(
        r'(?:^\|.+\|$\n?){2,}',
        convert_table,
        text,
        flags=re.MULTILINE,
    )

    # --- 2. Code blocks FIRST (protect from other transforms) ---
    code_blocks = []
    def save_code(m):
        code_blocks.append(m.group(1))
        return f"\x00CODE{len(code_blocks)-1}\x00"
    text = re.sub(r'```(?:\w*\n)?(.*?)```', save_code, text, flags=re.DOTALL)

    inline_codes = []
    def save_inline(m):
        inline_codes.append(m.group(1))
        return f"\x00INLINE{len(inline_codes)-1}\x00"
    text = re.sub(r'`(.+?)`', save_inline, text)

    # --- 3. Escape HTML special chars (outside code) ---
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")

    # --- 4. Markdown → HTML ---
    # Headers → bold
    text = re.sub(r'^#{1,6}\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    # Bold: **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Italic: *text* (not inside bold tags)
    text = re.sub(r'(?<![*])\*([^*]+?)\*(?![*])', r'<i>\1</i>', text)
    # Underline: __text__
    text = re.sub(r'__(.+?)__', r'<u>\1</u>', text)
    # Strikethrough: ~~text~~
    text = re.sub(r'~~(.+?)~~', r'<s>\1</s>', text)
    # Links: [text](url)
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
    # Blockquote: > text
    text = re.sub(r'^&gt;\s?(.+)$', r'<blockquote>\1</blockquote>', text, flags=re.MULTILINE)
    # Merge adjacent blockquotes
    text = text.replace("</blockquote>\n<blockquote>", "\n")
    # Horizontal rules: --- or ***
    text = re.sub(r'^[\-\*]{3,}$', '─' * 20, text, flags=re.MULTILINE)

    # --- 5. Restore code blocks ---
    for i, code in enumerate(code_blocks):
        safe_code = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00CODE{i}\x00", f"<pre>{safe_code}</pre>")
    for i, code in enumerate(inline_codes):
        safe_code = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00INLINE{i}\x00", f"<code>{safe_code}</code>")

    return text


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_whitelist(update):
        return
    await update.message.reply_text(
        "\U0001f44b Xin ch\u00e0o! T\u00f4i l\u00e0 tr\u1ee3 l\u00fd AI c\u1ee7a Masi OS.\n"
        "G\u00f5 /masi \u0111\u1ec3 xem danh s\u00e1ch l\u1ec7nh.\n"
        "Ho\u1eb7c h\u1ecfi t\u00f4i b\u1ea5t k\u1ef3 \u0111i\u1ec1u g\u00ec v\u1ec1 Odoo."
    )


async def masi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_whitelist(update):
        return
    await handle_message_internal(update, "Hiển thị menu commands cho tôi")


async def slash_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generic handler for all slash commands — forwards to agent as text."""
    if not await check_whitelist(update):
        return
    cmd = update.message.text  # e.g. "/morning_brief" or "/credit 42"
    await handle_message_internal(update, cmd)


# ---------------------------------------------------------------------------
# Message handler
# ---------------------------------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_whitelist(update):
        return
    await handle_message_internal(update, update.message.text)


async def keep_typing(chat, stop_event: asyncio.Event):
    """Send typing indicator every 4s until stop_event is set."""
    while not stop_event.is_set():
        try:
            await chat.send_action("typing")
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            pass


async def handle_message_internal(update: Update, text: str):
    user_id = update.effective_user.id

    # Add user message to history
    add_to_history(user_id, "user", text)

    # Start persistent typing indicator
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(update.message.chat, stop_typing))

    try:
        history = get_history(user_id)
        response = await agent.chat(list(history), telegram_user_id=user_id)

        add_to_history(user_id, "assistant", response)
        stop_typing.set()
        await typing_task
        await send_long_message(update, response)
    except Exception as e:
        stop_typing.set()
        await typing_task
        logger.error("Error processing message: %s", e, exc_info=True)
        await update.message.reply_text(
            f"\u274c L\u1ed7i x\u1eed l\u00fd: {e}"
        )


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
async def post_init(application: Application):
    """Initialize MCP client after bot starts but before polling."""
    global mcp_client, agent
    mcp_client = OdooMCPClient()
    await mcp_client.connect()
    agent = MasiAgent(mcp_client)
    logger.info("Bot initialized with %d MCP tools", len(mcp_client.tools))


def main():
    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("masi", masi_command))

    # All other slash commands → forward to agent
    SLASH_COMMANDS = [
        "morning_brief", "ceo_alert", "doanhso_homnay",
        "brief_hunter", "brief_farmer", "brief_ar", "brief_cash",
        "hunter_today", "hunter_sla", "hunter_quotes",
        "hunter_first_orders", "hunter_sources", "khachmoi_homnay",
        "farmer_today", "farmer_reorder", "farmer_sleeping",
        "farmer_vip", "farmer_ar", "farmer_retention",
        "congno_denhan", "congno_quahan",
        "task_quahan", "midday", "eod",
        "kpi", "pipeline", "newlead", "newcustomer",
        "quote", "invoice", "credit", "findcustomer",
    ]
    for cmd in SLASH_COMMANDS:
        app.add_handler(CommandHandler(cmd, slash_command))

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logger.info("Starting Masi Bot v2...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
