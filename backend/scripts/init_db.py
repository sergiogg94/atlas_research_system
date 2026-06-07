import asyncio
import os
import sys

# Obtén la ruta absoluta del directorio backend
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(script_dir)
sys.path.insert(0, backend_dir)

from app.core.database import init_db, engine
from app.models import Task


async def main():
    print("🔧 Creating database tables...")
    await init_db()
    print("✅ Database initialized successfully!")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
