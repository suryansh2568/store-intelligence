"""
Complete system setup with real Brigade Bangalore data.

This script:
1. Verifies Docker services are running
2. Loads POS transaction data
3. Generates realistic events from POS data
4. Validates the system is working
"""
import subprocess
import time
import requests
import sys


def check_docker():
    """Check if Docker services are running."""
    print("="*60)
    print("Step 1: Checking Docker Services")
    print("="*60)
    
    try:
        result = subprocess.run(
            ["docker", "compose", "ps"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if "api" in result.stdout and "db" in result.stdout:
            print("✓ Docker services are running")
            return True
        else:
            print("✗ Docker services not found")
            print("\nPlease run: docker compose up -d")
            return False
            
    except Exception as e:
        print(f"✗ Error checking Docker: {e}")
        print("\nPlease run: docker compose up -d")
        return False


def wait_for_api():
    """Wait for API to be ready."""
    print("\n" + "="*60)
    print("Step 2: Waiting for API")
    print("="*60)
    
    max_attempts = 30
    for i in range(max_attempts):
        try:
            response = requests.get("http://localhost:8000/health", timeout=2)
            if response.status_code == 200:
                print(f"✓ API is ready (attempt {i+1})")
                return True
        except:
            pass
        
        print(f"  Waiting for API... ({i+1}/{max_attempts})")
        time.sleep(2)
    
    print("✗ API did not start in time")
    return False


def load_pos_data():
    """Load POS transaction data."""
    print("\n" + "="*60)
    print("Step 3: Loading POS Transaction Data")
    print("="*60)
    
    try:
        result = subprocess.run(
            ["python", "scripts/load_pos_data.py"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print(result.stdout)
        
        if result.returncode == 0:
            print("✓ POS data loaded successfully")
            return True
        else:
            print(f"✗ Error loading POS data: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def generate_events():
    """Generate realistic events from POS data."""
    print("\n" + "="*60)
    print("Step 4: Generating Realistic Events")
    print("="*60)
    
    try:
        result = subprocess.run(
            ["python", "scripts/generate_realistic_events.py"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        print(result.stdout)
        
        if result.returncode == 0:
            print("✓ Events generated successfully")
            return True
        else:
            print(f"✗ Error generating events: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def validate_system():
    """Validate the system is working correctly."""
    print("\n" + "="*60)
    print("Step 5: Validating System")
    print("="*60)
    
    store_id = "STORE_BLR_002"
    date = "2026-04-10"
    
    endpoints = [
        f"/stores/{store_id}/metrics?date={date}",
        f"/stores/{store_id}/funnel?date={date}",
        f"/stores/{store_id}/heatmap?date={date}",
        f"/stores/{store_id}/anomalies?date={date}",
        "/health"
    ]
    
    all_passed = True
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"http://localhost:8000{endpoint}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"  ✓ {endpoint}")
                
                # Show key metrics
                if "metrics" in endpoint:
                    print(f"    - Unique Visitors: {data.get('unique_visitors', 0)}")
                    print(f"    - Conversion Rate: {data.get('conversion_rate', 0)*100:.1f}%")
                elif "funnel" in endpoint:
                    stages = data.get('stages', [])
                    if stages:
                        print(f"    - Entry: {stages[0]['count']}")
                        print(f"    - Purchase: {stages[-1]['count']}")
                elif "health" in endpoint:
                    print(f"    - Status: {data.get('status', 'unknown')}")
            else:
                print(f"  ✗ {endpoint} - Status {response.status_code}")
                all_passed = False
                
        except Exception as e:
            print(f"  ✗ {endpoint} - Error: {e}")
            all_passed = False
    
    return all_passed


def main():
    """Run complete system setup."""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  Store Intelligence System - Complete Setup".center(58) + "║")
    print("║" + "  Brigade Bangalore - April 10, 2026".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    print()
    
    # Step 1: Check Docker
    if not check_docker():
        print("\n❌ Setup failed: Docker services not running")
        print("\nPlease run:")
        print("  docker compose up -d")
        sys.exit(1)
    
    # Step 2: Wait for API
    if not wait_for_api():
        print("\n❌ Setup failed: API not responding")
        print("\nPlease check:")
        print("  docker compose logs api")
        sys.exit(1)
    
    # Step 3: Load POS data
    if not load_pos_data():
        print("\n❌ Setup failed: Could not load POS data")
        sys.exit(1)
    
    # Step 4: Generate events
    if not generate_events():
        print("\n❌ Setup failed: Could not generate events")
        sys.exit(1)
    
    # Step 5: Validate system
    if not validate_system():
        print("\n⚠️  Some endpoints failed validation")
    
    # Success!
    print("\n" + "="*60)
    print("✅ SYSTEM SETUP COMPLETE!")
    print("="*60)
    print()
    print("Your Store Intelligence system is ready!")
    print()
    print("📊 View Metrics:")
    print("  http://localhost:8000/stores/STORE_BLR_002/metrics?date=2026-04-10")
    print()
    print("📈 View Funnel:")
    print("  http://localhost:8000/stores/STORE_BLR_002/funnel?date=2026-04-10")
    print()
    print("🗺️  View Heatmap:")
    print("  http://localhost:8000/stores/STORE_BLR_002/heatmap?date=2026-04-10")
    print()
    print("🚨 View Anomalies:")
    print("  http://localhost:8000/stores/STORE_BLR_002/anomalies?date=2026-04-10")
    print()
    print("📱 Launch Dashboard:")
    print("  python dashboard/app.py --store-id STORE_BLR_002")
    print()
    print("📖 API Documentation:")
    print("  http://localhost:8000/docs")
    print()


if __name__ == "__main__":
    main()
