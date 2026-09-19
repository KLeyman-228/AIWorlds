"""Готовые пропы и ландшафтный материал. AI задаёт цвета/масштаб, код копирует меш."""
from __future__ import annotations

from copy import deepcopy

from .ai_client import STANDARD_VERTEX_SHADER

LEAF_VERTEX = """varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vPosition;
varying vec3 vWorldPos;
uniform float uTime;
void main() {
  vUv = uv;
  vNormal = normalize(normalMatrix * normal);
  vec3 p = position;
  float k = clamp(position.y * 0.45, 0.0, 1.0);
  p.x += sin(uTime * 1.5 + position.y * 3.0 + position.x * 2.0) * 0.05 * k;
  p.z += cos(uTime * 1.2 + position.x * 2.4 + position.z) * 0.04 * k;
  vPosition = p;
  vec4 wp = modelMatrix * vec4(p, 1.0);
  vWorldPos = wp.xyz;
  gl_Position = projectionMatrix * viewMatrix * wp;
}"""

BARK_FRAGMENT = """varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vPosition;
uniform vec3 uBark;
uniform vec3 uMoss;
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float n2(vec2 p){
  vec2 i = floor(p); vec2 f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(hash(i), hash(i+vec2(1.0,0.0)), f.x), mix(hash(i+vec2(0.0,1.0)), hash(i+vec2(1.0,1.0)), f.x), f.y);
}
void main() {
  vec3 n = normalize(vNormal);
  float ang = atan(vPosition.x, vPosition.z);
  float ridge = n2(vec2(ang * 6.0, vPosition.y * 1.2));
  float groove = step(0.72, n2(vec2(ang * 9.0, vPosition.y * 0.7)));
  float flake = n2(vec2(ang * 14.0, vPosition.y * 8.0));
  vec3 c = mix(uBark * 0.72, uBark * 1.15, flake);
  c *= 0.82 + 0.28 * ridge;
  c = mix(c, uBark * 0.45, groove * 0.7);
  float moss = (1.0 - clamp(vPosition.y * 0.7, 0.0, 1.0)) * step(0.5, n2(vPosition.xz * 8.0));
  c = mix(c, uMoss, moss * 0.65);
  c *= 0.55 + 0.45 * max(dot(n, normalize(vec3(0.4, 0.85, 0.2))), 0.0);
  c = floor(c * 8.0 + 0.5) / 8.0;
  gl_FragColor = vec4(c, 1.0);
}"""

LEAF_FRAGMENT = """varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vPosition;
uniform vec3 uLeaf;
uniform vec3 uLeafDark;
float hash(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
float n2(vec2 p){
  vec2 i = floor(p); vec2 f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(hash(i), hash(i+vec2(1.0,0.0)), f.x), mix(hash(i+vec2(0.0,1.0)), hash(i+vec2(1.0,1.0)), f.x), f.y);
}
void main() {
  vec3 n = normalize(vNormal);
  vec2 uv = vUv * 12.0 + vPosition.xz * 2.0;
  float clump = n2(uv) * 0.5 + n2(uv * 2.4 + 7.1) * 0.32 + n2(uv * 5.0) * 0.18;
  vec3 lite = uLeaf * 1.25;
  vec3 c = mix(uLeafDark, uLeaf, step(0.42, clump));
  c = mix(c, lite, step(0.72, clump));
  c = mix(c, uLeafDark * 0.45, step(0.82, n2(uv * 3.3)));
  c *= 0.55 + 0.45 * max(dot(n, normalize(vec3(0.35, 0.9, 0.2))), 0.0);
  c = floor(c * 8.0 + 0.5) / 8.0;
  gl_FragColor = vec4(c, 1.0);
}"""

