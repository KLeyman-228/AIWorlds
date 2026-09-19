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
SCENE_MAX_TOKENS = int(os.getenv("AI_SCENE_MAX_TOKENS", "25000"))
METADATA_MAX_TOKENS = min(5000, SCENE_MAX_TOKENS)

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
    "Верни ТОЛЬКО компактный JSON по схеме. Без markdown. "
    "GLSL только массивом строк fs. Не обрезай JSON."
)

METADATA_SYSTEM_PROMPT = r"""Ретро-RTS артдиректор (Warcraft/Dota/Civ3). Верни ТОЛЬКО компактный JSON.

Схема:
{"n":"имя","d":"1 фраза","t":{"sc":45,"oc":4,"sd":42,"w":0.18,"g":[[0,[30,90,40]],[1,[90,70,40]]],"f":[["rv",[[0.1,0.4],[0.9,0.55]],0.05,0.4]]},"tm":{"grass":[0.18,0.46,0.12],"dirt":[0.28,0.20,0.10],"rock":[0.40,0.38,0.34]},"a":{"td":"day","fg":[170,200,230],"fd":0.01,"sk":[135,185,235],"su":[255,244,220],"am":[150,170,200]},"p":[["oak","veg",10,"fr","oak",{"bark":[0.32,0.18,0.08],"leaf":[0.18,0.5,0.12],"size":1.0}]],"pp":["uniform sampler2D tDiffuse;","varying vec2 vUv;","void main(){ gl_FragColor=texture2D(tDiffuse,vUv);}"]}

Ключи: n имя, d описание, t террейн, tm цвета ландшафта, a атмосфера, p пропы, pp постпроцесс.
t.w вода 0.12-0.22. t.g 6 ретро-ступеней. t.f: rv река, lk озеро.
tm: grass/dirt/rock 0-1. ts (кастомный fragment ландшафта) пиши ТОЛЬКО если биом нельзя описать tm (лава, снег, кристалл). Иначе tm хватает.
Заготовки пропов: oak, birch, pine, bush, boulder, stone, flower, mushroom, crystal, ruin, hay, cactus.
p элемент: [id, cat, count, dist, tpl, params]. tpl = oak|birch|pine|bush|boulder|stone|flower|mushroom|crystal|ruin|hay|cactus ИЛИ "x" если нужен кастомный меш/шейдер.
params: size 0.6-1.6, em 0-1.5 (свечение, 0 по умолчанию). дерево: bark, leaf. камень/руина: rock. цветок: petal, stem. гриб: cap, stem. кристалл: crystal + em. стог: hay.
Кастом (tpl=x) только если заготовки не хватает (мост, статуя, уникальный меш). Для свечения не нужен custom — ставь em.
a.td day, sk голубой. 4-6 пропов count<=14. Не делай проп-поляну.
JSON компактный, без markdown.
"""

