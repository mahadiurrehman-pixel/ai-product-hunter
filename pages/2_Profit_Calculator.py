"""
REHU — Profit Calculator (Standalone + Prefill)

First-class financial tool. Works independently of any search.
Accepts optional prefill from opportunity rows via session state.
Calls ProfitCalculator.calculate() only — no custom fee math.
"""
from __future__ import annotations

from decimal import Decimal
import streamlit as st

from ui.helpers import (
    GLOBAL_CSS, MARKETPLACE_LABELS, init_session_state,
    format_currency, format_percent,
)
from ui.components.sidebar import render_sidebar


st.set_page_config(
    page_title="REHU — Profit Calculator",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_session_state()

active_mp = render_sidebar(current_page="Profit Calculator")

st.markdown('<div class="rehu-title">Profit Calculator</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="rehu-subtitle">'
    "Calculate net profit, margins, and fees for any eBay marketplace."
    "</div>",
    unsafe_allow_html=True,
)

# -------------------------------------------------------------------
# Import backend contracts
# -------------------------------------------------------------------
try:
    from services.profit.calculator import ProfitCalculator
    from services.profit.models import (
        ProfitInput, ProfitResult, FeeBreakdown,
        StoreType, SellerLevel, TaxType,
        UKSellerType, UKBuyerRegion,
        DESellerType, DEBuyerRegion,
        AUStoreType,
        CAStoreType, CADestination,
    )
    BACKEND_OK = True
except ImportError as e:
    BACKEND_OK = False
    st.error(f"Cannot load profit engine: {e}")

if not BACKEND_OK:
    st.stop()


# -------------------------------------------------------------------
# Dynamic Enum Mapping (immune to member-name discrepancies)
# -------------------------------------------------------------------
def _enum_map(enum_cls):
    try:
        return {e.value.replace("_", " ").title(): e for e in enum_cls}
    except Exception:
        return {}


US_STORES = _enum_map(StoreType)
SELLER_LEVELS = _enum_map(SellerLevel)
UK_SELLER_TYPES = _enum_map(UKSellerType)
UK_REGIONS = _enum_map(UKBuyerRegion)
DE_SELLER_TYPES = _enum_map(DESellerType)
DE_REGIONS = _enum_map(DEBuyerRegion)
AU_STORES = _enum_map(AUStoreType)
CA_STORES = _enum_map(CAStoreType)
CA_DESTINATIONS = _enum_map(CADestination)


# -------------------------------------------------------------------
# Prefill from opportunity row (if available)
# -------------------------------------------------------------------
prefill = st.session_state.get("calculator_prefill") or {}
prefill_title = prefill.get("product_title", "")
if prefill_title:
    st.markdown(
        f'<div class="rehu-notice" style="margin-bottom:16px;">'
        f"Prefilled from: <b>{prefill_title}</b></div>",
        unsafe_allow_html=True,
    )

# -------------------------------------------------------------------
# Input Form
# -------------------------------------------------------------------
col_form, col_results = st.columns([1, 1.3])

with col_form:
    st.markdown('<div class="rehu-card">', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:12px;font-weight:700;color:#64748B;'
        'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:14px;'
        'padding-bottom:8px;border-bottom:1px solid #E2E8F0;">Inputs</div>',
        unsafe_allow_html=True,
    )

    # Marketplace selector (local to calculator, defaults to workspace active)
    mp_labels = list(MARKETPLACE_LABELS.values())
    mp_default = MARKETPLACE_LABELS.get(prefill.get("marketplace", active_mp), "United States")
    mp_idx = mp_labels.index(mp_default) if mp_default in mp_labels else 0
    mp_choice = st.selectbox("Marketplace", mp_labels, index=mp_idx, key="calc_mp")
    calc_mp = next(
        (k for k, v in MARKETPLACE_LABELS.items() if v == mp_choice), "US"
    )

    st.markdown(
        '<div style="font-size:11px;font-weight:600;color:#64748B;'
        'text-transform:uppercase;margin:16px 0 8px 0;">Pricing</div>',
        unsafe_allow_html=True,
    )
    sold_price = st.number_input(
        "Selling Price", min_value=0.0,
        value=float(prefill.get("sold_price", 0.0)), step=0.50, key="calc_sold",
    )
    item_cost = st.number_input(
        "Supplier / Item Cost", min_value=0.0,
        value=float(prefill.get("item_cost", 0.0)), step=0.50, key="calc_cost",
    )
    shipping_cost = st.number_input(
        "Your Shipping Cost", min_value=0.0,
        value=float(prefill.get("shipping_cost", 5.0)), step=0.50, key="calc_ship",
    )
    shipping_charged = st.number_input(
        "Shipping Charged to Buyer", min_value=0.0,
        value=0.0, step=0.50, key="calc_ship_buyer",
    )

    st.markdown(
        '<div style="font-size:11px;font-weight:600;color:#64748B;'
        'text-transform:uppercase;margin:16px 0 8px 0;">Fees & Ads</div>',
        unsafe_allow_html=True,
    )
    promoted = st.number_input(
        "Promoted Ad Rate (%)", min_value=0.0, max_value=20.0,
        value=float(prefill.get("promoted_rate", 0.0)), step=0.5, key="calc_promo",
    )
    st.caption("Your planned eBay advertising rate. Directly affects promoted listing fee.")
    charity = st.number_input(
        "Charity (%)", min_value=0.0, max_value=100.0,
        value=0.0, step=1.0, key="calc_charity",
    )

    st.markdown(
        '<div style="font-size:11px;font-weight:600;color:#64748B;'
        'text-transform:uppercase;margin:16px 0 8px 0;">Seller Profile</div>',
        unsafe_allow_html=True,
    )

    # Marketplace-specific fields
    us_store = uk_seller = de_seller = au_store = ca_store = None
    uk_region = de_region = ca_dest = None
    vat_reg = ebay_shop = has_abn = overseas = currency_conv = False

    if calc_mp == "US":
        if US_STORES:
            us_store = st.selectbox("Store Type", list(US_STORES.keys()), key="calc_us_store")
        if SELLER_LEVELS:
            seller_lvl = st.selectbox("Seller Level", list(SELLER_LEVELS.keys()), key="calc_seller")
        overseas = st.checkbox("Overseas Sales", value=False, key="calc_over")

    elif calc_mp == "UK":
        if UK_SELLER_TYPES:
            uk_seller = st.selectbox("Seller Type", list(UK_SELLER_TYPES.keys()), key="calc_uk_seller")
        if SELLER_LEVELS:
            seller_lvl = st.selectbox("Seller Level", list(SELLER_LEVELS.keys()), key="calc_seller_uk")
        vat_reg = st.checkbox("VAT Registered", value=True, key="calc_vat")
        if UK_REGIONS:
            uk_region = st.selectbox("Buyer Region", list(UK_REGIONS.keys()), key="calc_uk_region")
        currency_conv = st.checkbox("Currency Conversion", value=False, key="calc_conv")

    elif calc_mp == "DE":
        if DE_SELLER_TYPES:
            de_seller = st.selectbox("Seller Type", list(DE_SELLER_TYPES.keys()), key="calc_de_seller")
        if SELLER_LEVELS:
            seller_lvl = st.selectbox("Seller Level", list(SELLER_LEVELS.keys()), key="calc_seller_de")
        ebay_shop = st.checkbox("eBay Shop", value=False, key="calc_shop")
        if DE_REGIONS:
            de_region = st.selectbox("Buyer Region", list(DE_REGIONS.keys()), key="calc_de_region")

    elif calc_mp == "AU":
        if AU_STORES:
            au_store = st.selectbox("Store Type", list(AU_STORES.keys()), key="calc_au_store")
        if SELLER_LEVELS:
            seller_lvl = st.selectbox("Seller Level", list(SELLER_LEVELS.keys()), key="calc_seller_au")
        has_abn = st.checkbox("Has ABN", value=True, key="calc_abn")
        overseas = st.checkbox("Overseas Sales", value=False, key="calc_over_au")

    elif calc_mp == "CA":
        if CA_STORES:
            ca_store = st.selectbox("Store Type", list(CA_STORES.keys()), key="calc_ca_store")
        if SELLER_LEVELS:
            seller_lvl = st.selectbox("Seller Level", list(SELLER_LEVELS.keys()), key="calc_seller_ca")
        if CA_DESTINATIONS:
            ca_dest = st.selectbox("Destination", list(CA_DESTINATIONS.keys()), key="calc_ca_dest")

    with st.expander("Tax & Other"):
        tax_rate = st.number_input("Sales Tax (%)", 0.0, 25.0, 0.0, 0.5, key="calc_tax")
        other_costs = st.number_input("Other Costs", 0.0, value=0.0, step=0.5, key="calc_other")
        num_orders = st.number_input("Number of Orders", 1, 1000, 1, key="calc_orders")

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------------------------
# Calculate via ProfitCalculator
# -------------------------------------------------------------------
result: ProfitResult | None = None

try:
    kwargs = dict(
        marketplace=calc_mp,
        sold_price=Decimal(str(sold_price)),
        item_cost=Decimal(str(item_cost)),
        shipping_cost=Decimal(str(shipping_cost)),
        shipping_charged=Decimal(str(shipping_charged)),
        other_costs=Decimal(str(other_costs)),
        num_orders=int(num_orders),
        promoted_rate=float(promoted),
        charity_percent=float(charity),
        tax_type=TaxType.PERCENTAGE if tax_rate > 0 else TaxType.NONE,
        tax_rate=float(tax_rate),
    )

    if calc_mp == "US":
        if us_store and us_store in US_STORES:
            kwargs["store_type"] = US_STORES[us_store]
        if seller_lvl and seller_lvl in SELLER_LEVELS:
            kwargs["seller_level"] = SELLER_LEVELS[seller_lvl]
        kwargs["overseas_sales"] = overseas

    elif calc_mp == "UK":
        if uk_seller and uk_seller in UK_SELLER_TYPES:
            kwargs["uk_seller_type"] = UK_SELLER_TYPES[uk_seller]
        if seller_lvl and seller_lvl in SELLER_LEVELS:
            kwargs["seller_level"] = SELLER_LEVELS[seller_lvl]
        kwargs["vat_registered"] = vat_reg
        if uk_region and uk_region in UK_REGIONS:
            kwargs["buyer_region"] = UK_REGIONS[uk_region]
        kwargs["currency_conversion"] = currency_conv

    elif calc_mp == "DE":
        if de_seller and de_seller in DE_SELLER_TYPES:
            kwargs["de_seller_type"] = DE_SELLER_TYPES[de_seller]
        if seller_lvl and seller_lvl in SELLER_LEVELS:
            kwargs["seller_level"] = SELLER_LEVELS[seller_lvl]
        kwargs["ebay_shop"] = ebay_shop
        if de_region and de_region in DE_REGIONS:
            kwargs["de_buyer_region"] = DE_REGIONS[de_region]

    elif calc_mp == "AU":
        if au_store and au_store in AU_STORES:
            kwargs["au_store_type"] = AU_STORES[au_store]
        if seller_lvl and seller_lvl in SELLER_LEVELS:
            kwargs["seller_level"] = SELLER_LEVELS[seller_lvl]
        kwargs["has_abn"] = has_abn
        kwargs["overseas_sales"] = overseas

    elif calc_mp == "CA":
        if ca_store and ca_store in CA_STORES:
            kwargs["ca_store_type"] = CA_STORES[ca_store]
        if seller_lvl and seller_lvl in SELLER_LEVELS:
            kwargs["seller_level"] = SELLER_LEVELS[seller_lvl]
        if ca_dest and ca_dest in CA_DESTINATIONS:
            kwargs["ca_destination"] = CA_DESTINATIONS[ca_dest]

    result = ProfitCalculator().calculate(ProfitInput(**kwargs))
except Exception as exc:
    st.error(f"Calculation error: {exc}")

# -------------------------------------------------------------------
# Results Presentation
# -------------------------------------------------------------------
with col_results:
    if result is None:
        st.markdown(
            '<div class="rehu-empty"><h3>Enter values to calculate</h3>'
            "<p>Fill in the form on the left to see profit breakdown.</p></div>",
            unsafe_allow_html=True,
        )
    else:
        cur = result.currency
        fees = result.fees

        st.markdown('<div class="rehu-card">', unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:12px;font-weight:700;color:#64748B;'
            'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:14px;'
            'padding-bottom:8px;border-bottom:1px solid #E2E8F0;">Results</div>',
            unsafe_allow_html=True,
        )

        # Headline metrics
        h1, h2, h3 = st.columns(3)
        profit_color = "#047857" if result.is_profitable else "#B91C1C"
        with h1:
            st.markdown(
                f'<div class="rehu-metric">'
                f'<div class="rehu-metric-label">Net Profit</div>'
                f'<div class="rehu-metric-value" style="color:{profit_color};">'
                f'{format_currency(result.net_profit_per_item, cur)}</div></div>',
                unsafe_allow_html=True,
            )
        with h2:
            st.markdown(
                f'<div class="rehu-metric">'
                f'<div class="rehu-metric-label">Margin</div>'
                f'<div class="rehu-metric-value">{format_percent(result.profit_margin)}</div></div>',
                unsafe_allow_html=True,
            )
        with h3:
            st.markdown(
                f'<div class="rehu-metric">'
                f'<div class="rehu-metric-label">ROI</div>'
                f'<div class="rehu-metric-value">{format_percent(result.roi)}</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown('<div style="height:16px;"></div>', unsafe_allow_html=True)

        # Fee breakdown
        st.markdown(
            '<div style="font-size:11px;font-weight:700;color:#64748B;'
            'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">'
            "Fee Breakdown</div>",
            unsafe_allow_html=True,
        )
        fee_lines = [
            ("Final Value Fee", fees.fvf),
            ("Transaction Fee", fees.transaction_fee),
            ("Promoted Listings", fees.promoted_fee),
            ("International Fee", fees.international_fee),
            ("Charity", fees.charity_cost),
        ]
        if float(fees.vat_on_fees or 0) > 0:
            fee_lines.append(("VAT on Fees", fees.vat_on_fees))
        if float(fees.currency_conversion_fee or 0) > 0:
            fee_lines.append(("Currency Conversion", fees.currency_conversion_fee))

        for label, val in fee_lines:
            st.markdown(
                f'<div class="rehu-kv"><span class="rehu-kv-k">{label}</span>'
                f'<span class="rehu-kv-v">{format_currency(val, cur)}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            f'<div class="rehu-kv" style="border-top:1px solid #E2E8F0;padding-top:8px;margin-top:4px;">'
            f'<span class="rehu-kv-k" style="font-weight:600;color:#0F172A;">Total Fees</span>'
            f'<span class="rehu-kv-v" style="font-weight:700;">'
            f'{format_currency(fees.total_fees, cur)}</span></div>',
            unsafe_allow_html=True,
        )

        # Warnings / Assumptions
        if result.warnings:
            with st.expander(f"Warnings ({len(result.warnings)})"):
                for w in result.warnings:
                    st.markdown(f'<div style="font-size:12px;color:#B45309;margin-bottom:4px;">- {w}</div>',
                                unsafe_allow_html=True)
        if result.assumptions:
            with st.expander(f"Assumptions ({len(result.assumptions)})"):
                for a in result.assumptions:
                    st.markdown(f'<div style="font-size:12px;color:#64748B;margin-bottom:4px;">- {a}</div>',
                                unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

# Clear prefill after hydration
if prefill_title:
    st.session_state["calculator_prefill"] = None