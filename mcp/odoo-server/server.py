#!/usr/bin/env python3
"""
Odoo MCP Server — Real-time bridge between AI agents and Odoo instance.

Exposes Odoo's XML-RPC API as MCP tools for:
- Model/field introspection (types, constraints, relations)
- CRUD operations on any model
- CRM-specific helpers

Requires: pip install mcp (xmlrpc is stdlib)
"""

import hashlib
import hmac
import json
import os
import secrets
import sys
import xmlrpc.client
from functools import lru_cache
from pathlib import Path
from typing import Any

# MCP SDK
try:
    from mcp.server.fastmcp import FastMCP
    from mcp.server.transport_security import TransportSecuritySettings
except ImportError:
    print("ERROR: Install mcp package: pip install mcp", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Load Odoo connection config from environment or .env.local file."""
    env_file = Path(__file__).resolve().parent.parent.parent / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))

    return {
        "url": os.environ.get("ODOO_URL", ""),
        "db": os.environ.get("ODOO_DB", ""),
        "username": os.environ.get("ODOO_USERNAME", ""),
        "password": os.environ.get("ODOO_PASSWORD", ""),
        "api_token": os.environ.get("MCP_API_TOKEN", ""),
    }


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def _odoo_error(func):
    """Decorator: catch XML-RPC and connection errors, return structured JSON."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except xmlrpc.client.Fault as e:
            msg = e.faultString
            if "\n" in msg:
                msg = msg.strip().split("\n")[-1]
            return json.dumps({"error": msg, "fault_code": e.faultCode})
        except (ConnectionRefusedError, OSError) as e:
            return json.dumps({"error": f"Cannot reach Odoo server: {e}"})
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON input: {e}"})
        except ValueError as e:
            return json.dumps({"error": str(e)})
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    wrapper.__wrapped__ = func
    return wrapper


def _parse_json(val: Any) -> Any:
    """Parse JSON string or pass through already-parsed objects.
    Validates that the result is a list when used for domain parameters."""
    if isinstance(val, (dict, list, int, float, bool)):
        return val
    return json.loads(val)


def _parse_domain(val: Any) -> list:
    """Parse and validate an Odoo domain filter (must be a list)."""
    result = _parse_json(val)
    if not isinstance(result, list):
        raise ValueError(f"Domain must be a list, got {type(result).__name__}")
    return result


def _parse_ids(val: Any) -> list[int]:
    """Parse and validate a list of record IDs."""
    result = _parse_json(val)
    if not isinstance(result, list):
        raise ValueError(f"IDs must be a list, got {type(result).__name__}")
    if not all(isinstance(i, int) for i in result):
        raise ValueError("All IDs must be integers")
    return result


def _parse_values(val: Any) -> dict:
    """Parse and validate a values dict for create/write."""
    result = _parse_json(val)
    if not isinstance(result, dict):
        raise ValueError(f"Values must be a dict, got {type(result).__name__}")
    return result


# ---------------------------------------------------------------------------
# Odoo XML-RPC Client
# ---------------------------------------------------------------------------

class OdooClient:
    """Thin wrapper around Odoo's XML-RPC API."""

    def __init__(self, url: str, db: str, username: str, password: str):
        self.url = url.rstrip("/")
        self.db = db
        self.username = username
        self.password = password
        self._uid = None
        self._common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
        self._object = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")

    @property
    def uid(self) -> int:
        if self._uid is None:
            self._uid = self._common.authenticate(
                self.db, self.username, self.password, {}
            )
            if not self._uid:
                raise ConnectionError(
                    f"Authentication failed for {self.username}@{self.db}"
                )
        return self._uid

    def execute(self, model: str, method: str, *args, **kwargs) -> Any:
        return self._object.execute_kw(
            self.db, self.uid, self.password, model, method, list(args), kwargs
        )

    @lru_cache(maxsize=64)
    def fields_get_cached(self, model: str, attrs_tuple: tuple) -> dict:
        """Cached version of fields_get (attrs as tuple for hashability)."""
        return self._object.execute_kw(
            self.db, self.uid, self.password, model, "fields_get",
            [], {"attributes": list(attrs_tuple)},
        )

    def fields_get(
        self, model: str,
        attributes: list[str] | None = None,
    ) -> dict:
        attrs = attributes or [
            "string", "type", "required", "readonly", "help",
            "size", "relation", "relation_field", "selection",
            "domain", "store", "depends",
        ]
        return self.fields_get_cached(model, tuple(attrs))

    def search_read(
        self, model: str, domain: list, fields: list[str] | None = None,
        limit: int = 20, offset: int = 0, order: str | None = None,
    ) -> list[dict]:
        kw: dict[str, Any] = {"limit": limit, "offset": offset}
        if fields:
            kw["fields"] = fields
        if order:
            kw["order"] = order
        return self.execute(model, "search_read", domain, **kw)

    def search_count(self, model: str, domain: list) -> int:
        return self.execute(model, "search_count", domain)

    def create(self, model: str, values: dict) -> int:
        # execute_kw args: [values_dict] — Odoo create accepts dict or list-of-dicts
        return self._object.execute_kw(
            self.db, self.uid, self.password, model, "create", [values], {},
        )

    def write(self, model: str, ids: list[int], values: dict) -> bool:
        return self.execute(model, "write", ids, values)

    def unlink(self, model: str, ids: list[int]) -> bool:
        return self.execute(model, "unlink", ids)

    def server_version(self) -> dict:
        return self._common.version()


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "odoo",
    instructions="Real-time Odoo introspection and CRUD via XML-RPC",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)

