"""Дефолтные шейдеры и планы на случай ошибок AI."""


def fallback_prop_shader() -> dict:
    return {
        "vertex": (
            "varying vec2 vUv;\n"
            "varying vec3 vNormal;\n"
            "varying vec3 vWorldPos;\n"
            "void main() {\n"
            "  vUv = uv;\n"
            "  vNormal = normalize(normalMatrix * normal);\n"
            "  vec4 wp = modelMatrix * vec4(position, 1.0);\n"
            "  vWorldPos = wp.xyz;\n"
            "  gl_Position = projectionMatrix * viewMatrix * wp;\n"
            "}"
        ),
        "fragment": (
            "uniform float uTime;\n"
            "varying vec2 vUv;\n"
            "varying vec3 vNormal;\n"
            "varying vec3 vWorldPos;\n"
            "void main() {\n"
            "  vec3 color = vec3(0.5, 0.6, 0.4);\n"
            "  float d = fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453);\n"
            "  color += (d - 0.5) * 0.05;\n"
            "  gl_FragColor = vec4(color, 1.0);\n"
            "}"
        ),
        "uniforms": {"uTime": {"type": "float", "value": 0}},
    }


def fallback_post_shader() -> dict:
    return {
        "vertex": (
            "varying vec2 vUv;\n"
            "void main() {\n"
            "  vUv = uv;\n"
            "  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);\n"
            "}"
        ),
        "fragment": (
            "uniform sampler2D tDiffuse;\n"
            "uniform float uTime;\n"
            "varying vec2 vUv;\n"
            "void main() {\n"
            "  gl_FragColor = texture2D(tDiffuse, vUv);\n"
            "}"
        ),
        "uniforms": {"uTime": {"type": "float", "value": 0}},
    }


def default_gradient():
    return [
        {"height": 0.0, "color": [194, 178, 128]},
        {"height": 0.25, "color": [120, 160, 90]},
        {"height": 0.55, "color": [80, 130, 70]},
        {"height": 0.8, "color": [130, 120, 110]},
        {"height": 1.0, "color": [230, 235, 240]},
    ]


def fallback_plan():
    return {
        "world_name": "Fallback World",
        "description": "Дефолтный мир",
        "terrain": {
            "scale": 45,
            "octaves": 4,
            "seed": 42,
            "color_gradient": default_gradient(),
        },
        "atmosphere": {
            "fog_color": [150, 180, 220],
            "fog_density": 0.02,
            "sky_color": [200, 220, 255],
            "sun_color": [255, 240, 220],
            "ambient_color": [120, 140, 170],
        },
        "props": {},
        "post_process": {"shader": fallback_post_shader()},
    }