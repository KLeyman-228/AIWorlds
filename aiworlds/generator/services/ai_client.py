"""
Клиент для VibeCodeCheap (Claude через Anthropic SDK).
"""
import os
import json
import re
from anthropic import Anthropic


API_KEY = os.getenv(
    "VIBECODE_API_KEY",
    "sk-cvc-2d33e7d4a5cd24678cc3d8ac305291e471bb10550bc640ec68062b0741ecc726"
)
BASE_URL = "https://ru.cheapvibecode.ru"
MODEL = "claude-sonnet-4-6"

_client = Anthropic(base_url=BASE_URL, api_key=API_KEY)


SYSTEM_PROMPT = r"""Ты — эксперт по Three.js, GLSL и процедурной генерации.
Создай JSON-план 3D-мира в стиле PSX.

Верни ТОЛЬКО валидный JSON без markdown. Структура:

{
  "world_name": "string",
  "description": "string",
  "terrain": {
    "scale": 45, "octaves": 4, "seed": 42,
    "color_gradient": [
      {"height": 0.0, "color": [R,G,B]},
      {"height": 0.25, "color": [R,G,B]},
      {"height": 0.55, "color": [R,G,B]},
      {"height": 0.8, "color": [R,G,B]},
      {"height": 1.0, "color": [R,G,B]}
    ]
  },
  "atmosphere": {
    "fog_color": [R,G,B],
    "fog_density": 0.02,
    "sky_color": [R,G,B],
    "sun_color": [R,G,B],
    "ambient_color": [R,G,B]
  },
  "props": {
    "unique_prop_name": {
      "geometry": {
        "primitives": [
          {"type": "cylinder|cone|box|sphere|torus|octahedron|icosahedron|plane",
           "params": {"rTop": 0.1, "rBottom": 0.15, "height": 0.8, "segments": 6},
           "position": [0, 0.4, 0],
           "rotation": [0, 0, 0],
           "scale": [1, 1, 1]}
        ]
      },
      "shader": {
        "vertex": "GLSL код",
        "fragment": "GLSL код",
        "uniforms": {}
      },
      "instances": [
        {"position": [3, 0, 5], "rotation": [0, 0, 0], "scale": 1.2}
      ]
    }
  },
  "post_process": {
    "shader": {
      "vertex": "GLSL",
      "fragment": "GLSL",
      "uniforms": {}
    }
  }
}

## DSL: доступные примитивы
- cylinder: {rTop, rBottom, height, segments: 6}
- cone: {radius, height, segments: 8}
- box: {width, height, depth}
- sphere: {radius, widthSegments: 8, heightSegments: 6}
- torus: {radius, tube, radialSegments: 8, tubularSegments: 16}
- octahedron: {radius}
- icosahedron: {radius}
- plane: {width, height}

Используй НИЗКИЕ segments (6-8) для PSX-стиля.

## SHADER пропсов
Vertex — стандартный:
varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vPosition;
varying vec3 vWorldPos;
void main() {
  vUv = uv;
  vNormal = normalize(normalMatrix * normal);
  vPosition = position;
  vec4 wp = modelMatrix * vec4(position, 1.0);
  vWorldPos = wp.xyz;
  gl_Position = projectionMatrix * viewMatrix * wp;
}

Fragment — доступны uTime и твои uniforms.
Обязательно объявляй все uniforms в "uniforms".

Пример воды:
uniform float uTime;
varying vec2 vUv;
void main() {
  float wave = sin(vUv.x * 20.0 + uTime * 2.0) * 0.5 + 0.5;
  vec3 color = mix(vec3(0.1, 0.3, 0.6), vec3(0.3, 0.6, 0.9), wave);
  gl_FragColor = vec4(color, 0.85);
}

## POST_PROCESS
Vertex — стандартный fullscreen quad:
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}

Fragment — обязательно:
uniform sampler2D tDiffuse;
uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;
void main() {
  vec4 color = texture2D(tDiffuse, vUv);
  // модификация: виньетка, tint, chromatic aberration, dither
  gl_FragColor = color;
}

## ОГРАНИЧЕНИЯ
- GLSL ES 1.0 (без #version, только varying)
- Максимум 60 строк на шейдер
- uTime добавляется автоматически

Создай мир по запросу пользователя."""


def generate_world_plan(user_prompt: str) -> dict:
    """Вызывает Claude, парсит JSON, возвращает план."""
    message = _client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}]
    )

    text = message.content[0].text.strip()

    # Убираем markdown-обёртки
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    # Ищем первый { и последний } — на случай мусора вокруг
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)

    return json.loads(text)