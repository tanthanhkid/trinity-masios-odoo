import anthropic
import asyncio
import json
import logging
import re

from config import LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, SYSTEM_PROMPT
from formatter import format_command

logger = logging.getLogger(__name__)

# Slash command → MCP tool direct mapping (skip LLM round 1)
COMMAND_TOOL_MAP = {
    "/morning_brief": ("odoo_morning_brief", {}),
    "/ceo_alert": ("odoo_ceo_alert", {}),
    "/doanhso_homnay": ("odoo_revenue_today", {}),
    "/brief_hunter": ("odoo_brief_hunter", {}),
    "/brief_farmer": ("odoo_brief_farmer", {}),
    "/brief_ar": ("odoo_brief_ar", {}),
    "/brief_cash": ("odoo_brief_cash", {}),
    "/hunter_today": ("odoo_hunter_today", {}),
    "/hunter_sla": ("odoo_hunter_sla_details", {}),
    "/hunter_quotes": ("odoo_hunter_today", {"section": "quotes"}),
    "/hunter_first_orders": ("odoo_hunter_today", {"section": "first_orders"}),
    "/hunter_sources": ("odoo_hunter_today", {"section": "sources"}),
    "/khachmoi_homnay": ("odoo_hunter_today", {"section": "overview"}),
    "/farmer_today": ("odoo_farmer_today", {}),
    "/farmer_reorder": ("odoo_farmer_today", {"section": "reorder"}),
    "/farmer_sleeping": ("odoo_farmer_today", {"section": "sleeping"}),
    "/farmer_vip": ("odoo_farmer_today", {"section": "vip"}),
    "/farmer_ar": ("odoo_farmer_ar", {}),
    "/farmer_retention": ("odoo_farmer_today", {"section": "retention"}),
    "/congno_denhan": ("odoo_congno", {"mode": "due_soon"}),
    "/congno_quahan": ("odoo_congno", {"mode": "overdue"}),
    "/task_quahan": ("odoo_task_overdue", {}),
    "/midday": ("odoo_flash_report", {"report_type": "midday"}),
    "/eod": ("odoo_flash_report", {"report_type": "eod"}),
    "/kpi": ("odoo_dashboard_kpis", {}),
    "/pipeline": ("odoo_pipeline_by_stage", {}),
    "/credit": ("odoo_customers_exceeding_credit", {}),
}

# Tools that return PDF base64 — intercept and handle specially
PDF_TOOLS = {"odoo_sale_order_pdf", "odoo_invoice_pdf"}

# Quick reply patterns — skip LLM entirely
_QUICK_PATTERNS = [
    re.compile(r'^(ok|oke|okie|oki)$'),
    re.compile(r'^(ok )?(cảm ơn|cam on|thanks|thank you|tks).*$'),
    re.compile(r'^(ok )?(được rồi|dc rồi|dc roi|ok rồi)$'),
    re.compile(r'^(tốt lắm|tốt|good|great|nice|hay|hay quá)$'),
    re.compile(r'^(ok )?(ghi nhận|noted)$'),
    re.compile(r'^(bye|tạm biệt|hẹn gặp lại).*$'),
    re.compile(r'^(uh huh|uhm|hmm|à|ờ)$'),
    re.compile(r'^(ok )?(xong|done)$'),
    re.compile(r'^(ok )?(tạm ổn|ổn)$'),
]

_QUICK_REPLIES = [
    "Dạ, nếu cần gì thêm cứ hỏi nhé! 😊",
    "Vâng ạ! Có gì cứ gọi nhé 👍",
    "Ok anh/chị! Chúc làm việc hiệu quả! 💪",
    "Dạ rồi ạ! 😊",
]


