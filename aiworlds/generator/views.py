"""
HTTP API views. Возвращают только JSON.
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .services.scene_builder import build_world

log = logging.getLogger(__name__)


def _json_response(data, status=200):
    """Единая точка для JSON-ответов."""
    return JsonResponse(data, status=status, json_dumps_params={'ensure_ascii': False})


def _error(message, status=400):
    return _json_response({'ok': False, 'error': message}, status=status)


@require_http_methods(['GET'])
def health(request):
    """Проверка что сервер работает."""
    return _json_response({
        'ok': True,
        'service': 'ai-worlds-api',
        'version': '1.0',
    })


@csrf_exempt
@require_http_methods(['POST'])
def generate_world(request):
    """
    POST /api/worlds/generate/
    
    Body: {"prompt": "Создай фэнтези-лес"}
    
    Response:
    {
      "ok": true,
      "plan": {...},
      "heightmap": "base64...",
      "colormap": "base64..."
    }
    """
    # 1. Парсим тело запроса
    try:
        body = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _error('Invalid JSON body', status=400)

    prompt = body.get('prompt', '').strip()
    if not prompt:
        return _error('Field "prompt" is required', status=400)
    if len(prompt) > 1000:
        return _error('Prompt too long (max 1000 chars)', status=400)

    # 2. Генерируем мир
    try:
        log.info(f'🌍 Generate request: {prompt!r}')
        world = build_world(prompt)
        return _json_response({'ok': True, **world})
    except Exception as e:
        log.exception('Generation failed')
        return _error(f'Generation failed: {e}', status=500)


@require_http_methods(['GET'])
def list_models(request):
    """Список доступных AI-моделей."""
    return _json_response({
        'ok': True,
        'models': [
            {'id': 'claude-haiku-4-5', 'label': 'Claude Haiku 4.5', 'multiplier': 0.9},
            {'id': 'claude-sonnet-4-6', 'label': 'Claude Sonnet 4.6', 'multiplier': 2},
            {'id': 'claude-opus-4-8', 'label': 'Claude Opus 4.8', 'multiplier': 4},
        ],
        'default': 'claude-sonnet-4-6',
    })