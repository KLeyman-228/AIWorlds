"""
Генерация карты высот: базовый Perlin + скульпт-фичи от AI
(реки, озёра, впадины, хребты, плато).
"""
from __future__ import annotations

import base64
import hashlib
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
FEATURE_TYPES = (
    "river", "lake", "basin", "ridge", "plateau", "mound", "mountain",
    "canyon", "valley", "crater",
)
TERRAIN_STYLES = (
    "plains", "hills", "mountains", "canyon", "valley", "island", "dunes", "crater",
)


def mix_seed(prompt: str, ai_seed) -> int:
    """Разные промпты не должны давать один и тот же рельеф, даже если AI шлёт seed=42."""
    try:
        base = int(ai_seed)
    except (TypeError, ValueError):
        base = 0
    digest = hashlib.md5((prompt or "").encode("utf-8")).hexdigest()
    prompt_part = int(digest[:8], 16)
    return abs(base * 10007 + prompt_part) % 1000003


def default_river(seed: int) -> dict:
    rng = np.random.default_rng(int(seed) + 91)
    axis = rng.uniform(0.28, 0.72)
    bend = rng.uniform(0.08, 0.22) * (1.0 if rng.random() < 0.5 else -1.0)
    if rng.random() < 0.5:
        pts = [
            [0.02, float(np.clip(axis - bend, 0.08, 0.92))],
            [0.32, float(np.clip(axis + bend * 0.4, 0.08, 0.92))],
            [0.62, float(np.clip(axis + bend, 0.08, 0.92))],
            [0.98, float(np.clip(axis - bend * 0.3, 0.08, 0.92))],
        ]
    else:
        pts = [
            [float(np.clip(axis - bend, 0.08, 0.92)), 0.02],
            [float(np.clip(axis + bend * 0.4, 0.08, 0.92)), 0.35],
            [float(np.clip(axis + bend, 0.08, 0.92)), 0.68],
            [float(np.clip(axis - bend * 0.3, 0.08, 0.92)), 0.98],
        ]
    return {
        "type": "river",
        "points": pts,
        "width": float(rng.uniform(0.04, 0.07)),
        "depth": float(rng.uniform(0.32, 0.5)),
    }


def generate_heightmap(
    size=128,
    scale=45.0,
    octaves=4,
    seed=42,
    features=None,
    style="hills",
    amplitude=1.0,
) -> np.ndarray:
    """Карта высот 0..1: стиль базы + скульпт-фичи AI. Без растяжки 0-1."""
    octaves = max(1, min(8, int(octaves)))
    seed = int(seed)
    scale = max(8.0, min(120.0, float(scale)))
    style = str(style or "hills").lower()
    if style not in TERRAIN_STYLES:
        style = "hills"
    amp = max(0.35, min(1.8, float(amplitude or 1.0)))
    started = time.perf_counter()

    hm = _sculpted_base(size, seed, octaves, scale, style, amp)
    hm = gaussian_filter(hm, sigma=0.7)
    hm = apply_features(hm, features or [])
    hm = gaussian_filter(hm, sigma=0.4)
    hm = np.clip(hm, 0.0, 1.0)

    log.info(
        "Heightmap size=%s scale=%s octaves=%s seed=%s style=%s amp=%s features=%s time=%.2fs",
        size,
        scale,
        octaves,
        seed,
        style,
        amp,
        [(f.get("type"), f.get("center") or f.get("points")) for f in (features or []) if isinstance(f, dict)],
        time.perf_counter() - started,
    )
    return hm


