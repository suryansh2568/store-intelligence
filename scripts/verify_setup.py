"""
Verify that the Store Intelligence system is set up correctly.
"""
import sys
import subprocess
import importlib.util
from pathlib import Path


def check_python_version():
    """Check Python version."""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor}.{version.micro} (need 3.10+)")
        return False


def check_package(package_name):
    """Check if a Python package is installed."""
    spec = importlib.util.find_spec(package_name)
    if spec is not None:
        print(f"✓ {package_name}")
        return True
    else:
        print(f"✗ {package_name} (not installed)")
        return False


def check_docker():
    """Check if Docker is available."""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✓ Docker ({version})")
            return True
        else:
            print("✗ Docker (not found)")
            return False
    except Exception:
        print("✗ Docker (not found)")
        return False


def check_docker_compose():
    """Check if Docker Compose is available."""
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✓ Docker Compose ({version})")
            return True
        else:
            print("✗ Docker Compose (not found)")
            return False
    except Exception:
        print("✗ Docker Compose (not found)")
        return False


def check_file_structure():
    """Check if required files exist."""
    required_files = [
        "README.md",
        "requirements.txt",
        "docker-compose.yml",
        "app/main.py",
        "pipeline/detect.py",
        "dashboard/app.py",
        "docs/DESIGN.md",
        "docs/CHOICES.md"
    ]
    
    all_exist = True
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path} (missing)")
            all_exist = False
    
    return all_exist


def main():
    """Run all verification checks."""
    print("=" * 60)
    print("Store Intelligence System - Setup Verification")
    print("=" * 60)
    
    print("\n1. Checking Python Version...")
    python_ok = check_python_version()
    
    print("\n2. Checking Required Python Packages...")
    packages = [
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "pydantic",
        "ultralytics",
        "cv2",
        "numpy",
        "pandas",
        "pytest",
        "requests",
        "rich"
    ]
    
    packages_ok = all(check_package(pkg) for pkg in packages)
    
    print("\n3. Checking Docker...")
    docker_ok = check_docker()
    
    print("\n4. Checking Docker Compose...")
    compose_ok = check_docker_compose()
    
    print("\n5. Checking File Structure...")
    files_ok = check_file_structure()
    
    print("\n" + "=" * 60)
    print("Verification Summary")
    print("=" * 60)
    
    all_checks = [
        ("Python Version", python_ok),
        ("Python Packages", packages_ok),
        ("Docker", docker_ok),
        ("Docker Compose", compose_ok),
        ("File Structure", files_ok)
    ]
    
    for check_name, status in all_checks:
        status_str = "✓ PASS" if status else "✗ FAIL"
        print(f"{check_name:.<40} {status_str}")
    
    print("=" * 60)
    
    if all(status for _, status in all_checks):
        print("\n✓ All checks passed! System is ready.")
        print("\nNext steps:")
        print("  1. docker compose up -d")
        print("  2. python scripts/load_sample_data.py")
        print("  3. python dashboard/app.py")
        return 0
    else:
        print("\n✗ Some checks failed. Please fix the issues above.")
        print("\nTo install missing packages:")
        print("  pip install -r requirements.txt")
        return 1


if __name__ == "__main__":
    sys.exit(main())