ROCK_FRAGMENT = """varying vec3 vNormal;
varying vec3 vPosition;
uniform vec3 uRock;
uniform vec3 uMoss;
float hash(vec3 p){ return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
float n3(vec3 p){
  vec3 i = floor(p); vec3 f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(hash(i), hash(i + vec3(1.0, 1.0, 1.0)), (f.x+f.y+f.z)/3.0);
}
void main() {
  vec3 n = normalize(vNormal);
  vec3 c = uRock + (n3(vPosition * 16.0) - 0.5) * 0.12;
  float crack = 1.0 - smoothstep(0.0, 0.07, abs(n3(vPosition * 5.0) - 0.5));
  c = mix(c, uRock * 0.4, crack * 0.7);
  float moss = step(0.55, n.y) * step(0.45, n3(vPosition * 8.0));
  c = mix(c, uMoss, moss * 0.55);
  c *= 0.5 + 0.5 * max(dot(n, normalize(vec3(0.4, 0.85, 0.2))), 0.0);
  c = floor(c * 7.0 + 0.5) / 7.0;
  gl_FragColor = vec4(c, 1.0);
}"""

FLOWER_STEM = """varying vec3 vNormal;
varying vec3 vPosition;
uniform vec3 uStem;
void main() {
  float n = fract(sin(dot(floor(vPosition.xy * 18.0), vec2(12.9, 78.2))) * 43758.5);
  vec3 c = mix(uStem * 0.7, uStem, step(0.5, n));
  c *= 0.6 + 0.4 * max(dot(normalize(vNormal), normalize(vec3(0.4, 0.9, 0.2))), 0.0);
  gl_FragColor = vec4(c, 1.0);
}"""

FLOWER_PETAL = """varying vec2 vUv;
varying vec3 vNormal;
uniform vec3 uPetal;
void main() {
  float r = length(vUv - vec2(0.5)) * 2.0;
  float n = fract(sin(dot(floor(vUv * 16.0), vec2(26.7, 91.3))) * 24634.6);
  vec3 core = vec3(0.95, 0.78, 0.18);
  vec3 c = mix(core, uPetal, step(0.28, r));
  c = mix(c, uPetal * 1.2, step(0.65, n) * 0.4);
  c *= 0.7 + 0.3 * max(dot(normalize(vNormal), normalize(vec3(0.4, 0.9, 0.2))), 0.0);
  gl_FragColor = vec4(c, 1.0);
}"""

TERRAIN_FRAGMENT = """varying vec3 vNormal;
varying vec3 vWorldPos;
uniform vec3 uGrass;
uniform vec3 uDirt;
uniform vec3 uRock;
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float n2(vec2 p){
  vec2 i = floor(p); vec2 f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(hash(i), hash(i+vec2(1.0,0.0)), f.x), mix(hash(i+vec2(0.0,1.0)), hash(i+vec2(1.0,1.0)), f.x), f.y);
}
void main() {
  vec3 n = normalize(vNormal);
  float h = clamp(vWorldPos.y / 4.0, 0.0, 1.0);
  float slope = 1.0 - clamp(n.y, 0.0, 1.0);
  float patches = n2(vWorldPos.xz * 2.4);
  float tufts = n2(vWorldPos.xz * 9.0);
  float blades = step(0.52, n2(vWorldPos.xz * 28.0));
  vec3 sand = mix(uDirt, vec3(0.55, 0.46, 0.24), 0.45);
  vec3 grassB = uGrass * 1.25;
  vec3 dry = mix(uGrass, uDirt, 0.45);
  vec3 c = mix(uDirt, sand, step(0.12, h));
  c = mix(c, mix(uGrass, grassB, step(0.5, patches)), step(0.22, h));
  c = mix(c, dry, step(0.62, h));
  c = mix(c, uRock, step(0.82, h));
  c = mix(c, uGrass * 0.75, blades * (1.0 - step(0.7, h)) * 0.45);
  c = mix(c, uDirt, step(0.62, tufts) * 0.2);
  c = mix(c, uRock, smoothstep(0.25, 0.55, slope));
  c *= 0.55 + 0.45 * max(dot(n, normalize(vec3(0.4, 0.85, 0.2))), 0.0);
  c = floor(c * 8.0 + 0.5) / 8.0;
  gl_FragColor = vec4(c, 1.0);
}"""