_client: OdooClient | None = None


def get_client() -> OdooClient:
    global _client
    if _client is None:
        cfg = load_config()
        missing = [k for k in ("url", "db", "username", "password") if not cfg[k]]
        if missing:
            raise ValueError(
                f"Missing Odoo config: {', '.join(missing)}. "
                "Set via environment variables (ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD) "
                "or in .env.local file."
            )
        odoo_cfg = {k: cfg[k] for k in ("url", "db", "username", "password")}
        _client = OdooClient(**odoo_cfg)
    return _client


# --- Introspection Tools ---

@mcp.tool()
@_odoo_error
def odoo_server_info() -> str:
    """Get Odoo server version and connection status."""
    client = get_client()
    ver = client.server_version()
    return json.dumps({
        "status": "connected",
        "server_version": ver.get("server_version", "unknown"),
    }, indent=2)


@mcp.tool()
@_odoo_error
def odoo_list_models(filter: str = "") -> str:
    """List all installed Odoo models. Use filter to search by name (e.g. 'crm', 'sale').

    Args:
        filter: Substring to filter model names (case-insensitive). Empty = all models.
    """
    client = get_client()
    domain = []
    if filter:
        domain = [("model", "ilike", filter)]
    models = client.search_read(
        "ir.model", domain,
        fields=["model", "name", "info", "transient"],
        limit=200,
        order="model",
    )
    result = []
    for m in models:
        result.append({
            "model": m["model"],
            "name": m["name"],
            "description": (m.get("info") or "")[:200],
            "transient": m.get("transient", False),
        })
    return json.dumps(result, indent=2)


@mcp.tool()
@_odoo_error
def odoo_model_fields(model: str, field_filter: str = "") -> str:
    """Get all fields of an Odoo model with types, constraints, and relations.

    Args:
        model: Model technical name (e.g. 'crm.lead', 'res.partner')
        field_filter: Optional substring to filter field names
    """
    client = get_client()
    fields = client.fields_get(model)

    result = {}
    for name, info in sorted(fields.items()):
        if field_filter and field_filter.lower() not in name.lower():
            continue
        entry = {
            "label": info.get("string", ""),
            "type": info.get("type", ""),
            "required": info.get("required", False),
            "readonly": info.get("readonly", False),
            "stored": info.get("store", True),
        }
        if info.get("help"):
            entry["help"] = info["help"][:300]
        if info.get("size"):
            entry["max_length"] = info["size"]
        if info.get("relation"):
            entry["relation"] = info["relation"]
        if info.get("relation_field"):
            entry["relation_field"] = info["relation_field"]
        if info.get("selection"):
            entry["selection"] = info["selection"]
        if info.get("domain"):
            entry["domain"] = str(info["domain"])
        if info.get("depends"):
            entry["depends"] = info["depends"]
        result[name] = entry

    return json.dumps(result, indent=2)


