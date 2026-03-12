---
name: midday
description: Flash report giữa ngày — tóm tắt nhanh
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "☀️", "requires": { "bins": ["mcporter"] } } }
---

# Flash Report Giữa Ngày

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="midday"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_flash_report report_type=midday — KHÔNG hỏi gì thêm
2. Tóm tắt tiến độ nửa ngày: doanh số, leads, tasks
3. So sánh với target ngày

## Commands

### Lấy Midday Flash
```bash
mcporter call odoo.odoo_flash_report report_type=midday
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Format ngắn gọn, dễ scan trên Telegram

## Drill-down & Điều hướng
Sau khi hiển thị báo cáo, LUÔN thêm:

🔍 Drill-down:
/doanhso_homnay — Doanh số chi tiết
/task_quahan — Task quá hạn

🔙 /masi ← Menu chính
