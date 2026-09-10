"""
HTTP API. Возвращает готовый JS-код.
"""
import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .services.scene_builder import build_world_js

log = logging.getLogger(__name__)


def _json_response(data, status=200):
    return JsonResponse(data, status=status, json_dumps_params={'ensure_ascii': False})


def _error(message, status=400):
    return _json_response({'ok': False, 'error': message}, status=status)


@require_http_methods(['GET'])
def health(request):
    return _json_response({'ok': True, 'service': 'ai-worlds-api', 'version': '2.0'})


@csrf_exempt
@require_http_methods(['POST'])
def generate_world(request):
    """
    POST /api/worlds/generate/
    Body: {"prompt": "...", "model": "..." (optional)}
    
    Response:
    {
      "ok": true,
      "world_name": "...",
      "description": "...",
      "js_code": "import * as THREE ...",  // готовый JS-файл
      "plan": {...}                         // для дебага
    }
    """
    try:
        body = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _error('Invalid JSON body')

    prompt = (body.get('prompt') or '').strip()
    if not prompt:
        return _error('Field "prompt" is required')
    if len(prompt) > 1000:
        return _error('Prompt too long (max 1000 chars)')

    model = body.get('model')  # optional

    try:
        result = build_world_js(prompt, model=model)
        return _json_response({'ok': True, **result})
    except Exception as e:
        log.exception('Generation failed')
        return _error(f'Generation failed: {e}', status=500)


@csrf_exempt
@require_http_methods(['POST'])
def generate_world_file(request):
    """
    POST /api/worlds/generate/file/
    Возвращает .js файл напрямую (для скачивания).
    """
    try:
        body = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponse('Invalid JSON', status=400)

    prompt = (body.get('prompt') or '').strip()
    if not prompt:
        return HttpResponse('Missing prompt', status=400)

    try:
        result = build_world_js(prompt)
        response = HttpResponse(result['js_code'], content_type='application/javascript')
        response['Content-Disposition'] = f'attachment; filename="world.js"'
        return response
    except Exception as e:
        log.exception('Generation failed')
        return HttpResponse(f'Error: {e}', status=500)