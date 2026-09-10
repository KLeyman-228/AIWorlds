from .fallbacks import (
    fallback_prop_shader,
    fallback_post_shader,
    default_gradient,
    fallback_plan,
)


def validate_plan(plan: dict) -> dict:
    if not isinstance(plan, dict):
        return fallback_plan()

    # === TERRAIN ===
    terrain = plan.setdefault("terrain", {})
    if not isinstance(terrain.get("octaves"), int) or terrain["octaves"] < 1:
        terrain["octaves"] = 4
    if not isinstance(terrain.get("scale"), (int, float)) or terrain["scale"] <= 0:
        terrain["scale"] = 45.0
    if not isinstance(terrain.get("seed"), int):
        terrain["seed"] = 42
    if not terrain.get("color_gradient"):
        terrain["color_gradient"] = default_gradient()

    # === ATMOSPHERE ===
    atmo = plan.setdefault("atmosphere", {})
    atmo.setdefault("fog_color", [150, 180, 220])
    atmo.setdefault("fog_density", 0.02)
    atmo.setdefault("sky_color", [200, 220, 255])
    atmo.setdefault("sun_color", [255, 240, 220])
    atmo.setdefault("ambient_color", [120, 140, 170])

    # === PROPS ===
    props = plan.setdefault("props", {})
    if not isinstance(props, dict):
        props = {}
        plan["props"] = props

    for name, prop in list(props.items()):
        if not isinstance(prop, dict):
            del props[name]
            continue
        prop.setdefault("geometry", {"primitives": []})
        prop.setdefault("instances", [])

        if not prop.get("shader"):
            prop["shader"] = fallback_prop_shader()
        else:
            prop["shader"] = _validate_shader(prop["shader"], is_post=False)

    # === POST_PROCESS ===
    pp = plan.setdefault("post_process", {})
    if not pp.get("shader"):
        pp["shader"] = fallback_post_shader()
    else:
        pp["shader"] = _validate_shader(pp["shader"], is_post=True)

    return plan


def _validate_shader(shader: dict, is_post: bool = False) -> dict:
    if not isinstance(shader, dict) or not shader.get("vertex") or not shader.get("fragment"):
        return fallback_post_shader() if is_post else fallback_prop_shader()

    uniforms = shader.setdefault("uniforms", {})
    if not isinstance(uniforms, dict):
        uniforms = {}
        shader["uniforms"] = uniforms

    if "uTime" not in uniforms:
        uniforms["uTime"] = {"type": "float", "value": 0}
    if is_post:
        uniforms.setdefault("uResolution", {"type": "vec2", "value": [1024, 768]})

    return shader