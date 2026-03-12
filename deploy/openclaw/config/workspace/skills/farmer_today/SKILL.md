---
name: farmer_today
description: Tổng quan Farmer hôm nay — tất cả sections
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🌿", "requires": { "bins": ["mcporter"] } } }
---

# Farmer Hôm Nay — Tổng Quan

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="farmer_today"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_farmer_today section=all — KHÔNG hỏi gì thêm
   ⚠️ Kiểm tra data_quality: Nếu MCP tool trả về data_quality = "issue" hoặc "warning", PHẢI hiển thị phần DATA ISSUE trước báo cáo:
   "⚠️ DATA ISSUE: [liệt kê data_issues]. Số liệu dưới đây có thể chưa đầy đủ."
2. Hiển thị: reorder, sleeping, VIP, retention
3. Format từng section rõ ràng

## Commands

### Lấy Farmer Overview
```bash
mcporter call odoo.odoo_farmer_today section=all
```

## Drill-down & Điều hướng
Sau khi hiển thị báo cáo, LUÔN thêm:

🔍 Drill-down:
/farmer_reorder — Khách cần tái đặt hàng
/farmer_sleeping — Khách ngủ đông
/farmer_vip — Khách VIP cần chăm
/farmer_ar — Công nợ Farmer

🔙 /brief_farmer ← Quay lại | /masi ← Menu chính

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Format dễ đọc trên Telegram