def _sculpted_base(
    size: int,
    seed: int,
    octaves: int,
    scale: float = 45.0,
    style: str = "hills",
    amplitude: float = 1.0,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    continent = PerlinNoise(octaves=1, seed=seed)
    hills = PerlinNoise(octaves=1, seed=seed + 11)
    detail = PerlinNoise(octaves=1, seed=seed + 23)
    warp_x = PerlinNoise(octaves=1, seed=seed + 41)
    warp_y = PerlinNoise(octaves=1, seed=seed + 57)
    ridge_n = PerlinNoise(octaves=1, seed=seed + 73)

    freq = 48.0 / max(scale, 8.0)
    ou, ov = float(rng.uniform(0, 11)), float(rng.uniform(0, 11))
    tilt_u = float(rng.uniform(-0.18, 0.18))
    tilt_v = float(rng.uniform(-0.18, 0.18))
    inv = 1.0 / max(size - 1, 1)
    hm = np.zeros((size, size), dtype=np.float64)
    for i in range(size):
        v = i * inv
        for j in range(size):
            u = j * inv
            wx = warp_x([u * 1.7 * freq + ou, v * 1.7 * freq]) * 0.16
            wy = warp_y([u * 1.7 * freq, v * 1.7 * freq + ov]) * 0.16
            pu, pv = u + wx + ou * 0.015, v + wy + ov * 0.015
            land = continent([pu * 1.1 * freq, pv * 1.1 * freq])
            hill = hills([pu * 3.1 * freq, pv * 3.1 * freq])
            fine = detail([pu * 8.2 * freq, pv * 8.2 * freq])
            ridge = 1.0 - abs(ridge_n([pu * 2.4 * freq, pv * 2.4 * freq]))
            dx, dy = u - 0.5, v - 0.5
            radial = np.sqrt(dx * dx + dy * dy)
            h = 0.62 * land + 0.28 * hill + 0.1 * fine
            if style == "plains":
                h = 0.22 + 0.12 * land + 0.04 * fine
            elif style == "hills":
                h = 0.28 + 0.22 * land + 0.16 * hill + 0.05 * fine
            elif style == "mountains":
                h = 0.22 + 0.18 * land + 0.22 * hill + 0.38 * (ridge ** 2)
            elif style == "canyon":
                groove = np.exp(-((v - (0.42 + 0.12 * land)) ** 2) / 0.018)
                h = 0.55 + 0.2 * hill - 0.48 * groove
            elif style == "valley":
                groove = np.exp(-((v - 0.5) ** 2) / 0.04)
                h = 0.22 + 0.38 * (1.0 - groove) + 0.1 * hill
            elif style == "island":
                fall = np.clip(1.0 - radial / 0.48, 0.0, 1.0) ** 1.4
                h = 0.06 + fall * (0.38 + 0.18 * land + 0.1 * hill)
            elif style == "dunes":
                wave = np.sin((u * 9.0 + land * 1.8) * 3.1416)
                h = 0.26 + 0.16 * abs(wave) + 0.08 * hill
            elif style == "crater":
                bowl = np.clip(1.0 - abs(radial - 0.22) / 0.16, 0.0, 1.0)
                h = 0.34 + 0.08 * land + 0.32 * bowl - 0.28 * np.clip(1.0 - radial / 0.16, 0.0, 1.0)
            h += tilt_u * (u - 0.5) + tilt_v * (v - 0.5)
            edge = min(u, v, 1.0 - u, 1.0 - v)
            if style != "island":
                h *= 0.9 + 0.1 * np.clip(edge / 0.08, 0.0, 1.0)
            hm[i, j] = h
    n = _normalize(hm)
    spans = {
        "plains": 0.20,
        "hills": 0.36,
        "mountains": 0.58,
        "canyon": 0.50,
        "valley": 0.46,
        "island": 0.52,
        "dunes": 0.32,
        "crater": 0.44,
    }
    span = spans.get(style, 0.36) * amplitude
    base = 0.05 if style == "island" else 0.14
    return np.clip(n * span + base, 0.0, 1.0)


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
            if kind in ("river", "canyon", "valley"):
                hm = _carve_river(hm, uu, vv, feat, wide=(kind != "river"))
            elif kind in ("lake", "basin"):
                hm = _carve_radial(hm, uu, vv, feat, bowl=True)
            elif kind == "crater":
                hm = _carve_crater(hm, uu, vv, feat)
            elif kind in ("mound", "mountain"):
                hm = _raise_radial(hm, uu, vv, feat, peaked=(kind == "mountain"))
            elif kind == "plateau":
                hm = _raise_plateau(hm, uu, vv, feat)
            elif kind == "ridge":
                hm = _raise_ridge(hm, uu, vv, feat)
        except Exception:
            log.exception("Failed terrain feature %s", kind)
    return hm


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


def river_clearance_uv(u: float, v: float, features: list | None) -> float:
    """Минимальная UV-дистанция до реки/озера, нормированная на ширину. None — воды нет."""
    best = None
    for feat in features or []:
        if not isinstance(feat, dict):
            continue
        kind = str(feat.get("type") or "").lower()
        if kind == "river":
            pts = feat.get("points") or []
            if len(pts) < 2:
                continue
            width = float(feat.get("width") or 0.05)
            dist = 1e9
            for start, end in zip(pts[:-1], pts[1:]):
                dist = min(dist, float(_seg_dist_point(u, v, start[0], start[1], end[0], end[1])))
            best = dist / max(width, 1e-4) if best is None else min(best, dist / max(width, 1e-4))
        elif kind in ("lake", "basin"):
            cx, cy = _center(feat)
            radius = float(feat.get("radius") or 0.12)
            dist = ((u - cx) ** 2 + (v - cy) ** 2) ** 0.5
            best = dist / max(radius, 1e-4) if best is None else min(best, dist / max(radius, 1e-4))
    return best


def _seg_dist_point(u, v, x0, y0, x1, y1) -> float:
    dx, dy = x1 - x0, y1 - y0
    length2 = dx * dx + dy * dy + 1e-8
    t = max(0.0, min(1.0, ((u - x0) * dx + (v - y0) * dy) / length2))
    px, py = x0 + t * dx, y0 + t * dy
    return ((u - px) ** 2 + (v - py) ** 2) ** 0.5


def choose_water_level(hm: np.ndarray, features: list | None) -> float:
    """Уровень воды чуть выше дна русла, не заливает берег."""
    wet = _wet_mask(hm, features or [])
    if wet.any():
        bed = hm[wet]
        shore = hm[~wet]
        level = float(np.percentile(bed, 62))
        if shore.size:
            level = min(level, float(np.percentile(shore, 12) - 0.01))
        return float(np.clip(level, 0.05, 0.28))
    return float(np.clip(np.percentile(hm, 6), 0.04, 0.14))


def _wet_mask(hm: np.ndarray, features: list):
    size = hm.shape[0]
    yy, xx = np.mgrid[0:size, 0:size]
    uu = xx / max(size - 1, 1)
    vv = yy / max(size - 1, 1)
    mask = np.zeros(hm.shape, dtype=bool)
    for feat in features:
        if not isinstance(feat, dict):
            continue
        kind = str(feat.get("type") or "").lower()
        if kind == "river":
            try:
                points = _points(feat, 2)
            except ValueError:
                continue
            width = float(feat.get("width") or 0.05) * 1.15
            dist = _polyline_distance(uu, vv, points)
            mask |= dist <= width
        elif kind in ("lake", "basin"):
            cx, cy = _center(feat)
            radius = float(feat.get("radius") or 0.12)
            dist = np.sqrt((uu - cx) ** 2 + (vv - cy) ** 2)
            mask |= dist <= radius
    if not mask.any():
        mask = hm <= np.percentile(hm, 6)
    return mask


def gradient_strip_to_base64(gradient: list, width: int = 256) -> str:
    """1D-палитра по высоте: вода → песок → трава → камень."""
    strip = np.zeros((1, width, 3), dtype=np.uint8)
    dummy = np.linspace(0.0, 1.0, width).reshape(1, width)
    strip[0] = generate_color_map(dummy, gradient)[0]
    img = Image.fromarray(strip, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


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
            color_map[i, j] = np.clip(c0 * 1.08, 0, 255).astype(np.uint8)
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


def _carve_river(hm, uu, vv, feat, wide=False):
    points = _points(feat, 2)
    width = float(feat.get("width") or (0.1 if wide else 0.045))
    depth = float(feat.get("depth") or (0.55 if wide else 0.42))
    dist = _polyline_distance(uu, vv, points)
    influence = _smooth_falloff(dist, max(width, 1e-4))
    if wide:
        influence = np.sqrt(np.clip(influence, 0.0, 1.0))
    return hm - influence * depth


def _carve_radial(hm, uu, vv, feat, bowl=True):
    cx, cy = _center(feat)
    radius = float(feat.get("radius") or 0.12)
    depth = float(feat.get("depth") or 0.4)
    dist = np.sqrt((uu - cx) ** 2 + (vv - cy) ** 2)
    influence = _smooth_falloff(dist, max(radius, 1e-4))
    if bowl:
        influence = np.sqrt(np.clip(influence, 0.0, 1.0))
    return hm - influence * depth


def _raise_radial(hm, uu, vv, feat, peaked=False):
    cx, cy = _center(feat)
    radius = float(feat.get("radius") or (0.18 if peaked else 0.12))
    height = float(feat.get("height") or (0.72 if peaked else 0.38))
    aspect = max(0.4, min(2.5, float(feat.get("aspect") or 1.0)))
    rot = np.deg2rad(float(feat.get("rot") or 0.0))
    du, dv = uu - cx, vv - cy
    ru = du * np.cos(rot) + dv * np.sin(rot)
    rv = -du * np.sin(rot) + dv * np.cos(rot)
    dist = np.sqrt((ru * aspect) ** 2 + (rv / aspect) ** 2)
    influence = _smooth_falloff(dist, max(radius, 1e-4))
    if peaked:
        influence = np.power(np.clip(influence, 0.0, 1.0), 1.65)
    return hm + influence * height


def _carve_crater(hm, uu, vv, feat):
    cx, cy = _center(feat)
    radius = float(feat.get("radius") or 0.16)
    depth = float(feat.get("depth") or 0.45)
    rim = float(feat.get("height") or 0.28)
    dist = np.sqrt((uu - cx) ** 2 + (vv - cy) ** 2)
    bowl = _smooth_falloff(dist, max(radius * 0.72, 1e-4))
    ring = _smooth_falloff(np.abs(dist - radius * 0.78), max(radius * 0.28, 1e-4))
    return hm - bowl * depth + ring * rim


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
    influence = _smooth_falloff(dist, max(width, 1e-4))
    return hm + influence * height


def _smooth_falloff(dist, radius):
    t = np.clip(1.0 - dist / max(radius, 1e-4), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _center(feat):
    center = feat.get("center") or [0.5, 0.5]
    if not isinstance(center, (list, tuple)) or len(center) < 2:
        return 0.5, 0.5
    return float(np.clip(center[0], 0, 1)), float(np.clip(center[1], 0, 1))
