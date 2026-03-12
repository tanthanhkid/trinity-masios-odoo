---
name: brief_cash
description: Tổng hợp thu tiền — cash collection
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "💵", "requires": { "bins": ["mcporter"] } } }
---

# Báo Cáo Thu Tiền

## Workflow
1. Chạy ngay odoo_brief_cash — KHÔNG hỏi gì thêm
2. Hiển thị: tổng thu, theo kênh, theo nhân viên
3. So sánh với target nếu có

## Commands

### Lấy Cash Collection
```bash
mcporter call odoo.odoo_brief_cash
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Format bảng/bullet dễ đọc trên Telegram
