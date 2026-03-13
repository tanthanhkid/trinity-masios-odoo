import anthropic
import asyncio
import json
import logging

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
    "/khachmoi_homnay": ("odoo_hunter_today", {"section": "leads"}),
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


class MasiAgent:
    MAX_TOOL_ROUNDS = 10
    MAX_TOKENS = 4096

    def __init__(self, mcp_client):
        self.mcp = mcp_client
        self.client = anthropic.Anthropic(
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
            timeout=60.0,
        )

    async def chat(self, messages: list[dict], telegram_user_id: int) -> str:
        tools = self.mcp.get_anthropic_tools()
        system = SYSTEM_PROMPT + f"\n\nTelegram user ID hiện tại: {telegram_user_id}"
        msgs = [m.copy() for m in messages]

        # Fast path: known slash commands → call MCP directly, then 1 LLM call to format
        last_msg = msgs[-1]["content"] if msgs else ""
        cmd = last_msg.strip().split()[0] if last_msg.strip() else ""

        if cmd in COMMAND_TOOL_MAP:
            return await self._fast_command(cmd, system, telegram_user_id, tools)

        # Normal path: full tool-calling loop
        return await self._tool_loop(msgs, system, tools, telegram_user_id)

    async def _fast_command(self, cmd: str, system: str, user_id: int, tools: list) -> str:
        """Fast path: call MCP tool directly, then 1 LLM call to format."""
        tool_name, tool_args = COMMAND_TOOL_MAP[cmd]

        # Step 1: Permission check (direct MCP call, no LLM)
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
            logger.warning("Permission check failed for %s: %s", cmd, e)
            # Continue anyway — don't block on permission errors

        # Step 2: Call the actual MCP tool directly
        logger.info("Fast path: %s → %s(%s)", cmd, tool_name, tool_args)
        try:
            result = await self.mcp.call_tool(tool_name, tool_args)
        except Exception as e:
            logger.error("Fast path tool %s failed: %s", tool_name, e)
            return f"❌ Lỗi gọi tool {tool_name}: {e}"

        # Step 3: Format with Python template (no LLM needed!)
        formatted = format_command(cmd, result)
        if formatted:
            logger.info("Fast path formatted: %s → %d chars (no LLM)", cmd, len(formatted))
            return formatted

        # Fallback: LLM format if template fails
        logger.info("Fast path fallback to LLM format for %s", cmd)
        format_prompt = (
            f"User gõ lệnh {cmd}. Dữ liệu từ Odoo:\n\n{result}\n\n"
            "Format thành báo cáo ngắn gọn cho Telegram. Dùng emoji + bullet list. KHÔNG dùng bảng."
        )
        try:
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=LLM_MODEL,
                max_tokens=self.MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": format_prompt}],
            )
            text_parts = [b.text for b in response.content if b.type == "text"]
            return "\n".join(text_parts) or "Đã xử lý."
        except anthropic.APITimeoutError:
            return "⏱️ Request timeout. Vui lòng thử lại."
        except anthropic.APIError as e:
            return f"❌ Lỗi LLM: {e.message}"

    async def _tool_loop(self, msgs: list, system: str, tools: list, user_id: int) -> str:
        """Full tool-calling loop for free-form messages."""
        for turn in range(self.MAX_TOOL_ROUNDS):
            logger.info("LLM call turn %d (user_id=%s)", turn + 1, user_id)

            try:
                response = await asyncio.to_thread(
                    self.client.messages.create,
                    model=LLM_MODEL,
                    max_tokens=self.MAX_TOKENS,
                    system=system,
                    messages=msgs,
                    tools=tools,
                )
            except anthropic.APITimeoutError:
                logger.error("LLM timeout on turn %d", turn + 1)
                return "⏱️ Request timeout. Vui lòng thử lại."
            except anthropic.APIError as e:
                logger.error("LLM API error on turn %d: %s", turn + 1, e)
                return f"❌ Lỗi hệ thống LLM: {e.message}"

            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if not tool_use_blocks:
                text_parts = [b.text for b in response.content if b.type == "text"]
                return "\n".join(text_parts) or "Đã xử lý."

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

        return "⚠️ Đã vượt giới hạn xử lý (10 rounds). Vui lòng thử lại với yêu cầu đơn giản hơn."
