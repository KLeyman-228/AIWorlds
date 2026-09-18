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

    gradient = terrain.get("color_gradient")
    if not isinstance(gradient, list) or len(gradient) < 2:
        raise PlanValidationError("color_gradient: минимум 2 точки от AI")
    cleaned = []
    for point in gradient:
        if not isinstance(point, dict):
            continue
        try:
            height = float(point["height"])
            color = [int(c) for c in point["color"][:3]]
        except (KeyError, TypeError, ValueError):
            continue
        cleaned.append(
            {
                "height": max(0.0, min(1.0, height)),
                "color": [max(0, min(255, c)) for c in color],
            }
        )
    if len(cleaned) < 2:
        raise PlanValidationError("color_gradient не содержит валидных точек")
    terrain["color_gradient"] = cleaned
    terrain["features"] = _validate_features(terrain.get("features"))
    terrain["water_level"] = _optional_float(terrain.get("water_level"), 0.0, 1.0)
    return terrain


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
    for feat in features[:8]:
        if not isinstance(feat, dict):
            continue
        kind = str(feat.get("type") or "").lower()
        if kind not in FEATURE_TYPES:
            continue
        item = {"type": kind}
        if kind in ("river", "ridge"):
            points = _uv_points(feat.get("points"), min_count=2)
            if not points:
                continue
            item["points"] = points
            item["width"] = _clamped(feat.get("width"), 0.02, 0.2, 0.05)
            if kind == "river":
                item["depth"] = _clamped(feat.get("depth"), 0.1, 0.8, 0.42)
            else:
                item["height"] = _clamped(feat.get("height"), 0.1, 0.8, 0.35)
        else:
            center = feat.get("center")
            if isinstance(center, (list, tuple)) and len(center) >= 2:
                item["center"] = [
                    max(0.0, min(1.0, float(center[0]))),
                    max(0.0, min(1.0, float(center[1]))),
                ]
            else:
                item["center"] = [0.5, 0.5]
            item["radius"] = _clamped(feat.get("radius"), 0.04, 0.4, 0.12)
            if kind in ("lake", "basin"):
                item["depth"] = _clamped(feat.get("depth"), 0.1, 0.8, 0.4)
            elif kind == "plateau":
                item["height"] = _clamped(feat.get("height"), 0.1, 0.8, 0.32)
                item["falloff"] = _clamped(feat.get("falloff"), 0.01, 0.2, 0.05)
            else:
                item["height"] = _clamped(feat.get("height"), 0.08, 0.7, 0.25)
        cleaned.append(item)
    return cleaned


def _uv_points(points, min_count=2):
    if not isinstance(points, list):
        return []
    cleaned = []
    for pt in points[:12]:
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            cleaned.append(
                [max(0.0, min(1.0, float(pt[0]))), max(0.0, min(1.0, float(pt[1])))]
            )
    return cleaned if len(cleaned) >= min_count else []


def _clamped(value, lo, hi, default):
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


def validate_and_place_props(props, seed: int, heightmap=None) -> dict:
    """Нормализует пропы и ставит инстансы на heightmap."""
    if not isinstance(props, dict) or not props:
        raise PlanValidationError("AI не вернул ни одного пропа")

    from .instances import place_instances

    cleaned = {}
    for name, prop in props.items():
        if not isinstance(prop, dict):
            log.warning("Skip prop %s: not an object", name)
            continue
        geometry = _normalize_geometry(prop.get("geometry"))
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
            placed = _snap_instances(instances, heightmap)
        else:
            rule = instances if isinstance(instances, dict) else {}
            if "count" not in rule:
                rule["count"] = 8
            try:
                placed = place_instances(rule, seed=seed + len(name), heightmap=heightmap)
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


def _snap_instances(instances: list, heightmap) -> list:
    from .terrain import HEIGHT_SCALE, sample_height_uv, world_to_uv

    placed = []
    for inst in instances:
        if not isinstance(inst, dict):
            continue
        pos = list(inst.get("position") or [0, 0, 0])
        if len(pos) < 3:
            continue
        x, z = float(pos[0]), float(pos[2])
        y = float(pos[1]) if heightmap is None else (
            sample_height_uv(heightmap, *world_to_uv(x, z)) * HEIGHT_SCALE
        )
        item = dict(inst)
        item["position"] = [x, y, z]
        placed.append(item)
    return placed


def _normalize_geometry(geometry) -> dict:
    if not isinstance(geometry, dict):
        return {"primitives": []}
    raw = geometry.get("primitives") or []
    primitives = []
    for prim in raw:
        if not isinstance(prim, dict):
            continue
        ptype = str(prim.get("type") or "").lower()
        if ptype not in ALLOWED_PRIMITIVES:
            continue
        params = prim.get("params")
        if not isinstance(params, dict):
            params = {
                k: v
                for k, v in prim.items()
                if k not in ("type", "position", "rotation", "scale", "params")
            }
        item = {"type": ptype, "params": params}
        if prim.get("position"):
            item["position"] = _vec3(prim["position"])
        if prim.get("rotation"):
            item["rotation"] = _vec3(prim["rotation"])
        if prim.get("scale") is not None:
            item["scale"] = prim["scale"]
        primitives.append(item)
    return {"primitives": primitives}


def _vec3(value) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return [0.0, 0.0, 0.0]
    return [float(value[0]), float(value[1]), float(value[2])]


def _validate_post_process(pp) -> dict:
    if not isinstance(pp, dict):
        raise PlanValidationError("Нет post_process от AI")
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
    if is_post:
        uniforms.setdefault("uResolution", {"type": "vec2", "value": [1024, 768]})
        uniforms.pop("tDiffuse", None)

    return {"vertex": vertex, "fragment": fragment, "uniforms": uniforms}
