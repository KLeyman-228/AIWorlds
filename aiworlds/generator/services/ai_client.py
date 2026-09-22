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
{"n":"имя","d":"1 фраза","t":{"st":"hills","sc":34,"oc":3,"sd":917,"amp":1.0,"w":0.14,"g":[[0,[90,80,40]],[0.4,[40,110,40]],[1,[130,120,110]]],"f":[{"k":"md","c":[0.22,0.7],"r":0.16,"h":0.4}]},"tm":{"grass":[0.18,0.46,0.12],"dirt":[0.32,0.22,0.10],"rock":[0.42,0.40,0.36],"snow":[0.82,0.84,0.86]},"a":{"td":"day","fg":[170,200,230],"fd":0.01,"sk":[135,185,235],"su":[255,244,220],"am":[150,170,200]},"p":[{"n":"oak","c":"veg","k":22,"d":"fr","t":"oak","p":{"bark":[0.32,0.18,0.08],"leaf":[0.18,0.5,0.12],"size":1.0}}],"pp":["uniform sampler2D tDiffuse;","varying vec2 vUv;","void main(){ gl_FragColor=texture2D(tDiffuse,vUv);}"]}

Ключи: n имя, d описание, t террейн, tm палитра, a атмосфера, p пропы-ОБЪЕКТЫ, pp постпроцесс.
p объект {n,c,k,d,t,p}. c=veg|str|rk|un|mag|dec. d=sc|fr|cl|rv. t шаблон или "x" (дом/мост/статуя).
Шаблоны: oak birch pine fir bush boulder stone flower mushroom crystal ruin hay cactus.
t="x" ТОЛЬКО дом/мост/статуя. Цвет дерева в p.leaf, не новый шаблон. Синие деревья: t:"oak" p.leaf:[0.15,0.35,0.95]. Glow: p.em 0.8-1.4.

КАРТА — ГЛАВНОЕ. Скульпт строго по словам промпта, НЕ копируй пример и НЕ ставь гору в центр по умолчанию.
UV: [0,0] ЮЗ, [0.5,0.5] центр, [1,0] ЮВ, [0,1] СЗ, [1,1] СВ.
«слева/запад» u=0.18  «справа/восток» u=0.82  «север» v=0.82  «юг» v=0.18  «центр» 0.5,0.5
«в углу» = один из [0.18,0.18]|[0.82,0.18]|[0.18,0.82]|[0.82,0.82]

t.st стиль базы, ОБЯЗАТЕЛЬНО один:
plains равнина  hills холмы  mountains гряды  canyon каньон  valley долина  island остров  dunes дюны  crater кратер
Луг/поле=plains. Пустыня=dunes. Горы/альпы=mountains. Остров=island. Каньон/ущелье=canyon. Кратер=crater.
t.amp 0.5-1.6 (горы 1.2-1.6, равнина 0.5-0.8). t.sc 18-80. t.sd уникальный.

t.f 2-5 фич, координаты СМЕЩЕНЫ, не все в центре.
k: mt гора {c:[u,v],r,h,aspect,rot}  md холм  pl плато {c,r,h}
   rd хребет {pts:[[u,v]...],w,h}  cn каньон {pts,w,dp}  vl долина {pts,w,dp}
   rv река {pts,w,dp}  lk озеро {c,r,dp}  bs впадина  cr кратер {c,r,dp,h}
«гора в центре» → st:mountains + {"k":"mt","c":[0.5,0.5],"r":0.24,"h":0.95}
«холмы слева» → st:hills + md c:[0.2,0.5]
«хребет с севера на юг» → rd pts:[[0.5,0.08],[0.52,0.5],[0.48,0.92]]
«река через карту» → rv pts от края до края. Вода ТОЛЬКО если в промпте есть река/озеро/пруд.
Гора h=0.75-1.1 r=0.16-0.3. Холм h=0.22-0.5. Каньон dp=0.45-0.75 w=0.08-0.16.

