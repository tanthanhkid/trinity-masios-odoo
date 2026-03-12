---
name: brief_cash
description: Tổng hợp thu tiền — cash collection
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "💵", "requires": { "bins": ["mcporter"] } } }
---

# Báo Cáo Thu Tiền

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="brief_cash"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_brief_cash — KHÔNG hỏi gì thêm
   ⚠️ Kiểm tra data_quality: Nếu MCP tool trả về data_quality = "issue" hoặc "warning", PHẢI hiển thị phần DATA ISSUE trước báo cáo:
   "⚠️ DATA ISSUE: [liệt kê data_issues]. Số liệu dưới đây có thể chưa đầy đủ."
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

## Drill-down & Điều hướng
Sau khi hiển thị báo cáo, LUÔN thêm:

🔍 Drill-down:
/congno_denhan — Công nợ đến hạn
/brief_ar — Tổng hợp công nợ

🔙 /morning_brief ← Quay lại | /masi ← Menu chính