def _extract_pdf(result_str: str) -> dict | None:
    """Check if tool result contains PDF base64 data. Returns parsed dict or None."""
    try:
        data = json.loads(result_str) if isinstance(result_str, str) else result_str
        if isinstance(data, dict) and data.get("pdf_base64"):
            return data
        if isinstance(data, dict) and "result" in data:
            inner = data["result"]
            if isinstance(inner, str):
                inner = json.loads(inner)
            if isinstance(inner, dict) and inner.get("pdf_base64"):
                return inner
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _pdf_summary(pdf_data: dict) -> str:
    """Create a short summary for LLM context (no base64)."""
    return json.dumps({
        "status": "pdf_generated",
        "filename": pdf_data.get("filename", "document.pdf"),
        "size_bytes": pdf_data.get("size_bytes", 0),
        "order_name": pdf_data.get("order_name", ""),
        "partner": pdf_data.get("partner", ""),
        "amount_total": pdf_data.get("amount_total", 0),
        "note": "PDF file will be sent as attachment automatically.",
    }, ensure_ascii=False)


class MasiAgent:
    MAX_TOOL_ROUNDS = 5
    MAX_TOKENS = 4096
    LLM_TIMEOUT = 45.0  # Hard timeout per LLM call (seconds)

    def __init__(self, mcp_client):
        self.mcp = mcp_client
        self.client = anthropic.Anthropic(
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
            timeout=60.0,
        )
        # Per-user PDF queues to prevent cross-user PDF leaks
        self._pending_pdfs: dict[int, list[dict]] = {}

    def pop_pending_pdfs(self, user_id: int = 0) -> list[dict]:
        """Retrieve and clear pending PDF attachments for a specific user."""
        pdfs = self._pending_pdfs.pop(user_id, [])
        return pdfs

    async def chat(self, messages: list[dict], telegram_user_id: int) -> str:
        tools = self.mcp.get_anthropic_tools()
        system = SYSTEM_PROMPT + f"\n\nTelegram user ID hiện tại: {telegram_user_id}"
        msgs = [m.copy() for m in messages]

        self._pending_pdfs[telegram_user_id] = []

        # Fast path: known slash commands
        last_msg = msgs[-1]["content"] if msgs else ""
        cmd = last_msg.strip().split()[0] if last_msg.strip() else ""
        if "@" in cmd:
            cmd = cmd.split("@")[0]

        if cmd in COMMAND_TOOL_MAP:
            return await self._fast_command(cmd, system, telegram_user_id, tools)

        # Quick reply guard: "ok", "cảm ơn", etc. → canned response, no LLM
        quick = self._quick_reply(last_msg)
        if quick:
            return quick

        # Context injection
        msgs = self._inject_context(msgs)

        # Normal path: full tool-calling loop
        return await self._tool_loop(msgs, system, tools, telegram_user_id)

    @staticmethod
    def _quick_reply(msg: str) -> str | None:
        """Return canned response for simple acknowledgements. Skip LLM entirely."""
        import random
        normalized = msg.strip().lower().rstrip("!.?")
        for p in _QUICK_PATTERNS:
            if p.match(normalized):
                return random.choice(_QUICK_REPLIES)
        return None

    def _inject_context(self, msgs: list[dict]) -> list[dict]:
        """Inject context hints for short replies and drill-down questions."""
        if len(msgs) < 3:
            return msgs

        last_user = msgs[-1]["content"].strip()
        if last_user.startswith("/"):
            return msgs

        # Find last assistant message
        prev_assistant = None
        for m in reversed(msgs[:-1]):
            if m["role"] == "assistant":
                prev_assistant = m["content"]
                break

        if not prev_assistant:
            return msgs

        pa = prev_assistant.lower()

        # --- 1. Short reply injection (bare numbers, single words <=20 chars) ---
        if len(last_user) <= 20:
            context_map = [
                (["sale order", "so ", "báo giá", "quote", "số so"],
                 f"User đang trong flow /quote. Họ trả lời '{last_user}' = Sale Order ID. Gọi odoo_sale_order_summary(order_id={last_user}) NGAY."),
                (["invoice", "hóa đơn", "số invoice", "số hđ"],
                 f"User đang trong flow /invoice. Họ trả lời '{last_user}' = Invoice ID. Gọi odoo_invoice_summary(invoice_id={last_user}) NGAY."),
                (["tên khách", "khách hàng", "findcustomer", "tên kh"],
                 f"User đang trong flow /findcustomer. Họ trả lời '{last_user}' = tên khách hàng cần tìm. Gọi odoo_search_read ngay."),
                (["id khách", "partner", "credit"],
                 f"User đang trong flow kiểm tra credit. Họ trả lời '{last_user}' = partner ID. Gọi tool ngay."),
            ]
            for keywords, context_hint in context_map:
                if any(kw in pa for kw in keywords):
                    msgs = list(msgs)
                    msgs[-1] = {"role": "user", "content": f"[CONTEXT: {context_hint}]\n\n{last_user}"}
                    logger.info("Context injected (short): '%s'", last_user)
                    return msgs

        # --- 2. Drill-down injection: follow-up questions about a found entity ---
        # Try multiple regex patterns to extract partner_id (handles HTML, bold, code formatting)
        partner_id = None
        for pattern in [
            r'partner_id[=:\s]*(\d+)',
            r'<code>(\d+)</code>',
            r'ID[:\s]*(?:<[^>]+>)*(\d+)',
            r'id[:\s=]+(\d+)',
        ]:
            m = re.search(pattern, prev_assistant, re.IGNORECASE)
            if m:
                partner_id = m.group(1)
                break

        # Extract partner name from various LLM response formats
        partner_name = None
        for pattern in [
            r'<b>(Công ty[^<]+|[^<]{5,50})</b>\s*\n\s*<code>',  # <b>Name</b>\n<code>id</code>
            r'\*\*([^*]{3,50})\*\*\s*(?:\(|partner_id|<code>)',   # **Name** (partner_id=N)
            r'(?:Tên|KH|khách hàng|customer)[:\s]*(?:<[^>]*>)*([A-ZĐÁÂĂÊÔƠƯÀẢÃẠĂẮẶẦẨẪẬÉÊẾỆÍÌỊÓÔƠỜỚỢÙÚƯỤ][^*\n<(]{2,50})',
            r'(?:tìm thấy|found|kết quả)[:\s]*\n\s*[•\-]\s*(?:<[^>]*>)*([^<\n]{3,60})',
        ]:
            m = re.search(pattern, prev_assistant, re.IGNORECASE)
            if m:
                partner_name = m.group(1).strip().rstrip(":")
                break

        drill_keywords = [
            "lịch sử", "đơn hàng", "nợ", "credit", "thanh toán", "mua gì",
            "chi tiết", "thông tin", "xếp hạng", "revenue", "doanh thu",
            "nhắc nợ", "gửi nhắc", "liên hệ", "dispute", "escalate",
            "cần gọi", "gọi cho", "contact", "limit", "hạn mức",
            "phân loại", "classification", "tag", "note", "ghi chú",
            "địa chỉ", "email", "điện thoại", "sdt", "phone",
        ]

        if partner_id and any(kw in last_user.lower() for kw in drill_keywords):
            name_str = f"'{partner_name}'" if partner_name else "đã tìm"
            context_hint = (
                f"User đang xem KH {name_str} (partner_id={partner_id}). "
                f"Câu hỏi '{last_user}' là DRILL-DOWN về KH này, KHÔNG phải tìm KH mới. "
                f"Dùng partner_id={partner_id} làm filter trực tiếp."
            )
            msgs = list(msgs)
            msgs[-1] = {"role": "user", "content": f"[CONTEXT: {context_hint}]\n\n{last_user}"}
            logger.info("Context injected (drill-down): partner_id=%s, msg='%s'", partner_id, last_user)
            return msgs

        # --- 3. List context: follow-up on a list of leads/customers shown ---
        # When bot just showed a list and user asks a short analytical question
        list_context_keywords = ["cần gọi ai", "ai quan trọng", "ưu tiên", "plan", "tiếp cận",
                                  "expected", "target", "focus", "tập trung"]
        if any(kw in last_user.lower() for kw in list_context_keywords) and len(last_user) <= 60:
            if any(kw in pa for kw in ["danh sách", "leads", "khách", "list", "record"]):
                context_hint = (
                    f"User đang xem danh sách data vừa hiển thị ở trên. "
                    f"Câu hỏi '{last_user}' là phân tích/hành động trên danh sách đó. "
                    f"KHÔNG search mới — hãy phân tích từ data đã có hoặc trả lời dựa trên context."
                )
                msgs = list(msgs)
                msgs[-1] = {"role": "user", "content": f"[CONTEXT: {context_hint}]\n\n{last_user}"}
                logger.info("Context injected (list-analysis): msg='%s'", last_user)
                return msgs

        return msgs

    @staticmethod
    def _trim_history(msgs: list, keep: int = 8) -> list:
        """Trim conversation history to reduce token count.
        Preserves first 2 messages (command + initial response) + last `keep` messages.
        This keeps the original intent AND recent context for drill-down coherence."""
        if len(msgs) <= keep + 2:
            return msgs
        # Keep first 2 (original command context) + last `keep` (recent turns)
        anchor = msgs[:2]
        recent = msgs[-keep:]
        # Avoid duplicates if overlap
        seen_ids = {id(m) for m in anchor}
        deduped_recent = [m for m in recent if id(m) not in seen_ids]
        trimmed = anchor + deduped_recent
        # Ensure starts with user role (Anthropic API requirement)
        while trimmed and trimmed[0]["role"] != "user":
            trimmed = trimmed[1:]
        if not trimmed:
            return msgs
        logger.info("History trimmed: %d → %d messages (anchor=2, recent=%d)", len(msgs), len(trimmed), len(deduped_recent))
        return trimmed

    async def _fast_command(self, cmd: str, system: str, user_id: int, tools: list) -> str:
        """Fast path: call MCP tool directly, then Python template format."""
        tool_name, tool_args = COMMAND_TOOL_MAP[cmd]

        # Step 1: Permission check
        try:
            perm_result = await self.mcp.call_tool("odoo_telegram_check_permission", {
                "telegram_id": str(user_id),
                "command": cmd.lstrip("/"),
            })
            perm = json.loads(perm_result) if isinstance(perm_result, str) else perm_result
            if isinstance(perm, dict) and perm.get("allowed") is False:
                reason = perm.get("reason", "Không có quyền")
                return f"🚫 {reason}"
        except Exception as e:
            logger.error("Permission check failed for %s (fail-closed): %s", cmd, e)
            return "⚠️ Không thể kiểm tra quyền. Vui lòng thử lại sau."

        # Step 2: Call MCP tool
        logger.info("Fast path: %s → %s(%s)", cmd, tool_name, tool_args)
        try:
            result = await self.mcp.call_tool(tool_name, tool_args)
        except Exception as e:
            logger.error("Fast path tool %s failed: %s", tool_name, e)
            logger.error("Fast path tool %s error detail: %s", tool_name, e, exc_info=True)
            return f"❌ Lỗi gọi tool {tool_name}. Vui lòng thử lại."

        # Step 3: Python template format (no LLM!)
        formatted = format_command(cmd, result)
        if formatted:
            logger.info("Fast path formatted: %s → %d chars (no LLM)", cmd, len(formatted))
            return formatted

        # Fallback: LLM format with retry
        logger.info("Fast path fallback to LLM format for %s", cmd)
        format_prompt = (
            f"User gõ lệnh {cmd}. Dữ liệu từ Odoo:\n\n{result}\n\n"
            "Format thành báo cáo ngắn gọn cho Telegram. Dùng emoji + bullet list. KHÔNG dùng bảng."
        )
        for attempt in range(2):
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.messages.create,
                        model=LLM_MODEL,
                        max_tokens=self.MAX_TOKENS,
                        system=system,
                        messages=[{"role": "user", "content": format_prompt}],
                    ),
                    timeout=self.LLM_TIMEOUT,
                )
                text_parts = [b.text for b in response.content if b.type == "text"]
                return "\n".join(text_parts) or "Đã xử lý."
            except (asyncio.TimeoutError, anthropic.APITimeoutError):
                if attempt == 0:
                    logger.warning("Fast path LLM timeout, retrying...")
                    await asyncio.sleep(2)
                    continue
                return "⏱️ Request timeout. Vui lòng thử lại."
            except anthropic.APIError as e:
                return f"❌ Lỗi LLM: {e.message}"

    async def _tool_loop(self, msgs: list, system: str, tools: list, user_id: int) -> str:
        """Full tool-calling loop for free-form messages."""
        # Trim history to prevent context overflow and reduce latency
        msgs = self._trim_history(msgs, keep=8)

        for turn in range(self.MAX_TOOL_ROUNDS):
            logger.info("LLM call turn %d/%d (user_id=%s, history=%d)",
                        turn + 1, self.MAX_TOOL_ROUNDS, user_id, len(msgs))

            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.messages.create,
                        model=LLM_MODEL,
                        max_tokens=self.MAX_TOKENS,
                        system=system,
                        messages=msgs,
                        tools=tools,
                    ),
                    timeout=self.LLM_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.error("LLM hard timeout (%.0fs) on turn %d", self.LLM_TIMEOUT, turn + 1)
                return "⏱️ Hệ thống đang tải, vui lòng thử lại sau 10 giây."
            except anthropic.APITimeoutError:
                logger.error("LLM SDK timeout on turn %d", turn + 1)
                return "⏱️ Request timeout. Vui lòng thử lại."
            except anthropic.APIError as e:
                logger.error("LLM API error on turn %d: %s", turn + 1, e)
                return f"❌ Lỗi hệ thống LLM: {e.message}"

            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if not tool_use_blocks:
                text_parts = [b.text for b in response.content if b.type == "text"]
                result_text = "\n".join(text_parts)
                if not result_text:
                    logger.warning("Empty LLM response on turn %d (stop_reason=%s)",
                                   turn + 1, getattr(response, "stop_reason", "?"))
                    return "⚠️ Hệ thống không trả về phản hồi. Hội thoại quá dài — vui lòng bắt đầu câu hỏi mới."
                return result_text

            msgs.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in tool_use_blocks:
                logger.info(
                    "Tool call: %s(%s)",
                    block.name,
                    json.dumps(block.input, ensure_ascii=False, default=str)[:500],
                )
                try:
                    result = await self.mcp.call_tool(block.name, block.input)
                    if not isinstance(result, str):
                        result = json.dumps(result, ensure_ascii=False, default=str)

                    # Intercept PDF results
                    if block.name in PDF_TOOLS:
                        pdf_data = _extract_pdf(result)
                        if pdf_data:
                            self._pending_pdfs.setdefault(user_id, []).append(pdf_data)
                            result = _pdf_summary(pdf_data)
                            logger.info("PDF intercepted: %s (%d bytes)",
                                        pdf_data.get("filename"), pdf_data.get("size_bytes", 0))

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
                    logger.info("Tool %s returned %d chars", block.name, len(result))
                except Exception as e:
                    logger.error("Tool %s failed: %s", block.name, e)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Error: {e}",
                        "is_error": True,
                    })

            msgs.append({"role": "user", "content": tool_results})

        return "⚠️ Đã vượt giới hạn xử lý. Vui lòng thử lại với yêu cầu đơn giản hơn."
