import asyncio
import logging

from app.worker.runner import run_loop

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    asyncio.run(run_loop())
