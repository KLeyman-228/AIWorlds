"""
Пайплайн: промпт → метаданные AI → пропсы/материалы AI → террейн → JS.
"""
from __future__ import annotations

import logging
import time

import numpy as np

from .ai_client import generate_props_parallel, generate_world_metadata
from .js_transpiler import transpile_to_js
from .terrain import (
    choose_water_level,
    colormap_to_base64,
    generate_color_map,
    generate_heightmap,
    heightmap_to_js_array,
)
from .templates import instantiate_terrain_shader
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
    custom_terrain = ((plan.get("terrain") or {}).get("shader") or {}).get("fragment")
    if not custom_terrain:
        plan["terrain"]["shader"] = instantiate_terrain_shader(
            (plan.get("terrain") or {}).get("material")
        )

    _status("terrain_generating")
    heightmap = generate_heightmap(
        size=128,
        scale=plan["terrain"]["scale"],
        octaves=plan["terrain"]["octaves"],
        seed=plan["terrain"]["seed"],
        features=plan["terrain"].get("features") or [],
    )
    features = plan["terrain"].setdefault("features", [])
    if not any(f.get("type") in ("river", "lake", "basin") for f in features):
        features.append({
            "type": "river",
            "points": [[0.02, 0.38], [0.28, 0.46], [0.55, 0.52], [0.98, 0.62]],
            "width": 0.055,
            "depth": 0.42,
        })
        heightmap = generate_heightmap(
            size=128,
            scale=plan["terrain"]["scale"],
            octaves=plan["terrain"]["octaves"],
            seed=plan["terrain"]["seed"],
            features=features,
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
