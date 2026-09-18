"""
WebSocket для стриминга статусов генерации.
"""
import asyncio
import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .services.scene_builder import build_world_js

log = logging.getLogger(__name__)


class WorldConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        log.info("WS connected")

    async def disconnect(self, close_code):
        log.info("WS disconnected code=%s", close_code)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_json({"status": "error", "message": "Invalid JSON"})
            return

        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            await self.send_json({"status": "error", "message": "Empty prompt"})
            return

        model = data.get("model")
        loop = asyncio.get_running_loop()

        def progress(status: str):
            asyncio.run_coroutine_threadsafe(
                self.send_json({"status": status}),
                loop,
            )

        try:
            result = await database_sync_to_async(build_world_js)(
                prompt,
                model=model,
                progress=progress,
            )
            await self.send_json(
                {
                    "status": "complete",
                    "world_name": result["world_name"],
                    "description": result["description"],
                    "js_code": result["js_code"],
                }
            )
        except Exception as e:
            log.exception("WS generation failed")
            await self.send_json({"status": "error", "message": str(e)})

    async def send_json(self, payload):
        await self.send(text_data=json.dumps(payload, ensure_ascii=False))
