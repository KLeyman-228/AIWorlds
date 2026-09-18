"""
Клиент AI: OpenAI-совместимый шлюз, модель kimi-k3.

AI генерирует данные мира и GLSL-материалы. Код считает террейн
и расставляет инстансы. Заглушки мира не используются.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from openai import OpenAI

log = logging.getLogger(__name__)

API_KEY = os.getenv(
    "AI_API_KEY",
    os.getenv(
        "VIBECODE_API_KEY",
        "sk-cvc-2d33e7d4a5cd24678cc3d8ac305291e471bb10550bc640ec68062b0741ecc726",
    ),
)
BASE_URL = os.getenv("AI_BASE_URL", "https://ru.cheapvibecode.ru/v1")
MODEL = os.getenv("AI_MODEL", "kimi-k3")
FAST_MODEL = os.getenv("AI_FAST_MODEL", "kimi-k3")

STANDARD_VERTEX_SHADER = """varying vec2 vUv;
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
}"""

POST_VERTEX_SHADER = """varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}"""

JSON_RETRY_HINT = (
    "Предыдущий ответ был пустым или невалидным JSON. "
    "Верни ТОЛЬКО один JSON-объект, без markdown. "
    "GLSL клади массивом строк в shader.fragment_lines и shader.vertex_lines. "
    "Никаких сырых переносов внутри кавычек."
)

METADATA_SYSTEM_PROMPT = r"""Ты — арт-директор ретро-стратегий: Warcraft II/III, ранняя Dota, Civilization III.
Генерируешь JSON-описание изометрического 3D-уровня в духе RTS/TBS 90-х–начала 2000-х:
низкополигональные меши, палитра 16–32 цвета, террасы ландшафта, читаемые силуэты юнитов и строений.

Верни ТОЛЬКО валидный JSON без markdown и комментариев.

{
  "world_name": "атмосферное название 2-5 слов",
  "description": "1-2 предложения: биом, фракция, настроение",
  "style": {
    "era": "warcraft|dota|civ3|hybrid",
    "palette_name": "название палитры",
    "mood": "коротко"
  },
  "terrain": {
    "scale": 10-100,
    "octaves": 1-8,
    "seed": целое,
    "water_level": 0.22,
    "color_gradient": [
      {"height": 0.0, "color": [R,G,B]},
      {"height": 1.0, "color": [R,G,B]}
    ],
    "features": [
      {"type": "river", "points": [[0.05, 0.4], [0.4, 0.5], [0.95, 0.6]], "width": 0.05, "depth": 0.45},
      {"type": "basin", "center": [0.3, 0.7], "radius": 0.12, "depth": 0.35},
      {"type": "ridge", "points": [[0.2, 0.2], [0.8, 0.25]], "width": 0.08, "height": 0.4}
    ]
  },
  "atmosphere": {
    "time_of_day": "day",
    "clouds": true,
    "fog_color": [170, 200, 230],
    "fog_density": 0.01,
    "sky_color": [135, 185, 235],
    "sun_color": [255, 244, 220],
    "ambient_color": [150, 170, 200]
  },
  "prop_list": [
    {
      "name": "snake_case_id",
      "category": "vegetation|structure|rock|unit_prop|magic|decoration",
      "count": 5-40,
      "role": "зачем объект на карте RTS"
    }
  ],
  "post_process": {
    "shader": {
      "vertex_lines": ["varying vec2 vUv;", "void main() {", "  vUv = uv;", "  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);", "}"],
      "fragment_lines": ["uniform sampler2D tDiffuse;", "uniform float uTime;", "uniform vec2 uResolution;", "varying vec2 vUv;", "void main() {", "  vec4 color = texture2D(tDiffuse, vUv);", "  gl_FragColor = color;", "}"],
      "uniforms": {
        "uTint": {"type": "vec3", "value": [1.0, 0.95, 0.8]}
      }
    }
  }
}

Правила:
- color_gradient: 5-8 точек, height строго от 0.0 до 1.0, цвета 0-255. Нижние ступени = вода/ил, если есть река/озеро.
- Палитра как в Warcraft/Civ3: трава, грязь, песок, камень, вода отдельными ступенями, не фотореализм.
- Ландшафт НЕ только шум. Обязательно 1-4 features в UV 0..1 (x=u, y=v):
  river: points[], width, depth — прорезает русло
  lake/basin: center[u,v], radius, depth — впадина
  ridge: points[], width, height — хребет
  plateau: center, radius, height — плоскогорье
  mound: center, radius, height — холм
