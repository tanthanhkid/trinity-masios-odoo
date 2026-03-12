---
name: credit
description: Kiểm tra công nợ khách hàng — hỏi tên KH rồi tra luôn
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "💰", "requires": { "bins": ["mcporter"] } } }
---

# Kiểm Tra Công Nợ

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="credit"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Hỏi user: tên khách hàng
2. Tìm KH trong hệ thống
3. Tra credit status ngay
4. Báo kết quả: phân loại, hạn mức, dư nợ, tình trạng

## Commands

### Tìm khách hàng
```bash
mcporter call odoo.odoo_search_read model=res.partner 'domain=[["name","ilike","KEYWORD"]]' fields=id,name,customer_classification,credit_limit,outstanding_debt limit=10
```

### Tra credit status
```bash
mcporter call odoo.odoo_customer_credit_status partner_id=ID
```

### Xem KH vượt hạn mức (nếu cần)
```bash
mcporter call odoo.odoo_customers_exceeding_credit
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Format rõ ràng: phân loại, hạn mức, dư nợ hiện tại
