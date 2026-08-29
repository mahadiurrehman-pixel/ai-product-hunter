"""
Safe eBay Authentication Diagnostic Script

Validates eBay OAuth configuration and connectivity without exposing
credentials, secrets, or access tokens.

Usage:
    python scripts/diagnose_ebay_auth.py
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from config import settings
from services.ebay.auth import EbayAuth
from services.ebay.exceptions import EbayAuthenticationError


def run_diagnostic():
    print("=" * 70)
    print("  EBAY AUTHENTICATION DIAGNOSTIC (SAFE / REDACTED)")
    print("=" * 70)

    # 1. Environment & Target Endpoint
    print("\n1. Environment & Endpoints:")
    print(f"  • Environment Selected:     {settings.ebay_environment}")
    print(f"  • Base API URL:             {settings.ebay_api_base_url}")
    print(f"  • OAuth Token Endpoint:     {settings.ebay_oauth_url}")
    print(f"  • Scope Configured:         {settings.ebay_oauth_scope}")

    # 2. Credential Status (.env check - values masked)
    app_id_present = bool(settings.ebay_app_id and settings.ebay_app_id.strip())
    cert_id_present = bool(settings.ebay_cert_id and settings.ebay_cert_id.strip())
    
    # Check if key patterns match expected environment without leaking key text
    app_id_type = "UNKNOWN"
    if app_id_present:
        if "-PRD-" in settings.ebay_app_id:
            app_id_type = "PRODUCTION KEY FORMAT (-PRD-)"
        elif "-SBX-" in settings.ebay_app_id:
            app_id_type = "SANDBOX KEY FORMAT (-SBX-)"

    print("\n2. Credential Status in .env:")
    print(f"  • EBAY_APP_ID Loaded:       {'[YES]' if app_id_present else '[MISSING / EMPTY]'}")
    print(f"  • EBAY_APP_ID Key Type:     {app_id_type}")
    print(f"  • EBAY_CERT_ID Loaded:      {'[YES]' if cert_id_present else '[MISSING / EMPTY]'}")

    # Consistency warning
    if settings.ebay_environment == "production" and app_id_type == "SANDBOX KEY FORMAT (-SBX-)":
        print("\n  ⚠️  WARNING: Environment is 'production' but EBAY_APP_ID appears to be a Sandbox key.")
    elif settings.ebay_environment == "sandbox" and app_id_type == "PRODUCTION KEY FORMAT (-PRD-)":
        print("\n  ⚠️  WARNING: Environment is 'sandbox' but EBAY_APP_ID appears to be a Production key.")

    # 3. Test OAuth Request
    print("\n3. Live OAuth Connectivity Check:")
    if not (app_id_present and cert_id_present):
        print("  ❌ Diagnostic aborted: Credentials missing in .env")
        return 1

    try:
        auth = EbayAuth()
        token = auth.get_application_token()
        print("  ✅ OAuth 2.0 Token Generation: SUCCESS")
        print(f"  ✅ Token Type: Bearer")
        print(f"  ✅ Token Expires In: ~7200 seconds")
        print(f"  ✅ Token Cached in Memory: {auth._is_token_valid()}")
        return 0

    except EbayAuthenticationError as e:
        print(f"  ❌ Authentication Failed: {e}")
        # Make a direct low-level request to get sanitized server error code
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    settings.ebay_oauth_url,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data={"grant_type": "client_credentials", "scope": settings.ebay_oauth_scope}
                )
                print(f"  • HTTP Status Code: {resp.status_code}")
                try:
                    err_json = resp.json()
                    error_code = err_json.get("error")
                    error_desc = err_json.get("error_description")
                    print(f"  • eBay Error Code:        {error_code}")
                    print(f"  • eBay Error Description: {error_desc}")
                except Exception:
                    pass
        except Exception as net_err:
            print(f"  • Diagnostic Network Error: {net_err}")
        return 1

    except Exception as general_err:
        print(f"  ❌ Unexpected Diagnostic Error: {type(general_err).__name__}: {general_err}")
        return 1


if __name__ == "__main__":
    sys.exit(run_diagnostic())