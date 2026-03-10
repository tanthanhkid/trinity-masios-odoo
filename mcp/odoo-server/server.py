#!/usr/bin/env python3
"""
Odoo MCP Server — Real-time bridge between Claude Code and Odoo instance.

Exposes Odoo's XML-RPC API as MCP tools for:
- Model/field introspection (types, constraints, relations)
- CRUD operations on any model
- CRM-specific helpers
- Authentication info

Requires: pip install mcp xmlrpc-client (xmlrpc is stdlib)
"""

import json
import os
import sys
import xmlrpc.client
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

# MCP SDK
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("ERROR: Install mcp package: pip install mcp", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Load Odoo connection config from environment or .env.local file."""
    # Try .env.local in project root (2 levels up from this file)
    env_file = Path(__file__).resolve().parent.parent.parent / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))

    return {
        "url": os.environ.get("ODOO_URL", "http://103.72.97.51:8069"),
        "db": os.environ.get("ODOO_DB", "odoo"),
        "username": os.environ.get("ODOO_USERNAME", "admin"),
        "password": os.environ.get("ODOO_PASSWORD", ""),
    }


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

    def fields_get(
        self, model: str, fields: list[str] | None = None,
        attributes: list[str] | None = None,
    ) -> dict:
        attrs = attributes or [
            "string", "type", "required", "readonly", "help",
            "size", "relation", "relation_field", "selection",
            "domain", "store", "depends",
        ]
        kw = {"attributes": attrs}
        if fields:
            kw["allfields"] = False  # not used, just pass fields list
            return self._object.execute_kw(
                self.db, self.uid, self.password, model, "fields_get",
                [fields], {"attributes": attrs},
            )
        return self._object.execute_kw(
            self.db, self.uid, self.password, model, "fields_get",
            [], {"attributes": attrs},
        )

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

    def read(self, model: str, ids: list[int], fields: list[str] | None = None) -> list[dict]:
        kw = {}
        if fields:
            kw["fields"] = fields
        return self.execute(model, "read", ids, **kw)

    def create(self, model: str, values: dict) -> int:
        return self._object.execute_kw(
            self.db, self.uid, self.password, model, "create", [[values]], {},
        )

    def write(self, model: str, ids: list[int], values: dict) -> bool:
        return self.execute(model, "write", ids, values)

    def unlink(self, model: str, ids: list[int]) -> bool:
        return self.execute(model, "unlink", ids)

    def server_version(self) -> str:
        return self._common.version()


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "odoo",
    instructions="Real-time Odoo introspection and CRUD via XML-RPC",
)

_client: OdooClient | None = None


def get_client() -> OdooClient:
    global _client
    if _client is None:
        cfg = load_config()
        if not cfg["password"]:
            raise ValueError(
                "ODOO_PASSWORD not set. Add it to .env.local:\n"
                "ODOO_PASSWORD=your_admin_password"
            )
        _client = OdooClient(**cfg)
    return _client


# --- Introspection Tools ---

@mcp.tool()
def odoo_server_info() -> str:
    """Get Odoo server version and connection info (no secrets exposed)."""
    client = get_client()
    ver = client.server_version()
    return json.dumps({
        "url": client.url,
        "db": client.db,
        "user": client.username,
        "server_version": ver,
    }, indent=2)


@mcp.tool()
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
def odoo_model_access(model: str) -> str:
    """Get access rights (CRUD permissions) for a model by group.

    Args:
        model: Model technical name (e.g. 'crm.lead')
    """
    client = get_client()
    # Find model id
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
        # Include arch for small views, truncate for large ones
        arch = v.get("arch_db", "") or ""
        if len(arch) <= 2000:
            entry["arch_xml"] = arch
        else:
            entry["arch_xml_truncated"] = arch[:2000] + "... (truncated)"
        result.append(entry)
    return json.dumps(result, indent=2, ensure_ascii=False)


# --- CRM-Specific Tools ---

@mcp.tool()
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
    parsed_domain = _parse_json(domain) if domain else []
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
def odoo_count(model: str, domain: Any = "[]") -> str:
    """Count records matching a domain.

    Args:
        model: Model name
        domain: Search domain as JSON string
    """
    client = get_client()
    parsed_domain = _parse_json(domain) if domain else []
    count = client.search_count(model, parsed_domain)
    return json.dumps({"model": model, "domain": domain, "count": count})


def _parse_json(val: str | dict | list) -> Any:
    """Parse JSON string or pass through already-parsed objects."""
    if isinstance(val, (dict, list, int, float, bool)):
        return val
    return json.loads(val)


@mcp.tool()
def odoo_create(model: str, values: Any = "{}") -> str:
    """Create a new record in any Odoo model.

    Args:
        model: Model name (e.g. 'crm.lead')
        values: JSON string of field values (e.g. '{"name": "New Lead", "partner_id": 1}')
    """
    client = get_client()
    parsed_values = _parse_json(values)
    record_id = client.create(model, parsed_values)
    return json.dumps({"model": model, "created_id": record_id})


@mcp.tool()
def odoo_write(model: str, ids: Any = "[]", values: Any = "{}") -> str:
    """Update existing records.

    Args:
        model: Model name
        ids: JSON array of record IDs (e.g. '[1, 2, 3]')
        values: JSON string of field values to update
    """
    client = get_client()
    parsed_ids = _parse_json(ids)
    parsed_values = _parse_json(values)
    result = client.write(model, parsed_ids, parsed_values)
    return json.dumps({"model": model, "ids": parsed_ids, "success": result})


@mcp.tool()
def odoo_delete(model: str, ids: Any = "[]") -> str:
    """Delete records from a model. USE WITH CAUTION.

    Args:
        model: Model name
        ids: JSON array of record IDs to delete
    """
    client = get_client()
    parsed_ids = _parse_json(ids)
    result = client.unlink(model, parsed_ids)
    return json.dumps({"model": model, "deleted_ids": parsed_ids, "success": result})


@mcp.tool()
def odoo_execute(model: str, method: str, args: Any = "[]", kwargs: Any = "{}") -> str:
    """Execute any method on an Odoo model (advanced).

    Args:
        model: Model name
        method: Method name (e.g. 'action_set_won', 'message_post')
        args: JSON array of positional arguments
        kwargs: JSON object of keyword arguments
    """
    client = get_client()
    parsed_args = _parse_json(args)
    parsed_kwargs = _parse_json(kwargs)
    result = client._object.execute_kw(
        client.db, client.uid, client.password,
        model, method, parsed_args, parsed_kwargs,
    )
    return json.dumps(result, indent=2, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