t.g градиент 0-255 под биом. tm grass,dirt,rock,snow 0-1.
a.td day. 5-8 пропов. Лес/поляна ОБЯЗАТЕЛЬНО густо: деревья k=20-32, кусты 16-28, цветы 24-40, камни 10-18. Дом k=1. Не ставь k=8. JSON без markdown.
"""

PROP_SYSTEM_PROMPT = r"""Ретро-RTS теххудожник. Painted-pixel как Warcraft 3. Один КАСТОМНЫЙ проп. ТОЛЬКО компактный JSON.

{"n":"cottage","g":[["box",[1.5,1.0,1.3],[0,0.5,0]],["con",[1.1,0.8,4],[0,1.35,0]],["box",[0.28,0.55,0.08],[0,0.35,0.66]],["box",[0.22,0.22,0.06],[0.38,0.72,0.66]],["cyl",[0.08,0.1,0.4,6],[0.45,1.5,-0.2]]],"fs":["varying vec3 vPosition;","varying vec3 vNormal;","float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5);}","float n2(vec2 p){vec2 i=floor(p);vec2 f=fract(p);f=f*f*(3.0-2.0*f);return mix(mix(hash(i),hash(i+vec2(1.0,0.0)),f.x),mix(hash(i+vec2(0.0,1.0)),hash(i+vec2(1.0,1.0)),f.x),f.y);}","void main(){ vec3 n=normalize(vNormal); float pl=step(0.5,fract(vPosition.y*7.0+n2(vPosition.xz*2.0)*0.2)); vec3 wood=mix(vec3(0.42,0.24,0.10),vec3(0.62,0.38,0.16),pl); float roof=step(1.05,vPosition.y); vec3 c=mix(wood,mix(vec3(0.55,0.16,0.12),vec3(0.72,0.24,0.14),fract(vPosition.x*5.0)),roof); float wrap=max(dot(n,normalize(vec3(0.46,0.84,0.26))),0.0)*0.62+0.38; float band=floor(wrap*5.0+0.35)/5.0; c*=mix(vec3(0.58,0.68,0.88),vec3(1.06,0.97,0.84),mix(wrap,band,0.55)); c=floor(c*20.0+0.5)/20.0; gl_FragColor=vec4(c,1.0); }"],"u":{"uA":[0.52,0.30,0.12]},"i":[1,"cl",[1.0,1.15]]}

