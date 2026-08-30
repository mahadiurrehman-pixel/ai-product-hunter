"""
REHU UI Helpers — Single shared utility module.

Formatters, URL resolvers, view-model mappers, badge renderers,
session-state management, and global CSS.

Pure presentation utilities. No business logic. No backend imports
except data contracts (ProfitResult, PipelineResult shapes via dicts).
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st


# ===================================================================
# Constants
# ===================================================================

MARKETPLACE_LABELS = {
    "US": "United States",
    "UK": "United Kingdom",
    "DE": "Germany",
    "AU": "Australia",
    "CA": "Canada",
}

CURRENCY_SYMBOLS = {
    "USD": "$", "GBP": "\u00a3", "EUR": "\u20ac", "AUD": "A$", "CAD": "C$",
}

RECOMMENDATION_STYLES = {
    "strong_buy": {"label": "STRONG BUY", "bg": "#ECFDF5", "fg": "#047857", "bd": "#A7F3D0"},
    "buy":        {"label": "BUY",        "bg": "#F0FDF4", "fg": "#15803D", "bd": "#BBF7D0"},
    "hold":       {"label": "HOLD",       "bg": "#FFFBEB", "fg": "#B45309", "bd": "#FDE68A"},
    "avoid":      {"label": "AVOID",      "bg": "#FEF2F2", "fg": "#B91C1C", "bd": "#FECACA"},
    "high_risk":  {"label": "HIGH RISK",  "bg": "#FEF2F2", "fg": "#991B1B", "bd": "#FCA5A5"},
}

POLICY_STYLES = {
    "low":             {"label": "LOW RISK",    "bg": "#F0FDF4", "fg": "#15803D"},
    "review_required": {"label": "REVIEW",      "bg": "#F5F3FF", "fg": "#6D28D9"},
    "medium":          {"label": "MEDIUM RISK", "bg": "#FFFBEB", "fg": "#B45309"},
    "high":            {"label": "HIGH RISK",   "bg": "#FEF2F2", "fg": "#B91C1C"},
    "not_checked":     {"label": "NOT CHECKED", "bg": "#F1F5F9", "fg": "#64748B"},
}


# ===================================================================
# Formatters
# ===================================================================

def format_currency(value: Any, currency: str = "USD", decimals: int = 2) -> str:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "--"
    sym = CURRENCY_SYMBOLS.get((currency or "USD").upper(), "$")
    if num < 0:
        return f"-{sym}{abs(num):,.{decimals}f}"
    return f"{sym}{num:,.{decimals}f}"


def format_percent(value: Any, decimals: int = 1) -> str:
    try:
        return f"{float(value):.{decimals}f}%"
    except (TypeError, ValueError):
        return "--"


def format_score(value: Any, decimals: int = 1) -> str:
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "--"


def truncate(text: str, length: int = 55) -> str:
    if not text:
        return ""
    text = str(text).strip()
    return text if len(text) <= length else text[:length - 1].rstrip() + "\u2026"


# ===================================================================
# Badge Renderers (HTML)
# ===================================================================

def _badge_html(label: str, bg: str, fg: str, bd: Optional[str] = None) -> str:
    border = f"border:1px solid {bd};" if bd else "border:1px solid transparent;"
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};{border}'
        f"padding:3px 9px;border-radius:4px;font-size:11px;font-weight:600;"
        f'letter-spacing:0.3px;white-space:nowrap;">{label}</span>'
    )


def recommendation_badge(rec: str) -> str:
    """Alias kept for backward compat with existing pages."""
    return recommendation_html(rec)


def recommendation_html(rec: str) -> str:
    s = RECOMMENDATION_STYLES.get(
        (rec or "hold").lower(),
        {"label": (rec or "HOLD").upper(), "bg": "#F1F5F9", "fg": "#475569", "bd": "#CBD5E1"},
    )
    return _badge_html(s["label"], s["bg"], s["fg"], s.get("bd"))


def policy_badge(risk: str) -> str:
    """Alias kept for backward compat."""
    return policy_html(risk)


def policy_html(risk: str) -> str:
    s = POLICY_STYLES.get(
        (risk or "not_checked").lower(),
        {"label": (risk or "N/A").upper(), "bg": "#F1F5F9", "fg": "#475569"},
    )
    return _badge_html(s["label"], s["bg"], s["fg"])


# ===================================================================
# URL Resolution
# ===================================================================

_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


def is_valid_url(url: Optional[str]) -> bool:
    return bool(url and isinstance(url, str) and _URL_RE.match(url.strip()))


def resolve_ebay_url(listing: Dict[str, Any]) -> Optional[str]:
    """Resolve eBay URL from listing dict. Never fabricates."""
    if not listing:
        return None
    for key in ("item_url", "item_web_url", "web_url", "url"):
        val = listing.get(key)
        if is_valid_url(val):
            return val.strip()
    raw = listing.get("raw_data") or {}
    if isinstance(raw, dict):
        for key in ("itemWebUrl", "item_web_url"):
            val = raw.get(key)
            if is_valid_url(val):
                return val.strip()
    item_id = listing.get("item_id", "")
    if isinstance(item_id, str):
        digits = "".join(c for c in item_id if c.isdigit())
        if len(digits) >= 9:
            return f"https://www.ebay.com/itm/{digits}"
    return None


def resolve_supplier_url(supplier: Any) -> Optional[str]:
    """Resolve AliExpress supplier URL. Never fabricates."""
    if supplier is None:
        return None
    if hasattr(supplier, "product_url"):
        url = getattr(supplier, "product_url", None)
        if is_valid_url(url):
            return url.strip()
    if isinstance(supplier, dict):
        for key in ("product_url", "url"):
            val = supplier.get(key)
            if is_valid_url(val):
                return val.strip()
    return None


# ===================================================================
# Supplier URL Enrichment Map
# ===================================================================

def build_supplier_url_map(query: str, limit: int = 15) -> Dict[str, Dict[str, Any]]:
    """
    Call AliExpress adapter to build product_id -> {url, title, image} map.
    UI-layer enrichment only. No backend changes.
    """
    try:
        from services.aliexpress import get_adapter
        adapter = get_adapter()
        products = adapter.search_products(query, limit=limit)
    except Exception:
        return {}

    out: Dict[str, Dict[str, Any]] = {}
    for p in products or []:
        pid = getattr(p, "product_id", None) or (
            p.get("product_id") if isinstance(p, dict) else None
        )
        if not pid:
            continue
        out[str(pid)] = {
            "url": resolve_supplier_url(p),
            "title": getattr(p, "title", None) or (
                p.get("title") if isinstance(p, dict) else None
            ),
            "image_url": getattr(p, "image_url", None) or (
                p.get("image_url") if isinstance(p, dict) else None
            ),
        }
    return out


# ===================================================================
# View-Model Mapping
# ===================================================================

def build_opportunity_rows(
    pipeline_results: List[Dict[str, Any]],
    supplier_map: Optional[Dict[str, Dict[str, Any]]] = None,
    category_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Flatten serialized PipelineResult dicts into row view-models.
    Single point of URL resolution and field normalization.
    """
    supplier_map = supplier_map or {}
    rows: List[Dict[str, Any]] = []

    for result in pipeline_results or []:
        ebay = result.get("ebay_listing", {}) or {}
        policy = result.get("policy", {}) or {}
        ebay_url = resolve_ebay_url(ebay)

        for m in result.get("matches", []) or []:
            match_data = m.get("match", {}) or {}
            profit = m.get("profit", {}) or {}
            score = m.get("score", {}) or {}

            ali_id = str(match_data.get("ali_product_id", ""))
            sup = supplier_map.get(ali_id, {})

            category = (
                (match_data.get("ebay_identity") or {}).get("product_type")
                or ebay.get("category")
                or "Uncategorized"
            )
            if category_filter and category != category_filter:
                continue

            comp_scores = score.get("component_scores") or {}
            row = {
                "ebay_item_id": match_data.get("ebay_item_id", ""),
                "ali_product_id": ali_id,
                "product_title": ebay.get("title") or "Unknown Product",
                "ebay_url": ebay_url,
                "ebay_image_url": ebay.get("image_url"),
                "ebay_condition": ebay.get("condition") or "Unknown",
                "ebay_seller": (ebay.get("seller") or {}).get("username", "Unknown"),
                "ebay_marketplace": ebay.get("marketplace", ""),
                "supplier_url": sup.get("url"),
                "supplier_title": sup.get("title") or "Supplier match",
                "supplier_image_url": sup.get("image_url"),
                "category": category,
                "currency": profit.get("currency") or "USD",
                "sold_price": profit.get("sold_price", 0),
                "item_cost": profit.get("item_cost", 0),
                "shipping_cost": profit.get("shipping_cost", 0),
                "net_profit": profit.get("net_profit_per_item", 0),
                "margin": profit.get("profit_margin", 0),
                "roi": profit.get("roi", 0),
                "is_profitable": profit.get("is_profitable", False),
                "fees": profit.get("fees", {}),
                "match_score": float(match_data.get("match_score", 0) or 0),
                "match_type": match_data.get("match_type", ""),
                "match_confidence": float(match_data.get("confidence", 0) or 0),
                "text_similarity": float(match_data.get("text_similarity", 0) or 0),
                "attribute_similarity": float(match_data.get("attribute_similarity", 0) or 0),
                "matching_reasons": match_data.get("matching_reasons") or [],
                "differing_attributes": match_data.get("differing_attributes") or [],
                "policy_risk": policy.get("overall_risk") or "not_checked",
                "final_score": float(score.get("final_score", 0) or 0),
                "recommendation": score.get("recommendation") or "hold",
                "component_scores": comp_scores,
                "reasoning": score.get("reasoning") or [],
                "warnings": score.get("warnings") or [],
                "assumptions": score.get("assumptions") or [],
            }
            rows.append(row)

    rows.sort(key=lambda x: x["final_score"], reverse=True)
    return rows


