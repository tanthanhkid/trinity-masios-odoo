# Masi Telegram Bot v2 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Thay thế OpenClaw bằng bot Telegram nhẹ, nhanh, tuân thủ — dùng python-telegram-bot + Anthropic SDK + GLM-5 + MCP client.

**Architecture:** Bot polling Telegram messages → gọi GLM-5 (Alibaba Anthropic-compatible API) với tool_use → MCP SSE client gọi Odoo MCP server (port 8200) → trả kết quả về Telegram. Không framework nặng, không personality engine.

**Tech Stack:** python-telegram-bot 21.x, anthropic SDK, mcp SDK (client), Docker

---

### Task 1: Project scaffold + config

**Files:**
- Create: `deploy/masi-bot/config.py`
- Create: `deploy/masi-bot/requirements.txt`

**Step 1: Create requirements.txt**

```
python-telegram-bot==21.7
anthropic>=0.42.0
mcp>=1.0.0
python-dotenv==1.0.1
```

**Step 2: Create config.py**

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_WHITELIST = {
    2048339435,  # CEO Minh Sang
    1481072032,  # Hunter Lead
}

# GLM-5 via Alibaba (Anthropic-compatible)
LLM_BASE_URL = "https://coding-intl.dashscope.aliyuncs.com/apps/anthropic"
LLM_API_KEY = os.environ["ALIBABA_API_KEY"]
LLM_MODEL = "glm-5"

# Odoo MCP Server
MCP_SERVER_URL = os.environ.get("ODOO_MCP_URL", "http://103.72.97.51:8200/sse")
MCP_API_TOKEN = os.environ.get("ODOO_MCP_TOKEN", "")

# System prompt — ngắn gọn, tuân thủ
SYSTEM_PROMPT = """Bạn là trợ lý AI của Masi OS, kết nối trực tiếp Odoo 18.
Trả lời tiếng Việt có dấu. Thuật ngữ kỹ thuật giữ tiếng Anh.

QUY TẮC:
1. Gọi tool ngay khi có thể, không hỏi lại trừ khi thiếu thông tin bắt buộc
2. KHÔNG bịa số liệu — chỉ dùng dữ liệu từ tools
3. Format ngắn gọn cho Telegram (bullets, emoji)
4. Kiểm tra quyền bằng odoo_telegram_check_permission TRƯỚC mỗi command
5. Hành động nhạy cảm (doi_owner, gan_dispute, escalate, tao_task): hỏi xác nhận trước
6. Sau mỗi thay đổi state: gọi odoo_audit_log
7. Khi data rỗng: nói "Chưa có dữ liệu", KHÔNG trả số 0 giả
8. Khi data_quality = "issue": hiển thị "⚠️ DATA ISSUE" trước báo cáo
"""
```

**Step 3: Commit**
```bash
git add deploy/masi-bot/
git commit -m "feat(masi-bot): Project scaffold with config and dependencies"
```

---

### Task 2: MCP Client — kết nối SSE + discover/call tools

**Files:**
- Create: `deploy/masi-bot/mcp_client.py`

**Step 1: Create mcp_client.py**

MCP SSE client kết nối đến Odoo MCP server, discover tất cả tools lúc startup, và cung cấp hàm call_tool() để gọi tool theo tên.

Cần handle:
- SSE connection với bearer token auth
- `list_tools()` → cache tool schemas
- `call_tool(name, args)` → trả kết quả JSON string
- Reconnect khi mất kết nối
- Convert tool schemas sang Anthropic tool format

**Step 2: Commit**
```bash
git add deploy/masi-bot/mcp_client.py
git commit -m "feat(masi-bot): MCP SSE client with tool discovery and calling"
```

---

### Task 3: Agent — GLM-5 tool calling loop

**Files:**
- Create: `deploy/masi-bot/agent.py`

**Step 1: Create agent.py**

Anthropic SDK gọi GLM-5 qua Alibaba endpoint. Tool calling loop:
1. Gửi messages + tools → GLM-5
2. Nếu response có tool_use blocks → thực thi qua MCP client
3. Append tool_result → gọi lại GLM-5
4. Loop cho đến khi GLM-5 trả text (không tool_use)
5. Return text response

Cần handle:
- Max 10 tool calls per turn (tránh loop vô hạn)
- Timeout 60s per LLM call
- Error handling: MCP tool fail → trả error message cho LLM để nó format lỗi

**Step 2: Commit**
```bash
git add deploy/masi-bot/agent.py
git commit -m "feat(masi-bot): GLM-5 agent with tool calling loop"
```

---

### Task 4: Telegram Bot — handler + RBAC

**Files:**
- Create: `deploy/masi-bot/bot.py`

**Step 1: Create bot.py**

python-telegram-bot polling mode:
- `/start` → welcome message
- `/masi` → gọi agent với "hiển thị menu commands"
- Mọi text message → kiểm tra whitelist → gọi agent → trả response
- Conversation memory: giữ 20 messages gần nhất per user (in-memory dict)
- Telegram markdown formatting
- Typing indicator khi đang xử lý
- Split messages > 4096 chars

**Step 2: Commit**
```bash
git add deploy/masi-bot/bot.py
git commit -m "feat(masi-bot): Telegram bot with RBAC and message handling"
```

---

### Task 5: Docker deployment

**Files:**
- Create: `deploy/masi-bot/Dockerfile`
- Create: `deploy/masi-bot/docker-compose.yml`
- Create: `deploy/masi-bot/.env.example`

**Step 1: Create Dockerfile**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

**Step 2: Create docker-compose.yml**

```yaml
services:
  masi-bot:
    build: .
    container_name: masi-bot
    restart: always
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - ALIBABA_API_KEY=${ALIBABA_API_KEY}
      - ODOO_MCP_URL=${ODOO_MCP_URL:-http://103.72.97.51:8200/sse}
      - ODOO_MCP_TOKEN=${ODOO_MCP_TOKEN}
    healthcheck:
      test: ["CMD", "python", "-c", "import os; print('ok')"]
      interval: 30s
      timeout: 5s
      retries: 3
```

**Step 3: Create .env.example**

```bash
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
ALIBABA_API_KEY=your-alibaba-api-key
ODOO_MCP_URL=http://127.0.0.1:8200/sse
ODOO_MCP_TOKEN=your-mcp-bearer-token
```

**Step 4: Commit**
```bash
git add deploy/masi-bot/
git commit -m "feat(masi-bot): Docker deployment config"
```

---

### Task 6: Integration test + deploy to Mac Studio

**Step 1: Test local (without Docker)**
```bash
cd deploy/masi-bot
pip install -r requirements.txt
# Set env vars
python bot.py
# Gửi tin nhắn test từ Telegram
```

**Step 2: Deploy to Mac Studio**
- SCP files đến Mac Studio
- Build + run Docker container
- Verify bot respond trên Telegram

**Step 3: Final commit**
```bash
git commit -m "feat(masi-bot): Integration tested and deployed"
```