OAK_GEO = {
    "primitives": [
        {"type": "cylinder", "params": {"rTop": 0.14, "rBottom": 0.2, "height": 1.5, "segments": 7}, "position": [0.0, 0.75, 0.0]},
        {"type": "sphere", "params": {"radius": 0.85, "widthSegments": 7, "heightSegments": 5}, "position": [0.0, 1.9, 0.0]},
        {"type": "sphere", "params": {"radius": 0.6, "widthSegments": 6, "heightSegments": 5}, "position": [0.5, 1.55, 0.15]},
        {"type": "sphere", "params": {"radius": 0.55, "widthSegments": 6, "heightSegments": 5}, "position": [-0.45, 1.6, -0.1]},
        {"type": "sphere", "params": {"radius": 0.5, "widthSegments": 6, "heightSegments": 4}, "position": [0.1, 2.4, -0.1]},
    ]
}
BIRCH_GEO = {
    "primitives": [
        {"type": "cylinder", "params": {"rTop": 0.09, "rBottom": 0.14, "height": 1.9, "segments": 7}, "position": [0.0, 0.95, 0.0]},
        {"type": "cylinder", "params": {"rTop": 0.05, "rBottom": 0.03, "height": 0.7, "segments": 5}, "position": [0.28, 1.55, 0.1]},
        {"type": "sphere", "params": {"radius": 0.55, "widthSegments": 7, "heightSegments": 5}, "position": [0.0, 2.1, 0.0]},
        {"type": "sphere", "params": {"radius": 0.4, "widthSegments": 6, "heightSegments": 4}, "position": [0.32, 1.8, 0.15]},
        {"type": "sphere", "params": {"radius": 0.36, "widthSegments": 6, "heightSegments": 4}, "position": [-0.22, 1.85, -0.12]},
    ]
}
BUSH_GEO = {
    "primitives": [
        {"type": "cylinder", "params": {"rTop": 0.05, "rBottom": 0.08, "height": 0.45, "segments": 6}, "position": [0.0, 0.22, 0.0]},
        {"type": "cylinder", "params": {"rTop": 0.04, "rBottom": 0.06, "height": 0.35, "segments": 6}, "position": [0.14, 0.18, 0.06], "rotation": [0.0, 0.0, 20.0]},
        {"type": "cylinder", "params": {"rTop": 0.04, "rBottom": 0.06, "height": 0.32, "segments": 6}, "position": [-0.13, 0.16, -0.06], "rotation": [17.0, 0.0, -17.0]},
        {"type": "sphere", "params": {"radius": 0.42, "widthSegments": 8, "heightSegments": 6}, "position": [0.0, 0.62, 0.0]},
        {"type": "sphere", "params": {"radius": 0.32, "widthSegments": 7, "heightSegments": 5}, "position": [0.28, 0.5, 0.12]},
        {"type": "sphere", "params": {"radius": 0.3, "widthSegments": 7, "heightSegments": 5}, "position": [-0.26, 0.46, -0.1]},
    ]
}
BOULDER_GEO = {
    "primitives": [
        {"type": "sphere", "params": {"radius": 0.55, "widthSegments": 7, "heightSegments": 5}, "position": [0.0, 0.32, 0.0]},
        {"type": "sphere", "params": {"radius": 0.38, "widthSegments": 6, "heightSegments": 4}, "position": [0.32, 0.22, 0.14]},
        {"type": "sphere", "params": {"radius": 0.32, "widthSegments": 6, "heightSegments": 4}, "position": [-0.28, 0.2, -0.12]},
        {"type": "sphere", "params": {"radius": 0.22, "widthSegments": 5, "heightSegments": 4}, "position": [0.08, 0.12, 0.28]},
    ]
}
FLOWER_GEO = {
    "primitives": [
        {"type": "cylinder", "params": {"rTop": 0.03, "rBottom": 0.045, "height": 0.5, "segments": 5}, "position": [0.0, 0.25, 0.0]},
        {"type": "sphere", "params": {"radius": 0.05, "widthSegments": 5, "heightSegments": 4}, "position": [0.08, 0.18, 0.02]},
        {"type": "sphere", "params": {"radius": 0.06, "widthSegments": 6, "heightSegments": 4}, "position": [0.0, 0.54, 0.0]},
        {"type": "sphere", "params": {"radius": 0.075, "widthSegments": 5, "heightSegments": 4}, "position": [0.1, 0.52, 0.0]},
        {"type": "sphere", "params": {"radius": 0.075, "widthSegments": 5, "heightSegments": 4}, "position": [-0.1, 0.52, 0.0]},
        {"type": "sphere", "params": {"radius": 0.075, "widthSegments": 5, "heightSegments": 4}, "position": [0.0, 0.52, 0.1]},
    ]
}

