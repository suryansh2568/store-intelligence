#!/usr/bin/env python3
"""
Test script to verify production API endpoints are working correctly.
"""
import requests
import json
from datetime import datetime

API_URL = "https://store-intelligence-api.onrender.com"
STORE_ID = "STORE_BLR_002"

def test_endpoint(endpoint_name, url):
    """Test a single API endpoint."""
    print(f"\n{'='*60}")
    print(f"Testing: {endpoint_name}")
    print(f"URL: {url}")
    print('='*60)
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response Type: {type(data)}")
            
            if isinstance(data, dict):
                print(f"Keys: {list(data.keys())}")
            elif isinstance(data, list):
                print(f"List Length: {len(data)}")
                if data:
                    print(f"First Item Type: {type(data[0])}")
                    if isinstance(data[0], dict):
                        print(f"First Item Keys: {list(data[0].keys())}")
            
            print(f"Response Preview:")
            print(json.dumps(data, indent=2)[:500] + "..." if len(str(data)) > 500 else json.dumps(data, indent=2))
            
            return True, data
        else:
            print(f"Error: {response.status_code}")
            print(f"Response: {response.text}")
            return False, None
            
    except Exception as e:
        print(f"Exception: {e}")
        return False, None

def main():
    """Test all production API endpoints."""
    print("Store Intelligence Production API Test")
    print(f"API URL: {API_URL}")
    print(f"Store ID: {STORE_ID}")
    print(f"Test Time: {datetime.now()}")
    
    endpoints = [
        ("Health Check", f"{API_URL}/health"),
        ("Store Metrics", f"{API_URL}/stores/{STORE_ID}/metrics"),
        ("Zone Heatmap", f"{API_URL}/stores/{STORE_ID}/heatmap"),
        ("Conversion Funnel", f"{API_URL}/stores/{STORE_ID}/funnel"),
        ("Anomalies", f"{API_URL}/stores/{STORE_ID}/anomalies"),
    ]
    
    results = {}
    
    for name, url in endpoints:
        success, data = test_endpoint(name, url)
        results[name] = {"success": success, "data": data}
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    
    for name, result in results.items():
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        print(f"{status} {name}")
    
    # Specific checks for dashboard compatibility
    print(f"\n{'='*60}")
    print("DASHBOARD COMPATIBILITY CHECKS")
    print('='*60)
    
    # Check heatmap format
    if results["Zone Heatmap"]["success"]:
        heatmap_data = results["Zone Heatmap"]["data"]
        if isinstance(heatmap_data, list):
            print("⚠️  Heatmap returns list (not dict) - Dashboard fix needed")
        elif isinstance(heatmap_data, dict) and "zones" in heatmap_data:
            print("✅ Heatmap returns correct dict format")
        else:
            print("❌ Heatmap format unexpected")
    
    # Check funnel format
    if results["Conversion Funnel"]["success"]:
        funnel_data = results["Conversion Funnel"]["data"]
        if isinstance(funnel_data, dict) and "stages" in funnel_data:
            print("✅ Funnel returns correct dict format")
        else:
            print("❌ Funnel format unexpected")
    
    print(f"\n{'='*60}")
    print("RECOMMENDATIONS")
    print('='*60)
    
    if results["Zone Heatmap"]["success"]:
        heatmap_data = results["Zone Heatmap"]["data"]
        if isinstance(heatmap_data, list):
            print("1. Dashboard code has been updated to handle list format")
            print("2. Consider fixing API to return proper Heatmap object")
    
    if results["Health Check"]["success"]:
        health_data = results["Health Check"]["data"]
        if "stale_feed_warnings" in health_data and health_data["stale_feed_warnings"]:
            print("3. Data feed is stale - consider refreshing data")
            for warning in health_data["stale_feed_warnings"]:
                print(f"   - {warning}")

if __name__ == "__main__":
    main()