def aggregate_categories(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group rows by category with aggregate metrics."""
    buckets: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        cat = r.get("category") or "Uncategorized"
        b = buckets.setdefault(cat, {
            "category": cat, "count": 0, "score_sum": 0.0,
            "profit_sum": 0.0, "margin_sum": 0.0,
            "currency": r.get("currency", "USD"),
        })
        b["count"] += 1
        b["score_sum"] += r.get("final_score", 0)
        try:
            b["profit_sum"] += float(r.get("net_profit", 0))
        except (TypeError, ValueError):
            pass
        try:
            b["margin_sum"] += float(r.get("margin", 0))
        except (TypeError, ValueError):
            pass

    out = []
    for b in buckets.values():
        n = max(1, b["count"])
        out.append({
            "category": b["category"],
            "count": b["count"],
            "avg_score": b["score_sum"] / n,
            "avg_profit": b["profit_sum"] / n,
            "avg_margin": b["margin_sum"] / n,
            "currency": b["currency"],
        })
    out.sort(key=lambda x: x["avg_score"], reverse=True)
    return out


def build_watchlist_snapshot(row: Dict[str, Any]) -> Dict[str, Any]:
    """Create a watchlist-safe snapshot from an opportunity row."""
    return {
        "saved_at": datetime.utcnow().isoformat(),
        "ebay_item_id": row.get("ebay_item_id", ""),
        "ali_product_id": row.get("ali_product_id", ""),
        "product_title": row.get("product_title", ""),
        "marketplace": row.get("ebay_marketplace", ""),
        "category": row.get("category", ""),
        "currency": row.get("currency", "USD"),
        "sold_price": row.get("sold_price", 0),
        "item_cost": row.get("item_cost", 0),
        "shipping_cost": row.get("shipping_cost", 0),
        "net_profit": row.get("net_profit", 0),
        "margin": row.get("margin", 0),
        "roi": row.get("roi", 0),
        "final_score": row.get("final_score", 0),
        "recommendation": row.get("recommendation", "hold"),
        "policy_risk": row.get("policy_risk", "not_checked"),
        "match_score": row.get("match_score", 0),
        "ebay_url": row.get("ebay_url"),
        "supplier_url": row.get("supplier_url"),
        "notes": "",
    }


# ===================================================================
# Session State Management
# ===================================================================

def safe_rerun():
    """Version-safe Streamlit rerun."""
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


def init_session_state():
    """
    Initialize canonical session state contract.

    Keys:
        marketplace        str         Global workspace market
        search_query       str         Last search query
        search_results     list|None   Serialized PipelineResult dicts
        supplier_map       dict        product_id -> URL enrichment
        selected_opportunity dict|None Detail page payload
        watchlist          list        Saved opportunity snapshots
        calculator_prefill dict|None   Calculator hydrate payload
        selected_category  str|None    Category filter (legacy compat)
    """
    # Migrate legacy keys silently
    if "wishlist" in st.session_state and "watchlist" not in st.session_state:
        st.session_state["watchlist"] = st.session_state.pop("wishlist")
    if "selected_match" in st.session_state and "selected_opportunity" not in st.session_state:
        st.session_state["selected_opportunity"] = st.session_state.pop("selected_match")

    defaults = {
        "marketplace": "US",
        "search_query": "",
        "search_results": None,
        "supplier_map": {},
        "selected_opportunity": None,
        "watchlist": [],
        "calculator_prefill": None,
        "selected_category": None,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


# ===================================================================
# Global CSS
# ===================================================================

GLOBAL_CSS = """
<style>
/* Hide Streamlit chrome */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebarNav"] { display: none !important; }

/* Base */
.stApp { background-color: #F8FAFC; font-family: "Inter", system-ui, sans-serif; }
.main .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1400px; }

/* Sidebar */
section[data-testid="stSidebar"] { background-color: #0F172A; border-right: 1px solid #1E293B; }
section[data-testid="stSidebar"] * { color: #E2E8F0; }
section[data-testid="stSidebar"] hr { border-color: #1E293B !important; margin: 12px 0 !important; }
section[data-testid="stSidebar"] .stSelectbox label { color: #94A3B8 !important; }
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background-color: #1E293B !important; border-color: #334155 !important; color: #F1F5F9 !important;
}

/* Typography */
.rehu-title { font-size: 24px; font-weight: 600; color: #0F172A; margin: 0 0 4px 0; letter-spacing: -0.02em; }
.rehu-subtitle { font-size: 14px; color: #64748B; margin: 0 0 24px 0; }
.rehu-section {
    font-size: 12px; font-weight: 700; color: #64748B;
    text-transform: uppercase; letter-spacing: 0.6px; margin: 28px 0 12px 0;
}

/* Cards */
.rehu-card {
    background: #FFFFFF; border: 1px solid #E2E8F0;
    border-radius: 8px; padding: 20px; margin-bottom: 12px;
}

/* Metrics */
.rehu-metric {
    background: #FFFFFF; border: 1px solid #E2E8F0;
    border-radius: 8px; padding: 16px;
}
.rehu-metric-label {
    font-size: 11px; font-weight: 600; color: #64748B;
    text-transform: uppercase; letter-spacing: 0.5px;
}
.rehu-metric-value { font-size: 26px; font-weight: 700; color: #0F172A; margin-top: 6px; }
.rehu-metric-sub { font-size: 12px; color: #64748B; margin-top: 4px; }

/* KV pairs */
.rehu-kv {
    display: flex; justify-content: space-between; padding: 6px 0;
    font-size: 13px; border-bottom: 1px dashed #F1F5F9;
}
.rehu-kv:last-child { border-bottom: none; }
.rehu-kv-k { color: #64748B; }
.rehu-kv-v { color: #0F172A; font-weight: 500; font-variant-numeric: tabular-nums; }

/* Link buttons */
.rehu-btn {
    display: inline-block; padding: 7px 14px; border-radius: 6px;
    background: #2563EB; color: #FFFFFF !important;
    text-decoration: none !important; font-size: 12px; font-weight: 500;
    border: 1px solid #2563EB; text-align: center;
    width: 100%; box-sizing: border-box;
}
.rehu-btn:hover { background: #1E40AF; border-color: #1E40AF; }
.rehu-btn-secondary {
    background: #FFFFFF; color: #2563EB !important; border-color: #BFDBFE;
}
.rehu-btn-secondary:hover { background: #EFF6FF; }
.rehu-btn-disabled {
    display: inline-block; padding: 7px 14px; border-radius: 6px;
    background: #F1F5F9; color: #94A3B8; font-size: 12px;
    border: 1px solid #E2E8F0; text-align: center;
    width: 100%; box-sizing: border-box;
}

/* Empty state */
.rehu-empty {
    background: #FFFFFF; border: 1px dashed #CBD5E1;
    border-radius: 10px; padding: 48px 24px; text-align: center;
}
.rehu-empty h3 { font-size: 16px; color: #0F172A; margin: 0 0 6px 0; }
.rehu-empty p { font-size: 13px; color: #64748B; margin: 0; }

/* Notice */
.rehu-notice {
    display: inline-flex; align-items: center; gap: 8px;
    background: #EFF6FF; border: 1px solid #BFDBFE;
    border-radius: 4px; padding: 6px 12px; font-size: 12px; color: #1E40AF;
}

/* Buttons */
.stButton > button { border-radius: 6px !important; font-weight: 500 !important; }
.stButton > button[kind="primary"] {
    background: #2563EB !important; border-color: #2563EB !important; color: #FFF !important;
}
.stButton > button[kind="primary"]:hover {
    background: #1E40AF !important; border-color: #1E40AF !important;
}
</style>
"""