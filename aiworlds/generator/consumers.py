"""
WebSocket для стриминга статусов генерации.
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .services.scene_builder import build_world_js

log = logging.getLogger(__name__)


class WorldConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        log.info('🔌 WS connected')

    async def disconnect(self, close_code):
        log.info('🔌 WS disconnected')

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_json({'status': 'error', 'message': 'Invalid JSON'})
            return

        prompt = (data.get('prompt') or '').strip()
        if not prompt:
            await self.send_json({'status': 'error', 'message': 'Empty prompt'})
            return

        try:
            await self.send_json({'status': 'ai_thinking'})

            result = await database_sync_to_async(build_world_js)(prompt)

            await self.send_json({
                'status': 'complete',
                'world_name': result['world_name'],
                'description': result['description'],
                'js_code': result['js_code'],
            })

        except Exception as e:
            log.exception('WS generation failed')
            await self.send_json({'status': 'error', 'message': str(e)})

    async def send_json(self, payload):
        await self.send(text_data=json.dumps(payload, ensure_ascii=False))