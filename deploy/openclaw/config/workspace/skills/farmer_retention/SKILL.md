---
name: farmer_retention
description: Chỉ số giữ chân khách hàng — retention metrics
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🤝", "requires": { "bins": ["mcporter"] } } }
---

# Retention Metrics

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="farmer_retention"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_farmer_today section=retention — KHÔNG hỏi gì thêm
2. Hiển thị: tỷ lệ giữ chân, churn rate, trend
3. So sánh với kỳ trước nếu có

## Commands

### Lấy Retention Metrics
```bash
mcporter call odoo.odoo_farmer_today section=retention
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Highlight chỉ số cần cải thiện

## Điều hướng
🔙 /farmer_today ← Quay lại | /masi ← Menu chính
