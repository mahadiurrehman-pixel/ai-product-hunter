"""
REHU Internal Python Engine API (Phase M1).

Wraps the core Python business logic (Pipeline, Profit, Matching) in a
FastAPI service. Strictly for internal consumption by the future Node.js
backend. Protected by shared-secret header X-INTERNAL-AUTH.

DO NOT expose this port to the public internet.
"""
from __future__ import annotations

import traceback
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field

from config import settings
from services.pipeline import OpportunityPipeline
from services.profit.calculator import ProfitCalculator
from services.profit.models import ProfitInput
from database.connection import get_db_context
from utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="REHU Python Engine",
    description="Internal microservice wrapping REHU core algorithms.",
    version="1.0.0",
    docs_url=None,       # Disable Swagger in production
    redoc_url=None,
)


# ── Auth Guard ─────────────────────────────────────────────────────
def verify_internal_auth(
    x_internal_auth: Optional[str] = Header(None, alias="X-INTERNAL-AUTH"),
) -> None:
    """Reject any request that doesn't carry the shared secret."""
    expected = getattr(settings, "internal_auth_secret", "")
    if not expected or expected == "dev_internal_secret_change_in_production":
        logger.warning(
            "INTERNAL_AUTH_SECRET is unset or still the default — "
            "this is unsafe in production!"
        )
    if not x_internal_auth or x_internal_auth != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal auth token",
        )


# ── Request / Response DTOs ───────────────────────────────────────
class PipelineRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    marketplace: str = "US"
    limit: int = Field(default=20, ge=1, le=100)
    min_match_score: float = Field(default=0.60, ge=0.0, le=1.0)
    profit_defaults: Dict[str, Any] = Field(default_factory=dict)


class ProfitCalcRequest(BaseModel):
    """
    Intentionally flat. We only pass fields that ProfitInput is
    *guaranteed* to accept per the handoff data model. Marketplace-
    specific enum fields (store_type, seller_level, etc.) are passed
    through `extra_kwargs` so the caller can supply them without us
    hard-coding enum imports that may change.
    """
    marketplace: str
    sold_price: float
    item_cost: float
    shipping_cost: float
    currency: str = "USD"
    shipping_charged: float = 0.0
    other_costs: float = 0.0
    num_orders: int = 1
    promoted_rate: float = 0.0
    charity_percent: float = 0.0
    extra_kwargs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Marketplace-specific fields forwarded to ProfitInput",
    )


# ── Endpoints ──────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    """Public liveness probe — no auth required."""
    return {"status": "healthy", "service": "rehu-python-engine"}


@app.post(
    "/internal/pipeline/analyze",
    dependencies=[Depends(verify_internal_auth)],
)
def analyze_pipeline(req: PipelineRequest):
    """Run the full Opportunity Pipeline (eBay → Match → Profit → Score)."""
    try:
        pipeline = OpportunityPipeline()
        with get_db_context() as db:
            results = pipeline.analyze(
                query=req.query,
                marketplace=req.marketplace,
                limit=req.limit,
                min_match_score=req.min_match_score,
                profit_defaults=req.profit_defaults,
                db=db,
            )

        # FIX: guard against empty result set
        diagnostics: Dict[str, Any] = {}
        serialized: List[Dict[str, Any]] = []
        if results:
            serialized = [r.to_dict() for r in results]
            if hasattr(results[0], "diagnostics"):
                diagnostics = results[0].diagnostics or {}

        return {"results": serialized, "diagnostics": diagnostics}

    except Exception as exc:
        logger.error("Pipeline error: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(exc))


@app.post(
    "/internal/profit/calculate",
    dependencies=[Depends(verify_internal_auth)],
)
def calculate_profit(req: ProfitCalcRequest):
    """Calculate profit for a single scenario."""
    try:
        # Build the core kwargs that ProfitInput is guaranteed to accept
        kwargs: Dict[str, Any] = {
            "marketplace": req.marketplace,
            "currency": req.currency,
            "sold_price": Decimal(str(req.sold_price)),
            "item_cost": Decimal(str(req.item_cost)),
            "shipping_cost": Decimal(str(req.shipping_cost)),
            "shipping_charged": Decimal(str(req.shipping_charged)),
            "other_costs": Decimal(str(req.other_costs)),
            "num_orders": req.num_orders,
            "promoted_rate": req.promoted_rate,
            "charity_percent": req.charity_percent,
        }

        # Merge marketplace-specific fields from the caller.
        # We convert any float values to Decimal to avoid type errors.
        for key, val in req.extra_kwargs.items():
            if isinstance(val, float):
                try:
                    kwargs[key] = Decimal(str(val))
                except InvalidOperation:
                    kwargs[key] = val
            else:
                kwargs[key] = val

        profit_input = ProfitInput(**kwargs)
        result = ProfitCalculator().calculate(profit_input)

        if hasattr(result, "to_dict"):
            return result.to_dict()
        return {"error": "Result object has no to_dict() method"}

    except TypeError as exc:
        # Catches unexpected kwargs that ProfitInput doesn't accept
        logger.warning("ProfitInput rejected kwargs: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("Profit calc error: %s", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(exc))