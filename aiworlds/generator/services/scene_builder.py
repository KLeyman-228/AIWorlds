"""
Главный пайплайн: промпт → готовый JS-код.
"""
import logging
from .ai_client import generate_world_plan
from .validator import validate_plan
from .terrain import (
    generate_heightmap,
    generate_color_map,
    heightmap_to_base64,
    colormap_to_base64,
)
from .js_transpiler import transpile_to_js

log = logging.getLogger(__name__)


def build_world_js(user_prompt: str, model: str = None) -> dict:
    """
    Полный пайплайн: промпт → JS-код.
    Возвращает словарь с готовым кодом и метаданными.
    """
    log.info(f'🌍 Build world: {user_prompt!r}')

    kwargs = {'model': model} if model else {}
    raw_plan = generate_world_plan(user_prompt, **kwargs)
    plan = validate_plan(raw_plan)

    # Heightmap + colormap
    hm = generate_heightmap(
        size=128,
        scale=plan['terrain']['scale'],
        octaves=plan['terrain']['octaves'],
        seed=plan['terrain']['seed'],
    )
    cm = generate_color_map(hm, plan['terrain']['color_gradient'])

    hm_b64 = heightmap_to_base64(hm)
    cm_b64 = colormap_to_base64(cm)

    # Транспиляция в JS
    js_code = transpile_to_js(plan, hm_b64, cm_b64)

    return {
        'world_name': plan.get('world_name', 'Unnamed World'),
        'description': plan.get('description', ''),
        'js_code': js_code,
        'plan': plan,  # оставляем для дебага
    }