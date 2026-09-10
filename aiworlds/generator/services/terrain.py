"""
Генерация карты высот и цветовой карты.
"""
import io
import base64
import numpy as np
from PIL import Image
from perlin_noise import PerlinNoise
from scipy.ndimage import gaussian_filter


def generate_heightmap(size=128, scale=45.0, octaves=4, seed=42) -> np.ndarray:
    octaves = max(1, min(10, int(octaves)))
    scale = max(1.0, float(scale))
    seed = int(seed)

    noise = PerlinNoise(octaves=octaves, seed=seed)

    hm = np.zeros((size, size))
    for i in range(size):
        for j in range(size):
            hm[i][j] = (noise([i / scale, j / scale]) + 1) / 2

    hm = (hm - hm.min()) / (hm.max() - hm.min() + 1e-8)

    # PSX-террасирование
    step = 1.0 / 8
    hm = np.floor(hm / step) * step + step / 2
    hm = gaussian_filter(hm, sigma=0.5)

    return hm


def generate_color_map(hm: np.ndarray, gradient: list) -> np.ndarray:
    size = hm.shape[0]
    color_map = np.zeros((size, size, 3), dtype=np.uint8)

    sorted_grad = sorted(gradient, key=lambda x: x["height"])
    heights = np.array([p["height"] for p in sorted_grad])
    colors = np.array([p["color"] for p in sorted_grad], dtype=np.float32)

    for i in range(size):
        for j in range(size):
            h = hm[i][j]
            idx = np.searchsorted(heights, h, side="right") - 1
            idx = max(0, min(len(heights) - 2, idx))

            h0, h1 = heights[idx], heights[idx + 1]
            c0, c1 = colors[idx], colors[idx + 1]

            t = 0.0 if h1 - h0 < 1e-6 else max(0.0, min(1.0, (h - h0) / (h1 - h0)))
            color_map[i][j] = (c0 * (1 - t) + c1 * t).astype(np.uint8)

    return color_map


def heightmap_to_base64(hm: np.ndarray) -> str:
    data = (hm * 255).astype(np.uint8)
    img = Image.fromarray(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def colormap_to_base64(cm: np.ndarray) -> str:
    img = Image.fromarray(cm, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()