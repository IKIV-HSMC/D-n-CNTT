import asyncio
import logging

from app.services.run_worker import run_worker_forever

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


if __name__ == "__main__":
    asyncio.run(run_worker_forever())
