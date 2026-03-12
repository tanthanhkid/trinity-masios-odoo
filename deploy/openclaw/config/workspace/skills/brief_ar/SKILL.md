---
name: brief_ar
description: Tổng hợp công nợ phải thu (AR aging)
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "📋", "requires": { "bins": ["mcporter"] } } }
---

# Báo Cáo Công Nợ Phải Thu

## Workflow
1. Chạy ngay odoo_brief_ar — KHÔNG hỏi gì thêm
2. Hiển thị AR aging: current, 1-30, 31-60, 61-90, >90 ngày
3. Tổng số dư và phân bổ theo bucket

## Commands

### Lấy AR Summary
```bash
mcporter call odoo.odoo_brief_ar
```

## Drill-down
Sau khi hiển thị, gợi ý: "Gõ /congno_denhan để xem công nợ đến hạn, /congno_quahan để xem công nợ quá hạn"

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Format bảng aging dễ đọc trên Telegram
