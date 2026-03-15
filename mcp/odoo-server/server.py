#!/usr/bin/env python3
"""
Odoo MCP Server — Real-time bridge between AI agents and Odoo instance.

Exposes Odoo's XML-RPC API as MCP tools for:
- Model/field introspection (types, constraints, relations)
- CRUD operations on any model
- CRM-specific helpers

Requires: pip install mcp (xmlrpc is stdlib)
"""

import base64
import hmac
import http.cookiejar
import json
import logging
import os
import secrets
import sys
import threading
import urllib.error
import urllib.request
import xmlrpc.client
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
import re as _re_module

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger("odoo-mcp")

# ---------------------------------------------------------------------------
# Security: unified protected model set for create/write/delete
# ---------------------------------------------------------------------------
_PROTECTED_MODELS: frozenset[str] = frozenset({
    "ir.model", "ir.module.module", "ir.model.access", "ir.rule",
    "ir.config_parameter", "res.users", "res.company",
    "ir.ui.view", "ir.actions.server", "ir.cron", "mail.message",
})

# Models allowed for odoo_execute (business models only)
_ALLOWED_EXECUTE_MODELS: frozenset[str] = frozenset({
    "crm.lead", "sale.order", "account.move", "res.partner",
    "project.task", "product.product", "product.template",
    "sale.order.line", "account.move.line",
    "credit.approval.request",
})

# Sensitive models blocked from odoo_search_read/odoo_count
_BLOCKED_READ_MODELS: frozenset[str] = frozenset({
    "ir.config_parameter", "ir.attachment", "res.users",
})

# Models allowed for odoo_escalate/odoo_change_owner
_ALLOWED_ACTION_MODELS: frozenset[str] = frozenset({
    "crm.lead", "sale.order", "account.move", "res.partner", "project.task",
})

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
    """Decorator: catch XML-RPC errors and run sync tools off the event loop.

    FastMCP + anyio runs sync tool functions inline on the event loop,
    blocking uvicorn from handling SSE responses while XML-RPC calls are
    in progress.  We wrap every tool with ``anyio.to_thread.run_sync``
    so the blocking work happens in a worker thread.
    """
    import functools

    def _sync_call(*args, **kwargs):
        logger.info(f"tool={func.__name__} called")
        try:
            result = func(*args, **kwargs)
            logger.info(f"tool={func.__name__} completed")
            return result
        except xmlrpc.client.Fault as e:
            msg = e.faultString
            if "\n" in msg:
                msg = msg.strip().split("\n")[-1]
            logger.error(f"tool={func.__name__} XML-RPC fault: {msg}")
            return json.dumps({"error": msg, "fault_code": e.faultCode})
        except xmlrpc.client.ProtocolError as e:
            logger.error(f"tool={func.__name__} protocol error: {e.errcode} {e.errmsg}")
            return json.dumps({"error": f"Odoo HTTP error: {e.errcode} {e.errmsg}"})
        except (ConnectionRefusedError, OSError) as e:
            logger.error(f"tool={func.__name__} connection error: {e}")
            return json.dumps({"error": f"Cannot reach Odoo server: {e}"})
        except json.JSONDecodeError as e:
            logger.error(f"tool={func.__name__} JSON error: {e}")
            return json.dumps({"error": f"Invalid JSON input: {e}"})
        except ValueError as e:
            logger.error(f"tool={func.__name__} value error: {e}")
            return json.dumps({"error": str(e)})
        except Exception as e:
            logger.error(f"tool={func.__name__} unexpected error: {e}", exc_info=True)
            return json.dumps({"error": f"Unexpected error in {func.__name__}: {type(e).__name__}: {e}"})

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        import anyio
        return await anyio.to_thread.run_sync(lambda: _sync_call(*args, **kwargs))

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

def _make_timeout_transport(url: str, timeout: int = 30):
    """Create an XML-RPC transport with a connection timeout."""
    base_class = xmlrpc.client.SafeTransport if url.startswith("https") else xmlrpc.client.Transport

    class TimeoutTransport(base_class):
        def __init__(self, timeout_val, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.timeout = timeout_val

        def make_connection(self, host):
            conn = super().make_connection(host)
            conn.timeout = self.timeout
            return conn

    return TimeoutTransport(timeout)


class OdooClient:
    """Thin wrapper around Odoo's XML-RPC API."""

    def __init__(self, url: str, db: str, username: str, password: str):
        self.url = url.rstrip("/")
        self.db = db
        self.username = username
        self.password = password
        self._uid = None
        self._lock = threading.RLock()
        transport = _make_timeout_transport(self.url, timeout=30)
        self._common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", transport=transport)
        self._object = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", transport=transport)

    @property
    def uid(self) -> int:
        if self._uid is None:
            with self._lock:
                # Double-check after acquiring lock
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
        with self._lock:
            return self._object.execute_kw(
                self.db, self.uid, self.password, model, method, list(args), kwargs
            )

    @lru_cache(maxsize=64)
    def fields_get_cached(self, model: str, attrs_tuple: tuple) -> dict:
        """Cached version of fields_get (attrs as tuple for hashability)."""
        with self._lock:
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
        with self._lock:
            return self._object.execute_kw(
                self.db, self.uid, self.password, model, "create", [values], {},
            )

    def write(self, model: str, ids: list[int], values: dict) -> bool:
        return self.execute(model, "write", ids, values)

    def unlink(self, model: str, ids: list[int]) -> bool:
        return self.execute(model, "unlink", ids)

    def server_version(self) -> dict:
        with self._lock:
            return self._common.version()

    # --- HTTP session for report downloads ---

    def _get_http_opener(self):
        """Get an authenticated HTTP opener with session cookies."""
        with self._lock:
            if hasattr(self, "_http_opener") and self._http_opener:
                return self._http_opener

            cj = http.cookiejar.CookieJar()
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(cj)
            )

            auth_url = f"{self.url}/web/session/authenticate"
            payload = json.dumps({
                "jsonrpc": "2.0", "method": "call", "id": 1,
                "params": {
                    "db": self.db,
                    "login": self.username,
                    "password": self.password,
                },
            }).encode("utf-8")

            req = urllib.request.Request(
                auth_url, data=payload,
                headers={"Content-Type": "application/json"},
            )
            resp = opener.open(req, timeout=30)
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("error"):
                raise ConnectionError(f"HTTP auth failed: {result['error']}")

            self._http_opener = opener
            return opener

    def download_report(self, report_name: str, record_ids: list[int]) -> bytes:
        """Download a PDF report from Odoo's report engine via HTTP."""
        if not _re_module.match(r'^[a-z0-9_.]+$', report_name):
            raise ValueError(f"Invalid report name: {report_name}")
        for attempt in range(2):
            try:
                opener = self._get_http_opener()
                ids_str = ",".join(str(i) for i in record_ids)
                report_url = f"{self.url}/report/pdf/{report_name}/{ids_str}"
                req = urllib.request.Request(report_url)
                resp = opener.open(req, timeout=60)
                data = resp.read()
                # Check PDF magic bytes — if missing, probably HTML error page
                if not data.startswith(b"%PDF-"):
                    raise ValueError("Got non-PDF response — session may have expired")
                return data
            except (ValueError, urllib.error.HTTPError):
                if attempt == 0:
                    self._http_opener = None  # Force re-auth
                    continue
                raise


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "odoo",
    instructions="Real-time Odoo introspection and CRUD via XML-RPC",
    transport_security=TransportSecuritySettings(
        # DNS rebinding protection disabled — Bearer token auth handles security.
        # Re-enabling blocks localhost connections (bot → MCP on same server).
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
    limit = min(limit, 200)
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
    if model in _BLOCKED_READ_MODELS:
        return json.dumps({"error": f"Cannot read from restricted model '{model}'"})
    client = get_client()
    parsed_domain = _parse_domain(domain) if domain else []
    if fields:
        parsed_fields = [f.strip() for f in fields.split(",") if f.strip()]
    else:
        # Default safe fields — avoid binary/image fields that cause AssertionError
        _DEFAULT_FIELDS = {
            "res.partner": ["id", "name", "phone", "email", "mobile", "company_type",
                            "customer_classification", "credit_limit", "outstanding_debt",
                            "credit_available", "credit_exceeded", "street", "city", "active"],
            "crm.lead": ["id", "name", "partner_name", "phone", "email_from", "type",
                          "stage_id", "user_id", "expected_revenue", "probability",
                          "priority", "date_deadline", "create_date", "active"],
            "sale.order": ["id", "name", "partner_id", "date_order", "amount_total",
                           "state", "invoice_status", "user_id"],
            "account.move": ["id", "name", "partner_id", "invoice_date", "invoice_date_due",
                             "amount_total", "amount_residual", "state", "payment_state", "move_type"],
            "project.task": ["id", "name", "project_id", "user_ids", "date_deadline",
                             "stage_id", "priority"],
        }
        parsed_fields = _DEFAULT_FIELDS.get(model, None)
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
    if model in _BLOCKED_READ_MODELS:
        return json.dumps({"error": f"Cannot count restricted model '{model}'"})
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
    if model in _PROTECTED_MODELS:
        return json.dumps({"error": f"Cannot create records in protected model '{model}'"})
    client = get_client()
    parsed_values = _parse_values(values)
    # Default crm.lead type to opportunity (visible in Pipeline)
    if model == "crm.lead" and "type" not in parsed_values:
        parsed_values["type"] = "opportunity"
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
    if model in _PROTECTED_MODELS:
        return json.dumps({"error": f"Cannot write to protected model '{model}'"})
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
    if model in _PROTECTED_MODELS:
        return json.dumps({"error": f"Cannot delete records from protected model '{model}'"})
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
        "default_get", "onchange",
        "action_confirm", "action_quotation_send",
        "action_post", "_create_invoices",
        "do_approve", "do_reject", "action_approve",
    }
    if method not in ALLOWED_METHODS:
        return json.dumps({
            "error": f"Method '{method}' is not in the allowed list",
            "allowed_methods": sorted(ALLOWED_METHODS),
        })
    if model not in _ALLOWED_EXECUTE_MODELS:
        return json.dumps({
            "error": f"Model '{model}' is not allowed for execute. Use odoo_search_read/odoo_count instead.",
            "allowed_models": sorted(_ALLOWED_EXECUTE_MODELS),
        })

    client = get_client()
    parsed_args = _parse_json(args)
    parsed_kwargs = _parse_json(kwargs)
    if not isinstance(parsed_args, list):
        return json.dumps({"error": "args must be a JSON list"})
    if not isinstance(parsed_kwargs, dict):
        return json.dumps({"error": "kwargs must be a JSON object"})
    with client._lock:
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
    # Pre-check: order must exist and be in draft state
    order = client.search_read(
        "sale.order", [("id", "=", order_id)],
        fields=["state", "name"],
        limit=1,
    )
    if not order:
        return json.dumps({"error": f"Sale order {order_id} not found"})
    if order[0]["state"] not in ("draft", "sent"):
        return json.dumps({"error": f"Order {order[0]['name']} is in state '{order[0]['state']}', must be in draft or sent state"})
    with client._lock:
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
    with client._lock:
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
    credit_limit: float = 0,
) -> str:
    """Create a new customer (res.partner) with simple parameters — no JSON needed.

    Args:
        name: Customer name (required)
        phone: Phone number
        email: Email address
        company_type: 'company' or 'person' (default 'company')
        classification: 'new' or 'old' (default 'new')
        credit_limit: Credit limit amount (default 0, only applied if > 0)
    """
    client = get_client()
    vals = {"name": name, "company_type": company_type, "customer_classification": classification}
    if phone:
        vals["phone"] = phone
    if email:
        vals["email"] = email
    if credit_limit > 0:
        vals["credit_limit"] = credit_limit
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


# --- Credit Approval Tools ---