@mcp.tool()
@_odoo_error
def odoo_model_access(model: str) -> str:
    """Get access rights (CRUD permissions) for a model by group.

    Args:
        model: Model technical name (e.g. 'crm.lead')
    """
    client = get_client()
    model_ids = client.search_read(
        "ir.model", [("model", "=", model)],
        fields=["id"], limit=1,
    )
    if not model_ids:
        return json.dumps({"error": f"Model '{model}' not found"})

    model_id = model_ids[0]["id"]
    access = client.search_read(
        "ir.model.access",
        [("model_id", "=", model_id)],
        fields=["name", "group_id", "perm_read", "perm_write", "perm_create", "perm_unlink"],
        limit=50,
    )
    result = []
    for a in access:
        result.append({
            "name": a["name"],
            "group": a["group_id"][1] if a["group_id"] else "Everyone",
            "read": a["perm_read"],
            "write": a["perm_write"],
            "create": a["perm_create"],
            "delete": a["perm_unlink"],
        })
    return json.dumps(result, indent=2)


@mcp.tool()
@_odoo_error
def odoo_model_views(model: str) -> str:
    """List all views (form, list, search, kanban, etc.) for a model.

    Args:
        model: Model technical name (e.g. 'crm.lead')
    """
    client = get_client()
    views = client.search_read(
        "ir.ui.view",
        [("model", "=", model)],
        fields=["name", "type", "priority", "arch_db", "inherit_id"],
        limit=50,
        order="type, priority",
    )
    result = []
    for v in views:
        entry = {
            "name": v["name"],
            "type": v["type"],
            "priority": v["priority"],
            "inherits": v["inherit_id"][1] if v["inherit_id"] else None,
        }
        arch = v.get("arch_db", "") or ""
        if len(arch) <= 2000:
            entry["arch_xml"] = arch
        else:
            entry["arch_xml_truncated"] = arch[:2000] + "... (truncated)"
        result.append(entry)
    return json.dumps(result, indent=2, ensure_ascii=False)


# --- CRM-Specific Tools ---

@mcp.tool()
@_odoo_error
def odoo_crm_stages() -> str:
    """Get all CRM pipeline stages with their configuration."""
    client = get_client()
    stages = client.search_read(
        "crm.stage", [],
        fields=["name", "sequence", "is_won", "fold", "team_id", "requirements"],
        order="sequence",
    )
    return json.dumps(stages, indent=2, ensure_ascii=False)


@mcp.tool()
@_odoo_error
def odoo_crm_lead_summary(
    stage_id: int = 0,
    limit: int = 20,
    type_filter: str = "",
) -> str:
    """Get CRM leads/opportunities summary.

    Args:
        stage_id: Filter by stage ID (0 = all stages)
        limit: Max records to return (default 20)
        type_filter: 'lead' or 'opportunity' or '' for both
    """
    client = get_client()
    domain: list = []
    if stage_id:
        domain.append(("stage_id", "=", stage_id))
    if type_filter:
        domain.append(("type", "=", type_filter))

    leads = client.search_read(
        "crm.lead", domain,
        fields=[
            "name", "type", "stage_id", "user_id", "partner_id",
            "expected_revenue", "probability", "priority",
            "date_deadline", "create_date", "active",
        ],
        limit=limit,
        order="create_date desc",
    )
    return json.dumps(leads, indent=2, ensure_ascii=False, default=str)


# --- Generic CRUD Tools ---

