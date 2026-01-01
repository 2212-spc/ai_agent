import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

try:
    from app.main import app
    print("Syntax check passed for main.py")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
