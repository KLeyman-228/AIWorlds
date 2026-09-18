"""
Раскладка инстансов по правилу distribution.
AI задаёт count и тип распределения, координаты считает код.
"""
from __future__ import annotations

import logging

import numpy as np

from .terrain import HEIGHT_SCALE, TERRAIN_SIZE, sample_height_uv, world_to_uv

log = logging.getLogger(__name__)

MAP_SIZE = TERRAIN_SIZE
VALID_DISTRIBUTIONS = ("scattered", "forest", "cluster", "river_line")


def place_instances(rule: dict, seed: int = 42, heightmap=None) -> list[dict]:
    """Превращает правило инстансов в список {position, rotation, scale}."""
    if not isinstance(rule, dict):
        raise ValueError("instances должен быть объектом-правилом")

    count = int(rule.get("count") or 0)
    if count < 1:
        raise ValueError("instances.count должен быть >= 1")
    count = min(count, 80)

    distribution = str(rule.get("distribution") or "scattered").lower()
    if distribution not in VALID_DISTRIBUTIONS:
        log.warning("Unknown distribution %s, using scattered", distribution)
        distribution = "scattered"

    scale_range = rule.get("scale_range") or [0.8, 1.2]
    if not isinstance(scale_range, (list, tuple)) or len(scale_range) < 2:
        scale_range = [0.8, 1.2]
    lo, hi = float(scale_range[0]), float(scale_range[1])
    if hi < lo:
        lo, hi = hi, lo

    rng = np.random.default_rng(int(seed) + count * 17)
    xs, zs = _sample_xz(rng, count, distribution)

    instances = []
    for x, z in zip(xs, zs):
        yaw = float(rng.uniform(0, 360))
        scale = float(rng.uniform(lo, hi))
        y = 0.0
        if heightmap is not None:
            u, v = world_to_uv(float(x), float(z))
            y = sample_height_uv(heightmap, u, v) * HEIGHT_SCALE
        instances.append(
            {
                "position": [float(x), float(y), float(z)],
                "rotation": [0.0, yaw, 0.0],
                "scale": scale,
            }
        )
    log.info("Instances placed dist=%s count=%s", distribution, len(instances))
    return instances


def _sample_xz(rng: np.random.Generator, count: int, distribution: str):
    half = MAP_SIZE * 0.45
    if distribution == "forest":
        clusters = max(2, min(5, count // 6 or 2))
        centers = rng.uniform(-half * 0.7, half * 0.7, size=(clusters, 2))
        xs, zs = [], []
        for i in range(count):
            cx, cz = centers[i % clusters]
            xs.append(np.clip(cx + rng.normal(0, 1.6), -half, half))
            zs.append(np.clip(cz + rng.normal(0, 1.6), -half, half))
        return xs, zs

    if distribution == "cluster":
        cx, cz = rng.uniform(-half * 0.5, half * 0.5, size=2)
        xs = np.clip(cx + rng.normal(0, 1.1, size=count), -half, half)
        zs = np.clip(cz + rng.normal(0, 1.1, size=count), -half, half)
        return xs, zs

    if distribution == "river_line":
        t = np.linspace(-half, half, count)
        meander = np.sin(t * 0.35) * 3.0 + rng.normal(0, 0.35, size=count)
        if rng.random() < 0.5:
            return t, np.clip(meander, -half, half)
        return np.clip(meander, -half, half), t

    xs = rng.uniform(-half, half, size=count)
    zs = rng.uniform(-half, half, size=count)
    return xs, zs
