import asyncio
import json
import queue
import threading

from channels.generic.websocket import AsyncWebsocketConsumer

from agentcore.evidence import EvidenceLedger
from agentcore.report import ReportCollector

from committee_web.run import DONE_SENTINEL, run_committee, serialize_event


class RunConsumer(AsyncWebsocketConsumer):
    """Streams a committee run over a WebSocket. The (synchronous) engine runs on
    a daemon thread that pushes Events onto a queue; this consumer drains the queue
    in the event loop and forwards each Event as JSON, then closes on the sentinel."""

    async def connect(self):
        await self.accept()
        kwargs = self.scope["url_route"]["kwargs"]
        q = queue.Queue()
        collector = ReportCollector()
        ledger = EvidenceLedger()
        threading.Thread(
            target=run_committee,
            args=(kwargs["stock_no"], kwargs["market"], q, collector, ledger),
            daemon=True,
        ).start()
        self._drain_task = asyncio.create_task(self._drain(q))

    async def _drain(self, q):
        try:
            while True:
                try:
                    item = q.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.05)
                    continue
                if item is DONE_SENTINEL:
                    break
                await self.send(text_data=json.dumps(serialize_event(item)))
        finally:
            await self.close()

    async def disconnect(self, code):
        task = getattr(self, "_drain_task", None)
        if task is not None:
            task.cancel()
