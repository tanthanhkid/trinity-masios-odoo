---
name: hunter_today
description: Tổng quan Hunter hôm nay — tất cả sections
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🏹", "requires": { "bins": ["mcporter"] } } }
---

# Hunter Hôm Nay — Tổng Quan

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="hunter_today"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_hunter_today section=all — KHÔNG hỏi gì thêm
   ⚠️ Kiểm tra data_quality: Nếu MCP tool trả về data_quality = "issue" hoặc "warning", PHẢI hiển thị phần DATA ISSUE trước báo cáo:
   "⚠️ DATA ISSUE: [liệt kê data_issues]. Số liệu dưới đây có thể chưa đầy đủ."
2. Hiển thị tổng quan: leads, quotes, first orders, sources
3. Format từng section rõ ràng

## Commands

### Lấy Hunter Overview
```bash
mcporter call odoo.odoo_hunter_today section=all
```

## Drill-down & Điều hướng
Sau khi hiển thị báo cáo, LUÔN thêm:

🔍 Drill-down:
/hunter_sla — SLA phản hồi lead
/hunter_quotes — Báo giá chờ duyệt
/hunter_first_orders — Đơn hàng đầu tiên
/hunter_sources — Nguồn lead
/khachmoi_homnay — Khách mới hôm nay

🔙 /brief_hunter ← Quay lại | /masi ← Menu chính

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Format dễ đọc trên Telegram
