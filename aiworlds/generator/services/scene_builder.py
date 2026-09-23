"""
Пайплайн: промпт → метаданные AI → пропсы/материалы AI → террейн → JS.
"""
from __future__ import annotations

import logging
import time

from .ai_client import generate_props_parallel, generate_world_metadata
from .js_transpiler import transpile_to_js
from .terrain import (
    choose_water_level,
    colormap_to_base64,
    default_river,
    generate_color_map,
    generate_heightmap,
    heightmap_to_js_array,
    mix_seed,
)
from .templates import apply_palette_to_terrain, infer_palette, instantiate_terrain_shader
from .validator import validate_and_place_props, validate_plan

log = logging.getLogger(__name__)


def build_world_js(user_prompt: str, model: str | None = None, progress=None) -> dict:
    """
    Полный пайплайн генерации мира.

    progress — опциональный callable(status: str) для WebSocket.
    """
    started = time.perf_counter()
    log.info("Build world prompt_chars=%s model=%s", len(user_prompt or ""), model)

    def _status(name: str):
        log.info("Status: %s", name)
        if progress:
            progress(name)

    _status("ai_thinking")
    meta = generate_world_metadata(user_prompt, model=model)

    _status("props_generating")
    props = generate_props_parallel(user_prompt, meta, model=model)
    meta["props"] = props

    plan = validate_plan(meta)
    palette = infer_palette(user_prompt)
    terrain = plan.setdefault("terrain", {})
    terrain["material"] = apply_palette_to_terrain(terrain.get("material"), palette)
    if palette.get("terrain") and palette["terrain"].get("gradient"):
        terrain["color_gradient"] = list(palette["terrain"]["gradient"])
    custom_terrain = (terrain.get("shader") or {}).get("fragment")
    palette_shader = instantiate_terrain_shader(terrain.get("material"))
    if not custom_terrain:
        terrain["shader"] = palette_shader
    else:
        shader = dict(terrain.get("shader") or {})
        uniforms = dict(shader.get("uniforms") or {})
        uniforms.update(palette_shader.get("uniforms") or {})
        shader["uniforms"] = uniforms
        terrain["shader"] = shader

    _status("terrain_generating")
    seed = mix_seed(user_prompt, plan["terrain"].get("seed"))
    plan["terrain"]["seed"] = seed
    prompt_l = (user_prompt or "").lower()
    style = plan["terrain"].get("style") or _infer_style(prompt_l)
    plan["terrain"]["style"] = style
    features = plan["terrain"].setdefault("features", [])
    wants_water = any(
        word in prompt_l
        for word in ("река", "реку", "озеро", "пруд", "вода", "вод", "river", "lake", "pond", "stream")
    )
    has_water_feat = any(f.get("type") in ("river", "lake", "basin") for f in features)
    if wants_water and not has_water_feat:
        features.append(default_river(seed))
    features.extend(_fallback_landforms(prompt_l, features, seed))
    heightmap = generate_heightmap(
        size=128,
        scale=plan["terrain"]["scale"],
        octaves=plan["terrain"]["octaves"],
        seed=seed,
        features=features,
        style=style,
        amplitude=plan["terrain"].get("amplitude", 1.0),
    )
    plan["terrain"]["water_level"] = choose_water_level(heightmap, features)
    plan["props"] = validate_and_place_props(
        plan.get("props") or meta.get("props"),
        seed=plan["terrain"]["seed"],
        heightmap=heightmap,
        features=features,
        water_level=plan["terrain"]["water_level"],
    )

    _status("coloring")
    colormap = generate_color_map(heightmap, plan["terrain"]["color_gradient"])
    cm_b64 = colormap_to_base64(colormap)
    hm_js = heightmap_to_js_array(heightmap)
    js_code = transpile_to_js(plan, colormap_b64=cm_b64, heightmap_js=hm_js)
    elapsed = time.perf_counter() - started
    log.info(
        "World ready name=%s props=%s js_chars=%s time=%.2fs",
        plan.get("world_name"),
        len(plan.get("props") or {}),
        len(js_code),
        elapsed,
    )

    return {
        "world_name": plan.get("world_name", "Unnamed World"),
        "description": plan.get("description", ""),
        "js_code": js_code,
        "plan": plan,
    }