g: 4-6 примитивов. Дом: box + крыша + дверь + окно + труба. Низ у y=0.
fs: painted pixel. Шум fbm/noise по world pos, мягкий wrap-light + лёгкие 5 полос, палитра floor(c*20)/20. Тёплый свет. БЕЗ pow(vec3), БЕЗ fresnel, БЕЗ gl_FragCoord dither. varying vPosition vNormal.
ls/lv только для кроны. i для дома=1. JSON валидный.
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
    "river": "river",
    "lk": "lake",
    "lake": "lake",
    "bs": "basin",
    "basin": "basin",
    "rd": "ridge",
    "ridge": "ridge",
    "pl": "plateau",
    "plateau": "plateau",
    "md": "mound",
    "mound": "mound",
    "hill": "mound",
    "mt": "mountain",
    "mountain": "mountain",
    "peak": "mountain",
    "гора": "mountain",
    "холм": "mound",
    "cn": "canyon",
    "canyon": "canyon",
    "каньон": "canyon",
    "vl": "valley",
    "valley": "valley",
    "долина": "valley",
    "cr": "crater",
    "crater": "crater",
    "кратер": "crater",
}
STYLE_ALIAS = {
    "plains": "plains", "plain": "plains", "равнина": "plains", "луг": "plains",
    "hills": "hills", "hill": "hills", "холмы": "hills",
    "mountains": "mountains", "mountain": "mountains", "горы": "mountains",
    "canyon": "canyon", "каньон": "canyon",
    "valley": "valley", "долина": "valley",
    "island": "island", "остров": "island",
    "dunes": "dunes", "desert": "dunes", "пустыня": "dunes", "дюны": "dunes",
    "crater": "crater", "кратер": "crater",
}
DIST_ALIAS = {
    "sc": "scattered",
    "fr": "forest",
    "cl": "cluster",
    "rv": "river_line",
    "scattered": "scattered",
    "forest": "forest",
    "cluster": "cluster",
    "river_line": "river_line",
}
VALID_DISTS = set(DIST_ALIAS.values())
CAT_ALIAS = {
    "veg": "vegetation",
    "str": "structure",
    "rk": "rock",
    "un": "unit_prop",
    "mag": "magic",
    "dec": "decoration",
    "vegetation": "vegetation",
    "structure": "structure",
    "rock": "rock",
    "unit_prop": "unit_prop",
    "magic": "magic",
    "decoration": "decoration",
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
            parsed = _parse_prop_row(item)
            if parsed:
                props.append(parsed)
        elif isinstance(item, dict):
            parsed = _parse_prop_obj(item)
            if parsed:
                props.append(parsed)
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
            "style": STYLE_ALIAS.get(str(terrain.get("st") or terrain.get("style") or "hills").lower(), "hills"),
            "amplitude": terrain.get("amp", terrain.get("amplitude", 1.0)),
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


def _parse_prop_row(item) -> dict | None:
    """[id, cat, count, dist, tpl, params] с устойчивостью к сдвигу полей."""
    name = item[0]
    rest = list(item[1:])
    category = "decoration"
    count = 18
    dist = "scattered"
    template = None
    params = {}

    if rest and isinstance(rest[0], str) and str(rest[0]).lower() in CAT_ALIAS:
        category = CAT_ALIAS[str(rest.pop(0)).lower()]
    if rest:
        try:
            count = int(rest[0])
            rest.pop(0)
        except (TypeError, ValueError):
            pass
    if rest and isinstance(rest[0], str) and str(rest[0]).lower() in DIST_ALIAS:
        dist = DIST_ALIAS[str(rest.pop(0)).lower()]
    elif rest and isinstance(rest[0], str) and str(rest[0]).lower() in CAT_ALIAS:
        rest.pop(0)
    if rest and isinstance(rest[0], str):
        template = rest.pop(0)
    if rest and isinstance(rest[0], dict):
        params = rest[0]

    if dist not in VALID_DISTS:
        dist = "scattered"
    entry = {
        "name": name,
        "category": category,
        "count": count,
        "distribution": dist,
    }
    if template not in (None, ""):
        entry["template"] = template
    if params:
        entry["params"] = params
        for key in ("bark", "leaf", "rock", "petal", "stem", "size", "moss", "em", "cap", "crystal", "hay"):
            if key in params:
                entry[key] = params[key]
    return entry


def _parse_prop_obj(item: dict) -> dict | None:
    name = item.get("n") or item.get("name")
    if not name:
        return None
    cat_raw = str(item.get("c") or item.get("category") or "dec").lower()
    dist_raw = str(item.get("d") or item.get("distribution") or "sc").lower()
    try:
        count = int(item.get("k") if item.get("k") is not None else item.get("count") or 14)
    except (TypeError, ValueError):
        count = 14
    template = item.get("t") or item.get("template") or item.get("tpl")
    params = item.get("p") if isinstance(item.get("p"), dict) else item.get("params") or {}
    dist = DIST_ALIAS.get(dist_raw, "scattered")
    if dist not in VALID_DISTS:
        dist = "scattered"
    entry = {
        "name": name,
        "category": CAT_ALIAS.get(cat_raw, "decoration"),
        "count": count,
        "distribution": dist,
    }
    if template not in (None, ""):
        entry["template"] = template
    if params:
        entry["params"] = params
        for key in ("bark", "leaf", "rock", "petal", "stem", "size", "moss", "em", "cap", "crystal", "hay"):
            if key in params:
                entry[key] = params[key]
    return entry


def _expand_feature(feat):
    if isinstance(feat, dict):
        kind = FEAT_ALIAS.get(str(feat.get("k") or feat.get("type") or ""), feat.get("type") or feat.get("k"))
        if not kind:
            return None
        item = {"type": kind}
        if kind in ("river", "ridge", "canyon", "valley"):
            item["points"] = feat.get("pts") or feat.get("points") or []
            item["width"] = feat.get("w", feat.get("width", 0.1 if kind in ("canyon", "valley") else 0.05))
            if kind in ("river", "canyon", "valley"):
                item["depth"] = feat.get("dp", feat.get("depth", 0.5 if kind != "river" else 0.4))
            else:
                item["height"] = feat.get("h", feat.get("height", 0.45))
        else:
            item["center"] = feat.get("c") or feat.get("center") or [0.5, 0.5]
            item["radius"] = feat.get("r", feat.get("radius", 0.18 if kind in ("mountain", "crater") else 0.12))
            if kind in ("lake", "basin", "crater"):
                item["depth"] = feat.get("dp", feat.get("depth", 0.4))
            if kind not in ("lake", "basin"):
                item["height"] = feat.get("h", feat.get("height", 0.85 if kind == "mountain" else 0.32))
            if feat.get("aspect") is not None:
                item["aspect"] = feat.get("aspect")
            if feat.get("rot") is not None:
                item["rot"] = feat.get("rot")
        return item
    if not isinstance(feat, (list, tuple)) or not feat:
        return None
    kind = FEAT_ALIAS.get(str(feat[0]), feat[0])
    item = {"type": kind}
    if kind in ("river", "ridge", "canyon", "valley"):
        item["points"] = feat[1] if len(feat) > 1 else []
        item["width"] = feat[2] if len(feat) > 2 else 0.05
        if kind in ("river", "canyon", "valley"):
            item["depth"] = feat[3] if len(feat) > 3 else 0.45
        else:
            item["height"] = feat[3] if len(feat) > 3 else 0.35
    else:
        item["center"] = feat[1] if len(feat) > 1 else [0.5, 0.5]
        item["radius"] = feat[2] if len(feat) > 2 else (0.2 if kind == "mountain" else 0.12)
        if kind in ("lake", "basin", "crater"):
            item["depth"] = feat[3] if len(feat) > 3 else 0.35
        if kind not in ("lake", "basin"):
            item["height"] = feat[3] if len(feat) > 3 else (0.8 if kind == "mountain" else 0.35)
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
        instances = inst if isinstance(inst, dict) else {"count": 18, "distribution": "scattered"}
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
        "Sculpt THIS prompt: pick t.st, place t.f with exact UV from words (left/right/north/south/center). "
        "Do not copy the sample mountain. p objects {n,c,k,d,t,p}. Unique t.sd. House t=x. Water only if prompt has water."
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
        "Build a unique mesh+material for THIS object. If house: walls+roof+door+window. Full fs shader."
    )
    n_props = max(1, len(world_meta.get("prop_list") or []))
    prop_tokens = max(3500, (SCENE_MAX_TOKENS - METADATA_MAX_TOKENS) // n_props)
    data = _chat(PROP_SYSTEM_PROMPT, user, chosen, prop_tokens, f"prop:{prop_spec.get('name')}")
    name = data.get("name") or prop_spec.get("name")
    data["name"] = name
    primitives = (data.get("geometry") or {}).get("primitives") or []
    shader = data.setdefault("shader", {})
    fragment = (shader.get("fragment") or "").strip()
    if len(primitives) < 3:
        raise AIGenerationError(f"Проп {name}: нужно 3-6 примитивов, получено {len(primitives)}")
    if len(fragment) < 40:
        shader["fragment"] = (
            "varying vec3 vPosition;\n"
            "varying vec3 vNormal;\n"
            "void main(){\n"
            "  vec3 n=normalize(vNormal);\n"
            "  float pl=step(0.5,fract(vPosition.y*8.0));\n"
            "  vec3 wood=mix(vec3(0.32,0.18,0.08),vec3(0.50,0.30,0.14),pl);\n"
            "  float roof=step(1.0,vPosition.y);\n"
            "  vec3 c=mix(wood,vec3(0.42,0.16,0.12),roof);\n"
            "  c*=0.55+0.45*max(dot(n,normalize(vec3(0.4,0.85,0.2))),0.0);\n"
            "  gl_FragColor=vec4(c,1.0);\n"
            "}"
        )
        log.warning("Custom prop %s: shader padded, mesh kept", name)
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
    from .templates import instantiate_prop, tint_spec_from_prompt, wants_custom

    prop_list = world_meta["prop_list"][:8]
    props = {}
    errors = []
    custom_specs = []
    started = time.perf_counter()

    for spec in prop_list:
        name = spec.get("name", "?")
        spec = tint_spec_from_prompt(spec, user_prompt)
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
                    log.warning("Custom prop failed %s: %s", name, exc)
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
