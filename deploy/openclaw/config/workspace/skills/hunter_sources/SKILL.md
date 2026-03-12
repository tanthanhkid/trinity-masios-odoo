---
name: hunter_sources
description: Phân tích nguồn lead — hiệu quả kênh
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "📡", "requires": { "bins": ["mcporter"] } } }
---

# Nguồn Lead — Phân Tích Kênh

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="hunter_sources"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_hunter_today section=sources — KHÔNG hỏi gì thêm
2. Breakdown theo nguồn: số lead, conversion, giá trị
3. So sánh hiệu quả các kênh

## Commands

### Lấy Lead Sources
```bash
mcporter call odoo.odoo_hunter_today section=sources
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Format bảng so sánh các nguồn

## Điều hướng
🔙 /hunter_today ← Quay lại | /masi ← Menu chính