- Код сам вырежет эти формы на heightmap. Клади реку/ущелье/озеро если промпт этого просит.
- water_level 0..1, если есть вода; иначе null.
- Небо ДНЁМ синее: sky_color около [135,185,235], fog_color около [170,200,230], fog_density <= 0.015.
  time_of_day=sunset/night только если промпт явно про закат/ночь.
- post_process: лёгкая виньетка + дитеринг. ЗАПРЕЩЕНО красить кадр в красный/оранжевый.
  tint максимум vec3(1.02, 1.0, 0.98). Небо должно остаться голубым.
- prop_list: 4-8 уникальных типов под КОНКРЕТНЫЙ промпт.
- Каждый проп — смысл на тактической карте (дерево-блокер, шахта, башня, ферма).
- Vertex пост-процесса: varying vec2 vUv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);
- Не объявляй uTime в uniforms. tDiffuse не клади в uniforms.
- GLSL ES 1.0: без #version, без in/out, только varying.
- Шейдеры ТОЛЬКО как vertex_lines / fragment_lines (массив строк).
"""

PROP_SYSTEM_PROMPT = r"""Ты — теххудожник ретро-RTS (Warcraft, Dota, Civilization III).
Пишешь ОДИН проп: низкополигональная геометрия из примитивов + уникальный GLSL ES 1.0 материал.

Верни ТОЛЬКО валидный JSON без markdown.

{
  "name": "тот же id",
  "geometry": {
    "primitives": [
      {
        "type": "cylinder",
        "params": {"rTop": 0.12, "rBottom": 0.18, "height": 1.4, "segments": 6},
        "position": [0, 0.7, 0],
        "rotation": [0, 0, 0],
        "scale": 1
      }
    ]
  },
  "shader": {
    "vertex_lines": ["varying vec2 vUv;", "varying vec3 vNormal;", "varying vec3 vPosition;", "varying vec3 vWorldPos;", "void main() {", "  vUv = uv;", "  vNormal = normalize(normalMatrix * normal);", "  vPosition = position;", "  vec4 wp = modelMatrix * vec4(position, 1.0);", "  vWorldPos = wp.xyz;", "  gl_Position = projectionMatrix * viewMatrix * wp;", "}"],
    "fragment_lines": ["uniform float uTime;", "varying vec2 vUv;", "varying vec3 vNormal;", "varying vec3 vPosition;", "void main() {", "  vec3 color = vec3(0.2, 0.45, 0.15);", "  gl_FragColor = vec4(color, 1.0);", "}"],
    "uniforms": {
      "uColorA": {"type": "vec3", "value": [0.2, 0.45, 0.15]}
    }
  },
  "instances": {
    "count": 20,
    "distribution": "scattered|forest|cluster|river_line",
    "scale_range": [0.7, 1.4]
  }
}

Примитивы: box, sphere, cylinder, cone, torus, octahedron, icosahedron, dodecahedron, tetrahedron, plane.
segments всегда 6-8 (ретро-силуэт). Проп = 3-6 примитивов.

