"""
Генерация карты высот: базовый Perlin + скульпт-фичи от AI
(реки, озёра, впадины, хребты, плато).
"""
from __future__ import annotations

import base64
import io
import logging
import time

import numpy as np
from PIL import Image
from perlin_noise import PerlinNoise
from scipy.ndimage import gaussian_filter

log = logging.getLogger(__name__)

TERRAIN_SIZE = 20.0
HEIGHT_SCALE = 4.0
FEATURE_TYPES = ("river", "lake", "basin", "ridge", "plateau", "mound")


def generate_heightmap(
    size=128,
    scale=45.0,
    octaves=4,
    seed=42,
    features=None,
) -> np.ndarray:
    """Нормализованная карта высот 0..1 после шума и фич AI."""
    octaves = max(1, min(10, int(octaves)))
    scale = max(1.0, float(scale))
    seed = int(seed)
    started = time.perf_counter()

    noise = PerlinNoise(octaves=octaves, seed=seed)
    hm = np.zeros((size, size), dtype=np.float64)
    for i in range(size):
        for j in range(size):
            hm[i, j] = (noise([i / scale, j / scale]) + 1) / 2

    hm = _normalize(hm)
    hm = apply_features(hm, features or [])

    step = 1.0 / 10
    hm = np.floor(hm / step) * step + step / 2
    hm = gaussian_filter(hm, sigma=0.45)
    hm = np.clip(hm, 0.0, 1.0)

    log.info(
        "Heightmap size=%s scale=%s octaves=%s features=%s time=%.2fs",
        size,
        scale,
        octaves,
        len(features or []),
        time.perf_counter() - started,
    )
    return hm


def apply_features(hm: np.ndarray, features: list) -> np.ndarray:
    size = hm.shape[0]
    yy, xx = np.mgrid[0:size, 0:size]
    uu = xx / max(size - 1, 1)
    vv = yy / max(size - 1, 1)

    for feat in features:
        if not isinstance(feat, dict):
            continue
        kind = str(feat.get("type") or "").lower()
        if kind not in FEATURE_TYPES:
            log.warning("Unknown terrain feature: %s", kind)
            continue
        try:
            if kind == "river":
                hm = _carve_river(hm, uu, vv, feat)
            elif kind == "lake":
                hm = _carve_radial(hm, uu, vv, feat, bowl=True)
            elif kind == "basin":
                hm = _carve_radial(hm, uu, vv, feat, bowl=True)
            elif kind == "mound":
                hm = _raise_radial(hm, uu, vv, feat)
            elif kind == "plateau":
                hm = _raise_plateau(hm, uu, vv, feat)
            elif kind == "ridge":
                hm = _raise_ridge(hm, uu, vv, feat)
        except Exception:
            log.exception("Failed terrain feature %s", kind)
    return _normalize(hm)


def sample_height_uv(hm: np.ndarray, u: float, v: float) -> float:
    size = hm.shape[0]
    x = np.clip(u, 0.0, 1.0) * (size - 1)
    y = np.clip(v, 0.0, 1.0) * (size - 1)
    x0, y0 = int(np.floor(x)), int(np.floor(y))
    x1, y1 = min(size - 1, x0 + 1), min(size - 1, y0 + 1)
    tx, ty = x - x0, y - y0
    a = hm[y0, x0] * (1 - tx) + hm[y0, x1] * tx
    b = hm[y1, x0] * (1 - tx) + hm[y1, x1] * tx
    return float(a * (1 - ty) + b * ty)


def world_to_uv(x: float, z: float, map_size: float = TERRAIN_SIZE) -> tuple[float, float]:
    return x / map_size + 0.5, z / map_size + 0.5


def generate_color_map(hm: np.ndarray, gradient: list) -> np.ndarray:
    size = hm.shape[0]
    color_map = np.zeros((size, size, 3), dtype=np.uint8)
    sorted_grad = sorted(gradient, key=lambda item: item["height"])
    heights = np.array([p["height"] for p in sorted_grad])
    colors = np.array([p["color"] for p in sorted_grad], dtype=np.float32)

    for i in range(size):
        for j in range(size):
            h = hm[i, j]
            idx = np.searchsorted(heights, h, side="right") - 1
            idx = max(0, min(len(heights) - 2, idx))
            h0, h1 = heights[idx], heights[idx + 1]
            c0, c1 = colors[idx], colors[idx + 1]
            t = 0.0 if h1 - h0 < 1e-6 else max(0.0, min(1.0, (h - h0) / (h1 - h0)))
            color_map[i, j] = (c0 * (1 - t) + c1 * t).astype(np.uint8)
    return color_map


