---
name: masi
triggers:
  - /masi
  - menu
  - help
  - commands
---

# Menu Command Center

## Bước thực hiện:

1. Lấy Telegram user ID từ session context
2. Gọi MCP: `mcporter call odoo.odoo_telegram_get_menu telegram_id="<ID>"`
3. Nếu lỗi hoặc user chưa đăng ký: hiển thị "🚫 Bạn chưa được đăng ký trong hệ thống. Liên hệ admin."
4. Hiển thị menu theo format:

```
🏢 MASI OS Command Center
👤 [user_name] | Vai trò: [role_name]

[Cho mỗi category có commands:]
[category.label]
  /[command] — [description]
  /[command] — [description]

[Category tiếp theo...]

⚡ Hành động nhanh (nếu có):
  da_lien_he <ID> — [description]
  ...

💡 Gõ /command để thực hiện. Quyền được quản lý bởi admin trên Odoo.
```

5. Chỉ hiển thị categories và commands mà MCP trả về (đã lọc theo quyền)
6. KHÔNG hardcode danh sách commands — luôn lấy từ MCP

Hoặc bạn có thể chat tự nhiên, ví dụ:
- "Tổng quan doanh thu tháng này"
- "Tìm khách hàng ABC"
- "Tạo báo giá cho công ty XYZ"
