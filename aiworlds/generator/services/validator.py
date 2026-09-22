"""
Жёсткая проверка плана AI. Нет подмены мира заглушкой:
битые поля чинятся только нормализацией чисел/шейдерных uniforms.
Если нет пропсов, градиента или шейдеров — ошибка.
"""
from __future__ import annotations

import logging

from .ai_client import POST_VERTEX_SHADER, STANDARD_VERTEX_SHADER

log = logging.getLogger(__name__)

ALLOWED_PRIMITIVES = {
    "box",
    "sphere",
    "cylinder",
    "cone",
    "torus",
    "octahedron",
    "icosahedron",
    "dodecahedron",
    "tetrahedron",
    "plane",
}


class PlanValidationError(ValueError):
    """План мира непригоден для рендера."""


def validate_plan(plan: dict) -> dict:
    if not isinstance(plan, dict):
        raise PlanValidationError("План мира не является объектом")

    name = (plan.get("world_name") or "").strip()
    if not name:
        raise PlanValidationError("Нет world_name")
    plan["world_name"] = name
    plan["description"] = (plan.get("description") or "").strip()

    plan["terrain"] = _validate_terrain(plan.get("terrain"))
    plan["atmosphere"] = _validate_atmosphere(plan.get("atmosphere"))
    plan["post_process"] = _validate_post_process(plan.get("post_process"))
    return plan


def _validate_terrain(terrain) -> dict:
    if not isinstance(terrain, dict):
        raise PlanValidationError("Нет terrain от AI")

    octaves = terrain.get("octaves")
    try:
        octaves = int(octaves)
    except (TypeError, ValueError):
        raise PlanValidationError("terrain.octaves должен быть целым") from None
    terrain["octaves"] = max(1, min(8, octaves))

    scale = terrain.get("scale")
    try:
        scale = float(scale)
    except (TypeError, ValueError):
        raise PlanValidationError("terrain.scale должен быть числом") from None
    if scale <= 0:
        raise PlanValidationError("terrain.scale должен быть > 0")
    terrain["scale"] = scale

    seed = terrain.get("seed")
    try:
        terrain["seed"] = int(seed)
    except (TypeError, ValueError):
        raise PlanValidationError("terrain.seed должен быть целым") from None

    from .terrain import TERRAIN_STYLES
    from .ai_client import STYLE_ALIAS

    style = STYLE_ALIAS.get(str(terrain.get("style") or "hills").lower(), "hills")
    terrain["style"] = style if style in TERRAIN_STYLES else "hills"
    terrain["amplitude"] = _clamped(terrain.get("amplitude"), 0.45, 1.8, 1.0)

    terrain["color_gradient"] = _clean_gradient(
        terrain.get("color_gradient"),
        terrain.get("material"),
    )
    terrain["features"] = _validate_features(terrain.get("features"))
    terrain["water_level"] = _optional_float(terrain.get("water_level"), 0.0, 1.0)
    shader = terrain.get("shader")
    if isinstance(shader, dict) and (
        shader.get("fragment") or shader.get("fragment_lines")
    ):
        try:
            terrain["shader"] = _validate_shader(shader, is_post=False)
        except PlanValidationError:
            terrain.pop("shader", None)
    elif "shader" in terrain:
        terrain.pop("shader", None)
    return terrain


def _rgb01_to_255(value, fallback):
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None if fallback is None else list(fallback)
    nums = []
    for item in value[:3]:
        while isinstance(item, (list, tuple)) and item:
            item = item[0]
        try:
            nums.append(float(item))
        except (TypeError, ValueError):
            return list(fallback)
    if max(nums) <= 1.5:
        nums = [n * 255.0 for n in nums]
    return [max(0, min(255, int(round(n)))) for n in nums]


