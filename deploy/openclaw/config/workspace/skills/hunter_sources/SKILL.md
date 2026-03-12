---
name: hunter_sources
description: Phân tích nguồn lead — hiệu quả kênh
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "📡", "requires": { "bins": ["mcporter"] } } }
---

# Nguồn Lead — Phân Tích Kênh

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