@mcp.tool()
@_odoo_error
def odoo_search_read(
    model: str,
    domain: Any = "[]",
    fields: str = "",
    limit: int = 20,
    offset: int = 0,
    order: str = "",
) -> str:
    """Search and read records from any Odoo model.

    Args:
        model: Model name (e.g. 'crm.lead', 'res.partner')
        domain: Search domain as JSON string (e.g. '[["stage_id","=",1]]')
        fields: Comma-separated field names (empty = all fields)
        limit: Max records (default 20, max 100)
        offset: Skip first N records
        order: Sort order (e.g. 'create_date desc')
    """
    client = get_client()
    parsed_domain = _parse_domain(domain) if domain else []
    parsed_fields = [f.strip() for f in fields.split(",") if f.strip()] if fields else None
    limit = min(limit, 100)

    records = client.search_read(
        model, parsed_domain,
        fields=parsed_fields,
        limit=limit,
        offset=offset,
        order=order or None,
    )
    return json.dumps(records, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_count(model: str, domain: Any = "[]") -> str:
    """Count records matching a domain.

    Args:
        model: Model name
        domain: Search domain as JSON string
    """
    client = get_client()
    parsed_domain = _parse_domain(domain) if domain else []
    count = client.search_count(model, parsed_domain)
    return json.dumps({"model": model, "count": count})


@mcp.tool()
@_odoo_error
def odoo_create(model: str, values: Any = "{}") -> str:
    """Create a new record in any Odoo model.

    Args:
        model: Model name (e.g. 'crm.lead')
        values: Field values as JSON (e.g. '{"name": "New Lead", "partner_id": 1}')
    """
    client = get_client()
    parsed_values = _parse_values(values)
    record_id = client.create(model, parsed_values)
    return json.dumps({"model": model, "created_id": record_id})


@mcp.tool()
@_odoo_error
def odoo_write(model: str, ids: Any = "[]", values: Any = "{}") -> str:
    """Update existing records.

    Args:
        model: Model name
        ids: JSON array of record IDs (e.g. '[1, 2, 3]')
        values: Field values to update as JSON
    """
    client = get_client()
    parsed_ids = _parse_ids(ids)
    parsed_values = _parse_values(values)
    if not parsed_ids:
        return json.dumps({"error": "No record IDs provided"})
    result = client.write(model, parsed_ids, parsed_values)
    return json.dumps({"model": model, "ids": parsed_ids, "success": result})


@mcp.tool()
@_odoo_error
def odoo_delete(model: str, ids: Any = "[]") -> str:
    """Delete records from a model. Requires non-empty list of IDs.

    Args:
        model: Model name
        ids: JSON array of record IDs to delete
    """
    client = get_client()
    parsed_ids = _parse_ids(ids)
    if not parsed_ids:
        return json.dumps({"error": "No record IDs provided — refusing to delete nothing"})
    result = client.unlink(model, parsed_ids)
    return json.dumps({"model": model, "deleted_ids": parsed_ids, "success": result})


@mcp.tool()
@_odoo_error
def odoo_execute(model: str, method: str, args: Any = "[]", kwargs: Any = "{}") -> str:
    """Execute a permitted method on an Odoo model.

    Only safe CRM/business methods are allowed. Restricted for security.

    Args:
        model: Model name
        method: Method name (e.g. 'action_set_won', 'message_post')
        args: JSON array of positional arguments
        kwargs: JSON object of keyword arguments
    """
    ALLOWED_METHODS = {
        "action_set_won", "action_set_lost", "action_set_active",
        "action_archive", "action_unarchive",
        "message_post", "message_subscribe", "message_unsubscribe",
        "toggle_active", "name_search", "name_get",
        "default_get", "onchange", "read_group",
        "action_confirm", "action_quotation_send",
        "action_post", "_create_invoices",
    }
    if method not in ALLOWED_METHODS:
        return json.dumps({
            "error": f"Method '{method}' is not in the allowed list",
            "allowed_methods": sorted(ALLOWED_METHODS),
        })

    client = get_client()
    parsed_args = _parse_json(args)
    parsed_kwargs = _parse_json(kwargs)
    result = client._object.execute_kw(
        client.db, client.uid, client.password,
        model, method, parsed_args, parsed_kwargs,
    )
    return json.dumps(result, indent=2, ensure_ascii=False, default=str)


# --- Sale Order Tools ---

@mcp.tool()
@_odoo_error
def odoo_sale_order_summary(
    partner_id: int = 0,
    state: str = "",
    limit: int = 20,
) -> str:
    """List sale orders with status and totals.

    Args:
        partner_id: Filter by customer ID (0 = all)
        state: Filter by state: draft, sent, sale, done, cancel (empty = all)
        limit: Max records (default 20)
    """
    client = get_client()
    domain = []
    if partner_id:
        domain.append(("partner_id", "=", partner_id))
    if state:
        domain.append(("state", "=", state))
    orders = client.search_read(
        "sale.order", domain,
        fields=["name", "partner_id", "date_order", "amount_total",
                "state", "invoice_status", "user_id"],
        limit=min(limit, 100),
        order="date_order desc",
    )
    return json.dumps(orders, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_create_sale_order(partner_id: int, order_lines: Any = "[]") -> str:
    """Create a quotation (draft sale order) with product lines.

    Args:
        partner_id: Customer ID (res.partner)
        order_lines: JSON array of lines, each: {"product_id": int, "quantity": float, "price_unit": float (optional)}
                     Example: [{"product_id": 1, "quantity": 5}, {"product_id": 2, "quantity": 3, "price_unit": 100}]
    """
    client = get_client()
    lines = _parse_json(order_lines)
    if not isinstance(lines, list) or not lines:
        raise ValueError("order_lines must be a non-empty JSON array")

    ol_commands = []
    for line in lines:
        if not isinstance(line, dict) or "product_id" not in line:
            raise ValueError("Each line must have 'product_id'")
        vals = {
            "product_id": line["product_id"],
            "product_uom_qty": line.get("quantity", 1),
        }
        if "price_unit" in line:
            vals["price_unit"] = line["price_unit"]
        ol_commands.append((0, 0, vals))

    order_id = client.create("sale.order", {
        "partner_id": partner_id,
        "order_line": ol_commands,
    })
    # Read back to confirm
    order = client.search_read(
        "sale.order", [("id", "=", order_id)],
        fields=["name", "partner_id", "amount_total", "state"],
        limit=1,
    )
    return json.dumps({"created": order[0] if order else {"id": order_id}},
                      indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_confirm_sale_order(order_id: int) -> str:
    """Confirm a draft sale order (quotation -> sale order).
    This triggers credit control checks if masios_credit_control is installed.

    Args:
        order_id: Sale order ID to confirm
    """
    client = get_client()
    client._object.execute_kw(
        client.db, client.uid, client.password,
        "sale.order", "action_confirm", [[order_id]], {},
    )
    order = client.search_read(
        "sale.order", [("id", "=", order_id)],
        fields=["name", "state", "partner_id", "amount_total", "invoice_status"],
        limit=1,
    )
    return json.dumps({"confirmed": order[0] if order else {"id": order_id}},
                      indent=2, ensure_ascii=False, default=str)


# --- Invoice Tools ---

@mcp.tool()
@_odoo_error
def odoo_invoice_summary(
    partner_id: int = 0,
    state: str = "",
    limit: int = 20,
) -> str:
    """List invoices with payment status.

    Args:
        partner_id: Filter by customer ID (0 = all)
        state: Filter: draft, posted, cancel (empty = all)
        limit: Max records (default 20)
    """
    client = get_client()
    domain = [("move_type", "=", "out_invoice")]
    if partner_id:
        domain.append(("partner_id", "=", partner_id))
    if state:
        domain.append(("state", "=", state))
    invoices = client.search_read(
        "account.move", domain,
        fields=["name", "partner_id", "invoice_date", "invoice_date_due",
                "amount_total", "amount_residual", "state", "payment_state"],
        limit=min(limit, 100),
        order="invoice_date desc",
    )
    return json.dumps(invoices, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_create_invoice_from_so(order_id: int) -> str:
    """Create an invoice from a confirmed sale order.

    Args:
        order_id: Sale order ID (must be in 'sale' state)
    """
    client = get_client()
    # Check order state
    order = client.search_read(
        "sale.order", [("id", "=", order_id)],
        fields=["name", "state", "invoice_status"],
        limit=1,
    )
    if not order:
        raise ValueError(f"Sale order {order_id} not found")
    if order[0]["state"] != "sale":
        raise ValueError(f"Order {order[0]['name']} is in state '{order[0]['state']}', must be 'sale'")

    # Create invoice via _create_invoices method
    invoice_ids = client._object.execute_kw(
        client.db, client.uid, client.password,
        "sale.order", "_create_invoices", [[order_id]], {},
    )
    if invoice_ids:
        invoices = client.search_read(
            "account.move", [("id", "in", invoice_ids)],
            fields=["name", "partner_id", "amount_total", "state"],
        )
        return json.dumps({"invoices_created": invoices},
                          indent=2, ensure_ascii=False, default=str)
    return json.dumps({"error": "No invoices created"})


# --- Customer Tools ---

@mcp.tool()
@_odoo_error
def odoo_create_customer(
    name: str,
    phone: str = "",
    email: str = "",
    company_type: str = "company",
    classification: str = "new",
) -> str:
    """Create a new customer (res.partner) with simple parameters — no JSON needed.

    Args:
        name: Customer name (required)
        phone: Phone number
        email: Email address
        company_type: 'company' or 'person' (default 'company')
        classification: 'new' or 'old' (default 'new')
    """
    client = get_client()
    vals = {"name": name, "company_type": company_type, "customer_classification": classification}
    if phone:
        vals["phone"] = phone
    if email:
        vals["email"] = email
    partner_id = client.create("res.partner", vals)
    partner = client.search_read(
        "res.partner", [("id", "=", partner_id)],
        fields=["name", "phone", "email", "company_type", "customer_classification"],
        limit=1,
    )
    return json.dumps({"created": partner[0] if partner else {"id": partner_id}},
                      indent=2, ensure_ascii=False, default=str)


# --- Credit Control Tools ---

@mcp.tool()
@_odoo_error
def odoo_customer_credit_status(partner_id: int) -> str:
    """Get customer credit status: classification, limit, debt, available credit.

    Args:
        partner_id: Customer (res.partner) ID
    """
    client = get_client()
    partners = client.search_read(
        "res.partner", [("id", "=", partner_id)],
        fields=["name", "customer_classification", "credit_allowed",
                "credit_limit", "outstanding_debt", "credit_available",
                "credit_exceeded"],
        limit=1,
    )
    if not partners:
        raise ValueError(f"Partner {partner_id} not found")
    return json.dumps(partners[0], indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_customer_set_classification(partner_id: int, classification: str) -> str:
    """Set customer classification to 'new' or 'old'.

    Args:
        partner_id: Customer (res.partner) ID
        classification: 'new' or 'old'
    """
    if classification not in ("new", "old"):
        raise ValueError("classification must be 'new' or 'old'")
    client = get_client()
    client.write("res.partner", [partner_id], {"customer_classification": classification})
    # Read back
    partner = client.search_read(
        "res.partner", [("id", "=", partner_id)],
        fields=["name", "customer_classification", "credit_allowed", "credit_limit"],
        limit=1,
    )
    return json.dumps({"updated": partner[0] if partner else {"id": partner_id}},
                      indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_customers_exceeding_credit(limit: int = 50) -> str:
    """List customers who have exceeded their credit limit.

    Args:
        limit: Max records (default 50)
    """
    client = get_client()
    # Get all 'old' customers with credit limit
    partners = client.search_read(
        "res.partner",
        [("customer_classification", "=", "old"), ("credit_limit", ">", 0)],
        fields=["name", "credit_limit", "outstanding_debt", "credit_available", "credit_exceeded"],
        limit=min(limit, 200),
    )
    exceeded = [p for p in partners if p.get("credit_exceeded")]
    return json.dumps(exceeded, indent=2, ensure_ascii=False, default=str)


# --- Dashboard Tools ---

@mcp.tool()
@_odoo_error
def odoo_dashboard_kpis() -> str:
    """Get CEO dashboard KPIs: pipeline value, monthly revenue, total debt, new leads count."""
    from datetime import datetime
    client = get_client()
    today = datetime.now()
    first_day = today.replace(day=1).strftime("%Y-%m-%d")

    # Pipeline value
    opps = client.search_read(
        "crm.lead",
        [("type", "=", "opportunity"), ("active", "=", True)],
        fields=["expected_revenue"],
        limit=500,
    )
    pipeline_value = sum(o.get("expected_revenue", 0) or 0 for o in opps)

    # Monthly revenue
    invs = client.search_read(
        "account.move",
        [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
         ("invoice_date", ">=", first_day)],
        fields=["amount_total"],
        limit=500,
    )
    monthly_revenue = sum(i.get("amount_total", 0) or 0 for i in invs)

    # Total debt
    unpaid = client.search_read(
        "account.move",
        [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
         ("amount_residual", ">", 0)],
        fields=["amount_residual"],
        limit=500,
    )
    total_debt = sum(i.get("amount_residual", 0) or 0 for i in unpaid)

    # New leads this month
    new_leads = client.search_count(
        "crm.lead", [("create_date", ">=", first_day)]
    )

    return json.dumps({
        "pipeline_value": pipeline_value,
        "monthly_revenue": monthly_revenue,
        "total_debt": total_debt,
        "new_leads": new_leads,
        "period": first_day + " to " + today.strftime("%Y-%m-%d"),
    }, indent=2)


@mcp.tool()
@_odoo_error
def odoo_pipeline_by_stage() -> str:
    """Get CRM pipeline data grouped by stage: count and total value per stage."""
    client = get_client()
    stages = client.search_read(
        "crm.stage", [],
        fields=["name", "sequence"],
        order="sequence",
    )
    result = []
    for stage in stages:
        leads = client.search_read(
            "crm.lead",
            [("stage_id", "=", stage["id"]), ("active", "=", True)],
            fields=["expected_revenue"],
            limit=500,
        )
        count = len(leads)
        value = sum(l.get("expected_revenue", 0) or 0 for l in leads)
        result.append({
            "stage_id": stage["id"],
            "stage": stage["name"],
            "count": count,
            "value": value,
        })
    return json.dumps(result, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _generate_token() -> str:
    """Generate a cryptographically secure API token."""
    return secrets.token_urlsafe(32)


def _create_authed_app(app, api_token: str):
    """Wrap a Starlette app with bearer token authentication middleware."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.types import ASGIApp, Receive, Scope, Send

    class BearerTokenMiddleware:
        def __init__(self, wrapped_app: ASGIApp, token: str):
            self.app = wrapped_app
            self.token = token

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                request = Request(scope)
                auth_header = request.headers.get("authorization", "")
                if not auth_header.startswith("Bearer "):
                    response = JSONResponse(
                        {"error": "Missing Authorization header. Use: Bearer <token>"},
                        status_code=401,
                    )
                    await response(scope, receive, send)
                    return
                provided_token = auth_header[7:]  # strip "Bearer "
                if not hmac.compare_digest(provided_token, self.token):
                    response = JSONResponse(
                        {"error": "Invalid API token"},
                        status_code=403,
                    )
                    await response(scope, receive, send)
                    return
            await self.app(scope, receive, send)

    return BearerTokenMiddleware(app, api_token)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Odoo MCP Server")
    parser.add_argument(
        "--http", action="store_true",
        help="Run as HTTP server (streamable-http) instead of stdio",
    )
    parser.add_argument("--port", type=int, default=8200, help="HTTP port (default 8200)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="HTTP host (default 127.0.0.1)")
    parser.add_argument("--generate-token", action="store_true", help="Generate a new API token and exit")
    cli_args = parser.parse_args()

    if cli_args.generate_token:
        token = _generate_token()
        print(f"Generated API token (add to /etc/odoo-mcp/credentials):\n")
        print(f"  MCP_API_TOKEN={token}\n")
        print(f"For mcporter clients:\n")
        print(f"  mcporter config add odoo http://YOUR_SERVER:8200/sse \\")
        print(f"    --header \"Authorization=Bearer {token}\" --scope home")
        sys.exit(0)

    if cli_args.http:
        cfg = load_config()
        api_token = cfg.get("api_token", "")

        if not api_token:
            print("WARNING: No MCP_API_TOKEN set — HTTP endpoint has NO authentication!", file=sys.stderr)
            print("Generate one with: python3 server.py --generate-token", file=sys.stderr)
            print("Then add MCP_API_TOKEN=<token> to /etc/odoo-mcp/credentials\n", file=sys.stderr)

        mcp.settings.host = cli_args.host
        mcp.settings.port = cli_args.port

        if api_token:
            # Wrap the Starlette app with bearer token auth
            import uvicorn
            app = mcp.sse_app()
            authed_app = _create_authed_app(app, api_token)
            print(f"Starting Odoo MCP Server on {cli_args.host}:{cli_args.port} (SSE, token auth enabled)")
            uvicorn.run(authed_app, host=cli_args.host, port=cli_args.port)
        else:
            mcp.run(transport="sse")
    else:
        mcp.run()
