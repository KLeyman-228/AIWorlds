"""
Главный пайплайн: промпт → готовый пакет мира.
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

log = logging.getLogger(__name__)


def build_world(user_prompt: str) -> dict:
    """
    Полный пайплайн генерации мира.
    Возвращает готовый пакет для отправки на клиент.
    """
    log.info(f"🌍 Генерация мира по промпту: {user_prompt!r}")

    # 1. AI-план
    raw_plan = generate_world_plan(user_prompt)
    plan = validate_plan(raw_plan)
    log.info(f"✅ План валиден: {plan.get('world_name')}")

    # 2. Heightmap
    hm = generate_heightmap(
        size=128,
        scale=plan["terrain"]["scale"],
        octaves=plan["terrain"]["octaves"],
        seed=plan["terrain"]["seed"],
    )
    log.info(f"✅ Heightmap готов: shape={hm.shape}")

    # 3. Colormap из градиента
    cm = generate_color_map(hm, plan["terrain"]["color_gradient"])
    log.info(f"✅ Colormap готов")

    # 4. Кодируем в base64
    hm_b64 = heightmap_to_base64(hm)
    cm_b64 = colormap_to_base64(cm)

    return {
        "plan": plan,
        "heightmap": hm_b64,
        "colormap": cm_b64,
    }