def _parse_gradient_point(point):
    if isinstance(point, dict):
        height = point.get("height")
        color = point.get("color")
    elif isinstance(point, (list, tuple)) and len(point) >= 2:
        height, color = point[0], point[1]
    else:
        return None
    while isinstance(height, (list, tuple)) and height:
        height = height[0]
    try:
        height = float(height)
    except (TypeError, ValueError):
        return None
    rgb = _rgb01_to_255(color, None)
    if rgb is None or len(rgb) < 3:
        return None
    return {"height": max(0.0, min(1.0, height)), "color": rgb}


def _gradient_from_material(material) -> list:
    mat = material if isinstance(material, dict) else {}
    dirt = _rgb01_to_255(mat.get("dirt") or mat.get("sand") or mat.get("mud"), [82, 56, 26])
    grass = _rgb01_to_255(mat.get("grass") or mat.get("dry"), [46, 117, 31])
    rock = _rgb01_to_255(mat.get("rock"), [107, 102, 92])
    snow = _rgb01_to_255(mat.get("snow") or mat.get("rock"), [209, 214, 219])
    return [
        {"height": 0.0, "color": dirt},
        {"height": 0.28, "color": grass},
        {"height": 0.62, "color": grass},
        {"height": 0.82, "color": rock},
        {"height": 1.0, "color": snow},
    ]


def _clean_gradient(gradient, material) -> list:
    cleaned = []
    if isinstance(gradient, list):
        for point in gradient:
            parsed = _parse_gradient_point(point)
            if parsed:
                cleaned.append(parsed)
    if len(cleaned) >= 2:
        return cleaned
    log.warning("color_gradient missing, using terrain.material")
    return _gradient_from_material(material)


def _optional_float(value, lo, hi):
    if value is None:
        return None
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return None


def _validate_features(features) -> list:
    if not features:
        return []
    if not isinstance(features, list):
        return []
    from .terrain import FEATURE_TYPES

    cleaned = []
    for feat in features[:10]:
        if not isinstance(feat, dict):
            continue
        kind = str(feat.get("type") or "").lower()
        if kind not in FEATURE_TYPES:
            continue
        item = {"type": kind}
        if kind in ("river", "ridge", "canyon", "valley"):
            points = _uv_points(feat.get("points"), min_count=2)
            if not points:
                continue
            item["points"] = points
            item["width"] = _clamped(feat.get("width"), 0.02, 0.28, 0.1 if kind in ("canyon", "valley") else 0.06)
            if kind == "ridge":
                item["height"] = _clamped(feat.get("height"), 0.15, 1.1, 0.5)
            else:
                item["depth"] = _clamped(feat.get("depth"), 0.15, 0.95, 0.55 if kind != "river" else 0.48)
        else:
            item["center"] = _uv_pair(feat.get("center"), [0.5, 0.5])
            item["radius"] = _clamped(
                feat.get("radius"),
                0.04,
                0.6,
                0.22 if kind in ("mountain", "crater") else 0.14,
            )
            if kind in ("lake", "basin"):
                item["depth"] = _clamped(feat.get("depth"), 0.15, 0.9, 0.45)
            elif kind == "crater":
                item["depth"] = _clamped(feat.get("depth"), 0.2, 0.9, 0.48)
                item["height"] = _clamped(feat.get("height"), 0.08, 0.6, 0.28)
            elif kind == "plateau":
                item["height"] = _clamped(feat.get("height"), 0.12, 0.9, 0.4)
                item["falloff"] = _clamped(feat.get("falloff"), 0.01, 0.2, 0.06)
            elif kind == "mountain":
                item["height"] = _clamped(feat.get("height"), 0.4, 1.25, 0.85)
            else:
                item["height"] = _clamped(feat.get("height"), 0.12, 0.85, 0.38)
            item["aspect"] = _clamped(feat.get("aspect"), 0.45, 2.4, 1.0)
            item["rot"] = _clamped(feat.get("rot"), -180.0, 180.0, 0.0)
        cleaned.append(item)
    return cleaned


def _uv_num(value, default=0.5) -> float:
    while isinstance(value, (list, tuple)) and value:
        value = value[0]
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _uv_pair(value, default=None) -> list[float]:
    fallback = default or [0.5, 0.5]
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return [_uv_num(value[0], fallback[0]), _uv_num(value[1], fallback[1])]
    if isinstance(value, (list, tuple)) and len(value) == 1:
        return _uv_pair(value[0], fallback)
    return list(fallback)


