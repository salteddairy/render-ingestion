"""
Pre-deployment validation script
Run this before deploying to Render to verify everything is set up correctly
"""

import os
import sys
from cryptography.fernet import Fernet
import json


def check_file_exists(filepath, description):
    """Check if a file exists."""
    if os.path.exists(filepath):
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description} NOT FOUND: {filepath}")
        return False


def check_env_variable(var_name, required=True):
    """Check if environment variable is set."""
    value = os.getenv(var_name)
    if value:
        # Mask sensitive values
        if "KEY" in var_name or "PASSWORD" in var_name:
            display_value = value[:4] + "..." + value[-4:]
        else:
            display_value = value
        print(f"✅ {var_name}: {display_value}")
        return True
    else:
        if required:
            print(f"❌ {var_name} NOT SET")
        else:
            print(f"⚠️  {var_name} NOT SET (optional)")
        return False


def test_encryption():
    """Test Fernet encryption/decryption."""
    try:
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            print("❌ Cannot test encryption: ENCRYPTION_KEY not set")
            return False

        cipher = Fernet(key.encode('utf-8'))
        test_data = {"test": "data"}
        encrypted = cipher.encrypt(json.dumps(test_data).encode('utf-8'))
        decrypted = json.loads(cipher.decrypt(encrypted).decode('utf-8'))

        if decrypted == test_data:
            print("✅ Encryption/decryption test PASSED")
            return True
        else:
            print("❌ Encryption/decryption test FAILED")
            return False
    except Exception as e:
        print(f"❌ Encryption test failed with error: {str(e)}")
        return False


def validate_project_structure():
    """Validate all required files exist."""
    print("\n" + "="*60)
    print("STEP 1: Validating Project Structure")
    print("="*60)

    required_files = {
        "app.py": "Main Flask application",
        "handlers.py": "Data type handlers",
        "supabase_client.py": "Supabase client integration",
        "requirements.txt": "Python dependencies",
        "Dockerfile": "Docker configuration",
        "render.yaml": "Render deployment config",
        ".env.example": "Environment variables template",
        ".gitignore": "Git ignore rules",
        "README.md": "Documentation",
        "tests/__init__.py": "Test package",
        "tests/test_app.py": "Test suite"
    }

    all_exist = True
    for file, description in required_files.items():
        if not check_file_exists(file, description):
            all_exist = False

    return all_exist


def validate_environment():
    """Validate environment variables."""
    print("\n" + "="*60)
    print("STEP 2: Validating Environment Variables")
    print("="*60)

    # Load .env if exists
    env_file = ".env"
    if os.path.exists(env_file):
        print(f"✅ Loading environment from {env_file}")
        from dotenv import load_dotenv
        load_dotenv(env_file)
    else:
        print(f"⚠️  {env_file} not found (you'll need to set vars manually)")

    required_vars = [
        "API_KEY",
        "ENCRYPTION_KEY",
        "DATABASE_URL"
    ]

    optional_vars = [
        "LOG_LEVEL",
        "PORT"
    ]

    all_set = True
    print("\nRequired Variables:")
    for var in required_vars:
        if not check_env_variable(var, required=True):
            all_set = False

    print("\nOptional Variables:")
    for var in optional_vars:
        check_env_variable(var, required=False)

    return all_set


def validate_encryption():
    """Validate encryption/decryption works."""
    print("\n" + "="*60)
    print("STEP 3: Validating Encryption/Decryption")
    print("="*60)

    return test_encryption()


def validate_dependencies():
    """Validate Python dependencies can be imported."""
    print("\n" + "="*60)
    print("STEP 4: Validating Python Dependencies")
    print("="*60)

    required_modules = [
        ("flask", "Flask"),
        ("cryptography", "Cryptography"),
        ("supabase", "Supabase client"),
        ("dotenv", "python-dotenv"),
        ("gunicorn", "Gunicorn")
    ]

    all_available = True
    for module, name in required_modules:
        try:
            __import__(module)
            print(f"✅ {name} available")
        except ImportError:
            print(f"❌ {name} NOT INSTALLED")
            all_available = False

    return all_available


def validate_code_syntax():
    """Validate Python files have no syntax errors."""
    print("\n" + "="*60)
    print("STEP 5: Validating Python Syntax")
    print("="*60)

    python_files = [
        "app.py",
        "handlers.py",
        "supabase_client.py"
    ]

    all_valid = True
    for file in python_files:
        try:
            with open(file, 'r') as f:
                compile(f.read(), file, 'exec')
            print(f"✅ {file} - Valid syntax")
        except SyntaxError as e:
            print(f"❌ {file} - Syntax error: {str(e)}")
            all_valid = False

    return all_valid


def generate_deployment_checklist():
    """Generate pre-deployment checklist."""
    print("\n" + "="*60)
    print("PRE-DEPLOYMENT CHECKLIST")
    print("="*60)

    checklist = [
        ("Create GitHub repository", False),
        ("Push code to GitHub", False),
        ("Create Render account", False),
        ("Set environment variables in Render", False),
        ("Deploy service via Render dashboard", False),
        ("Test /health endpoint", False),
        ("Test /api/ingest with sample data", False),
        ("Verify data in Supabase", False),
        ("Update SAP Agent configuration", False),
        ("Monitor first data ingestion", False)
    ]

    print("\nCheck off items as you complete them:")
    for i, (item, _) in enumerate(checklist, 1):
        print(f"  [ ] {i}. {item}")

    return checklist


def main():
    """Run all validation checks."""
    print("\n" + "="*60)
    print("RENDER INGESTION SERVICE - PRE-DEPLOYMENT VALIDATION")
    print("="*60)

    # Run validation steps
    results = {
        "Project Structure": validate_project_structure(),
        "Environment Variables": validate_environment(),
        "Encryption/Decryption": validate_encryption(),
        "Dependencies": validate_dependencies(),
        "Code Syntax": validate_code_syntax()
    }

    # Generate deployment checklist
    generate_deployment_checklist()

    # Summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)

    all_passed = True
    for step, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{step}: {status}")
        if not passed:
            all_passed = False

    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL VALIDATIONS PASSED - READY FOR DEPLOYMENT")
        print("="*60)
        print("\nNext steps:")
        print("1. Create GitHub repository")
        print("2. Push code to GitHub")
        print("3. Deploy to Render (see RENDER_INGESTION_DEPLOYMENT.md)")
        print("4. Test health check: curl https://your-service.onrender.com/health")
        return 0
    else:
        print("❌ VALIDATION FAILED - FIX ISSUES BEFORE DEPLOYING")
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
