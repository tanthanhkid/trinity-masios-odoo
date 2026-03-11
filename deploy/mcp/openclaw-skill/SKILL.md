---
name: odoo-crm
description: Quản lý Odoo 18 — bán hàng, hóa đơn, công nợ, CRM, dashboard. Dùng khi user hỏi về khách hàng, đơn hàng, hóa đơn, công nợ, pipeline, leads, doanh thu, hoặc bất kỳ dữ liệu Odoo nào.
allowed-tools: Bash
metadata:
  {
    "openclaw":
      {
        "emoji": "🏢",
        "requires": { "bins": ["mcporter"] },
      },
  }
---

# Odoo Business Management Skill

BẮT BUỘC: Khi user hỏi về Odoo data, bạn PHẢI chạy lệnh mcporter trong Bash tool. KHÔNG BAO GIỜ chỉ gợi ý lệnh cho user chạy tay. Bạn CÓ quyền chạy Bash.

## Cách gọi tool

Luôn dùng Bash tool để chạy:
```bash
mcporter call odoo.<tool_name> key=value
```

## 24 Tools có sẵn

### Khi user hỏi "tổng quan / dashboard / doanh thu / KPI"
```bash
mcporter call odoo.odoo_dashboard_kpis
```

### Khi user hỏi "pipeline / CRM / deals / giai đoạn"
```bash
mcporter call odoo.odoo_pipeline_by_stage
mcporter call odoo.odoo_crm_stages
mcporter call odoo.odoo_crm_lead_summary
```

### Khi user hỏi "đơn hàng / sale order / báo giá"
```bash
mcporter call odoo.odoo_sale_order_summary
mcporter call odoo.odoo_sale_order_summary partner_id=5 state=sale
```

### Khi user muốn "tạo đơn hàng / tạo báo giá"
```bash
mcporter call odoo.odoo_create_sale_order partner_id=ID 'order_lines=[{"product_id":1,"quantity":10}]'
```

### Khi user muốn "xác nhận đơn hàng"
```bash
mcporter call odoo.odoo_confirm_sale_order order_id=ID
```

### Khi user hỏi "hóa đơn / invoice / thanh toán"
```bash
mcporter call odoo.odoo_invoice_summary
mcporter call odoo.odoo_invoice_summary partner_id=5 state=posted
```

### Khi user muốn "tạo hóa đơn từ đơn hàng"
```bash
mcporter call odoo.odoo_create_invoice_from_so order_id=ID
```

### Khi user hỏi "công nợ / credit / hạn mức"
```bash
mcporter call odoo.odoo_customer_credit_status partner_id=ID
mcporter call odoo.odoo_customers_exceeding_credit
```

### Khi user muốn "đổi phân loại khách hàng"
```bash
mcporter call odoo.odoo_customer_set_classification partner_id=ID classification=old
```

### Khi user muốn "tạo khách hàng"
```bash
mcporter call odoo.odoo_create_customer name="Tên công ty" phone=0901234567 email=abc@company.vn company_type=company
```

### Khi user muốn tìm khách hàng
```bash
mcporter call odoo.odoo_search_read model=res.partner 'domain=[["name","ilike","keyword"]]' fields=id,name,phone,email,customer_classification,credit_limit,outstanding_debt limit=10
```

### Khi user muốn xem sản phẩm
```bash
mcporter call odoo.odoo_search_read model=product.product fields=id,name,list_price limit=20
```

### Khi user hỏi "hệ thống / kết nối / phiên bản"
```bash
mcporter call odoo.odoo_server_info
```

### Tools khám phá
```bash
mcporter call odoo.odoo_list_models filter=sale
mcporter call odoo.odoo_model_fields model=sale.order
mcporter call odoo.odoo_model_access model=sale.order
mcporter call odoo.odoo_model_views model=sale.order
```

### Thực thi method tùy chỉnh (advanced)
```bash
mcporter call odoo.odoo_execute model=sale.order method=action_confirm 'args=[[ORDER_ID]]'
```

### CRUD tổng quát
```bash
mcporter call odoo.odoo_search_read model=MODEL 'domain=FILTER' fields=FIELDS limit=N
mcporter call odoo.odoo_count model=MODEL 'domain=FILTER'
mcporter call odoo.odoo_create model=MODEL 'values=JSON'
mcporter call odoo.odoo_write model=MODEL 'ids=[ID]' 'values=JSON'
mcporter call odoo.odoo_delete model=MODEL 'ids=[ID]'
```

## Quy tắc kinh doanh

- **KH mới (new)**: Mặc định. Không cho phép công nợ.
- **KH cũ (old)**: Được phép công nợ trong hạn mức credit_limit.
- Xác nhận đơn hàng tự động kiểm tra công nợ.

## Domain Filter Syntax
```
[["field", "=", value]]
[["state", "=", "sale"], ["partner_id", "=", 5]]
["|", ["state", "=", "draft"], ["state", "=", "sent"]]
```

## QUAN TRỌNG
- LUÔN chạy lệnh bằng Bash tool, KHÔNG suggest cho user
- Trả lời bằng tiếng Việt
- Format kết quả dạng bảng/bullet cho dễ đọc
- Nếu lỗi, thử lại hoặc giải thích lỗi
- KHÔNG BAO GIỜ xóa record mà không hỏi user xác nhận trước. Luôn hỏi "Bạn có chắc muốn xóa [tên record]?" và đợi phản hồi.
- Khi xóa, LUÔN liệt kê cụ thể record nào sẽ bị xóa (tên, ID) trước khi thực hiện.
