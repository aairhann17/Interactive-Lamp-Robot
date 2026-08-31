"""
Interactive Lamp Robot - Entry Point

This script initializes and runs the complete lamp robot orchestrator,
connecting perception, dialogue, and expression systems.
"""

import asyncio
import logging
from pathlib import Path

from orchestrator.coordinator import RobotOrchestrator


async def main():
    """Main entry point for the lamp robot."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting Interactive Lamp Robot Orchestrator")

    # Initialize orchestrator
    orchestrator = RobotOrchestrator()
    
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
    asyncio.run(main())
