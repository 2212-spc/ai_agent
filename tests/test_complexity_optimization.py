import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../backend"))

from app.config import Settings
from app.graph_agent import analyze_query_complexity

async def main():
    # Set env vars manually to avoid encoding issues
    os.environ["DEEPSEEK_API_KEY"] = "sk-cbc4485ddce1470b82d7814cece07952"
    os.environ["DEEPSEEK_BASE_URL"] = "https://api.deepseek.com"
    
    settings = Settings()
    
    queries = [
        "你是谁",
        "今天天气怎么样",
        "帮我搜索一下 DeepSeek 的最新新闻",
        "你好"
    ]
    
    print("=== Testing analyze_query_complexity ===")
    for query in queries:
        print(f"\nQuery: {query}")
        result = await analyze_query_complexity(query, settings)
        print(f"Result: {result}")
        
        if result["complexity"] == "simple" and result["answer"]:
            print("✅ Optimized flow triggered (Simple + Answer)")
        elif result["complexity"] == "complex" and not result["answer"]:
            print("✅ Standard flow triggered (Complex)")
        elif result["complexity"] == "complex" and result["answer"] is None:
             print("✅ Standard flow triggered (Complex - correctly returned None)")
        else:
            print("⚠️ Unexpected result format")

if __name__ == "__main__":
    asyncio.run(main())