МАТЕРИАЛ (fragment) — это главное:
- Процедурный, без внешних текстур.
- Стилистика: палитра Warcraft/Dota/Civ3, плоское освещение, дитеринг, квантование цвета.
- 3-5 техник: hash-шум, fresnel, пульс uTime, дитеринг, градиент по vPosition.y, domain warp UV, псевдо-ламберт.
- Уникальный шейдер под ЭТОТ объект (кора, руны, золото шахты, слизь, лёд, кирпич, листва). Не универсальный серый.
- GLSL ES 1.0: varying, gl_FragColor, без #version, без texture2D кроме если сам не используешь карты.
- Не объявляй uTime в uniforms.
- JSON должен парситься json.loads без правок. Шейдеры только vertex_lines/fragment_lines (массив строк). Не вставляй GLSL куском с переносами внутри кавычек.
- vertex_lines можно опустить — код подставит стандартный vertex.
"""

_http_timeout = httpx.Timeout(600.0, connect=10.0)
_client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
    timeout=_http_timeout,
    max_retries=1,
)


class AIGenerationError(RuntimeError):
    """AI не вернул пригодный план мира."""


def _strip_fences(text: str) -> str:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0].strip()
    return raw


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        raise AIGenerationError("В ответе AI нет JSON-объекта")
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(text[start:], start):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return text[start:]


def _escape_controls_in_strings(text: str) -> str:
    out = []
    in_string = False
    escape = False
    for char in text:
        if in_string:
            if escape:
                out.append(char)
                escape = False
            elif char == "\\":
                out.append(char)
                escape = True
            elif char == '"':
                out.append(char)
                in_string = False
            elif char == "\n":
                out.append("\\n")
            elif char == "\r":
                continue
            elif char == "\t":
                out.append("\\t")
            elif ord(char) < 32:
                out.append(f"\\u{ord(char):04x}")
            else:
                out.append(char)
            continue
        out.append(char)
        if char == '"':
            in_string = True
    return "".join(out)


def _repair_json(text: str) -> str:
    repaired = _escape_controls_in_strings(text)
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    return repaired


def _parse_json(text: str) -> dict:
    raw = _extract_json_object(_strip_fences(text))
    candidates = [raw, _repair_json(raw)]
    last_error = None
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if not isinstance(data, dict):
                raise AIGenerationError("JSON AI должен быть объектом")
            return _normalize_shader_fields(data)
        except json.JSONDecodeError as exc:
            last_error = exc
    raise AIGenerationError(f"AI вернул невалидный JSON: {last_error}") from last_error


def _join_shader_lines(value) -> str:
    if isinstance(value, list):
        return "\n".join(str(line) for line in value)
    if isinstance(value, str):
        return value
    return ""


def _normalize_shader_fields(data: dict) -> dict:
    shader = data.get("shader")
    if isinstance(shader, dict):
        if not shader.get("fragment"):
            shader["fragment"] = _join_shader_lines(shader.get("fragment_lines"))
        if not shader.get("vertex"):
            shader["vertex"] = _join_shader_lines(shader.get("vertex_lines"))
        data["shader"] = shader
    post = data.get("post_process")
    if isinstance(post, dict) and isinstance(post.get("shader"), dict):
        post_shader = post["shader"]
        if not post_shader.get("fragment"):
            post_shader["fragment"] = _join_shader_lines(post_shader.get("fragment_lines"))
        if not post_shader.get("vertex"):
            post_shader["vertex"] = _join_shader_lines(post_shader.get("vertex_lines"))
        post["shader"] = post_shader
        data["post_process"] = post
    return data


def _chat(
    system_prompt: str,
    user_prompt: str,
    model: str,
    max_tokens: int,
    label: str,
    attempts: int = 3,
) -> dict:
    started = time.perf_counter()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    last_error = None
    for attempt in range(1, attempts + 1):
        in_size = sum(len(item.get("content") or "") for item in messages)
        log.info(
            "AI request [%s] model=%s attempt=%s in_chars=%s max_tokens=%s",
            label, model, attempt, in_size, max_tokens,
        )
        try:
            kwargs = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7 if attempt == 1 else 0.3,
            }
            response = _client.chat.completions.create(**kwargs)
        except Exception as exc:
            log.exception("AI HTTP error [%s] attempt=%s", label, attempt)
            last_error = AIGenerationError(f"Ошибка запроса к AI ({label}): {exc}")
            time.sleep(min(2 * attempt, 6))
            continue

        content = ""
        if response.choices:
            content = response.choices[0].message.content or ""
        log.info(
            "AI response [%s] attempt=%s out_chars=%s time=%.2fs",
            label, attempt, len(content), time.perf_counter() - started,
        )
        if not content.strip():
            last_error = AIGenerationError(f"Пустой ответ AI ({label})")
            log.warning("Empty AI response [%s] attempt=%s, retry", label, attempt)
            time.sleep(min(2 * attempt, 6))
            messages.append({"role": "user", "content": JSON_RETRY_HINT})
            continue
        try:
            return _parse_json(content)
        except AIGenerationError as exc:
            last_error = exc
            log.warning("JSON parse failed [%s] attempt=%s: %s", label, attempt, exc)
            messages.append({"role": "assistant", "content": content[:8000]})
            messages.append({"role": "user", "content": JSON_RETRY_HINT})
    raise last_error or AIGenerationError(f"Не удалось получить JSON от AI ({label})")


def generate_world_metadata(user_prompt: str, model: str | None = None) -> dict:
    """Этап 1: метаданные мира, террейн, атмосфера, список пропсов, пост-процесс."""
    chosen = model or MODEL
    user = (
        "Сгенерируй метаданные ретро-RTS уровня по промпту пользователя.\n"
        "Промпт:\n"
        f"{user_prompt.strip()}\n"
        "Подбери биом, features ландшафта (река/впадина/хребет если уместно), "
        "синее дневное небо если не сказано иное, 4-8 пропсов и мягкий пост-процесс."
    )
    data = _chat(METADATA_SYSTEM_PROMPT, user, chosen, 4000, "metadata")
    if not data.get("prop_list"):
        raise AIGenerationError("AI не вернул prop_list")
    if not isinstance(data["prop_list"], list) or len(data["prop_list"]) < 4:
        raise AIGenerationError("Нужно минимум 4 пропа в prop_list")
    if not data.get("post_process", {}).get("shader", {}).get("fragment"):
        raise AIGenerationError("AI не вернул fragment шейдер пост-процесса")
    return data


def generate_prop(user_prompt: str, world_meta: dict, prop_spec: dict, model: str | None = None) -> dict:
    """Этап 2: геометрия + уникальный GLSL-материал одного пропа."""
    chosen = model or MODEL
    spec_json = json.dumps(prop_spec, ensure_ascii=False)
    style = json.dumps(
        {
            "world_name": world_meta.get("world_name"),
            "description": world_meta.get("description"),
            "style": world_meta.get("style"),
            "atmosphere": world_meta.get("atmosphere"),
        },
        ensure_ascii=False,
    )
    user = (
        f"Мир: {style}\n"
        f"Промпт игрока: {user_prompt.strip()}\n"
        f"Сгенерируй ТОЛЬКО этот проп: {spec_json}\n"
        "Материал должен быть уникальным и стилизованным под ретро-RTS."
    )
    data = _chat(PROP_SYSTEM_PROMPT, user, chosen, 4000, f"prop:{prop_spec.get('name')}")
    name = data.get("name") or prop_spec.get("name")
    data["name"] = name
    primitives = (data.get("geometry") or {}).get("primitives") or []
    if len(primitives) < 3:
        raise AIGenerationError(f"Проп {name}: нужно 3-6 примитивов, получено {len(primitives)}")
    fragment = (data.get("shader") or {}).get("fragment") or ""
    if len(fragment.strip()) < 40:
        raise AIGenerationError(f"Проп {name}: пустой или слишком короткий fragment shader")
    shader = data.setdefault("shader", {})
    if not (shader.get("vertex") or "").strip():
        shader["vertex"] = STANDARD_VERTEX_SHADER
    return data


def generate_props_parallel(
    user_prompt: str,
    world_meta: dict,
    model: str | None = None,
    max_workers: int = 3,
) -> dict:
    """Параллельно генерирует все пропсы. Упавший проп пропускается; если все упали — ошибка."""
    prop_list = world_meta["prop_list"][:8]
    props = {}
    errors = []
    started = time.perf_counter()
    log.info("Prop generation start count=%s workers=%s", len(prop_list), max_workers)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(generate_prop, user_prompt, world_meta, spec, model): spec
            for spec in prop_list
        }
        for future in as_completed(futures):
            spec = futures[future]
            name = spec.get("name", "?")
            try:
                prop = future.result()
                props[prop["name"]] = prop
                log.info("Prop ready: %s", prop["name"])
            except Exception as exc:
                log.exception("Prop failed: %s", name)
                errors.append(f"{name}: {exc}")

    elapsed = time.perf_counter() - started
    log.info("Prop generation done ok=%s fail=%s time=%.2fs", len(props), len(errors), elapsed)
    if not props:
        raise AIGenerationError("Ни один проп не сгенерировался: " + "; ".join(errors))
    return props


def generate_world_plan(user_prompt: str, model: str | None = None) -> dict:
    """Полный AI-план: метаданные + пропсы. Совместимо со старым вызовом."""
    meta = generate_world_metadata(user_prompt, model=model)
    props = generate_props_parallel(user_prompt, meta, model=model)
    meta["props"] = props
    return meta
