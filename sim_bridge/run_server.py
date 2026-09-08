"""Start the browser bridge by itself.

Use this when the simulator should connect to a separate Python bridge process.
"""

import asyncio
import logging

from sim_bridge.websocket_server import SimulatorBridge


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main() -> None:
    bridge = SimulatorBridge()
    await bridge.start()
    print(f"Simulator bridge listening on ws://{bridge.host}:{bridge.port}")

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        raise
    except KeyboardInterrupt:
        pass
    finally:
        await bridge.stop()


if __name__ == "__main__":
    asyncio.run(main())