@mcp.tool()
@_odoo_error
def odoo_pending_approvals() -> str:
    """List pending credit approval requests waiting for CEO decision.

    Returns list of approval requests with sale order, customer, debt info.
    """
    client = get_client()
    approvals = client.search_read(
        "credit.approval.request",
        [("state", "=", "pending")],
        fields=["name", "sale_order_id", "partner_id", "salesperson_id",
                "amount_total", "outstanding_debt", "new_total_debt",
                "approval_threshold", "state", "create_date"],
        order="create_date desc",
        limit=50,
    )
    return json.dumps({"pending_count": len(approvals), "requests": approvals},
                      indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_approve_credit(request_id: int, approved_by: str = "CEO") -> str:
    """Approve a credit approval request. Auto-confirms the sale order.

    Args:
        request_id: ID of the credit.approval.request record
        approved_by: Name of person approving (default: CEO)
    """
    client = get_client()
    # Verify request exists and is pending
    reqs = client.search_read(
        "credit.approval.request",
        [("id", "=", request_id)],
        fields=["state", "name", "sale_order_id"],
        limit=1,
    )
    if not reqs:
        return json.dumps({"error": f"Approval request {request_id} not found"})
    if reqs[0]["state"] != "pending":
        return json.dumps({"error": f"Request {reqs[0]['name']} is already {reqs[0]['state']}"})

    # Call do_approve via execute_kw
    with client._lock:
        client._object.execute_kw(
            client.db, client.uid, client.password,
            "credit.approval.request", "do_approve", [[request_id]],
            {"approved_by": approved_by, "via": "telegram"},
        )

    # Read back the updated request
    updated = client.search_read(
        "credit.approval.request",
        [("id", "=", request_id)],
        fields=["name", "state", "sale_order_id", "partner_id",
                "approved_by", "approved_date"],
        limit=1,
    )
    # Also get the sale order state
    if updated:
        so_id = updated[0]["sale_order_id"][0] if updated[0].get("sale_order_id") else None
        if so_id:
            so = client.search_read(
                "sale.order", [("id", "=", so_id)],
                fields=["name", "state", "amount_total"],
                limit=1,
            )
            updated[0]["sale_order_state"] = so[0]["state"] if so else "unknown"

    return json.dumps({"approved": updated[0] if updated else {"id": request_id}},
                      indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_reject_credit(request_id: int, reason: str = "", rejected_by: str = "CEO") -> str:
    """Reject a credit approval request. Sale order stays in draft.

    Args:
        request_id: ID of the credit.approval.request record
        reason: Reason for rejection
        rejected_by: Name of person rejecting (default: CEO)
    """
    client = get_client()
    # Verify request exists and is pending
    reqs = client.search_read(
        "credit.approval.request",
        [("id", "=", request_id)],
        fields=["state", "name"],
        limit=1,
    )
    if not reqs:
        return json.dumps({"error": f"Approval request {request_id} not found"})
    if reqs[0]["state"] != "pending":
        return json.dumps({"error": f"Request {reqs[0]['name']} is already {reqs[0]['state']}"})

    with client._lock:
        client._object.execute_kw(
            client.db, client.uid, client.password,
            "credit.approval.request", "do_reject", [[request_id]],
            {"rejected_by": rejected_by, "reason": reason, "via": "telegram"},
        )

    updated = client.search_read(
        "credit.approval.request",
        [("id", "=", request_id)],
        fields=["name", "state", "partner_id", "approved_by",
                "reject_reason", "approved_date"],
        limit=1,
    )
    return json.dumps({"rejected": updated[0] if updated else {"id": request_id}},
                      indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_approval_history(
    state: str = "",
    partner_id: int = 0,
    limit: int = 20,
) -> str:
    """View credit approval history.

    Args:
        state: Filter by state: pending, approved, rejected (empty = all)
        partner_id: Filter by customer ID (0 = all)
        limit: Max records (default 20)
    """
    client = get_client()
    domain = []
    if state:
        domain.append(("state", "=", state))
    if partner_id:
        domain.append(("partner_id", "=", partner_id))
    approvals = client.search_read(
        "credit.approval.request", domain,
        fields=["name", "sale_order_id", "partner_id", "salesperson_id",
                "amount_total", "outstanding_debt", "new_total_debt",
                "approval_threshold", "state", "approved_by", "approved_via",
                "approved_date", "reject_reason", "create_date"],
        order="create_date desc",
        limit=min(limit, 100),
    )
    return json.dumps({"count": len(approvals), "requests": approvals},
                      indent=2, ensure_ascii=False, default=str)


# --- Dashboard Tools ---

@mcp.tool()
@_odoo_error
def odoo_dashboard_kpis() -> str:
    """Get CEO dashboard KPIs: pipeline value, monthly revenue, total debt, new leads count."""
    client = get_client()
    today = date.today()
    first_day = today.replace(day=1).isoformat()

    # Pipeline value (server-side aggregation via read_group)
    pipeline_group = client.execute(
        "crm.lead", "read_group",
        [("type", "=", "opportunity"), ("active", "=", True)],
        ["expected_revenue"], [],
    )
    pipeline_value = (pipeline_group[0]["expected_revenue"] or 0) if pipeline_group else 0

    # Monthly revenue (server-side aggregation via read_group)
    revenue_group = client.execute(
        "account.move", "read_group",
        [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
         ("invoice_date", ">=", first_day)],
        ["amount_total"], [],
    )
    monthly_revenue = (revenue_group[0]["amount_total"] or 0) if revenue_group else 0

    # Total debt (server-side aggregation via read_group)
    debt_group = client.execute(
        "account.move", "read_group",
        [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
         ("amount_residual", ">", 0)],
        ["amount_residual"], [],
    )
    total_debt = (debt_group[0]["amount_residual"] or 0) if debt_group else 0

    # New leads this month
    new_leads = client.search_count(
        "crm.lead", [("create_date", ">=", first_day)]
    )

    return json.dumps({
        "pipeline_value": pipeline_value,
        "monthly_revenue": monthly_revenue,
        "total_debt": total_debt,
        "new_leads": new_leads,
        "period": first_day + " to " + today.isoformat(),
    }, indent=2)


@mcp.tool()
@_odoo_error
def odoo_pipeline_by_stage() -> str:
    """Get CRM pipeline data grouped by stage: count and total value per stage."""
    client = get_client()
    # Single read_group query instead of N+1 queries
    groups = client.execute(
        "crm.lead", "read_group",
        [("active", "=", True), ("type", "=", "opportunity")],
        ["expected_revenue", "stage_id"],
        ["stage_id"],
    )
    result = []
    for g in groups:
        stage_info = g.get("stage_id")
        result.append({
            "stage_id": stage_info[0] if stage_info else None,
            "stage": stage_info[1] if stage_info else "Unknown",
            "count": g.get("__count", g.get("stage_id_count", 0)),
            "value": g.get("expected_revenue", 0) or 0,
        })
    return json.dumps(result, indent=2, ensure_ascii=False)


# --- PDF Report Tools ---

@mcp.tool()
@_odoo_error
def odoo_sale_order_pdf(order_id: int) -> str:
    """Download a sale order / quotation as PDF (base64-encoded).

    Args:
        order_id: Sale order ID (sale.order record)
    Returns:
        JSON with filename, pdf_base64, size_bytes, and order metadata
    """
    client = get_client()
    orders = client.search_read(
        "sale.order", [("id", "=", order_id)],
        fields=["name", "state", "partner_id", "amount_total"],
        limit=1,
    )
    if not orders:
        raise ValueError(f"Sale order {order_id} not found")

    pdf_bytes = client.download_report("sale.report_saleorder", [order_id])
    b64 = base64.b64encode(pdf_bytes).decode("ascii")

    order = orders[0]
    return json.dumps({
        "order": order["name"],
        "partner": order["partner_id"][1] if order["partner_id"] else None,
        "state": order["state"],
        "amount_total": order["amount_total"],
        "filename": f"{order['name'].replace('/', '_')}.pdf",
        "pdf_base64": b64,
        "size_bytes": len(pdf_bytes),
    }, ensure_ascii=False)


@mcp.tool()
@_odoo_error
def odoo_invoice_pdf(invoice_id: int) -> str:
    """Download an invoice as PDF (base64-encoded).

    Args:
        invoice_id: Invoice ID (account.move record)
    Returns:
        JSON with filename, pdf_base64, size_bytes, and invoice metadata
    """
    client = get_client()
    invoices = client.search_read(
        "account.move", [("id", "=", invoice_id)],
        fields=["name", "state", "partner_id", "move_type", "amount_total"],
        limit=1,
    )
    if not invoices:
        return json.dumps({"error": f"Invoice {invoice_id} not found"})
    if invoices[0]["state"] == "draft":
        return json.dumps({"error": f"Invoice {invoices[0]['name']} is in draft state. Post it first before downloading PDF."})
    if invoices[0]["move_type"] != "out_invoice":
        raise ValueError(
            f"Record {invoice_id} is type '{invoices[0]['move_type']}', not a customer invoice"
        )

    pdf_bytes = client.download_report("account.report_invoice", [invoice_id])
    b64 = base64.b64encode(pdf_bytes).decode("ascii")

    inv = invoices[0]
    return json.dumps({
        "invoice": inv["name"],
        "partner": inv["partner_id"][1] if inv["partner_id"] else None,
        "state": inv["state"],
        "amount_total": inv["amount_total"],
        "filename": f"{inv['name'].replace('/', '_')}.pdf",
        "pdf_base64": b64,
        "size_bytes": len(pdf_bytes),
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Command Center Helpers
# ---------------------------------------------------------------------------

_team_cache: dict[str, int | None] = {}
_team_cache_ts: float = 0
_TEAM_CACHE_TTL: float = 3600  # 1 hour


def _get_team_ids() -> dict[str, int | None]:
    """Resolve Hunter/Farmer team IDs from crm.team. Cached with 1h TTL."""
    import time as _time
    global _team_cache, _team_cache_ts
    if _team_cache and (_time.time() - _team_cache_ts) < _TEAM_CACHE_TTL:
        return _team_cache
    client = get_client()
    teams = client.search_read(
        "crm.team", [],
        fields=["id", "name"],
        limit=100,
    )
    hunter_id = None
    farmer_id = None
    for t in teams:
        name_lower = (t.get("name") or "").lower()
        if "hunter" in name_lower:
            hunter_id = t["id"]
        elif "farmer" in name_lower:
            farmer_id = t["id"]
    _team_cache = {"hunter": hunter_id, "farmer": farmer_id}
    _team_cache_ts = _time.time()
    logger.info(f"Team IDs resolved: hunter={hunter_id}, farmer={farmer_id}")
    return _team_cache


def _date_helpers() -> dict[str, str]:
    """Return common date boundaries as ISO strings."""
    today = date.today()
    first_of_month = today.replace(day=1)
    first_of_week = today - timedelta(days=today.weekday())
    return {
        "today": today.isoformat(),
        "first_of_month": first_of_month.isoformat(),
        "first_of_week": first_of_week.isoformat(),
        "yesterday": (today - timedelta(days=1)).isoformat(),
        "now": datetime.now().isoformat(),
    }


def _period_start(period: str) -> str:
    """Get the start date for a period string."""
    d = _date_helpers()
    if period == "today":
        return d["today"]
    elif period == "week":
        return d["first_of_week"]
    else:  # month (default)
        return d["first_of_month"]


def _safe_read_group(client, model: str, domain: list, fields: list, groupby: list, **kw):
    """Wrapper for read_group that catches errors for missing fields/models."""
    try:
        return client.execute(model, "read_group", domain, fields, groupby, **kw)
    except xmlrpc.client.Fault as e:
        fault_str = str(e.faultString).lower()
        if any(kw in fault_str for kw in ("field", "model", "column", "not found")):
            logger.warning(f"read_group on {model} failed (schema): {e.faultString}")
            return []
        logger.error(f"read_group on {model} failed (unexpected fault): {e.faultString}")
        raise


def _check_cc_field(client, field_name: str = "hunter_farmer_type") -> bool:
    """Check if masios_command_center fields exist on a model."""
    try:
        fields = client.fields_get("sale.order", attributes=["string", "type"])
        return field_name in fields
    except xmlrpc.client.Fault:
        return False
    except Exception as e:
        logger.warning("Field check for %s failed (not a schema issue): %s", field_name, e)
        return False


# ---------------------------------------------------------------------------
# Command Center Tools (14 tools)
# ---------------------------------------------------------------------------

@mcp.tool()
@_odoo_error
def odoo_morning_brief() -> str:
    """CEO morning briefing: hunter KPIs, farmer KPIs, AR task summary, top alerts.
    Returns 4 blocks: hunter_kpis, farmer_kpis, ar_task_summary, top_alerts.
    """
    client = get_client()
    d = _date_helpers()
    teams = _get_team_ids()
    today = d["today"]
    first_of_month = d["first_of_month"]

    # --- Hunter KPIs ---
    hunter_domain_base = []
    if teams.get("hunter"):
        hunter_domain_base = [("team_id", "=", teams["hunter"])]

    hunter_leads_new = client.search_count(
        "crm.lead",
        hunter_domain_base + [("create_date", ">=", first_of_month)],
    )
    hunter_leads_won = client.search_count(
        "crm.lead",
        hunter_domain_base + [
            ("stage_id.is_won", "=", True),
            ("date_closed", ">=", first_of_month),
        ],
    )
    # Hunter revenue (first orders this month)
    hunter_so_domain = [("state", "in", ("sale", "done")), ("date_order", ">=", first_of_month)]
    has_cc = _check_cc_field(client, "order_type")
    if has_cc:
        hunter_so_domain.append(("order_type", "=", "first_order"))
    hunter_rev_group = _safe_read_group(
        client, "sale.order", hunter_so_domain,
        ["amount_total"], [],
    )
    hunter_revenue = (hunter_rev_group[0]["amount_total"] or 0) if hunter_rev_group else 0

    hunter_kpis = {
        "leads_new_this_month": hunter_leads_new,
        "leads_won_this_month": hunter_leads_won,
        "first_order_revenue": hunter_revenue,
    }

    # --- Farmer KPIs ---
    farmer_domain_base = []
    if teams.get("farmer"):
        farmer_domain_base = [("team_id", "=", teams["farmer"])]

    farmer_so_domain = [("state", "in", ("sale", "done")), ("date_order", ">=", first_of_month)]
    if has_cc:
        farmer_so_domain.append(("order_type", "=", "repeat_order"))
    farmer_rev_group = _safe_read_group(
        client, "sale.order", farmer_so_domain,
        ["amount_total"], [],
    )
    farmer_revenue = (farmer_rev_group[0]["amount_total"] or 0) if farmer_rev_group else 0

    # Sleeping customers (no order in 90+ days) — use read_group for accuracy
    cutoff_90 = (date.today() - timedelta(days=90)).isoformat()
    sleeping_count = 0
    try:
        total_old_customers = client.search_count(
            "res.partner",
            [("customer_classification", "=", "old")],
        )
        # Get distinct partners with recent orders via read_group
        active_groups = _safe_read_group(
            client, "sale.order",
            [("date_order", ">=", cutoff_90), ("state", "in", ("sale", "done")),
             ("partner_id.customer_classification", "=", "old")],
            ["partner_id"], ["partner_id"],
        )
        active_count = len(active_groups)
        sleeping_count = max(0, total_old_customers - active_count)
    except Exception as e:
        logger.warning(f"Sleeping customer calc failed: {e}")

    farmer_kpis = {
        "repeat_order_revenue": farmer_revenue,
        "sleeping_customers_90d": sleeping_count,
    }

    # --- AR Task Summary ---
    overdue_inv = client.search_count(
        "account.move",
        [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
         ("amount_residual", ">", 0), ("invoice_date_due", "<", today)],
    )
    due_7d = client.search_count(
        "account.move",
        [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
         ("amount_residual", ">", 0),
         ("invoice_date_due", ">=", today),
         ("invoice_date_due", "<=", (date.today() + timedelta(days=7)).isoformat())],
    )
    ar_debt_group = _safe_read_group(
        client, "account.move",
        [("move_type", "=", "out_invoice"), ("state", "=", "posted"), ("amount_residual", ">", 0)],
        ["amount_residual"], [],
    )
    total_ar = (ar_debt_group[0]["amount_residual"] or 0) if ar_debt_group else 0

    ar_task_summary = {
        "total_receivable": total_ar,
        "overdue_invoices": overdue_inv,
        "due_within_7d": due_7d,
    }

    # --- Top Alerts ---
    alerts = []
    # SLA breached leads (open leads older than 48h without activity)
    sla_cutoff = (datetime.now() - timedelta(hours=48)).isoformat()
    old_leads = client.search_read(
        "crm.lead",
        [("type", "=", "opportunity"), ("active", "=", True),
         ("stage_id.is_won", "=", False), ("create_date", "<", sla_cutoff)],
        fields=["name", "partner_id", "create_date", "stage_id"],
        limit=5, order="create_date asc",
    )
    for lead in old_leads:
        alerts.append({
            "type": "sla_breach",
            "message": f"Lead '{lead['name']}' open since {lead['create_date']}",
            "record": f"crm.lead,{lead['id']}",
        })

    # 30d+ overdue invoices
    overdue_30 = (date.today() - timedelta(days=30)).isoformat()
    old_invoices = client.search_read(
        "account.move",
        [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
         ("amount_residual", ">", 0), ("invoice_date_due", "<", overdue_30)],
        fields=["name", "partner_id", "amount_residual", "invoice_date_due"],
        limit=5, order="invoice_date_due asc",
    )
    for inv in old_invoices:
        alerts.append({
            "type": "overdue_invoice_30d",
            "message": f"Invoice {inv['name']} overdue since {inv['invoice_date_due']}, "
                       f"amount: {inv['amount_residual']}",
            "record": f"account.move,{inv['id']}",
        })

    # Data quality checks
    data_issues = []
    if not teams.get("hunter"):
        data_issues.append("Team Hunter chưa được cấu hình trong CRM")
    if not teams.get("farmer"):
        data_issues.append("Team Farmer chưa được cấu hình trong CRM")

    result = {
        "date": today,
        "hunter_kpis": hunter_kpis,
        "farmer_kpis": farmer_kpis,
        "ar_task_summary": ar_task_summary,
        "top_alerts": alerts[:10],
        "data_quality": "issue" if data_issues else "ok",
        "data_issues": data_issues,
    }
    return json.dumps(result, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_ceo_alert(limit: int = 5) -> str:
    """Top critical issues needing CEO attention: SLA breached leads, 30d+ overdue invoices,
    sleeping VIP customers, critical overdue tasks.

    Args:
        limit: Max alerts per category (default 5, max 20)
    """
    client = get_client()
    limit = min(limit, 20)
    d = _date_helpers()
    today = d["today"]
    alerts = []

    # 1. SLA breached leads (open > 48h, not won)
    sla_cutoff = (datetime.now() - timedelta(hours=48)).isoformat()
    old_leads = client.search_read(
        "crm.lead",
        [("type", "=", "opportunity"), ("active", "=", True),
         ("stage_id.is_won", "=", False), ("create_date", "<", sla_cutoff)],
        fields=["name", "partner_id", "create_date", "stage_id", "user_id", "expected_revenue"],
        limit=limit, order="create_date asc",
    )
    for lead in old_leads:
        hours_open = (datetime.now() - datetime.fromisoformat(str(lead["create_date"]))).total_seconds() / 3600
        alerts.append({
            "severity": "critical",
            "category": "sla_breach",
            "summary": f"Lead '{lead['name']}' open {int(hours_open)}h (SLA breached)",
            "partner": lead["partner_id"][1] if lead["partner_id"] else None,
            "owner": lead["user_id"][1] if lead["user_id"] else None,
            "expected_revenue": lead.get("expected_revenue", 0),
            "record_id": lead["id"],
        })

    # 2. 30d+ overdue invoices
    overdue_30 = (date.today() - timedelta(days=30)).isoformat()
    old_invoices = client.search_read(
        "account.move",
        [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
         ("amount_residual", ">", 0), ("invoice_date_due", "<", overdue_30)],
        fields=["name", "partner_id", "amount_residual", "invoice_date_due"],
        limit=limit, order="amount_residual desc",
    )
    for inv in old_invoices:
        days_overdue = (date.today() - date.fromisoformat(str(inv["invoice_date_due"]))).days
        alerts.append({
            "severity": "critical",
            "category": "overdue_invoice_30d",
            "summary": f"Invoice {inv['name']} overdue {days_overdue}d, amount {inv['amount_residual']}",
            "partner": inv["partner_id"][1] if inv["partner_id"] else None,
            "amount": inv["amount_residual"],
            "record_id": inv["id"],
        })

    # 3. Sleeping VIP customers (old customers with credit limit, no order in 90d)
    cutoff_90 = (date.today() - timedelta(days=90)).isoformat()
    try:
        vip_customers = client.search_read(
            "res.partner",
            [("customer_classification", "=", "old"), ("credit_limit", ">", 0)],
            fields=["id", "name", "credit_limit"],
            limit=200, order="credit_limit desc",
        )
        if vip_customers:
            vip_ids = [c["id"] for c in vip_customers]
            active_orders = client.search_read(
                "sale.order",
                [("partner_id", "in", vip_ids), ("date_order", ">=", cutoff_90),
                 ("state", "in", ("sale", "done"))],
                fields=["partner_id"],
                limit=500,
            )
            active_set = set(o["partner_id"][0] for o in active_orders if o.get("partner_id"))
            sleeping_vips = [c for c in vip_customers if c["id"] not in active_set]
            for cust in sleeping_vips[:limit]:
                alerts.append({
                    "severity": "warning",
                    "category": "sleeping_vip",
                    "summary": f"VIP customer '{cust['name']}' no order in 90+ days",
                    "partner": cust["name"],
                    "record_id": cust["id"],
                })
    except xmlrpc.client.Fault as e:
        logger.warning(f"VIP sleeping check failed (schema): {e.faultString}")
    except Exception as e:
        logger.warning(f"VIP sleeping check failed: {e}")

    # 4. Overdue tasks (project.task if available)
    try:
        overdue_tasks = client.search_read(
            "project.task",
            [("date_deadline", "<", today), ("stage_id.fold", "=", False)],
            fields=["name", "user_ids", "date_deadline", "project_id", "priority"],
            limit=limit, order="date_deadline asc",
        )
        for task in overdue_tasks:
            alerts.append({
                "severity": "warning",
                "category": "overdue_task",
                "summary": f"Task '{task['name']}' overdue since {task['date_deadline']}",
                "project": task["project_id"][1] if task["project_id"] else None,
                "record_id": task["id"],
            })
    except Exception as e:
        logger.warning(f"Task check skipped (project module may not be installed): {e}")

    return json.dumps({
        "date": today,
        "total_alerts": len(alerts),
        "alerts": alerts,
    }, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_revenue_today(date_filter: str = "") -> str:
    """Today's revenue split by order type (hunter=first_order vs farmer=repeat_order).
    Uses read_group on sale.order grouped by order_type.

    Args:
        date_filter: ISO date string (default: today). E.g. '2026-03-12'
    """
    client = get_client()
    target_date = date_filter or _date_helpers()["today"]
    next_date = (date.fromisoformat(target_date) + timedelta(days=1)).isoformat()

    domain = [
        ("state", "in", ("sale", "done")),
        ("date_order", ">=", target_date),
        ("date_order", "<", next_date),
    ]

    has_cc = _check_cc_field(client, "order_type")
    if has_cc:
        groups = _safe_read_group(
            client, "sale.order", domain,
            ["amount_total", "order_type"], ["order_type"],
        )
        result = {"date": target_date, "breakdown": []}
        total = 0
        for g in groups:
            entry = {
                "order_type": g.get("order_type") or "unclassified",
                "count": g.get("__count", g.get("order_type_count", 0)),
                "revenue": g.get("amount_total", 0) or 0,
            }
            total += entry["revenue"]
            result["breakdown"].append(entry)
        result["total_revenue"] = total
    else:
        # No order_type field — just total
        groups = _safe_read_group(
            client, "sale.order", domain,
            ["amount_total"], [],
        )
        total = (groups[0]["amount_total"] or 0) if groups else 0
        count_total = client.search_count("sale.order", domain)
        result = {
            "date": target_date,
            "total_revenue": total,
            "total_orders": count_total,
            "note": "order_type field not available — install masios_command_center for hunter/farmer split",
        }

    # Data quality checks
    teams = _get_team_ids()
    data_issues = []
    if not teams.get("hunter"):
        data_issues.append("Team Hunter chưa được cấu hình trong CRM")
    if not teams.get("farmer"):
        data_issues.append("Team Farmer chưa được cấu hình trong CRM")
    result["data_quality"] = "issue" if data_issues else "ok"
    result["data_issues"] = data_issues

    return json.dumps(result, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_brief_hunter(period: str = "month") -> str:
    """Hunter team summary: leads_new, SLA counts, quotes pending, first_orders count+revenue, conversion_rate.

    Args:
        period: 'today', 'week', or 'month' (default 'month')
    """
    client = get_client()
    teams = _get_team_ids()
    start = _period_start(period)
    d = _date_helpers()
    today = d["today"]

    team_domain = []
    if teams.get("hunter"):
        team_domain = [("team_id", "=", teams["hunter"])]

    # Leads new
    leads_new = client.search_count(
        "crm.lead",
        team_domain + [("create_date", ">=", start)],
    )

    # SLA: leads open > 48h (breached), open <= 48h (ok)
    sla_cutoff = (datetime.now() - timedelta(hours=48)).isoformat()
    leads_open = client.search_count(
        "crm.lead",
        team_domain + [("type", "=", "opportunity"), ("active", "=", True),
                       ("stage_id.is_won", "=", False)],
    )
    sla_breached = client.search_count(
        "crm.lead",
        team_domain + [("type", "=", "opportunity"), ("active", "=", True),
                       ("stage_id.is_won", "=", False), ("create_date", "<", sla_cutoff)],
    )
    sla_ok = leads_open - sla_breached

    # Quotes pending (draft sale orders)
    quotes_pending = client.search_count(
        "sale.order",
        [("state", "=", "draft")] + ([("team_id", "=", teams["hunter"])] if teams.get("hunter") else []),
    )

    # First orders (confirmed SO in period)
    fo_domain = [("state", "in", ("sale", "done")), ("date_order", ">=", start)]
    has_cc = _check_cc_field(client, "order_type")
    if has_cc:
        fo_domain.append(("order_type", "=", "first_order"))
    if teams.get("hunter"):
        fo_domain.append(("team_id", "=", teams["hunter"]))

    fo_group = _safe_read_group(
        client, "sale.order", fo_domain,
        ["amount_total"], [],
    )
    first_order_count = (fo_group[0].get("__count", 0)) if fo_group else 0
    first_order_revenue = (fo_group[0]["amount_total"] or 0) if fo_group else 0

    # Won leads in period
    leads_won = client.search_count(
        "crm.lead",
        team_domain + [("stage_id.is_won", "=", True), ("date_closed", ">=", start)],
    )

    conversion_rate = round((leads_won / leads_new * 100), 1) if leads_new > 0 else 0

    return json.dumps({
        "period": period,
        "period_start": start,
        "leads_new": leads_new,
        "leads_open": leads_open,
        "sla_ok": sla_ok,
        "sla_breached": sla_breached,
        "quotes_pending": quotes_pending,
        "first_orders_count": first_order_count,
        "first_orders_revenue": first_order_revenue,
        "leads_won": leads_won,
        "conversion_rate_pct": conversion_rate,
    }, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_brief_farmer(period: str = "month") -> str:
    """Farmer team summary: repeat_orders, reorder_due, sleeping by bucket, vip_at_risk, farmer_ar_total.

    Args:
        period: 'today', 'week', or 'month' (default 'month')
    """
    client = get_client()
    teams = _get_team_ids()
    start = _period_start(period)
    d = _date_helpers()
    today_date = date.today()

    # Repeat orders
    ro_domain = [("state", "in", ("sale", "done")), ("date_order", ">=", start)]
    has_cc = _check_cc_field(client, "order_type")
    if has_cc:
        ro_domain.append(("order_type", "=", "repeat_order"))
    if teams.get("farmer"):
        ro_domain.append(("team_id", "=", teams["farmer"]))

    ro_group = _safe_read_group(
        client, "sale.order", ro_domain,
        ["amount_total"], [],
    )
    repeat_order_count = (ro_group[0].get("__count", 0)) if ro_group else 0
    repeat_order_revenue = (ro_group[0]["amount_total"] or 0) if ro_group else 0

    # Sleeping customers by bucket (30-60d, 60-90d, 90d+)
    # Use read_group to get max(date_order) per partner — no record limit issue
    total_old = client.search_count("res.partner", [("customer_classification", "=", "old")])
    cutoffs = {
        "30d": (today_date - timedelta(days=30)).isoformat(),
        "60d": (today_date - timedelta(days=60)).isoformat(),
        "90d": (today_date - timedelta(days=90)).isoformat(),
    }
    buckets = {"30_60d": 0, "60_90d": 0, "90d_plus": 0}

    # Count partners with last order in each bucket via read_group
    active_30 = _safe_read_group(
        client, "sale.order",
        [("state", "in", ("sale", "done")), ("date_order", ">=", cutoffs["30d"]),
         ("partner_id.customer_classification", "=", "old")],
        ["partner_id"], ["partner_id"],
    )
    active_60 = _safe_read_group(
        client, "sale.order",
        [("state", "in", ("sale", "done")), ("date_order", ">=", cutoffs["60d"]),
         ("date_order", "<", cutoffs["30d"]),
         ("partner_id.customer_classification", "=", "old")],
        ["partner_id"], ["partner_id"],
    )
    active_90 = _safe_read_group(
        client, "sale.order",
        [("state", "in", ("sale", "done")), ("date_order", ">=", cutoffs["90d"]),
         ("date_order", "<", cutoffs["60d"]),
         ("partner_id.customer_classification", "=", "old")],
        ["partner_id"], ["partner_id"],
    )
    # Partners active in last 30d
    active_30_ids = set(g["partner_id"][0] for g in active_30 if g.get("partner_id"))
    # Partners whose last order is 30-60d (active in 60d but NOT in 30d)
    active_60_ids = set(g["partner_id"][0] for g in active_60 if g.get("partner_id"))
    # Partners whose last order is 60-90d
    active_90_ids = set(g["partner_id"][0] for g in active_90 if g.get("partner_id"))

    buckets["30_60d"] = len(active_60_ids - active_30_ids)
    buckets["60_90d"] = len(active_90_ids - active_30_ids - active_60_ids)
    all_active_90d = active_30_ids | active_60_ids | active_90_ids
    buckets["90d_plus"] = max(0, total_old - len(all_active_90d))

    # Farmer AR total
    ar_domain = [("move_type", "=", "out_invoice"), ("state", "=", "posted"), ("amount_residual", ">", 0)]
    if teams.get("farmer"):
        ar_domain.append(("team_id", "=", teams["farmer"]))
    ar_group = _safe_read_group(
        client, "account.move", ar_domain,
        ["amount_residual"], [],
    )
    farmer_ar_total = (ar_group[0]["amount_residual"] or 0) if ar_group else 0

    return json.dumps({
        "period": period,
        "period_start": start,
        "repeat_orders_count": repeat_order_count,
        "repeat_orders_revenue": repeat_order_revenue,
        "sleeping_buckets": buckets,
        "total_sleeping": sum(buckets.values()),
        "farmer_ar_total": farmer_ar_total,
    }, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_brief_ar(team_filter: str = "") -> str:
    """AR aging report: total_receivable, aging buckets (current/1-30/31-60/61-90/90+),
    due_within_7d, overdue, disputes, top_debtors.

    Args:
        team_filter: 'hunter', 'farmer', or '' for all (default '')
    """
    client = get_client()
    d = _date_helpers()
    today_date = date.today()
    today = d["today"]

    base_domain = [("move_type", "=", "out_invoice"), ("state", "=", "posted"), ("amount_residual", ">", 0)]

    # Team filter
    if team_filter:
        teams = _get_team_ids()
        team_id = teams.get(team_filter.lower())
        if team_id:
            base_domain.append(("team_id", "=", team_id))

    # Total receivable
    total_group = _safe_read_group(client, "account.move", base_domain, ["amount_residual"], [])
    total_receivable = (total_group[0]["amount_residual"] or 0) if total_group else 0

    # Get all open invoices for aging
    invoices = client.search_read(
        "account.move", base_domain,
        fields=["name", "partner_id", "amount_residual", "invoice_date_due"],
        limit=200, order="amount_residual desc",
    )

    # Aging buckets
    buckets = {"current": 0, "1_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0}
    for inv in invoices:
        due = inv.get("invoice_date_due")
        if not due:
            buckets["current"] += inv["amount_residual"]
            continue
        due_date = date.fromisoformat(str(due)[:10])
        days_past = (today_date - due_date).days
        amt = inv["amount_residual"]
        if days_past <= 0:
            buckets["current"] += amt
        elif days_past <= 30:
            buckets["1_30"] += amt
        elif days_past <= 60:
            buckets["31_60"] += amt
        elif days_past <= 90:
            buckets["61_90"] += amt
        else:
            buckets["90_plus"] += amt

    # Due within 7d
    due_7d_date = (today_date + timedelta(days=7)).isoformat()
    due_7d_count = client.search_count(
        "account.move",
        base_domain + [("invoice_date_due", ">=", today), ("invoice_date_due", "<=", due_7d_date)],
    )

    # Overdue count
    overdue_count = client.search_count(
        "account.move",
        base_domain + [("invoice_date_due", "<", today)],
    )

    # Top debtors (aggregate by partner)
    partner_totals: dict[str, float] = {}
    for inv in invoices:
        pname = inv["partner_id"][1] if inv["partner_id"] else "Unknown"
        partner_totals[pname] = partner_totals.get(pname, 0) + inv["amount_residual"]
    top_debtors = sorted(partner_totals.items(), key=lambda x: x[1], reverse=True)[:10]

    return json.dumps({
        "team_filter": team_filter or "all",
        "total_receivable": total_receivable,
        "aging_buckets": buckets,
        "due_within_7d": due_7d_count,
        "overdue_count": overdue_count,
        "top_debtors": [{"partner": p, "amount": a} for p, a in top_debtors],
    }, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_brief_cash(period: str = "month") -> str:
    """Cash flow: collected (from account.payment), expected_7d, overdue_amount,
    collection_rate, top_pending invoices.

    Args:
        period: 'today', 'week', or 'month' (default 'month')
    """
    client = get_client()
    start = _period_start(period)
    d = _date_helpers()
    today = d["today"]
    today_date = date.today()

    # Collected payments in period
    collected_group = _safe_read_group(
        client, "account.payment",
        [("payment_type", "=", "inbound"), ("state", "=", "posted"), ("date", ">=", start)],
        ["amount"], [],
    )
    collected = (collected_group[0]["amount"] or 0) if collected_group else 0

    # Expected in next 7 days (invoices due within 7d)
    due_7d_date = (today_date + timedelta(days=7)).isoformat()
    expected_group = _safe_read_group(
        client, "account.move",
        [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
         ("amount_residual", ">", 0),
         ("invoice_date_due", ">=", today), ("invoice_date_due", "<=", due_7d_date)],
        ["amount_residual"], [],
    )
    expected_7d = (expected_group[0]["amount_residual"] or 0) if expected_group else 0

    # Overdue amount
    overdue_group = _safe_read_group(
        client, "account.move",
        [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
         ("amount_residual", ">", 0), ("invoice_date_due", "<", today)],
        ["amount_residual"], [],
    )
    overdue_amount = (overdue_group[0]["amount_residual"] or 0) if overdue_group else 0

    # Total invoiced in period
    invoiced_group = _safe_read_group(
        client, "account.move",
        [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
         ("invoice_date", ">=", start)],
        ["amount_total"], [],
    )
    total_invoiced = (invoiced_group[0]["amount_total"] or 0) if invoiced_group else 0

    collection_rate = round((collected / total_invoiced * 100), 1) if total_invoiced > 0 else 0

    # Top pending invoices
    top_pending = client.search_read(
        "account.move",
        [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
         ("amount_residual", ">", 0)],
        fields=["name", "partner_id", "amount_residual", "invoice_date_due"],
        limit=10, order="amount_residual desc",
    )
    top_pending_list = []
    for inv in top_pending:
        top_pending_list.append({
            "invoice": inv["name"],
            "partner": inv["partner_id"][1] if inv["partner_id"] else None,
            "amount": inv["amount_residual"],
            "due_date": str(inv.get("invoice_date_due") or ""),
        })

    return json.dumps({
        "period": period,
        "period_start": start,
        "collected": collected,
        "expected_7d": expected_7d,
        "overdue_amount": overdue_amount,
        "total_invoiced": total_invoiced,
        "collection_rate_pct": collection_rate,
        "top_pending": top_pending_list,
    }, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_hunter_today(section: str = "all") -> str:
    """Hunter daily dashboard. Sections: overview, sla, quotes, first_orders, sources.
    Use section param for /hunter_today, /hunter_quotes, /hunter_first_orders, /hunter_sources.

    Args:
        section: 'all', 'overview', 'sla', 'quotes', 'first_orders', 'sources' (default 'all')
    """
    client = get_client()
    teams = _get_team_ids()
    d = _date_helpers()
    today = d["today"]
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    team_domain = []
    so_team_domain = []
    if teams.get("hunter"):
        team_domain = [("team_id", "=", teams["hunter"])]
        so_team_domain = [("team_id", "=", teams["hunter"])]

    result = {"date": today, "section": section}

    if section in ("all", "overview"):
        leads_today = client.search_count(
            "crm.lead", team_domain + [("create_date", ">=", today), ("create_date", "<", tomorrow)],
        )
        activities_today = client.search_count(
            "crm.lead", team_domain + [("activity_date_deadline", "=", today)],
        )
        result["overview"] = {
            "leads_created_today": leads_today,
            "activities_due_today": activities_today,
        }

    if section in ("all", "sla"):
        sla_cutoff = (datetime.now() - timedelta(hours=48)).isoformat()
        sla_breached = client.search_count(
            "crm.lead",
            team_domain + [("type", "=", "opportunity"), ("active", "=", True),
                           ("stage_id.is_won", "=", False), ("create_date", "<", sla_cutoff)],
        )
        sla_ok = client.search_count(
            "crm.lead",
            team_domain + [("type", "=", "opportunity"), ("active", "=", True),
                           ("stage_id.is_won", "=", False), ("create_date", ">=", sla_cutoff)],
        )
        result["sla"] = {"ok": sla_ok, "breached": sla_breached}

    if section in ("all", "quotes"):
        quotes = client.search_read(
            "sale.order",
            so_team_domain + [("state", "in", ("draft", "sent"))],
            fields=["name", "partner_id", "amount_total", "state", "create_date"],
            limit=20, order="create_date desc",
        )
        result["quotes"] = {
            "count": len(quotes),
            "records": [{
                "name": q["name"],
                "partner": q["partner_id"][1] if q["partner_id"] else None,
                "amount": q["amount_total"],
                "state": q["state"],
            } for q in quotes],
        }

    if section in ("all", "first_orders"):
        fo_domain = so_team_domain + [
            ("state", "in", ("sale", "done")),
            ("date_order", ">=", today), ("date_order", "<", tomorrow),
        ]
        has_cc = _check_cc_field(client, "order_type")
        if has_cc:
            fo_domain.append(("order_type", "=", "first_order"))
        fo_group = _safe_read_group(client, "sale.order", fo_domain, ["amount_total"], [])
        fo_count = (fo_group[0].get("__count", 0)) if fo_group else 0
        fo_revenue = (fo_group[0]["amount_total"] or 0) if fo_group else 0
        result["first_orders"] = {"count": fo_count, "revenue": fo_revenue}

    if section in ("all", "sources"):
        # Lead sources (grouped by source_id)
        source_groups = _safe_read_group(
            client, "crm.lead",
            team_domain + [("create_date", ">=", d["first_of_month"])],
            ["source_id"], ["source_id"],
        )
        result["sources"] = [{
            "source": g["source_id"][1] if g.get("source_id") else "Unknown",
            "count": g.get("__count", g.get("source_id_count", 0)),
        } for g in source_groups]

    return json.dumps(result, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_hunter_sla_details(status: str = "breached", limit: int = 20) -> str:
    """Record-level SLA detail: leads with SLA issues, showing hours_since_creation.

    Args:
        status: 'breached' (open > 48h) or 'ok' (open <= 48h) (default 'breached')
        limit: Max records (default 20, max 200)
    """
    client = get_client()
    limit = min(limit, 200)
    teams = _get_team_ids()
    sla_cutoff = (datetime.now() - timedelta(hours=48)).isoformat()

    team_domain = []
    if teams.get("hunter"):
        team_domain = [("team_id", "=", teams["hunter"])]

    base = team_domain + [
        ("type", "=", "opportunity"), ("active", "=", True),
        ("stage_id.is_won", "=", False),
    ]
    if status == "breached":
        domain = base + [("create_date", "<", sla_cutoff)]
        order = "create_date asc"
    else:
        domain = base + [("create_date", ">=", sla_cutoff)]
        order = "create_date desc"

    leads = client.search_read(
        "crm.lead", domain,
        fields=["name", "partner_id", "user_id", "stage_id", "create_date",
                "expected_revenue", "priority", "activity_date_deadline"],
        limit=limit, order=order,
    )

    now = datetime.now()
    records = []
    for lead in leads:
        created = datetime.fromisoformat(str(lead["create_date"]))
        hours = round((now - created).total_seconds() / 3600, 1)
        records.append({
            "id": lead["id"],
            "name": lead["name"],
            "partner": lead["partner_id"][1] if lead["partner_id"] else None,
            "owner": lead["user_id"][1] if lead["user_id"] else None,
            "stage": lead["stage_id"][1] if lead["stage_id"] else None,
            "hours_since_creation": hours,
            "expected_revenue": lead.get("expected_revenue", 0),
            "priority": lead.get("priority", "0"),
            "next_activity": str(lead.get("activity_date_deadline") or ""),
        })

    return json.dumps({
        "status_filter": status,
        "sla_threshold_hours": 48,
        "count": len(records),
        "records": records,
    }, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_farmer_today(section: str = "all") -> str:
    """Farmer daily dashboard. Sections: overview, reorder, sleeping, vip, retention.
    Use for /farmer_today, /farmer_reorder, /farmer_sleeping, /farmer_vip, /farmer_retention.

    Args:
        section: 'all', 'overview', 'reorder', 'sleeping', 'vip', 'retention' (default 'all')
    """
    client = get_client()
    teams = _get_team_ids()
    d = _date_helpers()
    today = d["today"]
    today_date = date.today()

    result = {"date": today, "section": section}

    # Get customer base (old customers = established customers)
    customers = client.search_read(
        "res.partner",
        [("customer_classification", "=", "old")],
        fields=["id", "name", "credit_limit"],
        limit=500, order="credit_limit desc",
    )
    cust_ids = [c["id"] for c in customers]
    cust_map = {c["id"]: c["name"] for c in customers}

    # Get last order per customer via read_group (no record limit issue)
    last_order = {}
    if cust_ids:
        order_groups = _safe_read_group(
            client, "sale.order",
            [("partner_id", "in", cust_ids), ("state", "in", ("sale", "done"))],
            ["partner_id", "date_order:max"], ["partner_id"],
        )
        for g in order_groups:
            pid = g["partner_id"][0] if g.get("partner_id") else None
            max_date = g.get("date_order") or ""
            if pid and max_date:
                last_order[pid] = str(max_date)[:10]

    if section in ("all", "overview"):
        so_domain = [("state", "in", ("sale", "done")),
                     ("date_order", ">=", today),
                     ("date_order", "<", (today_date + timedelta(days=1)).isoformat())]
        if teams.get("farmer"):
            so_domain.append(("team_id", "=", teams["farmer"]))
        day_group = _safe_read_group(client, "sale.order", so_domain, ["amount_total"], [])
        day_count = (day_group[0].get("__count", 0)) if day_group else 0
        day_rev = (day_group[0]["amount_total"] or 0) if day_group else 0
        result["overview"] = {
            "orders_today": day_count,
            "revenue_today": day_rev,
            "total_customers": len(cust_ids),
        }

    if section in ("all", "reorder"):
        # Customers due for reorder (last order 25-35 days ago — typical monthly cycle)
        reorder_start = (today_date - timedelta(days=35)).isoformat()
        reorder_end = (today_date - timedelta(days=25)).isoformat()
        reorder_due = []
        for cid in cust_ids:
            lo = last_order.get(cid)
            if lo and reorder_end >= lo >= reorder_start:
                reorder_due.append({"id": cid, "name": cust_map[cid], "last_order": lo})
        result["reorder_due"] = {
            "count": len(reorder_due),
            "customers": reorder_due[:20],
        }

    if section in ("all", "sleeping"):
        buckets = {"30_60d": [], "60_90d": [], "90d_plus": []}
        for cid in cust_ids:
            lo = last_order.get(cid)
            if not lo:
                buckets["90d_plus"].append({"id": cid, "name": cust_map[cid], "last_order": None})
                continue
            days_since = (today_date - date.fromisoformat(lo)).days
            entry = {"id": cid, "name": cust_map[cid], "last_order": lo, "days_since": days_since}
            if days_since >= 90:
                buckets["90d_plus"].append(entry)
            elif days_since >= 60:
                buckets["60_90d"].append(entry)
            elif days_since >= 30:
                buckets["30_60d"].append(entry)
        result["sleeping"] = {
            "30_60d": {"count": len(buckets["30_60d"]), "customers": buckets["30_60d"][:10]},
            "60_90d": {"count": len(buckets["60_90d"]), "customers": buckets["60_90d"][:10]},
            "90d_plus": {"count": len(buckets["90d_plus"]), "customers": buckets["90d_plus"][:10]},
        }

    if section in ("all", "vip"):
        # VIP = top customers by rank, check if sleeping
        vip_customers = customers[:20]  # Already sorted by rank desc
        vip_at_risk = []
        for c in vip_customers:
            lo = last_order.get(c["id"])
            if not lo or (today_date - date.fromisoformat(lo)).days >= 60:
                vip_at_risk.append({
                    "id": c["id"], "name": c["name"],
                    "last_order": lo,
                    "days_since": (today_date - date.fromisoformat(lo)).days if lo else None,
                })
        result["vip_at_risk"] = {"count": len(vip_at_risk), "customers": vip_at_risk[:10]}

    if section in ("all", "retention"):
        # Retention: active vs sleeping ratio
        active = sum(1 for cid in cust_ids
                     if cid in last_order and (today_date - date.fromisoformat(last_order[cid])).days < 30)
        total = len(cust_ids)
        result["retention"] = {
            "active_customers": active,
            "total_customers": total,
            "retention_rate_pct": round((active / total * 100), 1) if total > 0 else 0,
        }

    return json.dumps(result, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_farmer_ar(limit: int = 20) -> str:
    """Farmer-scoped AR: total, aging buckets, top debtors.
    Filters by farmer team or hunter_farmer_type=farmer if available.

    Args:
        limit: Max debtor records (default 20, max 200)
    """
    client = get_client()
    limit = min(limit, 200)
    today_date = date.today()
    today = today_date.isoformat()

    # Build domain for farmer invoices
    base_domain = [("move_type", "=", "out_invoice"), ("state", "=", "posted"), ("amount_residual", ">", 0)]
    teams = _get_team_ids()
    if teams.get("farmer"):
        base_domain.append(("team_id", "=", teams["farmer"]))

    # Total
    total_group = _safe_read_group(client, "account.move", base_domain, ["amount_residual"], [])
    total = (total_group[0]["amount_residual"] or 0) if total_group else 0

    # Get invoices for aging
    invoices = client.search_read(
        "account.move", base_domain,
        fields=["name", "partner_id", "amount_residual", "invoice_date_due"],
        limit=200, order="amount_residual desc",
    )

    buckets = {"current": 0, "1_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0}
    for inv in invoices:
        due = inv.get("invoice_date_due")
        amt = inv["amount_residual"]
        if not due:
            buckets["current"] += amt
            continue
        days_past = (today_date - date.fromisoformat(str(due)[:10])).days
        if days_past <= 0:
            buckets["current"] += amt
        elif days_past <= 30:
            buckets["1_30"] += amt
        elif days_past <= 60:
            buckets["31_60"] += amt
        elif days_past <= 90:
            buckets["61_90"] += amt
        else:
            buckets["90_plus"] += amt

    # Top debtors
    partner_totals: dict[str, float] = {}
    for inv in invoices:
        pname = inv["partner_id"][1] if inv["partner_id"] else "Unknown"
        partner_totals[pname] = partner_totals.get(pname, 0) + inv["amount_residual"]
    top_debtors = sorted(partner_totals.items(), key=lambda x: x[1], reverse=True)[:limit]

    return json.dumps({
        "scope": "farmer",
        "total_receivable": total,
        "aging_buckets": buckets,
        "top_debtors": [{"partner": p, "amount": a} for p, a in top_debtors],
    }, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_congno(mode: str = "overdue", limit: int = 20) -> str:
    """Invoice collection list. mode=due_soon: invoices due within 7 days.
    mode=overdue: invoices past due. Each with dispute and collection status if available.

    Args:
        mode: 'due_soon' (due within 7d) or 'overdue' (past due) (default 'overdue')
        limit: Max records (default 20, max 200)
    """
    client = get_client()
    limit = min(limit, 200)
    today_date = date.today()
    today = today_date.isoformat()

    base_domain = [("move_type", "=", "out_invoice"), ("state", "=", "posted"), ("amount_residual", ">", 0)]

    if mode == "due_soon":
        due_7d = (today_date + timedelta(days=7)).isoformat()
        domain = base_domain + [("invoice_date_due", ">=", today), ("invoice_date_due", "<=", due_7d)]
        order = "invoice_date_due asc"
    else:  # overdue
        domain = base_domain + [("invoice_date_due", "<", today)]
        order = "invoice_date_due asc"

    fields = ["name", "partner_id", "amount_total", "amount_residual",
              "invoice_date", "invoice_date_due", "payment_state"]

    invoices = client.search_read(
        "account.move", domain,
        fields=fields,
        limit=limit, order=order,
    )

    records = []
    for inv in invoices:
        due = inv.get("invoice_date_due")
        days_info = 0
        if due:
            due_date = date.fromisoformat(str(due)[:10])
            days_info = (today_date - due_date).days
        records.append({
            "id": inv["id"],
            "invoice": inv["name"],
            "partner": inv["partner_id"][1] if inv["partner_id"] else None,
            "amount_total": inv["amount_total"],
            "amount_residual": inv["amount_residual"],
            "invoice_date": str(inv.get("invoice_date") or ""),
            "due_date": str(due or ""),
            "days_overdue": days_info if mode == "overdue" else None,
            "days_until_due": -days_info if mode == "due_soon" else None,
            "payment_state": inv.get("payment_state", ""),
        })

    # Summary
    total_amount = sum(r["amount_residual"] for r in records)

    # Data quality checks
    data_issues = []
    no_partner = [r for r in records if r["partner"] is None]
    if no_partner:
        data_issues.append(f"{len(no_partner)} hóa đơn không có khách hàng (partner)")
    result = {
        "mode": mode,
        "count": len(records),
        "total_amount": total_amount,
        "records": records,
        "data_quality": "issue" if data_issues else "ok",
        "data_issues": data_issues,
    }
    return json.dumps(result, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_task_overdue(team_filter: str = "", limit: int = 20) -> str:
    """Overdue tasks grouped by category and impact. Requires project module.

    Args:
        team_filter: 'hunter', 'farmer', or '' for all (default '')
        limit: Max records (default 20, max 200)
    """
    client = get_client()
    limit = min(limit, 200)
    today = _date_helpers()["today"]

    try:
        domain = [("date_deadline", "<", today), ("stage_id.fold", "=", False)]

        # Team filter by project name mapping
        if team_filter:
            # Filter by projects that contain the team name
            projects = client.search_read(
                "project.project",
                [("name", "ilike", team_filter)],
                fields=["id"],
                limit=50,
            )
            if projects:
                domain.append(("project_id", "in", [p["id"] for p in projects]))

        tasks = client.search_read(
            "project.task", domain,
            fields=["name", "user_ids", "date_deadline", "project_id",
                    "priority", "stage_id", "tag_ids"],
            limit=limit, order="date_deadline asc",
        )
    except xmlrpc.client.Fault as e:
        if "project.task" in str(e.faultString):
            return json.dumps({"error": "Project module not installed. Cannot fetch tasks."})
        raise

    today_date = date.today()
    records = []
    by_priority = {"3": 0, "2": 0, "1": 0, "0": 0}
    for task in tasks:
        dl = task.get("date_deadline")
        days_overdue = (today_date - date.fromisoformat(str(dl)[:10])).days if dl else 0
        priority = task.get("priority", "0")
        by_priority[priority] = by_priority.get(priority, 0) + 1
        records.append({
            "id": task["id"],
            "name": task["name"],
            "project": task["project_id"][1] if task["project_id"] else None,
            "stage": task["stage_id"][1] if task["stage_id"] else None,
            "priority": priority,
            "date_deadline": str(dl or ""),
            "days_overdue": days_overdue,
        })

    return json.dumps({
        "team_filter": team_filter or "all",
        "total_overdue": len(records),
        "by_priority": by_priority,
        "records": records,
    }, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_flash_report(report_type: str = "midday") -> str:
    """Compact flash report: revenue today, leads, orders, collections, open issues, tasks.
    EOD report adds delta_vs_yesterday.

    Args:
        report_type: 'midday' or 'eod' (default 'midday')
    """
    client = get_client()
    d = _date_helpers()
    today = d["today"]
    today_date = date.today()
    tomorrow = (today_date + timedelta(days=1)).isoformat()
    yesterday = d["yesterday"]

    # Revenue today
    rev_group = _safe_read_group(
        client, "sale.order",
        [("state", "in", ("sale", "done")),
         ("date_order", ">=", today), ("date_order", "<", tomorrow)],
        ["amount_total"], [],
    )
    revenue_today = (rev_group[0]["amount_total"] or 0) if rev_group else 0
    orders_today = (rev_group[0].get("__count", 0)) if rev_group else 0

    # Leads today
    leads_today = client.search_count(
        "crm.lead", [("create_date", ">=", today), ("create_date", "<", tomorrow)],
    )

    # Collections today (payments)
    coll_group = _safe_read_group(
        client, "account.payment",
        [("payment_type", "=", "inbound"), ("state", "=", "posted"),
         ("date", ">=", today), ("date", "<", tomorrow)],
        ["amount"], [],
    )
    collections_today = (coll_group[0]["amount"] or 0) if coll_group else 0

    # Open issues: overdue invoices + SLA breached leads
    overdue_inv = client.search_count(
        "account.move",
        [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
         ("amount_residual", ">", 0), ("invoice_date_due", "<", today)],
    )
    sla_cutoff = (datetime.now() - timedelta(hours=48)).isoformat()
    sla_breached = client.search_count(
        "crm.lead",
        [("type", "=", "opportunity"), ("active", "=", True),
         ("stage_id.is_won", "=", False), ("create_date", "<", sla_cutoff)],
    )

    # Overdue tasks
    overdue_tasks = 0
    try:
        overdue_tasks = client.search_count(
            "project.task",
            [("date_deadline", "<", today), ("stage_id.fold", "=", False)],
        )
    except xmlrpc.client.Fault as e:
        if "project.task" in str(e.faultString):
            overdue_tasks = 0  # Module not installed
        else:
            logger.error("Overdue task count failed: %s", e.faultString)
    except Exception as e:
        logger.error("Overdue task count failed: %s", e)

    result = {
        "report_type": report_type,
        "date": today,
        "revenue_today": revenue_today,
        "orders_today": orders_today,
        "leads_today": leads_today,
        "collections_today": collections_today,
        "open_issues": {
            "overdue_invoices": overdue_inv,
            "sla_breached_leads": sla_breached,
            "overdue_tasks": overdue_tasks,
        },
    }

    # EOD: add delta vs yesterday
    if report_type == "eod":
        yesterday_end = today
        rev_yday = _safe_read_group(
            client, "sale.order",
            [("state", "in", ("sale", "done")),
             ("date_order", ">=", yesterday), ("date_order", "<", yesterday_end)],
            ["amount_total"], [],
        )
        rev_yesterday = (rev_yday[0]["amount_total"] or 0) if rev_yday else 0
        leads_yesterday = client.search_count(
            "crm.lead",
            [("create_date", ">=", yesterday), ("create_date", "<", yesterday_end)],
        )
        coll_yday = _safe_read_group(
            client, "account.payment",
            [("payment_type", "=", "inbound"), ("state", "=", "posted"),
             ("date", ">=", yesterday), ("date", "<", yesterday_end)],
            ["amount"], [],
        )
        coll_yesterday = (coll_yday[0]["amount"] or 0) if coll_yday else 0

        result["delta_vs_yesterday"] = {
            "revenue": revenue_today - rev_yesterday,
            "leads": leads_today - leads_yesterday,
            "collections": collections_today - coll_yesterday,
        }

    return json.dumps(result, indent=2, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Action Tools (7 tools)
# ---------------------------------------------------------------------------

@mcp.tool()
@_odoo_error
def odoo_mark_contacted(lead_id: int) -> str:
    """Mark a CRM lead as contacted by setting first_touch_date to current datetime.

    Args:
        lead_id: CRM lead ID (crm.lead record)
    """
    client = get_client()
    leads = client.search_read(
        "crm.lead", [("id", "=", lead_id)],
        fields=["name"],
        limit=1,
    )
    if not leads:
        raise ValueError(f"Lead {lead_id} not found")

    now = datetime.now().isoformat()
    # first_touch_date is a custom field — check existence before writing
    try:
        flds = client.fields_get("crm.lead", attributes=["type"])
        if "first_touch_date" in flds:
            client.write("crm.lead", [lead_id], {"first_touch_date": now})
        else:
            # Fallback: post a note on the chatter
            with client._lock:
                client._object.execute_kw(
                    client.db, client.uid, client.password,
                    "crm.lead", "message_post", [[lead_id]],
                    {"body": f"Marked as contacted at {now}", "message_type": "comment",
                     "subtype_xmlid": "mail.mt_note"},
                )
    except xmlrpc.client.Fault:
        # Field doesn't exist, just log via message_post
        with client._lock:
            client._object.execute_kw(
                client.db, client.uid, client.password,
                "crm.lead", "message_post", [[lead_id]],
                {"body": f"Marked as contacted at {now}", "message_type": "comment",
                 "subtype_xmlid": "mail.mt_note"},
            )

    return json.dumps({
        "success": True,
        "lead_id": lead_id,
        "lead_name": leads[0]["name"],
        "contacted_at": now,
        "message": f"Lead '{leads[0]['name']}' marked as contacted",
    }, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_mark_collection(invoice_id: int, status: str) -> str:
    """Set collection status on an invoice (account.move).

    Args:
        invoice_id: Invoice ID (account.move record)
        status: Collection status: 'none', 'reminded', 'promised', 'collected'
    """
    valid_statuses = ("none", "reminded", "promised", "collected")
    if status not in valid_statuses:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}")

    client = get_client()
    invoices = client.search_read(
        "account.move", [("id", "=", invoice_id)],
        fields=["name"],
        limit=1,
    )
    if not invoices:
        raise ValueError(f"Invoice {invoice_id} not found")

    # collection_status is a custom field — verify it exists
    flds = client.fields_get("account.move", attributes=["type"])
    if "collection_status" not in flds:
        raise ValueError("Field 'collection_status' not found on account.move — masios_command_center module may not be installed")

    client.write("account.move", [invoice_id], {"collection_status": status})
    return json.dumps({
        "success": True,
        "invoice_id": invoice_id,
        "invoice_name": invoices[0]["name"],
        "collection_status": status,
        "message": f"Invoice {invoices[0]['name']} collection status set to '{status}'",
    }, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_set_dispute(invoice_id: int, note: str) -> str:
    """Mark an invoice as disputed with a note.

    Args:
        invoice_id: Invoice ID (account.move record)
        note: Dispute description/reason
    """
    client = get_client()
    invoices = client.search_read(
        "account.move", [("id", "=", invoice_id)],
        fields=["name"],
        limit=1,
    )
    if not invoices:
        raise ValueError(f"Invoice {invoice_id} not found")

    # dispute_status/dispute_note are custom fields — verify existence
    flds = client.fields_get("account.move", attributes=["type"])
    if "dispute_status" not in flds:
        raise ValueError("Field 'dispute_status' not found on account.move — masios_command_center module may not be installed")

    vals = {"dispute_status": "disputed"}
    if "dispute_note" in flds:
        vals["dispute_note"] = note
    client.write("account.move", [invoice_id], vals)
    return json.dumps({
        "success": True,
        "invoice_id": invoice_id,
        "invoice_name": invoices[0]["name"],
        "dispute_status": "disputed",
        "dispute_note": note,
        "message": f"Invoice {invoices[0]['name']} marked as disputed",
    }, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_change_owner(model: str, record_id: int, new_user_id: int) -> str:
    """Change the owner (user_id or hunter_owner_id for crm.lead) on a record.

    Args:
        model: Model name (e.g. 'crm.lead', 'sale.order')
        record_id: Record ID to update
        new_user_id: New owner's user ID (res.users)
    """
    if model not in _ALLOWED_ACTION_MODELS:
        return json.dumps({"error": f"Model '{model}' is not allowed for change_owner"})
    client = get_client()

    # Validate new user exists
    users = client.search_read(
        "res.users", [("id", "=", new_user_id)],
        fields=["name"],
        limit=1,
    )
    if not users:
        raise ValueError(f"User {new_user_id} not found")
    new_user_name = users[0]["name"]

    # Determine which field to use
    owner_field = "user_id"
    if model == "crm.lead":
        try:
            flds = client.fields_get(model, attributes=["string", "type"])
            if "hunter_owner_id" in flds:
                owner_field = "hunter_owner_id"
        except xmlrpc.client.Fault:
            pass
        except Exception as e:
            logger.warning("Field check for hunter_owner_id failed: %s", e)

    # Read current owner
    records = client.search_read(
        model, [("id", "=", record_id)],
        fields=["name" if model != "account.move" else "name", owner_field],
        limit=1,
    )
    if not records:
        raise ValueError(f"{model} record {record_id} not found")

    record = records[0]
    old_owner = record.get(owner_field)
    old_owner_name = old_owner[1] if isinstance(old_owner, (list, tuple)) and old_owner else "None"

    # Update owner
    client.write(model, [record_id], {owner_field: new_user_id})
    return json.dumps({
        "success": True,
        "model": model,
        "record_id": record_id,
        "owner_field": owner_field,
        "old_owner": old_owner_name,
        "new_owner": new_user_name,
        "message": f"Owner changed: {old_owner_name} → {new_user_name}",
    }, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_escalate(model: str, record_id: int, note: str) -> str:
    """Create an escalation task (project.task) linked to a record.

    Args:
        model: Source model (e.g. 'crm.lead', 'account.move')
        record_id: Source record ID
        note: Escalation description
    """
    if model not in _ALLOWED_ACTION_MODELS:
        return json.dumps({"error": f"Model '{model}' is not allowed for escalation"})
    client = get_client()

    # Read source record for context
    name_field = "name"
    records = client.search_read(
        model, [("id", "=", record_id)],
        fields=[name_field, "partner_id"] if model != "res.partner" else [name_field],
        limit=1,
    )
    if not records:
        raise ValueError(f"{model} record {record_id} not found")

    record = records[0]
    record_name = record.get(name_field, str(record_id))
    partner_id = None
    if model == "res.partner":
        partner_id = record_id
    elif record.get("partner_id"):
        partner_id = record["partner_id"][0] if isinstance(record["partner_id"], (list, tuple)) else record["partner_id"]

    # Build task values
    task_vals = {
        "name": f"[Escalation] {model} #{record_id}: {record_name}",
        "description": f"Escalation from {model} record {record_id} ({record_name})\n\n{note}",
        "priority": "1",  # High priority
    }

    # Try to set command center fields if available
    try:
        task_fields = client.fields_get("project.task", attributes=["string", "type"])
        if "task_category" in task_fields:
            task_vals["task_category"] = "escalation"
        if "impact_level" in task_fields:
            task_vals["impact_level"] = "high"
        if "source_alert_code" in task_fields:
            task_vals["source_alert_code"] = f"{model},{record_id}"
        if "related_partner_id" in task_fields and partner_id:
            task_vals["related_partner_id"] = partner_id
        if partner_id and "partner_id" in task_fields:
            task_vals["partner_id"] = partner_id
    except xmlrpc.client.Fault:
        pass
    except Exception as e:
        logger.warning("Escalation field check failed: %s", e)

    task_id = client.create("project.task", task_vals)
    return json.dumps({
        "success": True,
        "task_id": task_id,
        "source_model": model,
        "source_record_id": record_id,
        "source_record_name": record_name,
        "message": f"Escalation task #{task_id} created for {model} #{record_id}",
    }, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_complete_task(task_id: int) -> str:
    """Complete a task by moving it to the 'Done' stage.

    Args:
        task_id: Task ID (project.task record)
    """
    client = get_client()

    # Read the task to get its project
    tasks = client.search_read(
        "project.task", [("id", "=", task_id)],
        fields=["name", "project_id", "stage_id"],
        limit=1,
    )
    if not tasks:
        raise ValueError(f"Task {task_id} not found")

    task = tasks[0]
    project_id = task["project_id"][0] if task["project_id"] else None

    # Find the "Done" stage (fold=True and is the last stage, or name contains "Done"/"Terminé")
    done_stage = None

    # Strategy 1: Look for folded stages in the project's type
    stage_domain = [("fold", "=", True)]
    if project_id:
        stage_domain = ["|", ("project_ids", "in", [project_id]), ("project_ids", "=", False),
                        ("fold", "=", True)]

    done_stages = client.search_read(
        "project.task.type", stage_domain,
        fields=["name", "sequence", "fold"],
        limit=10, order="sequence desc",
    )

    if done_stages:
        # Prefer stage with "done"/"terminé"/"hoàn thành" in the name
        for s in done_stages:
            name_lower = (s.get("name") or "").lower()
            if any(kw in name_lower for kw in ("done", "terminé", "hoàn thành", "hoàn tất", "xong")):
                done_stage = s
                break
        if not done_stage:
            done_stage = done_stages[0]  # Use the highest sequence folded stage
    else:
        # Strategy 2: Get all stages and pick the last one
        all_stages = client.search_read(
            "project.task.type", [],
            fields=["name", "sequence", "fold"],
            limit=50, order="sequence desc",
        )
        if all_stages:
            done_stage = all_stages[0]

    if not done_stage:
        raise ValueError("Could not find a 'Done' stage for this project")

    client.write("project.task", [task_id], {"stage_id": done_stage["id"]})
    return json.dumps({
        "success": True,
        "task_id": task_id,
        "task_name": task["name"],
        "new_stage": done_stage["name"],
        "message": f"Task '{task['name']}' moved to '{done_stage['name']}'",
    }, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
@_odoo_error
def odoo_audit_log(action: str, model: str, record_id: int, user_telegram_id: str, details: str) -> str:
    """Create an audit log entry on a record using message_post (chatter) or mail.message.

    Args:
        action: Action performed (e.g. 'mark_contacted', 'change_owner', 'escalate')
        model: Model of the record (e.g. 'crm.lead', 'account.move')
        record_id: Record ID to log against
        user_telegram_id: Telegram user ID who performed the action
        details: Description of what was done
    """
    client = get_client()

    # Verify record exists
    records = client.search_read(
        model, [("id", "=", record_id)],
        fields=["name"] if model != "account.move" else ["name"],
        limit=1,
    )
    if not records:
        raise ValueError(f"{model} record {record_id} not found")

    import html as _html
    # Truncate inputs to prevent database bloat
    safe_action = _html.escape(action[:100])
    safe_details = _html.escape(details[:2000])
    log_body = (
        f"<p><strong>Audit Log</strong></p>"
        f"<ul>"
        f"<li><strong>Action:</strong> {safe_action}</li>"
        f"<li><strong>Telegram User:</strong> {_html.escape(user_telegram_id)}</li>"
        f"<li><strong>Details:</strong> {safe_details}</li>"
        f"<li><strong>Timestamp:</strong> {datetime.now().isoformat()}</li>"
        f"</ul>"
    )

    # Try message_post first (works on models that inherit mail.thread)
    log_id = None
    try:
        with client._lock:
            log_id = client._object.execute_kw(
                client.db, client.uid, client.password,
                model, "message_post", [[record_id]],
                {
                    "body": log_body,
                    "message_type": "comment",
                    "subtype_xmlid": "mail.mt_note",
                },
            )
    except xmlrpc.client.Fault:
        # Model doesn't support message_post — create a standalone mail.message
        try:
            log_id = client.create("mail.message", {
                "model": model,
                "res_id": record_id,
                "body": log_body,
                "message_type": "comment",
            })
        except Exception as e:
            logger.warning(f"Could not create audit log: {e}")
            log_id = None

    success = log_id is not None
    result = {
        "success": success,
        "log_id": log_id,
        "action": action,
        "model": model,
        "record_id": record_id,
        "user_telegram_id": user_telegram_id,
    }
    if success:
        result["message"] = f"Audit log created for {action} on {model} #{record_id}"
    else:
        result["warning"] = f"Audit log creation failed for {action} on {model} #{record_id}"
    return json.dumps(result, indent=2, ensure_ascii=False, default=str)

# ---------------------------------------------------------------------------
# Telegram Permission System
# ---------------------------------------------------------------------------

COMMAND_CATALOG = {
    "ceo_reports": {
        "label": "📊 Báo cáo CEO",
        "commands": {
            "morning_brief": "Báo cáo buổi sáng",
            "ceo_alert": "Cảnh báo khẩn cấp",
            "doanhso_homnay": "Doanh số hôm nay",
            "brief_hunter": "Tổng hợp Hunter",
            "brief_farmer": "Tổng hợp Farmer",
            "brief_ar": "Tổng hợp công nợ",
            "brief_cash": "Tổng hợp dòng tiền",
        }
    },
    "hunter": {
        "label": "🎯 Hunter — Săn khách mới",
        "commands": {
            "hunter_today": "Tổng quan Hunter hôm nay",
            "hunter_sla": "SLA phản hồi lead",
            "hunter_quotes": "Báo giá đang chờ",
            "hunter_first_orders": "Đơn hàng đầu tiên",
            "hunter_sources": "Nguồn lead",
            "khachmoi_homnay": "Khách mới hôm nay",
        }
    },
    "farmer": {
        "label": "🌱 Farmer — Chăm khách cũ",
        "commands": {
            "farmer_today": "Tổng quan Farmer hôm nay",
            "farmer_reorder": "Khách cần tái đặt hàng",
            "farmer_sleeping": "Khách ngủ đông",
            "farmer_vip": "Khách VIP",
            "farmer_ar": "Công nợ Farmer",
            "farmer_retention": "Tỷ lệ giữ chân",
        }
    },
    "finance": {
        "label": "💰 Finance — Công nợ",
        "commands": {
            "congno_denhan": "Công nợ đến hạn",
            "congno_quahan": "Công nợ quá hạn",
        }
    },
    "ops": {
        "label": "⚙️ Vận hành",
        "commands": {
            "task_quahan": "Task quá hạn",
            "midday": "Báo cáo giữa ngày",
            "eod": "Báo cáo cuối ngày",
        }
    },
    "utility": {
        "label": "🔧 Tiện ích",
        "commands": {
            "kpi": "KPI dashboard",
            "pipeline": "Pipeline CRM",
            "newlead": "Tạo lead mới",
            "newcustomer": "Tạo khách hàng",
            "quote": "Tạo báo giá + PDF",
            "invoice": "Tạo hóa đơn + PDF",
            "credit": "Kiểm tra công nợ KH",
            "findcustomer": "Tìm khách hàng",
        }
    },
    "actions": {
        "label": "⚡ Hành động nhanh",
        "commands": {
            "da_lien_he": "Đánh dấu đã liên hệ lead",
            "da_nhac_no": "Đánh dấu đã nhắc nợ",
            "gan_dispute": "Gắn tranh chấp hóa đơn",
            "doi_owner": "Đổi người phụ trách",
            "escalate": "Báo cáo cấp trên",
            "tao_task": "Tạo task mới",
            "xong": "Đánh dấu hoàn thành task",
        }
    },
}


def _resolve_user_permissions(client, telegram_id: str):
    """Look up Telegram user and role, return (user, role) or raise ValueError."""
    users = client.search_read(
        "masios.telegram_user",
        [("telegram_id", "=", telegram_id)],
        fields=["name", "role_id", "extra_commands", "blocked_commands", "active"],
        limit=1,
    )
    if not users:
        return None, None

    user = users[0]
    if not user.get("active", True):
        return user, None

    role_id = user["role_id"][0] if user.get("role_id") else None
    if not role_id:
        return user, None

    roles = client.search_read(
        "masios.telegram_role",
        [("id", "=", role_id)],
        fields=["name", "code", "allowed_commands", "allowed_actions", "view_scope"],
        limit=1,
    )
    role = roles[0] if roles else None
    return user, role


def _parse_command_list(raw: str | None) -> list[str]:
    """Parse a newline-separated command list string."""
    if not raw or not raw.strip():
        return []
    return [c.strip() for c in raw.strip().split("\n") if c.strip()]


@mcp.tool()
@_odoo_error
def odoo_telegram_check_permission(telegram_id: str, command: str = "", action: str = "") -> str:
    """Check if a Telegram user has permission to use a command or perform an action.

    Args:
        telegram_id: Telegram user ID
        command: Command to check (e.g. 'morning_brief', 'quote'). Empty = skip command check.
        action: Action to check (e.g. 'create_lead', 'change_owner'). Empty = skip action check.
    """
    client = get_client()
    user, role = _resolve_user_permissions(client, telegram_id)

    if user is None:
        return json.dumps({
            "allowed": False,
            "reason": "Telegram ID chưa được đăng ký trong hệ thống",
        }, indent=2, ensure_ascii=False)

    if role is None:
        if not user.get("active", True):
            return json.dumps({
                "allowed": False,
                "reason": "Tài khoản đã bị vô hiệu hóa",
            }, indent=2, ensure_ascii=False)
        return json.dumps({
            "allowed": False,
            "reason": "Tài khoản chưa được gán vai trò",
        }, indent=2, ensure_ascii=False)

    result = {
        "allowed": True,
        "role": role["code"],
        "role_name": role["name"],
        "user_name": user["name"],
        "view_scope": role.get("view_scope", ""),
        "reason": "OK",
    }

    # Parse role allowed commands
    raw_cmds = (role.get("allowed_commands") or "").strip()
    if raw_cmds == "*":
        allowed_cmds = ["*"]
    else:
        allowed_cmds = _parse_command_list(role.get("allowed_commands"))

    # Add extra commands, collect blocked
    extra = _parse_command_list(user.get("extra_commands"))
    if extra:
        allowed_cmds.extend(extra)
    blocked = set(_parse_command_list(user.get("blocked_commands")))

    # Check command permission
    if command:
        if command in blocked:
            result["allowed"] = False
            result["reason"] = f"Lệnh '{command}' đã bị chặn cho tài khoản của bạn"
        elif "*" in allowed_cmds:
            result["allowed"] = True
        elif command in allowed_cmds:
            result["allowed"] = True
        else:
            result["allowed"] = False
            result["reason"] = f"Vai trò '{role['name']}' không có quyền sử dụng lệnh '{command}'"

    # Check action permission
    if action and result["allowed"]:
        raw_actions = (role.get("allowed_actions") or "").strip()
        if raw_actions == "*":
            allowed_actions = ["*"]
        else:
            allowed_actions = _parse_command_list(role.get("allowed_actions"))

        if "*" in allowed_actions:
            result["allowed"] = True
        elif action in allowed_actions:
            result["allowed"] = True
        else:
            result["allowed"] = False
            result["reason"] = f"Vai trò '{role['name']}' không có quyền thực hiện hành động '{action}'"

    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
@_odoo_error
def odoo_telegram_get_menu(telegram_id: str) -> str:
    """Get the list of available commands for a Telegram user, organized by category.

    Args:
        telegram_id: Telegram user ID
    """
    client = get_client()
    user, role = _resolve_user_permissions(client, telegram_id)

    if user is None:
        return json.dumps({
            "error": "Telegram ID chưa được đăng ký trong hệ thống",
        }, indent=2, ensure_ascii=False)

    if role is None:
        reason = "Tài khoản đã bị vô hiệu hóa" if not user.get("active", True) else "Tài khoản chưa được gán vai trò"
        return json.dumps({"error": reason}, indent=2, ensure_ascii=False)

    # Parse role allowed commands
    raw_cmds = (role.get("allowed_commands") or "").strip()
    if raw_cmds == "*":
        allowed_cmds = {"*"}
    else:
        allowed_cmds = set(_parse_command_list(role.get("allowed_commands")))

    # Add extra commands, collect blocked
    extra = _parse_command_list(user.get("extra_commands"))
    if extra:
        allowed_cmds.update(extra)
    blocked = set(_parse_command_list(user.get("blocked_commands")))

    # Filter catalog
    categories = {}
    for cat_key, cat_data in COMMAND_CATALOG.items():
        visible_commands = []
        for cmd, desc in cat_data["commands"].items():
            if cmd in blocked:
                continue
            if "*" in allowed_cmds or cmd in allowed_cmds:
                visible_commands.append({"command": cmd, "description": desc})
        if visible_commands:
            categories[cat_key] = {
                "label": cat_data["label"],
                "commands": visible_commands,
            }

    return json.dumps({
        "user_name": user["name"],
        "role": role["code"],
        "role_name": role["name"],
        "view_scope": role.get("view_scope", ""),
        "categories": categories,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
@_odoo_error
def odoo_telegram_list_users() -> str:
    """List all registered Telegram users with their roles."""
    client = get_client()
    users = client.search_read(
        "masios.telegram_user", [],
        fields=["name", "telegram_id", "telegram_username", "role_id", "active"],
        order="name",
    )

    result = []
    # Collect role IDs for batch lookup
    role_ids = list({u["role_id"][0] for u in users if u.get("role_id")})
    roles_map = {}
    if role_ids:
        roles = client.search_read(
            "masios.telegram_role",
            [("id", "in", role_ids)],
            fields=["name", "code", "view_scope"],
        )
        roles_map = {r["id"]: r for r in roles}

    for u in users:
        role_data = {}
        if u.get("role_id"):
            r = roles_map.get(u["role_id"][0], {})
            role_data = {
                "role_name": r.get("name", ""),
                "role_code": r.get("code", ""),
                "view_scope": r.get("view_scope", ""),
            }
        else:
            role_data = {"role_name": "", "role_code": "", "view_scope": ""}

        result.append({
            "name": u["name"],
            "telegram_id": u["telegram_id"],
            "telegram_username": u.get("telegram_username", ""),
            "active": u.get("active", True),
            **role_data,
        })

    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
@_odoo_error
def odoo_telegram_register_user(telegram_id: str, name: str, role_code: str,
                                telegram_username: str = "", caller_telegram_id: str = "") -> str:
    """Register a new Telegram user or update an existing one.
    Restricted to CEO and Admin roles only.

    Args:
        telegram_id: Telegram user ID to register
        name: Display name for the user
        role_code: Role code to assign (e.g. 'ceo', 'hunter', 'farmer', 'accountant')
        telegram_username: Optional Telegram username (without @)
        caller_telegram_id: Telegram ID of the user making this request (for permission check)
    """
    client = get_client()

    # Permission check: only CEO and Admin/Tech can register users
    if caller_telegram_id:
        caller_user, caller_role = _resolve_user_permissions(client, caller_telegram_id)
        if caller_role is None or caller_role.get("code") not in ("ceo", "admin_tech"):
            return json.dumps({
                "error": "Chỉ CEO hoặc Admin/Tech mới có quyền đăng ký người dùng mới",
                "allowed_roles": ["ceo", "admin_tech"],
            }, indent=2, ensure_ascii=False)

    # Find role by code
    roles = client.search_read(
        "masios.telegram_role",
        [("code", "=", role_code)],
        fields=["name", "code", "view_scope"],
        limit=1,
    )
    if not roles:
        available = client.search_read(
            "masios.telegram_role", [],
            fields=["code", "name"],
            order="code",
        )
        codes = [r["code"] for r in available]
        raise ValueError(f"Vai trò '{role_code}' không tồn tại. Các vai trò hợp lệ: {', '.join(codes)}")

    role = roles[0]

    # Check if user already exists (including inactive)
    existing = client.search_read(
        "masios.telegram_user",
        [("telegram_id", "=", telegram_id)],
        fields=["id", "name"],
        limit=1,
    )

    vals = {
        "telegram_id": telegram_id,
        "name": name,
        "role_id": role["id"],
        "active": True,
    }
    if telegram_username:
        vals["telegram_username"] = telegram_username

    if existing:
        client.write("masios.telegram_user", [existing[0]["id"]], vals)
        user_id = existing[0]["id"]
        action = "updated"
    else:
        user_id = client.create("masios.telegram_user", vals)
        action = "created"

    return json.dumps({
        "success": True,
        "action": action,
        "user_id": user_id,
        "name": name,
        "telegram_id": telegram_id,
        "telegram_username": telegram_username,
        "role_code": role["code"],
        "role_name": role["name"],
        "view_scope": role.get("view_scope", ""),
        "message": f"Người dùng '{name}' đã được {action} với vai trò '{role['name']}'",
    }, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _generate_token() -> str:
    """Generate a cryptographically secure API token."""
    return secrets.token_urlsafe(32)


def _create_authed_app(app, api_token: str):
    """Wrap a Starlette app with bearer token authentication middleware.

    Only checks auth on POST /messages requests (the command channel).
    GET /sse (the SSE event stream) is left unblocked so the long-lived
    connection doesn't interfere with response delivery.
    """
    from starlette.responses import JSONResponse
    from starlette.types import ASGIApp, Receive, Scope, Send

    class BearerTokenMiddleware:
        def __init__(self, wrapped_app: ASGIApp, token: str):
            self.app = wrapped_app
            self.token = token

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return

            # Enforce auth on all HTTP requests (SSE + messages)
            path = scope.get("path", "")
            # Skip auth for health check endpoint only
            if path == "/health":
                await self.app(scope, receive, send)
                return

            # Extract Authorization header from ASGI scope
            auth_header = ""
            for header_name, header_value in scope.get("headers", []):
                if header_name == b"authorization":
                    auth_header = header_value.decode("latin-1")
                    break
            if not auth_header.startswith("Bearer "):
                response = JSONResponse(
                    {"error": "Missing Authorization header. Use: Bearer <token>"},
                    status_code=401,
                )
                await response(scope, receive, send)
                return
            provided_token = auth_header[7:]
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
            print("ERROR: No MCP_API_TOKEN set — refusing to start HTTP server without authentication!", file=sys.stderr)
            print("Generate one with: python3 server.py --generate-token", file=sys.stderr)
            print("Then add MCP_API_TOKEN=<token> to /etc/odoo-mcp/credentials", file=sys.stderr)
            sys.exit(1)

        mcp.settings.host = cli_args.host
        mcp.settings.port = cli_args.port

        if api_token:
            # Wrap the Starlette app with bearer token auth
            import uvicorn
            app = mcp.sse_app()
            authed_app = _create_authed_app(app, api_token)
            print(f"Starting Odoo MCP Server on {cli_args.host}:{cli_args.port} (SSE, token auth enabled)")
            uvicorn.run(
                authed_app,
                host=cli_args.host,
                port=cli_args.port,
                timeout_keep_alive=30,
                limit_concurrency=50,
                backlog=128,
                ws_ping_interval=20,
                ws_ping_timeout=10,
                h11_max_incomplete_event_size=64 * 1024,
            )
        # Note: the else branch (no token) is unreachable because
        # we sys.exit(1) above when api_token is empty.
    else:
        mcp.run()
