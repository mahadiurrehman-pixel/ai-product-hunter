"""
REHU — Search / Research Workspace (Main Entry)

Primary research console. Calls OpportunityPipeline.analyze() and
renders ranked opportunities with actions.
"""
from __future__ import annotations

from datetime import datetime
import streamlit as st

from ui.helpers import (
    GLOBAL_CSS, MARKETPLACE_LABELS,
    build_opportunity_rows, build_supplier_url_map,
    build_watchlist_snapshot, init_session_state, safe_rerun,
    format_currency, format_percent, format_score, truncate,
    recommendation_html, policy_html,
)
from ui.components.sidebar import render_sidebar


# ===================================================================
# Page Config
# ===================================================================
st.set_page_config(
    page_title="REHU — Search",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_session_state()

active_mp = render_sidebar(current_page="Search")


# ===================================================================
# Header
# ===================================================================
st.markdown('<div class="rehu-title">Search Products</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="rehu-subtitle">'
    "Find profitable eBay listings matched with supplier products."
    "</div>",
    unsafe_allow_html=True,
)


# ===================================================================
# Search Form
# ===================================================================
st.markdown('<div class="rehu-card">', unsafe_allow_html=True)

q_col, b_col = st.columns([5, 1])
with q_col:
    query = st.text_input(
        "Search",
        value=st.session_state.get("search_query", ""),
        placeholder="Search product keywords (e.g., wireless earbuds, phone case)...",
        label_visibility="collapsed",
        key="search_input",
    )
with b_col:
    do_search = st.button("Research", type="primary", use_container_width=True, key="search_btn")

f1, f2, f3 = st.columns(3)
with f1:
    limit = st.slider("Results Limit", 5, 50, 20, key="f_limit")
with f2:
    min_match = st.slider("Minimum Match Quality", 0.0, 1.0, 0.60, 0.05, key="f_match")
with f3:
    shipping = st.number_input("Supplier Shipping Cost Estimate ($)", 0.0, 50.0, 5.0, 0.5, key="f_ship")

with st.expander("Advanced Sourcing Parameters"):
    a1, a2, a3 = st.columns(3)
    with a1:
        promoted = st.number_input("eBay Promoted Ad Rate (%)", 0.0, 20.0, 0.0, 0.5, key="f_promo")
        st.caption("Ad rate you plan to apply. Directly reduces estimated net margins.")
    with a2:
        store = st.selectbox(
            "eBay Store Subscription",
            ["No Store", "Starter", "Basic", "Premium", "Anchor", "Enterprise"],
            key="f_store",
        )
    with a3:
        overseas = st.checkbox("Overseas Sales", value=False, key="f_over")

st.markdown("</div>", unsafe_allow_html=True)


# ===================================================================
# Execute Pipeline with Robust Boundaries
# ===================================================================
if do_search and query.strip():
    with st.spinner("Executing multi-dimensional scoring pipeline..."):
        try:
            from services.pipeline import OpportunityPipeline
            pipeline = OpportunityPipeline()
            results = pipeline.analyze(
                query=query.strip(),
                marketplace=active_mp,
                limit=int(limit),
                min_match_score=float(min_match),
                profit_defaults={
                    "shipping_cost": float(shipping),
                    "promoted_rate": float(promoted),
                    "overseas_sales": bool(overseas),
                    "store_type": store,
                },
            )
            st.session_state["search_results"] = [r.to_dict() for r in results]
            st.session_state["supplier_map"] = build_supplier_url_map(query.strip())
            st.session_state["search_query"] = query.strip()
            st.session_state["selected_category"] = None
        except Exception as exc:
            st.error(
                "An unexpected error occurred during research analysis. "
                "Please verify your credentials or adjust search filters."
            )
            st.session_state["search_results"] = None
    safe_rerun()


# ===================================================================
# Results Display
# ===================================================================
raw = st.session_state.get("search_results")
smap = st.session_state.get("supplier_map") or {}

if raw is None:
    st.markdown(
        '<div class="rehu-empty">'
        "<h3>No Active Research</h3>"
        "<p>Enter a query or keyword above and click Research to discover opportunities.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()

if not raw:
    st.markdown(
        '<div class="rehu-empty">'
        "<h3>No Matches Discovered</h3>"
        "<p>No opportunities met your minimum match or filtering thresholds. Try a broader search.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()

rows = build_opportunity_rows(raw, smap)

# --- Diagnostic State Detection ---
total_listings = len(raw)
total_matches = sum(len(r.get("matches", [])) for r in raw)
total_with_opportunities = len(rows)

# Collect diagnostic info from pipeline results
supplier_candidates_total = 0
for r in raw:
    diag = r.get("diagnostics", {})
    supplier_candidates_total += diag.get("supplier_candidates_found", 0)

if total_listings == 0:
    # State 1: No eBay listings at all
    st.markdown(
        '<div class="rehu-empty">'
        "<h3>No eBay Listings Found</h3>"
        "<p>No listings matched your search query on the selected marketplace. "
        "Try different keywords or a broader search.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
elif total_with_opportunities == 0:
    # State 2: Listings found but no supplier matches
    st.markdown(
        '<div class="rehu-empty">'
        f"<h3>No Supplier Matches Found</h3>"
        f"<p>Found {total_listings} eBay listing(s) and {supplier_candidates_total} "
        f"supplier candidate(s), but no matches met the minimum quality threshold "
        f"({st.session_state.get('f_match', 0.60):.0%}).</p>"
        f"<p>This is expected with simulated supplier data. "
        f"Real supplier integration (Phase 17) will resolve this.</p>"
        f"<p><b>Try:</b> Lower the Minimum Match Quality slider, "
        f"or search for common electronics like 'wireless earbuds' or 'phone case'.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
else:
    # State 3: Opportunities successfully generated
    st.markdown(
        f'<div class="rehu-section">Discovered Opportunities &mdash; '
        f'{total_with_opportunities} Items</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="rehu-notice">Supplier cost, stock, and fulfillment '
        "parameters are simulated. Real supplier integration is planned.</div>",
        unsafe_allow_html=True,
    )
    st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)

    for idx, r in enumerate(rows):
        cur = r.get("currency", "USD")
        with st.container():
            st.markdown('<div class="rehu-card" style="padding:16px;">', unsafe_allow_html=True)
            c1, c2, c3 = st.columns([4, 2, 2])

            with c1:
                st.markdown(
                    f'<div style="font-size:14px;font-weight:600;color:#0F172A;">'
                    f"{truncate(r['product_title'], 80)}</div>"
                    f'<div style="font-size:12px;color:#64748B;margin-top:4px;">'
                    f"{r['category']} &middot; "
                    f"Match Score: {format_percent(r['match_score'] * 100, 0)} &middot; "
                    f"Opportunity Score: {format_score(r['final_score'])}</div>"
                    f'<div style="margin-top:8px;">'
                    f"{recommendation_html(r['recommendation'])} "
                    f"{policy_html(r['policy_risk'])}</div>",
                    unsafe_allow_html=True,
                )

            with c2:
                st.markdown(
                    f'<div class="rehu-kv"><span class="rehu-kv-k">eBay Sold Price</span>'
                    f'<span class="rehu-kv-v">{format_currency(r["sold_price"], cur)}</span></div>'
                    f'<div class="rehu-kv"><span class="rehu-kv-k">Supplier Cost</span>'
                    f'<span class="rehu-kv-v">{format_currency(r["item_cost"], cur)}</span></div>'
                    f'<div class="rehu-kv"><span class="rehu-kv-k">Net Profit</span>'
                    f'<span class="rehu-kv-v" style="color:#047857;">'
                    f'{format_currency(r["net_profit"], cur)}</span></div>'
                    f'<div class="rehu-kv"><span class="rehu-kv-k">Margin</span>'
                    f'<span class="rehu-kv-v">{format_percent(r["margin"])}</span></div>',
                    unsafe_allow_html=True,
                )

            with c3:
                # Action: Inspect
                if st.button("Inspect Pair", key=f"insp_{idx}", use_container_width=True):
                    st.session_state["selected_opportunity"] = r
                    try:
                        st.switch_page("pages/1_Opportunity_Detail.py")
                    except Exception:
                        pass

                # Link: eBay
                if r.get("ebay_url"):
                    st.markdown(
                        f'<a class="rehu-btn" href="{r["ebay_url"]}" target="_blank">'
                        f"View eBay Listing</a>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown('<div class="rehu-btn-disabled">eBay Link Unavailable</div>',
                                unsafe_allow_html=True)

                st.markdown('<div style="height:4px;"></div>', unsafe_allow_html=True)

                # Link: Supplier
                if r.get("supplier_url"):
                    st.markdown(
                        f'<a class="rehu-btn rehu-btn-secondary" href="{r["supplier_url"]}" '
                        f'target="_blank">View Supplier Item</a>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown('<div class="rehu-btn-disabled">Supplier Link Unavailable</div>',
                                unsafe_allow_html=True)

                st.markdown('<div style="height:4px;"></div>', unsafe_allow_html=True)

                # Action: Save to Watchlist
                if st.button("Save Opportunity", key=f"save_{idx}", use_container_width=True):
                    wl = st.session_state.setdefault("watchlist", [])
                    key = (r["ebay_item_id"], r["ali_product_id"])
                    if not any((w.get("ebay_item_id"), w.get("ali_product_id")) == key for w in wl):
                        wl.append(build_watchlist_snapshot(r))
                        st.toast("Saved to Watchlist")

                # Action: Calculate Profit
                if st.button("Calculate Custom Profit", key=f"calc_{idx}", use_container_width=True):
                    st.session_state["calculator_prefill"] = {
                        "marketplace": active_mp,
                        "currency": cur,
                        "sold_price": float(r.get("sold_price", 0)),
                        "item_cost": float(r.get("item_cost", 0)),
                        "shipping_cost": float(r.get("shipping_cost", 0)),
                        "promoted_rate": float(st.session_state.get("f_promo", 0)),
                        "product_title": r.get("product_title", ""),
                    }
                    try:
                        st.switch_page("pages/2_Profit_Calculator.py")
                    except Exception:
                        pass

            st.markdown("</div>", unsafe_allow_html=True)