def _infer_style(prompt: str) -> str:
    if any(w in prompt for w in ("остров", "island", "архипелаг")):
        return "island"
    if any(w in prompt for w in ("дюн", "пустын", "dune", "desert", "саванн")):
        return "dunes"
    if any(w in prompt for w in ("каньон", "ущел", "canyon", "gorge")):
        return "canyon"
    if any(w in prompt for w in ("долин", "valley")):
        return "valley"
    if any(w in prompt for w in ("кратер", "crater", "вулкан", "volcano")):
        return "crater"
    if any(w in prompt for w in ("горн", "горы", "альп", "пик", "хребет", "mountain", "peak", "ridge")):
        return "mountains"
    if any(w in prompt for w in ("равнин", "луг", "поле", "степь", "plains", "meadow", "field", "flat")):
        return "plains"
    if any(w in prompt for w in ("холм", "hill")):
        return "hills"
    return "hills"


def _prompt_uv(prompt: str) -> list[float]:
    u, v = 0.5, 0.5
    if any(w in prompt for w in ("слева", "левый", "запад", "left", "west")):
        u = 0.2
    if any(w in prompt for w in ("справа", "правый", "восток", "right", "east")):
        u = 0.8
    if any(w in prompt for w in ("север", "сверху", "north")):
        v = 0.82
    if any(w in prompt for w in ("юг", "снизу", "south")):
        v = 0.18
    if any(w in prompt for w in ("центр", "середин", "посреди", "center", "middle")):
        u, v = 0.5, 0.5
    if "юго-запад" in prompt or "southwest" in prompt:
        u, v = 0.18, 0.18
    if "юго-восток" in prompt or "southeast" in prompt:
        u, v = 0.82, 0.18
    if "северо-запад" in prompt or "northwest" in prompt:
        u, v = 0.18, 0.82
    if "северо-восток" in prompt or "northeast" in prompt:
        u, v = 0.82, 0.82
    return [u, v]


def _has_type(features: list, kinds: tuple[str, ...]) -> bool:
    return any(f.get("type") in kinds for f in features)


def _fallback_landforms(prompt: str, features: list, seed: int) -> list:
    extra = []
    uv = _prompt_uv(prompt)
    if any(w in prompt for w in ("хребет", "ridge")) and not _has_type(features, ("ridge",)):
        extra.append({
            "type": "ridge",
            "points": [[uv[0], 0.08], [uv[0] + 0.04, 0.5], [uv[0] - 0.02, 0.92]],
            "width": 0.08,
            "height": 0.62,
        })
    elif any(w in prompt for w in ("гора", "гору", "горы", "пик", "mountain", "peak")) and not _has_type(features, ("mountain", "ridge")):
        extra.append({"type": "mountain", "center": uv, "radius": 0.24, "height": 0.95})
    elif any(w in prompt for w in ("холм", "hill")) and not _has_type(features, ("mound", "mountain")):
        extra.append({"type": "mound", "center": uv, "radius": 0.18, "height": 0.42})
    if any(w in prompt for w in ("каньон", "ущел", "canyon")) and not _has_type(features, ("canyon", "valley")):
        extra.append({
            "type": "canyon",
            "points": [[0.08, uv[1]], [0.5, uv[1] + 0.04], [0.92, uv[1] - 0.03]],
            "width": 0.12,
            "depth": 0.62,
        })
    if any(w in prompt for w in ("долин", "valley")) and not _has_type(features, ("valley", "canyon")):
        extra.append({
            "type": "valley",
            "points": [[uv[0], 0.06], [uv[0] + 0.03, 0.5], [uv[0] - 0.02, 0.94]],
            "width": 0.16,
            "depth": 0.42,
        })
    if any(w in prompt for w in ("кратер", "crater")) and not _has_type(features, ("crater",)):
        extra.append({"type": "crater", "center": uv, "radius": 0.18, "depth": 0.5, "height": 0.3})
    if any(w in prompt for w in ("плато", "plateau")) and not _has_type(features, ("plateau",)):
        extra.append({"type": "plateau", "center": uv, "radius": 0.22, "height": 0.48})
    return extra

