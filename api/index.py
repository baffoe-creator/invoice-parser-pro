import os
import sys
import traceback


current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
sys.path.insert(0, src_dir)

print(f"🔧 Current directory: {current_dir}")
print(f"🔧 Python path: {sys.path}")

try:
    print("🚀 Attempting to import main.py...")
    from main import app

    print("✅ Successfully imported main.py")

    handler = app

except Exception as e:
    print(f"❌ CRITICAL ERROR importing main.py: {e}")
    print("Full traceback:")
    traceback.print_exc()

    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/")
    async def emergency_root():
        return {
            "status": "error",
            "message": f"Main application failed to load: {str(e)}",
            "python_path": sys.path,
        }

    handler = app
