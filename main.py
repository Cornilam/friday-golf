"""Entry point for Friday Golf — runs the web dashboard + background scheduler."""

import logging
import os

import db
from app import app
from scheduler import create_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Initialize DB, start the background scheduler, and serve the Flask app."""
    db.init_db()
    logger.info("Database initialized")

    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Background scheduler started")

    for job in scheduler.get_jobs():
        logger.info(f"  Job '{job.id}' — next run: {job.next_run_time}")

    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting web dashboard on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
