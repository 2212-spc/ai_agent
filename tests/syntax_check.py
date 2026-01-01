import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

try:
    from app.graph_agent import stream_agent
    print("Syntax check passed for graph_agent.py")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