def _uv_points(points, min_count=2):
    if not isinstance(points, list):
        return []
    cleaned = []
    for pt in points[:12]:
        pair = _uv_pair(pt, None)
        if pair is None:
            continue
        cleaned.append(pair)
    return cleaned if len(cleaned) >= min_count else []


def _clamped(value, lo, hi, default):
    while isinstance(value, (list, tuple)) and value:
        value = value[0]
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return default


def _validate_atmosphere(atmo) -> dict:
    if not isinstance(atmo, dict):
        raise PlanValidationError("Нет atmosphere от AI")
    for key in ("fog_color", "sky_color", "sun_color", "ambient_color"):
        atmo[key] = _rgb(atmo.get(key), key)
    try:
        density = float(atmo.get("fog_density"))
    except (TypeError, ValueError):
        raise PlanValidationError("fog_density должен быть числом") from None
    atmo["fog_density"] = max(0.001, min(0.04, density))
    time_of_day = str(atmo.get("time_of_day") or "day").lower()
    if time_of_day not in ("day", "sunset", "night"):
        time_of_day = "day"
    atmo["time_of_day"] = time_of_day
    atmo["clouds"] = bool(atmo.get("clouds", True))
    if time_of_day == "day":
        sky = atmo["sky_color"]
        if sky[0] > sky[2] + 15:
            atmo["sky_color"] = [135, 185, 235]
            atmo["fog_color"] = [170, 200, 230]
    return atmo


def _rgb(value, field: str) -> list[int]:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        raise PlanValidationError(f"{field} должен быть RGB-массивом")
    try:
        return [max(0, min(255, int(v))) for v in value[:3]]
    except (TypeError, ValueError) as exc:
        raise PlanValidationError(f"{field} содержит нечисла") from exc


def validate_and_place_props(props, seed: int, heightmap=None, features=None, water_level=None) -> dict:
    """Нормализует пропы и ставит инстансы на heightmap."""
    if not isinstance(props, dict) or not props:
        raise PlanValidationError("AI не вернул ни одного пропа")

    from .instances import place_instances

    cleaned = {}
    for name, prop in props.items():
        if not isinstance(prop, dict):
            log.warning("Skip prop %s: not an object", name)
            continue
        if _is_ground_prop(name, prop.get("geometry")):
            log.warning("Skip prop %s: looks like a ground slab", name)
            continue
        geometry = _normalize_geometry(prop.get("geometry"), name=name)
        if len(geometry["primitives"]) < 1:
            log.warning("Skip prop %s: no primitives", name)
            continue
        try:
            shader = _validate_shader(prop.get("shader"), is_post=False)
        except PlanValidationError as exc:
            log.warning("Skip prop %s: %s", name, exc)
            continue

        instances = prop.get("instances")
        if isinstance(instances, list) and instances:
            placed = _snap_instances(
                instances[: _max_count_for(name, prop)],
                heightmap,
                features=features,
                water_level=water_level,
            )
        else:
            rule = instances if isinstance(instances, dict) else {}
            if "count" not in rule:
                rule["count"] = _default_count_for(name, prop)
            else:
                try:
                    rule["count"] = max(int(rule["count"]), _min_count_for(name, prop))
                except (TypeError, ValueError):
                    rule["count"] = _default_count_for(name, prop)
            rule["count"] = min(int(rule["count"]), _max_count_for(name, prop))
            size = prop.get("size") or (prop.get("params") or {}).get("size")
            if size is not None and "scale_range" not in rule:
                try:
                    s = max(0.25, min(8.0, float(size)))
                    rule["scale_range"] = [s * 0.88, s * 1.12]
                except (TypeError, ValueError):
                    pass
            try:
                placed = place_instances(
                    rule,
                    seed=seed + len(name),
                    heightmap=heightmap,
                    features=features,
                    water_level=water_level,
                    keep_dry=True,
                )
            except ValueError as exc:
                log.warning("Skip prop %s: %s", name, exc)
                continue

        cleaned[name] = {
            "name": name,
            "geometry": geometry,
            "shader": shader,
            "instances": placed,
        }

    if not cleaned:
        raise PlanValidationError("Все пропсы отбракованы: нет валидной геометрии/шейдеров")
    return cleaned