PROP_SYSTEM_PROMPT = r"""Ретро-RTS теххудожник. Один проп. ТОЛЬКО компактный JSON.

{"n":"oak","g":[["cyl",[0.12,0.18,1.4,6],[0,0.7,0]],["sph",[0.7,6,4],[0,1.7,0]],["sph",[0.5,6,4],[0.35,1.5,0.1]]],"fs":["varying vec3 vPosition;","varying vec3 vNormal;","void main(){ float b=step(0.5,fract(vPosition.y*8.0)); vec3 c=mix(vec3(0.28,0.16,0.08),vec3(0.42,0.26,0.12),b); gl_FragColor=vec4(c,1.0); }"],"ls":["varying vec2 vUv;","varying vec3 vNormal;","void main(){ float n=fract(sin(dot(floor(vUv*12.0),vec2(12.9,78.2)))*43758.5); vec3 c=mix(vec3(0.10,0.34,0.08),vec3(0.22,0.58,0.14),step(0.45,n)); gl_FragColor=vec4(c,1.0); }"],"lv":["varying vec2 vUv;","varying vec3 vNormal;","varying vec3 vPosition;","uniform float uTime;","void main(){ vUv=uv; vNormal=normalize(normalMatrix*normal); vec3 p=position; p.x+=sin(uTime*1.6+position.y*3.0)*0.05; p.z+=cos(uTime*1.2+position.x*2.0)*0.04; vPosition=p; vec4 wp=modelMatrix*vec4(p,1.0); gl_Position=projectionMatrix*viewMatrix*wp; }"],"u":{"uBark":[0.32,0.18,0.08]},"i":[8,"fr",[0.8,1.2]]}

g: 3-6 малых примитивов. Дерево: cyl ствол + sph/con крона. ЗАПРЕЩЕНО plane и огромные box.
Для ДЕРЕВА обязательно два материала, 24-40 строк каждый:
fs = КОРА: вертикальные трещины, чешуйки, тёмные борозды, мох снизу (vPosition.y). Матовая. БЕЗ fresnel/gloss/sin(uTime) в цвете.
ls = ЛИСТВА: 2-3 октавы hash по UV/world, комочки листьев, тёмные дырки между ними, 3 оттенка зелени. Матовая. БЕЗ fresnel и БЕЗ пульса цвета.
lv = vertex листвы: качай position через sin/cos(uTime), амплитуда 0.03-0.07. Цвет во fragment НЕ от uTime.
Камень: трещины+мох+зерно. Цветок: стебель/лепесток разными hash. i count<=14.
i count<=14. JSON валидный, шейдеры массивом строк, не обрезай.
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


def _close_truncated_json(text: str) -> str:
    in_string = False
    escape = False
    stack = []
    for char in text:
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
            stack.append("}")
        elif char == "[":
            stack.append("]")
        elif char in "}]" and stack:
            stack.pop()
    if in_string:
        text += '"'
    text = re.sub(r",\s*$", "", text)
    return text + "".join(reversed(stack))


def _insert_missing_commas(text: str) -> str:
    """Вставляет запятую, если после значения сразу идёт следующий ключ/элемент."""
    out = []
    in_string = False
    escape = False
    prev_ns = ""
    for char in text:
        if in_string:
            out.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            if prev_ns and prev_ns not in "{[:,":
                out.append(",")
            in_string = True
            out.append(char)
            prev_ns = char
            continue
        out.append(char)
        if not char.isspace():
            prev_ns = char
    return "".join(out)


def _repair_json(text: str) -> str:
    repaired = _escape_controls_in_strings(text)
    repaired = _insert_missing_commas(repaired)
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    return _close_truncated_json(repaired)


def _parse_json(text: str) -> dict:
    raw = _extract_json_object(_strip_fences(text))
    candidates = [raw, _repair_json(raw)]
    last_error = None
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if not isinstance(data, dict):
                raise AIGenerationError("JSON AI должен быть объектом")
            return _normalize_shader_fields(expand_compact(data))
        except json.JSONDecodeError as exc:
            last_error = exc
    raise AIGenerationError(f"AI вернул невалидный JSON: {last_error}") from last_error


PRIM_ALIAS = {
    "box": "box",
    "sph": "sphere",
    "sphere": "sphere",
    "cyl": "cylinder",
    "cylinder": "cylinder",
    "con": "cone",
    "cone": "cone",
    "tor": "torus",
    "torus": "torus",
    "oct": "octahedron",
    "octahedron": "octahedron",
    "ico": "icosahedron",
    "icosahedron": "icosahedron",
    "dod": "dodecahedron",
    "dodecahedron": "dodecahedron",
    "tet": "tetrahedron",
    "tetrahedron": "tetrahedron",
    "pln": "plane",
    "plane": "plane",
}
FEAT_ALIAS = {
    "rv": "river",
    "lk": "lake",
    "bs": "basin",
    "rd": "ridge",
    "pl": "plateau",
    "md": "mound",
}
DIST_ALIAS = {"sc": "scattered", "fr": "forest", "cl": "cluster", "rv": "river_line"}
CAT_ALIAS = {
    "veg": "vegetation",
    "str": "structure",
    "rk": "rock",
    "un": "unit_prop",
    "mag": "magic",
    "dec": "decoration",
}
PRIM_PARAMS = {
    "box": ("width", "height", "depth"),
    "sphere": ("radius", "widthSegments", "heightSegments"),
    "cylinder": ("rTop", "rBottom", "height", "segments"),
    "cone": ("radius", "height", "segments"),
    "torus": ("radius", "tube", "radialSegments", "tubularSegments"),
    "octahedron": ("radius",),
    "icosahedron": ("radius",),
    "dodecahedron": ("radius",),
    "tetrahedron": ("radius",),
    "plane": ("width", "height"),
}


def expand_compact(data: dict) -> dict:
    """Разворачивает сжатый DSL в полный план. Полный JSON пропускается."""
    if "g" in data and isinstance(data.get("g"), list) and "geometry" not in data:
        return _expand_prop(data)
    if "n" in data and ("t" in data or "p" in data) and "world_name" not in data:
        return _expand_metadata(data)
    return data


def _expand_metadata(data: dict) -> dict:
    terrain = data.get("t") or {}
    atmo = data.get("a") or {}
    props = []
    for item in data.get("p") or []:
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            dist = DIST_ALIAS.get(str(item[3]), item[3]) if len(item) > 3 else "scattered"
            entry = {
                "name": item[0],
                "category": CAT_ALIAS.get(str(item[1]), item[1]),
                "count": int(item[2]),
                "distribution": dist,
            }
            if len(item) > 4 and item[4] not in (None, ""):
                entry["template"] = item[4]
            if len(item) > 5 and isinstance(item[5], dict):
                entry["params"] = item[5]
                for key in ("bark", "leaf", "rock", "petal", "stem", "size", "moss", "em", "cap", "crystal", "hay"):
                    if key in item[5]:
                        entry[key] = item[5][key]
            props.append(entry)
        elif isinstance(item, dict):
            props.append(item)
    gradient = []
    for stop in terrain.get("g") or []:
        if isinstance(stop, (list, tuple)) and len(stop) >= 2:
            gradient.append({"height": stop[0], "color": stop[1]})
        elif isinstance(stop, dict):
            gradient.append(stop)
    features = []
    for feat in terrain.get("f") or []:
        expanded = _expand_feature(feat)
        if expanded:
            features.append(expanded)
    pp = data.get("pp")
    post = {"shader": {"fragment_lines": pp}} if isinstance(pp, list) else data.get("post_process") or {}
    ts = data.get("ts")
    terrain_shader = None
    if isinstance(ts, list):
        terrain_shader = {"fragment_lines": ts}
    elif isinstance(ts, str):
        terrain_shader = {"fragment": ts}
    return {
        "world_name": data.get("n") or data.get("world_name"),
        "description": data.get("d") or data.get("description") or "",
        "terrain": {
            "scale": terrain.get("sc", terrain.get("scale", 45)),
            "octaves": terrain.get("oc", terrain.get("octaves", 4)),
            "seed": terrain.get("sd", terrain.get("seed", 42)),
            "water_level": terrain.get("w", terrain.get("water_level")),
            "color_gradient": gradient or terrain.get("color_gradient"),
            "features": features or terrain.get("features") or [],
            "shader": terrain_shader or terrain.get("shader"),
            "material": data.get("tm") or terrain.get("material") or {},
        },
        "atmosphere": {
            "time_of_day": atmo.get("td", atmo.get("time_of_day", "day")),
            "clouds": True,
            "fog_color": atmo.get("fg", atmo.get("fog_color")),
            "fog_density": atmo.get("fd", atmo.get("fog_density", 0.01)),
            "sky_color": atmo.get("sk", atmo.get("sky_color")),
            "sun_color": atmo.get("su", atmo.get("sun_color")),
            "ambient_color": atmo.get("am", atmo.get("ambient_color")),
        },
        "prop_list": props or data.get("prop_list") or [],
        "post_process": post,
    }


def _expand_feature(feat):
    if isinstance(feat, dict):
        kind = FEAT_ALIAS.get(str(feat.get("type") or ""), feat.get("type"))
        if kind:
            feat = dict(feat)
            feat["type"] = kind
        return feat
    if not isinstance(feat, (list, tuple)) or not feat:
        return None
    kind = FEAT_ALIAS.get(str(feat[0]), feat[0])
    item = {"type": kind}
    if kind in ("river", "ridge"):
        item["points"] = feat[1] if len(feat) > 1 else []
        item["width"] = feat[2] if len(feat) > 2 else 0.05
        if kind == "river":
            item["depth"] = feat[3] if len(feat) > 3 else 0.4
        else:
            item["height"] = feat[3] if len(feat) > 3 else 0.35
    else:
        item["center"] = feat[1] if len(feat) > 1 else [0.5, 0.5]
        item["radius"] = feat[2] if len(feat) > 2 else 0.12
        if kind in ("lake", "basin"):
            item["depth"] = feat[3] if len(feat) > 3 else 0.35
        else:
            item["height"] = feat[3] if len(feat) > 3 else 0.3
    return item


def _expand_prop(data: dict) -> dict:
    primitives = []
    for prim in data.get("g") or []:
        expanded = _expand_primitive(prim)
        if expanded:
            primitives.append(expanded)
    uniforms = {}
    raw_u = data.get("u") or {}
    if isinstance(raw_u, dict):
        for name, value in raw_u.items():
            if isinstance(value, dict) and "type" in value:
                uniforms[name] = value
            elif isinstance(value, (list, tuple)):
                uniforms[name] = {"type": f"vec{len(value)}", "value": list(value)}
            else:
                uniforms[name] = {"type": "float", "value": value}
    inst = data.get("i")
    if isinstance(inst, (list, tuple)) and inst:
        instances = {
            "count": int(inst[0]),
            "distribution": DIST_ALIAS.get(str(inst[1]), inst[1]) if len(inst) > 1 else "scattered",
            "scale_range": inst[2] if len(inst) > 2 else [0.8, 1.2],
        }
    else:
        instances = inst if isinstance(inst, dict) else {"count": 8, "distribution": "scattered"}
    fs = data.get("fs") or data.get("fragment_lines")
    ls = data.get("ls")
    lv = data.get("lv")
    shader = {
        "fragment_lines": fs if isinstance(fs, list) else None,
        "fragment": None if isinstance(fs, list) else fs,
        "leaf_fragment_lines": ls if isinstance(ls, list) else None,
        "leaf_fragment": None if isinstance(ls, list) else ls,
        "leaf_vertex_lines": lv if isinstance(lv, list) else None,
        "leaf_vertex": None if isinstance(lv, list) else lv,
        "uniforms": uniforms,
    }
    return {
        "name": data.get("n") or data.get("name"),
        "geometry": {"primitives": primitives},
        "shader": shader,
        "instances": instances,
    }


def _expand_primitive(prim):
    if isinstance(prim, dict):
        ptype = PRIM_ALIAS.get(str(prim.get("type") or "").lower(), prim.get("type"))
        item = dict(prim)
        item["type"] = ptype
        return item
    if not isinstance(prim, (list, tuple)) or not prim:
        return None
    ptype = PRIM_ALIAS.get(str(prim[0]).lower(), prim[0])
    values = prim[1] if len(prim) > 1 and isinstance(prim[1], (list, tuple)) else []
    keys = PRIM_PARAMS.get(ptype, ())
    params = {keys[i]: values[i] for i in range(min(len(keys), len(values)))}
    item = {"type": ptype, "params": params}
    if len(prim) > 2 and prim[2]:
        item["position"] = prim[2]
    if len(prim) > 3 and prim[3]:
        item["rotation"] = prim[3]
    if len(prim) > 4 and prim[4] is not None:
        item["scale"] = prim[4]
    return item


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
        if not shader.get("leaf_fragment"):
            shader["leaf_fragment"] = _join_shader_lines(shader.get("leaf_fragment_lines"))
        if not shader.get("leaf_vertex"):
            shader["leaf_vertex"] = _join_shader_lines(shader.get("leaf_vertex_lines"))
        data["shader"] = shader
    if data.get("ts") and isinstance(data.get("terrain"), dict) and not (data["terrain"].get("shader") or {}).get("fragment"):
        ts = data["ts"]
        data["terrain"]["shader"] = {
            "fragment_lines": ts if isinstance(ts, list) else None,
            "fragment": None if isinstance(ts, list) else ts,
        }
    terrain = data.get("terrain")
    if isinstance(terrain, dict) and isinstance(terrain.get("shader"), dict):
        tsh = terrain["shader"]
        if not tsh.get("fragment"):
            tsh["fragment"] = _join_shader_lines(tsh.get("fragment_lines"))
        terrain["shader"] = tsh
        data["terrain"] = terrain
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
    attempts: int = 5,
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
            text = str(exc).lower()
            busy = any(word in text for word in ("503", "capacity", "unavailable", "overloaded", "timeout"))
            if busy:
                wait = min(8 * attempt, 32)
                log.warning("AI busy [%s] attempt=%s, wait %ss: %s", label, attempt, wait, exc)
            else:
                log.exception("AI HTTP error [%s] attempt=%s", label, attempt)
                wait = min(3 * attempt, 10)
            last_error = AIGenerationError(f"Ошибка запроса к AI ({label}): {exc}")
            time.sleep(wait)
            continue

        content = ""
        finish = None
        if response.choices:
            content = response.choices[0].message.content or ""
            finish = getattr(response.choices[0], "finish_reason", None)
        log.info(
            "AI response [%s] attempt=%s out_chars=%s finish=%s time=%.2fs",
            label, attempt, len(content), finish, time.perf_counter() - started,
        )
        if not content.strip():
            last_error = AIGenerationError(f"Пустой ответ AI ({label})")
            log.warning("Empty AI response [%s] attempt=%s, retry", label, attempt)
            time.sleep(min(2 * attempt, 6))
            continue
        try:
            return _parse_json(content)
        except AIGenerationError as exc:
            last_error = exc
            log.warning("JSON parse failed [%s] attempt=%s finish=%s: %s", label, attempt, finish, exc)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt + "\n" + JSON_RETRY_HINT},
            ]
    raise last_error or AIGenerationError(f"Не удалось получить JSON от AI ({label})")


def generate_world_metadata(user_prompt: str, model: str | None = None) -> dict:
    """Этап 1: метаданные мира, террейн, атмосфера, список пропсов, пост-процесс."""
    chosen = model or MODEL
    user = (
        f"prompt:{user_prompt.strip()}\n"
        "Prefer templates oak/birch/pine/bush/boulder/flower. custom tpl=x only if needed."
    )
    data = _chat(METADATA_SYSTEM_PROMPT, user, chosen, METADATA_MAX_TOKENS, "metadata")
    if not data.get("prop_list"):
        raise AIGenerationError("AI не вернул prop_list")
    if not isinstance(data["prop_list"], list) or len(data["prop_list"]) < 3:
        raise AIGenerationError("Нужно минимум 3 пропа в prop_list")
    return data


def generate_prop(user_prompt: str, world_meta: dict, prop_spec: dict, model: str | None = None) -> dict:
    """Этап 2: геометрия + уникальный GLSL-материал одного пропа."""
    chosen = model or MODEL
    spec = {
        "n": prop_spec.get("name"),
        "cat": prop_spec.get("category"),
        "cnt": prop_spec.get("count"),
        "dist": prop_spec.get("distribution") or "sc",
    }
    user = (
        f"world:{world_meta.get('world_name')}\n"
        f"prompt:{user_prompt.strip()}\n"
        f"prop:{json.dumps(spec, ensure_ascii=False)}\n"
        "compact JSON, keep fs shader lines full."
    )
    n_props = max(1, len(world_meta.get("prop_list") or []))
    prop_tokens = max(2500, (SCENE_MAX_TOKENS - METADATA_MAX_TOKENS) // n_props)
    data = _chat(PROP_SYSTEM_PROMPT, user, chosen, prop_tokens, f"prop:{prop_spec.get('name')}")
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
    max_workers: int = 2,
) -> dict:
    """Шаблоны копируются сразу. Кастомные пропы генерируются параллельно."""
    from .templates import instantiate_prop, wants_custom

    prop_list = world_meta["prop_list"][:8]
    props = {}
    errors = []
    custom_specs = []
    started = time.perf_counter()

    for spec in prop_list:
        name = spec.get("name", "?")
        if not wants_custom(spec):
            try:
                prop = instantiate_prop(spec)
                props[prop["name"]] = prop
                log.info("Prop template: %s -> %s", name, prop.get("template"))
                continue
            except Exception as exc:
                log.warning("Template miss %s, fallback to AI: %s", name, exc)
        custom_specs.append(spec)

    log.info("Prop generation templates=%s custom=%s", len(props), len(custom_specs))
    if custom_specs:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(generate_prop, user_prompt, world_meta, spec, model): spec
                for spec in custom_specs
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
