---
name: morning_brief
description: Báo cáo buổi sáng CEO — Hunter/Farmer/AR/Alerts
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🌅", "requires": { "bins": ["mcporter"] } } }
---

# Báo Cáo Buổi Sáng

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="morning_brief"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_morning_brief — KHÔNG hỏi gì thêm
   ⚠️ Kiểm tra data_quality: Nếu MCP tool trả về data_quality = "issue" hoặc "warning", PHẢI hiển thị phần DATA ISSUE trước báo cáo:
   "⚠️ DATA ISSUE: [liệt kê data_issues]. Số liệu dưới đây có thể chưa đầy đủ."
2. Format thành 4 block: Hunter | Farmer | AR | Alerts
3. Mỗi block có emoji + số liệu chính

## Commands

### Lấy Morning Brief
```bash
mcporter call odoo.odoo_morning_brief
```

## Drill-down
Sau khi hiển thị, LUÔN thêm:

🔍 Drill-down:
/ceo_alert — Xem vấn đề khẩn cấp
/brief_hunter — Chi tiết team Hunter
/brief_farmer — Chi tiết team Farmer
/brief_ar — Chi tiết công nợ
/brief_cash — Dòng tiền

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Format 4 block rõ ràng cho Telegram
