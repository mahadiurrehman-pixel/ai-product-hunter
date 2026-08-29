"""
eBay Sandbox API Verification Script

Tests OAuth authentication and Browse API search with real credentials.
Run this before Phase 3 to verify eBay integration works.

Usage:
    python scripts/verify_ebay_sandbox.py
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ebay.auth import EbayAuth
from services.ebay.client import EbayClient
from config import settings
from utils.logger import setup_logging

# Setup logging
logger = setup_logging("ebay_verification")


def verify_credentials():
    """Verify eBay credentials are configured."""
    print("\n" + "=" * 70)
    print("eBay SANDBOX CREDENTIALS VERIFICATION")
    print("=" * 70)
    
    if not settings.ebay_app_id or not settings.ebay_cert_id:
        print("❌ ERROR: eBay credentials not configured!")
        print("\nPlease update .env with:")
        print("  EBAY_APP_ID=<your-sandbox-app-id>")
        print("  EBAY_CERT_ID=<your-sandbox-cert-id>")
        return False
    
    # Check for placeholder values
    if "YourAppI" in settings.ebay_app_id or "SBX-1234" in settings.ebay_cert_id:
        print("❌ ERROR: Still using placeholder credentials!")
        print("\nPlease replace with actual eBay Sandbox credentials in .env")
        return False
    
    print(f"\n✅ Environment: {settings.ebay_environment}")
    print(f"✅ Marketplace: {settings.ebay_marketplace_id}")
    print(f"✅ App ID configured: Yes ({len(settings.ebay_app_id)} chars)")
    print(f"✅ Cert ID configured: Yes ({len(settings.ebay_cert_id)} chars)")
    print(f"✅ OAuth URL: {settings.ebay_oauth_url}")
    
    return True


def verify_oauth():
    """Test OAuth 2.0 authentication."""
    print("\n" + "-" * 70)
    print("STEP 1: OAuth 2.0 Authentication")
    print("-" * 70)
    
    try:
        auth = EbayAuth()
        print("\n⏳ Requesting OAuth token from eBay Sandbox...")
        
        token = auth.get_application_token()
        
        print(f"✅ SUCCESS: OAuth token obtained")
        print(f"✅ Token type: Application Access Token")
        print(f"✅ Token valid: {auth._is_token_valid()}")
        print(f"✅ Token length: {len(token)} characters")
        
        return True
        
    except Exception as e:
        print(f"❌ FAILED: OAuth authentication error")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {str(e)}")
        
        # Provide helpful hints
        if "401" in str(e) or "Unauthorized" in str(e):
            print("\n💡 Possible issues:")
            print("   • App ID or Cert ID is incorrect")
            print("   • Extra spaces in credentials")
            print("   • Sandbox keyset not activated yet (wait 5-10 min)")
        
        return False


def verify_browse_api():
    """Test Browse API search request."""
    print("\n" + "-" * 70)
    print("STEP 2: Browse API Search Request")
    print("-" * 70)
    
    try:
        client = EbayClient()
        print("\n⏳ Searching for 'wireless earbuds' (limit=5)...")
        
        result = client.search_items(
            query="wireless earbuds",
            limit=5
        )
        
        print(f"✅ SUCCESS: Search completed")
        print(f"✅ Total results: {result['total']}")
        print(f"✅ Items returned: {result['items_count']}")
        
        if result['items_count'] > 0:
            print(f"\n📦 Sample Product:")
            first_item = result['items'][0]
            print(f"   Title: {first_item['title'][:60]}...")
            print(f"   Price: ${first_item['price_value']} {first_item['price_currency']}")
            print(f"   Item ID: {first_item['item_id']}")
            print(f"   Condition: {first_item['condition']}")
            
            if first_item.get('estimated_sold_quantity'):
                print(f"   Estimated sold: {first_item['estimated_sold_quantity']}")
        
        return True
        
    except Exception as e:
        print(f"❌ FAILED: Browse API search error")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {str(e)}")
        return False


def verify_database_save():
    """Test saving eBay listings to database."""
    print("\n" + "-" * 70)
    print("STEP 3: Database Persistence")
    print("-" * 70)
    
    try:
        from services.ebay.repository import EbayListingRepository
        from database import get_db
        
        # Get fresh search results
        client = EbayClient()
        result = client.search_items(query="iphone", limit=3)
        
        if result['items_count'] == 0:
            print("⚠️  SKIPPED: No items to save")
            return True
        
        print(f"\n⏳ Saving {result['items_count']} listings to database...")
        
        db = next(get_db())
        saved = EbayListingRepository.save_listings_bulk(
            db, 
            result['items']
        )
        
        print(f"✅ SUCCESS: {len(saved)} listings saved")
        
        # Verify retrieval
        first_item_id = result['items'][0]['item_id']
        retrieved = EbayListingRepository.get_by_item_id(db, first_item_id)
        
        if retrieved:
            print(f"✅ Database retrieval verified")
            print(f"   Retrieved: {retrieved.title[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ FAILED: Database operation error")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {str(e)}")
        return False


def main():
    """Run all verification steps."""
    print("\n🔍 eBay Sandbox API Verification")
    print("=" * 70)
    
    results = {
        "credentials": False,
        "oauth": False,
        "browse_api": False,
        "database": False,
    }
    
    # Step 1: Verify credentials
    results["credentials"] = verify_credentials()
    if not results["credentials"]:
        print("\n" + "=" * 70)
        print("⛔ VERIFICATION ABORTED: Credentials not configured")
        print("=" * 70)
        print("\nPlease:")
        print("  1. Copy .env.example to .env")
        print("  2. Replace EBAY_APP_ID and EBAY_CERT_ID with actual values")
        print("  3. Run this script again")
        return False
    
    # Step 2: Test OAuth
    results["oauth"] = verify_oauth()
    if not results["oauth"]:
        print("\n" + "=" * 70)
        print("⛔ VERIFICATION FAILED: OAuth authentication")
        print("=" * 70)
        return False
    
    # Step 3: Test Browse API
    results["browse_api"] = verify_browse_api()
    if not results["browse_api"]:
        print("\n" + "=" * 70)
        print("⛔ VERIFICATION FAILED: Browse API search")
        print("=" * 70)
        return False
    
    # Step 4: Test Database
    results["database"] = verify_database_save()
    
    # Final summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    
    for step, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {step.replace('_', ' ').title()}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 ALL VERIFICATIONS PASSED")
        print("=" * 70)
        print("\neBay Sandbox integration is working correctly!")
        print("Ready to proceed to Phase 3.")
    else:
        print("⛔ SOME VERIFICATIONS FAILED")
        print("=" * 70)
        print("\nPlease resolve issues before proceeding to Phase 3.")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)