def _snap_instances(instances: list, heightmap, features=None, water_level=None) -> list:
    from .terrain import HEIGHT_SCALE, river_clearance_uv, sample_height_uv, world_to_uv

    placed = []
    wet_cut = None if water_level is None else float(water_level) + 0.045
    for inst in instances:
        if not isinstance(inst, dict):
            continue
        pos = list(inst.get("position") or [0, 0, 0])
        if len(pos) < 3:
            continue
        x, z = float(pos[0]), float(pos[2])
        u, v = world_to_uv(x, z)
        y_norm = sample_height_uv(heightmap, u, v) if heightmap is not None else 0.0
        if wet_cut is not None and y_norm <= wet_cut:
            continue
        clearance = river_clearance_uv(u, v, features)
        if clearance is not None and clearance < 1.35:
            continue
        item = dict(inst)
        item["position"] = [x, y_norm * HEIGHT_SCALE, z]
        placed.append(item)
    return placed


def _normalize_geometry(geometry, name: str = "") -> dict:
    if not isinstance(geometry, dict):
        return {"primitives": []}
    raw = geometry.get("primitives") or []
    primitives = []
    for prim in raw:
        if not isinstance(prim, dict):
            continue
        ptype = str(prim.get("type") or "").lower()
        if ptype not in ALLOWED_PRIMITIVES or ptype == "plane":
            continue
        params = prim.get("params")
        if not isinstance(params, dict):
            params = {
                k: v
                for k, v in prim.items()
                if k not in ("type", "position", "rotation", "scale", "params")
            }
        params = _clamp_prim_params(ptype, params, allow_building=_looks_like_building(name))
        if _is_huge_prim(ptype, params) and ptype == "plane":
            continue
        item = {"type": ptype, "params": params}
        if prim.get("position"):
            item["position"] = _vec3(prim["position"])
        if prim.get("rotation"):
            item["rotation"] = _vec3(prim["rotation"])
        if prim.get("scale") is not None:
            item["scale"] = prim["scale"]
        primitives.append(item)
    return _ground_geometry({"primitives": primitives})


def _prim_scale_y(prim) -> float:
    scale = prim.get("scale")
    if isinstance(scale, (list, tuple)) and len(scale) >= 2:
        try:
            return abs(float(scale[1]))
        except (TypeError, ValueError):
            return 1.0
    if isinstance(scale, (int, float)):
        return abs(float(scale))
    return 1.0


def _prim_half_height(prim) -> float:
    ptype = str(prim.get("type") or "").lower()
    params = prim.get("params") if isinstance(prim.get("params"), dict) else {}
    sy = _prim_scale_y(prim)

    def num(*keys, default=0.5):
        for key in keys:
            if key in params:
                try:
                    return abs(float(params[key]))
                except (TypeError, ValueError):
                    continue
        return default

    if ptype in ("cylinder", "cone", "box"):
        return num("height", default=1.0) * 0.5 * sy
    if ptype == "torus":
        return (num("radius", default=0.5) + num("tube", default=0.2)) * sy
    return num("radius", default=0.5) * sy


def _ground_geometry(geometry: dict) -> dict:
    """Сдвигает проп так, чтобы низ меша был на y=0, а не висел в воздухе."""
    prims = geometry.get("primitives") or []
    bottoms = []
    for prim in prims:
        pos = prim.get("position") or [0.0, 0.0, 0.0]
        if not isinstance(pos, (list, tuple)) or len(pos) < 3:
            pos = [0.0, 0.0, 0.0]
        bottoms.append(float(pos[1]) - _prim_half_height(prim))
    if not bottoms:
        return geometry
    shift = -min(bottoms) - 0.03
    if abs(shift) < 0.001:
        return geometry
    for prim in prims:
        pos = list(prim.get("position") or [0.0, 0.0, 0.0])
        while len(pos) < 3:
            pos.append(0.0)
        pos[1] = float(pos[1]) + shift
        prim["position"] = pos
    return geometry