PROP_TEMPLATES = {
    "oak": {"kind": "tree", "geometry": OAK_GEO, "defaults": {"bark": [0.32, 0.18, 0.08], "leaf": [0.18, 0.46, 0.10], "leaf_dark": [0.08, 0.26, 0.05], "moss": [0.15, 0.30, 0.08]}},
    "birch": {"kind": "tree", "geometry": BIRCH_GEO, "defaults": {"bark": [0.86, 0.82, 0.74], "leaf": [0.22, 0.48, 0.12], "leaf_dark": [0.08, 0.22, 0.05], "moss": [0.18, 0.32, 0.10]}},
    "pine": {"kind": "tree", "geometry": OAK_GEO, "defaults": {"bark": [0.28, 0.18, 0.10], "leaf": [0.10, 0.32, 0.12], "leaf_dark": [0.05, 0.18, 0.07], "moss": [0.12, 0.24, 0.08]}},
    "bush": {"kind": "tree", "geometry": BUSH_GEO, "defaults": {"bark": [0.30, 0.19, 0.09], "leaf": [0.16, 0.44, 0.10], "leaf_dark": [0.07, 0.22, 0.05], "moss": [0.14, 0.28, 0.07]}},
    "boulder": {"kind": "rock", "geometry": BOULDER_GEO, "defaults": {"rock": [0.46, 0.44, 0.41], "moss": [0.18, 0.34, 0.10]}},
    "stone": {"kind": "rock", "geometry": BOULDER_GEO, "defaults": {"rock": [0.50, 0.46, 0.40], "moss": [0.16, 0.30, 0.10]}},
    "flower": {"kind": "flower", "geometry": FLOWER_GEO, "defaults": {"petal": [0.86, 0.36, 0.48], "stem": [0.14, 0.40, 0.10]}},
}

TEMPLATE_ALIASES = {
    "oak": "oak", "tree": "oak", "trees": "oak",
    "birch": "birch", "pine": "pine", "fir": "pine", "spruce": "pine",
    "bush": "bush", "shrub": "bush",
    "boulder": "boulder", "rock": "boulder", "stone": "stone", "rocks": "boulder",
    "flower": "flower", "flowers": "flower",
}

TERRAIN_TEMPLATE_UNIFORMS = {
    "uGrass": {"type": "vec3", "value": [0.18, 0.46, 0.12]},
    "uDirt": {"type": "vec3", "value": [0.28, 0.20, 0.10]},
    "uRock": {"type": "vec3", "value": [0.40, 0.38, 0.34]},
    "uTime": {"type": "float", "value": 0},
}


def resolve_template_id(name: str, explicit=None) -> str | None:
    if explicit:
        key = str(explicit).lower().strip()
        if key in PROP_TEMPLATES:
            return key
        return TEMPLATE_ALIASES.get(key)
    lowered = str(name or "").lower()
    for alias, tid in TEMPLATE_ALIASES.items():
        if alias in lowered:
            return tid
    return None


def _rgb01(value, fallback):
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return list(fallback)
    nums = [float(value[0]), float(value[1]), float(value[2])]
    if max(nums) > 1.5:
        nums = [n / 255.0 for n in nums]
    return [max(0.0, min(1.0, n)) for n in nums]


def _scale_geometry(geometry: dict, scale: float) -> dict:
    geo = deepcopy(geometry)
    s = max(0.4, min(2.2, float(scale or 1.0)))
    if abs(s - 1.0) < 0.02:
        return geo
    for prim in geo.get("primitives") or []:
        params = prim.setdefault("params", {})
        for key in ("width", "height", "depth", "radius", "rTop", "rBottom", "tube"):
            if key in params:
                params[key] = float(params[key]) * s
        if prim.get("position"):
            prim["position"] = [float(v) * s for v in prim["position"]]
    return geo


