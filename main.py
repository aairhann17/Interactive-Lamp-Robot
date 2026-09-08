"""
Interactive Lamp Robot - Entry Point

This script initializes and runs the complete lamp robot orchestrator,
connecting perception, dialogue, and expression systems.
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.coordinator import RobotOrchestrator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Interactive Lamp Robot orchestrator")
    parser.add_argument(
        "--strict-startup",
        action="store_true",
        help="Fail fast when deploy-time prerequisites such as API keys or a camera are missing.",
    )
    return parser.parse_args()


async def main(strict_startup: bool = False):
    """Main entry point for the lamp robot."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting Interactive Lamp Robot Orchestrator")

    # Initialize orchestrator
    orchestrator = RobotOrchestrator()
    orchestrator.validate_startup(strict=strict_startup)
    
    try:
        await orchestrator.run()
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
        await orchestrator.shutdown()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        await orchestrator.shutdown()
        raise


if __name__ == "__main__":
    arguments = parse_args()
    asyncio.run(main(strict_startup=arguments.strict_startup))