def _looks_like_building(name) -> bool:
    lowered = str(name or "").lower()
    return any(
        word in lowered
        for word in (
            "house", "home", "hut", "cabin", "cottage", "barn", "mill", "tower",
            "shack", "shed", "temple", "church", "дом", "домик", "хижина", "изба",
            "башня", "мельница", "сарай",
        )
    )


def _is_ground_prop(name, geometry) -> bool:
    lowered = str(name or "").lower()
    if any(word in lowered for word in ("house", "hut", "cabin", "cottage", "barn", "tower", "дом", "хижина", "изба")):
        return False
    if any(word in lowered for word in ("glade", "ground", "terrain", "floor", "patch", "meadow", "field", "поляна", "земля")):
        return True
    raw = (geometry or {}).get("primitives") or []
    vertical = 0
    slabs = 0
    for prim in raw:
        if not isinstance(prim, dict):
            continue
        ptype = str(prim.get("type") or "").lower()
        params = prim.get("params") if isinstance(prim.get("params"), dict) else prim
        if ptype == "plane":
            slabs += 1
            continue
        h = float(params.get("height") or params.get("radius") or 0)
        w = float(params.get("width") or 0)
        d = float(params.get("depth") or 0)
        if ptype == "box" and (w >= 3.5 or d >= 3.5) and h <= 0.45:
            slabs += 1
        elif h >= 0.6 or ptype in ("cylinder", "cone", "sphere"):
            vertical += 1
    return slabs > 0 and vertical == 0


def _is_building_prop(name, prop=None) -> bool:
    lowered = str(name or "").lower()
    tmpl = str((prop or {}).get("template") or "").lower()
    if tmpl in ("x", "custom", "gen"):
        return _looks_like_building(name)
    return _looks_like_building(name)


def _min_count_for(name, prop) -> int:
    if _is_building_prop(name, prop):
        return 1
    lowered = str(name or "").lower()
    category = str((prop or {}).get("category") or "").lower()
    tmpl = str((prop or {}).get("template") or "").lower()
    if tmpl in ("flower", "bush") or "flower" in lowered or "bush" in lowered:
        return 22
    if tmpl in ("oak", "birch", "pine", "fir") or any(w in lowered for w in ("tree", "oak", "pine", "birch", "fir", "ель", "ёлка")):
        return 18
    if tmpl in ("boulder", "stone", "mushroom") or any(w in lowered for w in ("rock", "stone", "boulder", "mushroom")):
        return 10
    if category in ("vegetation", "veg"):
        return 16
    return 1


def _default_count_for(name, prop) -> int:
    if _is_building_prop(name, prop):
        return 1
    return min(_max_count_for(name, prop), _min_count_for(name, prop) + 6)


def _max_count_for(name, prop) -> int:
    if _is_building_prop(name, prop):
        return 3
    lowered = str(name or "").lower()
    category = str((prop or {}).get("category") or "").lower()
    tmpl = str((prop or {}).get("template") or "").lower()
    if tmpl == "flower" or "flower" in lowered or "grass" in lowered or category in ("decoration", "dec"):
        return 48
    if tmpl == "bush" or "bush" in lowered:
        return 36
    if tmpl in ("oak", "birch", "pine", "fir") or any(word in lowered for word in ("tree", "oak", "pine", "birch", "fir", "ель", "ёлка")):
        return 36
    if any(word in lowered for word in ("rock", "stone", "boulder", "mushroom")):
        return 24
    return 20


