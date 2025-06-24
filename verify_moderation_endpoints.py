#!/usr/bin/env python3
"""
Verify moderation endpoints are working after deployment
"""

import requests
import json

# Base URL for the API
BASE_URL = "https://calimara.ro"

# Test endpoints (no auth required)
TEST_ENDPOINTS = [
    "/api/moderation/test-simple",
    "/api/moderation/test-create-content"
]

# Endpoints that require authentication
AUTH_ENDPOINTS = [
    "/api/moderation/stats",
    "/api/moderation/content/pending",
    "/api/moderation/content/flagged",
    "/api/moderation/queue",
    "/api/moderation/logs"
]

def test_endpoint(url):
    """Test if an endpoint is accessible"""
    try:
        response = requests.get(url, timeout=5, verify=False)
        return response.status_code, response.text[:200] if response.text else "No content"
    except Exception as e:
        return "Error", str(e)

def main():
    print("=" * 60)
    print("VERIFYING MODERATION ENDPOINTS")
    print("=" * 60)
    
    # Test public endpoints
    print("\n1. Testing Public Endpoints:")
    print("-" * 40)
    for endpoint in TEST_ENDPOINTS:
        url = BASE_URL + endpoint
        status, content = test_endpoint(url)
        print(f"{endpoint}: {status}")
        if status == 200:
            print(f"   ✅ Endpoint is accessible")
            try:
                data = json.loads(content)
                print(f"   Response: {json.dumps(data, indent=2)[:200]}...")
            except:
                print(f"   Response: {content}")
        else:
            print(f"   ❌ Endpoint returned: {content}")
    
    # Test auth endpoints (expect 403 without auth)
    print("\n2. Testing Protected Endpoints (should return 403):")
    print("-" * 40)
    for endpoint in AUTH_ENDPOINTS:
        url = BASE_URL + endpoint
        status, content = test_endpoint(url)
        print(f"{endpoint}: {status}")
        if status == 403:
            print(f"   ✅ Protected correctly (requires auth)")
        elif status == 404:
            print(f"   ❌ Endpoint not found - deployment may be needed")
        else:
            print(f"   ⚠️  Unexpected status: {content}")
    
    # Test moderation functionality
    print("\n3. Testing AI Moderation:")
    print("-" * 40)
    url = BASE_URL + "/api/moderation/test-simple"
    status, response = test_endpoint(url)
    if status == 200:
        try:
            data = json.loads(response)
            if data.get("moderation_enabled"):
                print("✅ AI Moderation is ENABLED")
                if data.get("api_key_configured"):
                    print("✅ Gemini API key is configured")
                else:
                    print("❌ Gemini API key is NOT configured")
                    
                # Check test results
                toxic_test = data.get("toxic_content_test", {})
                if toxic_test.get("status") == "flagged":
                    print(f"✅ Toxic content correctly flagged (score: {toxic_test.get('score', 'N/A')})")
                else:
                    print(f"❌ Toxic content not flagged properly: {toxic_test}")
                    
                normal_test = data.get("normal_content_test", {})
                if normal_test.get("status") == "approved":
                    print(f"✅ Normal content correctly approved (score: {normal_test.get('score', 'N/A')})")
                else:
                    print(f"❌ Normal content not approved properly: {normal_test}")
            else:
                print("❌ AI Moderation is DISABLED")
        except Exception as e:
            print(f"❌ Error parsing response: {e}")
    else:
        print(f"❌ Test endpoint not accessible: {status}")
    
    print("\n" + "=" * 60)
    print("Verification complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()