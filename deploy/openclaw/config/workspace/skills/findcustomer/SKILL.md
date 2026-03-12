---
name: findcustomer
description: Tìm khách hàng — hỏi keyword rồi search ngay
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🔍", "requires": { "bins": ["mcporter"] } } }
---

# Tìm Khách Hàng

## Workflow
1. Hỏi user: keyword tìm kiếm (tên, phone, email)
2. Search ngay trong hệ thống
3. Hiển thị danh sách: ID, tên, phone, email, phân loại, công nợ

## Commands

### Tìm theo tên
```bash
mcporter call odoo.odoo_search_read model=res.partner 'domain=[["name","ilike","KEYWORD"]]' fields=id,name,phone,email,customer_classification,credit_limit,outstanding_debt limit=10
```

### Tìm theo phone
```bash
mcporter call odoo.odoo_search_read model=res.partner 'domain=[["phone","ilike","KEYWORD"]]' fields=id,name,phone,email,customer_classification limit=10
```

### Tìm theo email
```bash
mcporter call odoo.odoo_search_read model=res.partner 'domain=[["email","ilike","KEYWORD"]]' fields=id,name,phone,email,customer_classification limit=10
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Format bảng dễ đọc
- Thử tìm theo tên trước, nếu không có thử phone/email
