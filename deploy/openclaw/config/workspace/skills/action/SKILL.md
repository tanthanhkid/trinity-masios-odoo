---
name: action
triggers:
  - da_lien_he
  - da_nhac_no
  - gan_dispute
  - doi_owner
  - escalate
  - tao_task
  - xong
  - xac_nhan
---

# Xử lý hành động nhanh

## Kiểm tra quyền (BẮT BUỘC trước mỗi action):
1. Lấy Telegram user ID từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" action="<action_name>"`
3. Nếu allowed=false: "🚫 {reason}" → DỪNG, không thực hiện
4. Nếu allowed=true: tiếp tục xử lý action

Khi user gửi lệnh hành động, xử lý như sau:

## Các lệnh an toàn (thực hiện ngay):
- `da_lien_he <lead_id>` → Gọi `mcporter call odoo.odoo_mark_contacted lead_id=<ID>`. Trả về: "✅ Đã đánh dấu liên hệ lead #<ID>"
- `da_nhac_no <invoice_id>` → Gọi `mcporter call odoo.odoo_mark_collection invoice_id=<ID> status=reminded`. Trả về: "✅ Đã đánh dấu nhắc nợ hóa đơn #<ID>"
- `xong <task_id>` → Gọi `mcporter call odoo.odoo_complete_task task_id=<ID>`. Trả về: "✅ Task #<ID> đã hoàn thành"

## Các lệnh nhạy cảm (cần xác nhận 2 bước):
- `doi_owner <model> <record_id> <new_user_id>` → Trước khi thực hiện, HỎI: "⚠️ Bạn muốn đổi người phụ trách record #<ID> sang user #<new_user_id>? Gõ `xac_nhan` để thực hiện."
- `gan_dispute <invoice_id> "<lý do>"` → HỎI: "⚠️ Bạn muốn gắn tranh chấp cho hóa đơn #<ID> với lý do: <lý do>? Gõ `xac_nhan` để thực hiện."
- `escalate <model> <record_id>` → HỎI: "⚠️ Bạn muốn escalate record #<ID>? Sẽ tạo task escalation. Gõ `xac_nhan` để thực hiện."
- `tao_task "<mô tả>" <partner_id>` → HỎI: "⚠️ Tạo task: <mô tả> cho KH #<partner_id>? Gõ `xac_nhan` để thực hiện."

## Xử lý `xac_nhan`:
Khi user gõ `xac_nhan`, thực hiện lệnh nhạy cảm đã hỏi trước đó:
- doi_owner → `mcporter call odoo.odoo_change_owner model=<model> record_id=<ID> new_user_id=<new_user_id>`
- gan_dispute → `mcporter call odoo.odoo_set_dispute invoice_id=<ID> note="<lý do>"`
- escalate → `mcporter call odoo.odoo_escalate model=<model> record_id=<ID> note="Escalated via Telegram"`
- tao_task → `mcporter call odoo.odoo_create model=project.task 'values={"name":"<mô tả>","related_partner_id":<partner_id>,"task_category":"follow_up"}'`

Sau mỗi action, gọi `mcporter call odoo.odoo_audit_log action="<action>" model="<model>" record_id=<ID> user_telegram_id="<session_user_id>" details="<chi tiết>"`.

## Lưu ý về quyền:
Tất cả quyền được quản lý trên Odoo. KHÔNG dùng role_config.json. Luôn gọi MCP tool `odoo_telegram_check_permission` để kiểm tra trước mỗi action.
