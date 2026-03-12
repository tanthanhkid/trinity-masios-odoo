---
name: hunter_sla
description: Leads vi phạm SLA — cần xử lý gấp
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "⏰", "requires": { "bins": ["mcporter"] } } }
---

# Hunter SLA — Leads Vi Phạm

## Workflow
1. Chạy ngay odoo_hunter_sla_details — KHÔNG hỏi gì thêm
2. Liệt kê từng lead vi phạm SLA: tên, thời gian, nhân viên
3. Gợi ý action cần làm cho mỗi lead

## Commands

### Lấy SLA Details
```bash
mcporter call odoo.odoo_hunter_sla_details
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Highlight leads quá hạn lâu nhất