def instantiate_prop(spec: dict) -> dict:
    tid = resolve_template_id(spec.get("name"), spec.get("template") or spec.get("tpl"))
    if not tid:
        raise KeyError("no template")
    tmpl = PROP_TEMPLATES[tid]
    defaults = tmpl["defaults"]
    params = spec.get("params") if isinstance(spec.get("params"), dict) else {}
    geo_scale = spec.get("size") or spec.get("height") or params.get("size") or 1.0
    uniforms = {"uTime": {"type": "float", "value": 0}}
    shader = {
        "vertex": STANDARD_VERTEX_SHADER,
        "uniforms": uniforms,
    }
    if tmpl["kind"] == "tree":
        bark = _rgb01(spec.get("bark") or params.get("bark"), defaults["bark"])
        leaf = _rgb01(spec.get("leaf") or params.get("leaf"), defaults["leaf"])
        leaf_dark = _rgb01(spec.get("leaf_dark") or params.get("leaf_dark"), defaults["leaf_dark"])
        moss = _rgb01(spec.get("moss") or params.get("moss"), defaults["moss"])
        uniforms.update({
            "uBark": {"type": "vec3", "value": bark},
            "uLeaf": {"type": "vec3", "value": leaf},
            "uLeafDark": {"type": "vec3", "value": leaf_dark},
            "uMoss": {"type": "vec3", "value": moss},
        })
        shader["fragment"] = BARK_FRAGMENT
        shader["leaf_fragment"] = LEAF_FRAGMENT
        shader["leaf_vertex"] = LEAF_VERTEX
    elif tmpl["kind"] == "rock":
        rock = _rgb01(spec.get("rock") or spec.get("color") or params.get("rock"), defaults["rock"])
        moss = _rgb01(spec.get("moss") or params.get("moss"), defaults["moss"])
        uniforms.update({
            "uRock": {"type": "vec3", "value": rock},
            "uMoss": {"type": "vec3", "value": moss},
        })
        shader["fragment"] = ROCK_FRAGMENT
    else:
        petal = _rgb01(spec.get("petal") or spec.get("color") or params.get("petal"), defaults["petal"])
        stem = _rgb01(spec.get("stem") or params.get("stem"), defaults["stem"])
        uniforms.update({
            "uPetal": {"type": "vec3", "value": petal},
            "uStem": {"type": "vec3", "value": stem},
        })
        shader["fragment"] = FLOWER_STEM
        shader["leaf_fragment"] = FLOWER_PETAL
        shader["leaf_vertex"] = LEAF_VERTEX

    instances = spec.get("instances")
    if not isinstance(instances, dict):
        instances = {
            "count": int(spec.get("count") or 8),
            "distribution": spec.get("distribution") or "scattered",
            "scale_range": spec.get("scale_range") or [0.8, 1.2],
        }
    return {
        "name": spec.get("name") or tid,
        "template": tid,
        "geometry": _scale_geometry(tmpl["geometry"], geo_scale),
        "shader": shader,
        "instances": instances,
        "category": spec.get("category"),
    }


def instantiate_terrain_shader(params=None) -> dict:
    p = params if isinstance(params, dict) else {}
    uniforms = deepcopy(TERRAIN_TEMPLATE_UNIFORMS)
    if p.get("grass"):
        uniforms["uGrass"]["value"] = _rgb01(p.get("grass"), uniforms["uGrass"]["value"])
    if p.get("dirt"):
        uniforms["uDirt"]["value"] = _rgb01(p.get("dirt"), uniforms["uDirt"]["value"])
    if p.get("rock"):
        uniforms["uRock"]["value"] = _rgb01(p.get("rock"), uniforms["uRock"]["value"])
    return {
        "vertex": STANDARD_VERTEX_SHADER,
        "fragment": TERRAIN_FRAGMENT,
        "uniforms": uniforms,
    }


def wants_custom(spec: dict) -> bool:
    flag = spec.get("custom") or spec.get("mode") or spec.get("kind")
    tpl = str(spec.get("template") or spec.get("tpl") or "").lower()
    if str(flag).lower() in ("custom", "gen", "1", "true", "yes") or tpl in ("x", "custom", "gen"):
        return True
    if resolve_template_id(spec.get("name"), spec.get("template") or spec.get("tpl")):
        return False
    return True
