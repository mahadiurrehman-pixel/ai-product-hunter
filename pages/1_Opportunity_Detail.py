"""
REHU — Opportunity Detail (Contextual)

Deep inspection of one selected opportunity. Opened via Inspect action.
Shows match, profit, score, source links. No re-calculation.
"""
from __future__ import annotations

import streamlit as st

from ui.helpers import (
    GLOBAL_CSS, MARKETPLACE_LABELS, init_session_state, safe_rerun,
    format_currency, format_percent, format_score,
    recommendation_html, policy_html,
)
from ui.components.sidebar import render_sidebar


st.set_page_config(
    page_title="REHU — Opportunity Detail",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_session_state()

render_sidebar(current_page="Opportunity Detail")

st.markdown('<div class="rehu-title">Opportunity Detail</div>', unsafe_allow_html=True)

r = st.session_state.get("selected_opportunity")
if not r:
    st.markdown(
        '<div class="rehu-empty">'
        "<h3>No opportunity selected</h3>"
        "<p>Click Inspect on any opportunity in Search to view details here.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()

cur = r.get("currency", "USD")

# --- Header ---
h1, h2 = st.columns([3, 2])
with h1:
    st.markdown(
        f'<div style="font-size:18px;font-weight:600;color:#0F172A;">'
        f'{r["product_title"]}</div>'
        f'<div style="font-size:12px;color:#64748B;margin-top:4px;">'
        f"Marketplace: {MARKETPLACE_LABELS.get(st.session_state.get('marketplace','US'),'')} "
        f"&middot; Category: {r.get('category','')}</div>",
        unsafe_allow_html=True,
    )
with h2:
    st.markdown(
        f'<div style="text-align:right;">'
        f'<div style="font-size:32px;font-weight:700;color:#0F172A;">'
        f'{format_score(r["final_score"])}'
        f'<span style="font-size:14px;color:#64748B;"> / 100</span></div>'
        f'<div style="margin-top:8px;">'
        f"{recommendation_html(r['recommendation'])} "
        f"{policy_html(r['policy_risk'])}</div></div>",
        unsafe_allow_html=True,
    )

st.markdown('<div style="height:20px;"></div>', unsafe_allow_html=True)

# --- Side by Side ---
p1, p2 = st.columns(2)

with p1:
    st.markdown('<div class="rehu-card">', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:12px;font-weight:700;color:#64748B;'
        'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px;'
        'padding-bottom:8px;border-bottom:1px solid #E2E8F0;">eBay Listing</div>',
        unsafe_allow_html=True,
    )
    if r.get("ebay_image_url"):
        try:
            st.image(r["ebay_image_url"], use_column_width=True)
        except Exception:
            pass
    st.markdown(
        f'<div class="rehu-kv"><span class="rehu-kv-k">Price</span>'
        f'<span class="rehu-kv-v">{format_currency(r["sold_price"], cur)}</span></div>'
        f'<div class="rehu-kv"><span class="rehu-kv-k">Condition</span>'
        f'<span class="rehu-kv-v">{r.get("ebay_condition","--")}</span></div>'
        f'<div class="rehu-kv"><span class="rehu-kv-k">Seller</span>'
        f'<span class="rehu-kv-v">{r.get("ebay_seller","--")}</span></div>'
        f'<div class="rehu-kv"><span class="rehu-kv-k">Marketplace</span>'
        f'<span class="rehu-kv-v">{r.get("ebay_marketplace","--")}</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
    if r.get("ebay_url"):
        st.markdown(
            f'<a class="rehu-btn" href="{r["ebay_url"]}" target="_blank">View on eBay</a>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="rehu-btn-disabled">eBay URL unavailable</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with p2:
    st.markdown('<div class="rehu-card">', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:12px;font-weight:700;color:#64748B;'
        'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px;'
        'padding-bottom:8px;border-bottom:1px solid #E2E8F0;">AliExpress Supplier</div>',
        unsafe_allow_html=True,
    )
    if r.get("supplier_image_url"):
        try:
            st.image(r["supplier_image_url"], use_column_width=True)
        except Exception:
            pass
    st.markdown(
        f'<div class="rehu-kv"><span class="rehu-kv-k">Title</span>'
        f'<span class="rehu-kv-v" style="max-width:70%;text-align:right;">'
        f'{r.get("supplier_title","--")}</span></div>'
        f'<div class="rehu-kv"><span class="rehu-kv-k">Cost</span>'
        f'<span class="rehu-kv-v">{format_currency(r["item_cost"], cur)}</span></div>'
        f'<div class="rehu-kv"><span class="rehu-kv-k">Source</span>'
        f'<span class="rehu-kv-v">Simulated</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
    if r.get("supplier_url"):
        st.markdown(
            f'<a class="rehu-btn rehu-btn-secondary" href="{r["supplier_url"]}" '
            f'target="_blank">View Supplier</a>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="rehu-btn-disabled">Supplier URL unavailable</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div style="height:20px;"></div>', unsafe_allow_html=True)

# --- Match + Finance ---
fc1, fc2 = st.columns(2)

with fc1:
    st.markdown('<div class="rehu-card">', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:12px;font-weight:700;color:#64748B;'
        'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px;'
        'padding-bottom:8px;border-bottom:1px solid #E2E8F0;">Match Quality</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="font-size:24px;font-weight:700;color:#0F172A;">'
        f'{format_percent(r["match_score"] * 100, 1)}</div>'
        f'<div style="font-size:12px;color:#64748B;margin-bottom:12px;">'
        f'Type: {r.get("match_type","--")} &middot; '
        f'Confidence: {format_percent(r["match_confidence"] * 100, 0)}</div>',
        unsafe_allow_html=True,
    )
    st.progress(min(1.0, r["text_similarity"]), text=f"Text: {format_percent(r['text_similarity']*100, 0)}")
    st.progress(min(1.0, r["attribute_similarity"]), text=f"Attributes: {format_percent(r['attribute_similarity']*100, 0)}")

    if r.get("matching_reasons"):
        st.markdown(
            '<div style="font-size:11px;color:#64748B;text-transform:uppercase;margin-top:12px;">'
            "Matching</div>", unsafe_allow_html=True,
        )
        for reason in r["matching_reasons"][:5]:
            st.markdown(f'<div style="font-size:12px;color:#0F172A;">- {reason}</div>', unsafe_allow_html=True)
    if r.get("differing_attributes"):
        st.markdown(
            '<div style="font-size:11px;color:#64748B;text-transform:uppercase;margin-top:8px;">'
            "Differences</div>", unsafe_allow_html=True,
        )
        for d in r["differing_attributes"][:5]:
            st.markdown(f'<div style="font-size:12px;color:#0F172A;">- {d}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with fc2:
    st.markdown('<div class="rehu-card">', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:12px;font-weight:700;color:#64748B;'
        'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px;'
        'padding-bottom:8px;border-bottom:1px solid #E2E8F0;">Financial Breakdown</div>',
        unsafe_allow_html=True,
    )
    fees = r.get("fees") or {}
    st.markdown(
        f'<div class="rehu-kv"><span class="rehu-kv-k">Revenue</span>'
        f'<span class="rehu-kv-v">{format_currency(r["sold_price"], cur)}</span></div>'
        f'<div class="rehu-kv"><span class="rehu-kv-k">Supplier Cost</span>'
        f'<span class="rehu-kv-v">{format_currency(r["item_cost"], cur)}</span></div>'
        f'<div class="rehu-kv"><span class="rehu-kv-k">Shipping</span>'
        f'<span class="rehu-kv-v">{format_currency(r["shipping_cost"], cur)}</span></div>'
        f'<div class="rehu-kv"><span class="rehu-kv-k">FVF</span>'
        f'<span class="rehu-kv-v">{format_currency(fees.get("fvf", 0), cur)}</span></div>'
        f'<div class="rehu-kv"><span class="rehu-kv-k">Transaction</span>'
        f'<span class="rehu-kv-v">{format_currency(fees.get("transaction_fee", 0), cur)}</span></div>'
        f'<div class="rehu-kv"><span class="rehu-kv-k">Promoted</span>'
        f'<span class="rehu-kv-v">{format_currency(fees.get("promoted_fee", 0), cur)}</span></div>'
        f'<div style="height:8px;border-bottom:1px solid #E2E8F0;margin:8px 0;"></div>'
        f'<div class="rehu-kv"><span class="rehu-kv-k" style="font-weight:600;">Net Profit</span>'
        f'<span class="rehu-kv-v" style="color:#047857;font-weight:700;font-size:15px;">'
        f'{format_currency(r["net_profit"], cur)}</span></div>'
        f'<div class="rehu-kv"><span class="rehu-kv-k">Margin</span>'
        f'<span class="rehu-kv-v">{format_percent(r["margin"])}</span></div>'
        f'<div class="rehu-kv"><span class="rehu-kv-k">ROI</span>'
        f'<span class="rehu-kv-v">{format_percent(r["roi"])}</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

# --- Reasoning ---
if r.get("reasoning"):
    st.markdown('<div style="height:20px;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="rehu-card">', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:12px;font-weight:700;color:#64748B;'
        'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px;">'
        "Why this opportunity?</div>", unsafe_allow_html=True,
    )
    for line in r["reasoning"]:
        st.markdown(f'<div style="font-size:13px;color:#0F172A;margin-bottom:6px;">- {line}</div>',
                    unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# --- Actions ---
st.markdown('<div style="height:20px;"></div>', unsafe_allow_html=True)
a1, a2, a3 = st.columns(3)
with a1:
    if st.button("Calculate Profit", use_container_width=True, key="detail_calc"):
        st.session_state["calculator_prefill"] = {
            "marketplace": st.session_state.get("marketplace", "US"),
            "currency": cur,
            "sold_price": float(r.get("sold_price", 0)),
            "item_cost": float(r.get("item_cost", 0)),
            "shipping_cost": float(r.get("shipping_cost", 0)),
            "product_title": r.get("product_title", ""),
        }
        try:
            st.switch_page("pages/2_Profit_Calculator.py")
        except Exception:
            pass
with a2:
    if st.button("Save to Watchlist", use_container_width=True, key="detail_save"):
        from ui.helpers import build_watchlist_snapshot
        wl = st.session_state.setdefault("watchlist", [])
        key = (r["ebay_item_id"], r["ali_product_id"])
        if not any((w.get("ebay_item_id"), w.get("ali_product_id")) == key for w in wl):
            wl.append(build_watchlist_snapshot(r))
            st.toast("Saved to Watchlist")
with a3:
    if st.button("Back to Search", use_container_width=True, key="detail_back"):
        try:
            st.switch_page("app.py")
        except Exception:
            pass