def heightmap_to_js_array(hm: np.ndarray) -> str:
    return "[" + ",".join(f"{float(v):.4f}" for v in hm.flatten()) + "]"


def heightmap_to_base64(hm: np.ndarray) -> str:
    data = (np.clip(hm, 0, 1) * 255).astype(np.uint8)
    img = Image.fromarray(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def colormap_to_base64(cm: np.ndarray) -> str:
    img = Image.fromarray(cm, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _normalize(hm: np.ndarray) -> np.ndarray:
    return (hm - hm.min()) / (hm.max() - hm.min() + 1e-8)


def _seg_dist(uu, vv, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    length2 = dx * dx + dy * dy + 1e-8
    t = np.clip(((uu - x0) * dx + (vv - y0) * dy) / length2, 0.0, 1.0)
    px = x0 + t * dx
    py = y0 + t * dy
    return np.sqrt((uu - px) ** 2 + (vv - py) ** 2)


def _polyline_distance(uu, vv, points):
    dist = np.full(uu.shape, 1e9)
    for start, end in zip(points[:-1], points[1:]):
        dist = np.minimum(dist, _seg_dist(uu, vv, start[0], start[1], end[0], end[1]))
    return dist


def _points(feat, min_count=2):
    pts = feat.get("points") or []
    cleaned = []
    for pt in pts:
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            cleaned.append([float(np.clip(pt[0], 0, 1)), float(np.clip(pt[1], 0, 1))])
    if len(cleaned) < min_count:
        raise ValueError("not enough points")
    return cleaned


def _carve_river(hm, uu, vv, feat):
    points = _points(feat, 2)
    width = float(feat.get("width") or 0.045)
    depth = float(feat.get("depth") or 0.42)
    dist = _polyline_distance(uu, vv, points)
    influence = np.clip(1.0 - dist / max(width, 1e-4), 0.0, 1.0)
    influence = influence * influence
    return hm - influence * depth


def _carve_radial(hm, uu, vv, feat, bowl=True):
    cx, cy = _center(feat)
    radius = float(feat.get("radius") or 0.12)
    depth = float(feat.get("depth") or 0.4)
    dist = np.sqrt((uu - cx) ** 2 + (vv - cy) ** 2)
    influence = np.clip(1.0 - dist / max(radius, 1e-4), 0.0, 1.0)
    if bowl:
        influence = influence * influence
    return hm - influence * depth


def _raise_radial(hm, uu, vv, feat):
    cx, cy = _center(feat)
    radius = float(feat.get("radius") or 0.1)
    height = float(feat.get("height") or 0.28)
    dist = np.sqrt((uu - cx) ** 2 + (vv - cy) ** 2)
    influence = np.clip(1.0 - dist / max(radius, 1e-4), 0.0, 1.0)
    return hm + (influence * influence) * height


def _raise_plateau(hm, uu, vv, feat):
    cx, cy = _center(feat)
    radius = float(feat.get("radius") or 0.16)
    height = float(feat.get("height") or 0.35)
    falloff = float(feat.get("falloff") or 0.05)
    dist = np.sqrt((uu - cx) ** 2 + (vv - cy) ** 2)
    inner = max(radius - falloff, radius * 0.4)
    influence = 1.0 - np.clip((dist - inner) / max(radius - inner, 1e-4), 0.0, 1.0)
    return np.maximum(hm, hm * (1 - influence) + height * influence)


def _raise_ridge(hm, uu, vv, feat):
    points = _points(feat, 2)
    width = float(feat.get("width") or 0.07)
    height = float(feat.get("height") or 0.38)
    dist = _polyline_distance(uu, vv, points)
    influence = np.clip(1.0 - dist / max(width, 1e-4), 0.0, 1.0)
    return hm + (influence * influence) * height


def _center(feat):
    center = feat.get("center") or [0.5, 0.5]
    if not isinstance(center, (list, tuple)) or len(center) < 2:
        return 0.5, 0.5
    return float(np.clip(center[0], 0, 1)), float(np.clip(center[1], 0, 1))
