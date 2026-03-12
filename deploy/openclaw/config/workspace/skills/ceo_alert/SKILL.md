---
name: ceo_alert
description: Cảnh báo khẩn cấp cho CEO — top 3-5 vấn đề
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🚨", "requires": { "bins": ["mcporter"] } } }
---

# Cảnh Báo CEO

## Workflow
1. Chạy ngay odoo_ceo_alert — KHÔNG hỏi gì thêm
2. Hiển thị top 3-5 vấn đề critical nhất
3. Mỗi alert: mức độ + mô tả + action cần làm

## Commands

### Lấy CEO Alerts
```bash
mcporter call odoo.odoo_ceo_alert
```

## Drill-down
Sau khi hiển thị, gợi ý dựa trên loại alert:
- Alert về lead/pipeline: "Gõ /hunter_today hoặc /hunter_sla để xem chi tiết"
- Alert về công nợ: "Gõ /congno_quahan để xem chi tiết"
- Alert về khách ngủ đông: "Gõ /farmer_sleeping để xem chi tiết"
- Alert về task: "Gõ /task_quahan để xem chi tiết"

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Ưu tiên hiển thị vấn đề nghiêm trọng nhất trước