def _clamp_prim_params(ptype: str, params: dict, allow_building: bool = False) -> dict:
    limits = {
        "box": {"width": 4.5, "height": 3.6, "depth": 4.5} if allow_building else {"width": 1.8, "height": 2.4, "depth": 1.8},
        "sphere": {"radius": 1.6} if allow_building else {"radius": 1.1},
        "cylinder": {"rTop": 1.2, "rBottom": 1.4, "height": 3.4} if allow_building else {"rTop": 0.7, "rBottom": 0.9, "height": 2.2},
        "cone": {"radius": 2.2, "height": 2.8} if allow_building else {"radius": 1.2, "height": 2.2},
        "torus": {"radius": 0.8, "tube": 0.25},
        "octahedron": {"radius": 0.9},
        "icosahedron": {"radius": 0.9},
        "dodecahedron": {"radius": 0.9},
        "tetrahedron": {"radius": 0.9},
        "plane": {"width": 1.2, "height": 1.2},
    }
    capped = dict(params or {})
    for key, max_v in limits.get(ptype, {}).items():
        if key in capped:
            try:
                val = float(capped[key])
            except (TypeError, ValueError):
                continue
            if val > max_v:
                capped[key] = max_v
    return capped


def _is_huge_prim(ptype: str, params: dict) -> bool:
    if ptype == "box":
        return float(params.get("width") or 0) >= 3.5 or float(params.get("depth") or 0) >= 3.5
    if ptype == "plane":
        return True
    return False


def _vec3(value) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return [0.0, 0.0, 0.0]
    return [float(value[0]), float(value[1]), float(value[2])]


def _validate_post_process(pp) -> dict:
    if not isinstance(pp, dict) or not (pp.get("shader") or {}).get("fragment"):
        return {
            "shader": {
                "vertex": POST_VERTEX_SHADER,
                "fragment": (
                    "uniform sampler2D tDiffuse; varying vec2 vUv; "
                    "void main(){ gl_FragColor = texture2D(tDiffuse, vUv); }"
                ),
                "uniforms": {"uTime": {"type": "float", "value": 0}},
            }
        }
    shader = _validate_shader(pp.get("shader"), is_post=True)
    return {"shader": shader}


def _validate_shader(shader, is_post: bool = False) -> dict:
    if not isinstance(shader, dict):
        raise PlanValidationError("Шейдер должен быть объектом")
    fragment = (shader.get("fragment") or "").strip()
    if not fragment and isinstance(shader.get("fragment_lines"), list):
        fragment = "\n".join(str(line) for line in shader["fragment_lines"]).strip()
    if not fragment:
        raise PlanValidationError("Пустой fragment shader")
    vertex = (shader.get("vertex") or "").strip()
    if not vertex and isinstance(shader.get("vertex_lines"), list):
        vertex = "\n".join(str(line) for line in shader["vertex_lines"]).strip()
    if not vertex:
        vertex = POST_VERTEX_SHADER if is_post else STANDARD_VERTEX_SHADER

    uniforms = shader.get("uniforms") or {}
    if not isinstance(uniforms, dict):
        uniforms = {}
    uniforms["uTime"] = {"type": "float", "value": 0}
    if "uEm" not in uniforms:
        uniforms["uEm"] = {"type": "float", "value": 0}
    if is_post:
        uniforms.setdefault("uResolution", {"type": "vec2", "value": [1024, 768]})
        uniforms.pop("tDiffuse", None)

    result = {"vertex": vertex, "fragment": fragment, "uniforms": uniforms}
    leaf_fragment = (shader.get("leaf_fragment") or "").strip()
    if not leaf_fragment and isinstance(shader.get("leaf_fragment_lines"), list):
        leaf_fragment = "\n".join(str(line) for line in shader["leaf_fragment_lines"]).strip()
    leaf_vertex = (shader.get("leaf_vertex") or "").strip()
    if not leaf_vertex and isinstance(shader.get("leaf_vertex_lines"), list):
        leaf_vertex = "\n".join(str(line) for line in shader["leaf_vertex_lines"]).strip()
    if leaf_fragment:
        result["leaf_fragment"] = leaf_fragment
        result["leaf_vertex"] = leaf_vertex or STANDARD_VERTEX_SHADER
    return result
