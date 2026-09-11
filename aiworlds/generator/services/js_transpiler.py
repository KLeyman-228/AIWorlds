"""
Транспайлер: JSON-план мира → готовый JavaScript-код для Three.js.
Фронтендер просто подключает .js файл, и мир рендерится.
"""
import json
import logging
import hashlib
import re

log = logging.getLogger(__name__)


# ============================================================
# ШАБЛОНЫ
# ============================================================

JS_HEADER = """/**
 * AI World Generator — сгенерированный мир: {world_name}
 * {description}
 *
 * Подключение:
 *   <div id="world-container"></div>
 *   <script type="importmap">
 *   {{
 *     "imports": {{
 *       "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
 *       "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
 *     }}
 *   }}
 *   </script>
 *   <script type="module" src="./world.js"></script>
 */

import * as THREE from 'three';
import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';
import {{ EffectComposer }} from 'three/addons/postprocessing/EffectComposer.js';
import {{ RenderPass }} from 'three/addons/postprocessing/RenderPass.js';
import {{ ShaderPass }} from 'three/addons/postprocessing/ShaderPass.js';

// ============================================================
// НАСТРОЙКИ МИРА
// ============================================================
const WORLD_NAME = {world_name_json};
const DESCRIPTION = {description_json};

const ATMOSPHERE = {atmosphere_json};

// ============================================================
// PRIMITIVE BUILDERS
// ============================================================
const PRIMITIVE_BUILDERS = {{
  box: (p) => new THREE.BoxGeometry(p.width ?? 1, p.height ?? 1, p.depth ?? 1),
  sphere: (p) => new THREE.SphereGeometry(p.radius ?? 0.5, p.widthSegments ?? 8, p.heightSegments ?? 6),
  cylinder: (p) => new THREE.CylinderGeometry(p.rTop ?? 0.5, p.rBottom ?? 0.5, p.height ?? 1, p.segments ?? 6),
  cone: (p) => new THREE.ConeGeometry(p.radius ?? 0.5, p.height ?? 1, p.segments ?? 8),
  torus: (p) => new THREE.TorusGeometry(p.radius ?? 0.5, p.tube ?? 0.2, p.radialSegments ?? 8, p.tubularSegments ?? 16),
  octahedron: (p) => new THREE.OctahedronGeometry(p.radius ?? 0.5, 0),
  icosahedron: (p) => new THREE.IcosahedronGeometry(p.radius ?? 0.5, 0),
  dodecahedron: (p) => new THREE.DodecahedronGeometry(p.radius ?? 0.5, 0),
  tetrahedron: (p) => new THREE.TetrahedronGeometry(p.radius ?? 0.5, 0),
  plane: (p) => new THREE.PlaneGeometry(p.width ?? 1, p.height ?? 1),
}};

const _loader = new THREE.TextureLoader();
function loadB64Texture(b64, nearest = true) {{
  const tex = _loader.load(`data:image/png;base64,${{b64}}`);
  if (nearest) {{
    tex.minFilter = THREE.NearestFilter;
    tex.magFilter = THREE.NearestFilter;
  }}
  return tex;
}}

function buildPrimitive(prim) {{
  const builder = PRIMITIVE_BUILDERS[prim.type];
  if (!builder) {{
    console.warn(`[World] Unknown primitive: ${{prim.type}}`);
    return null;
  }}
  try {{
    return builder(prim.params || {{}});
  }} catch (e) {{
    console.warn(`[World] Failed to build ${{prim.type}}:`, e);
    return null;
  }}
}}

function applyTransform(mesh, prim) {{
  if (prim.position) mesh.position.set(...prim.position);
  if (prim.rotation) mesh.rotation.set(
    prim.rotation[0] * Math.PI / 180,
    prim.rotation[1] * Math.PI / 180,
    prim.rotation[2] * Math.PI / 180
  );
  if (prim.scale) {{
    if (Array.isArray(prim.scale)) mesh.scale.set(...prim.scale);
    else mesh.scale.setScalar(prim.scale);
  }}
}}

function compileShader(config, renderer) {{
  try {{
    const gl = renderer.getContext();
    const vs = gl.createShader(gl.VERTEX_SHADER);
    gl.shaderSource(vs, config.vertexShader);
    gl.compileShader(vs);
    if (!gl.getShaderParameter(vs, gl.COMPILE_STATUS)) {{
      console.warn('[World] VS error:', gl.getShaderInfoLog(vs));
      gl.deleteShader(vs);
      throw new Error('vertex shader failed');
    }}
    gl.deleteShader(vs);

    const fs = gl.createShader(gl.FRAGMENT_SHADER);
    gl.shaderSource(fs, config.fragmentShader);
    gl.compileShader(fs);
    if (!gl.getShaderParameter(fs, gl.COMPILE_STATUS)) {{
      console.warn('[World] FS error:', gl.getShaderInfoLog(fs));
      gl.deleteShader(fs);
      throw new Error('fragment shader failed');
    }}
    gl.deleteShader(fs);

    return new THREE.ShaderMaterial(config);
  }} catch (e) {{
    console.warn('[World] Shader failed, fallback used:', e.message);
    return new THREE.MeshStandardMaterial({{ color: 0x88aa66, flatShading: true }});
  }}
}}

// ============================================================
// ИНИЦИАЛИЗАЦИЯ СЦЕНЫ
// ============================================================
const container = document.getElementById('world-container');
if (!container) {{
  throw new Error('Element #world-container not found');
}}

const scene = new THREE.Scene();
scene.background = new THREE.Color(`rgb(${{ATMOSPHERE.sky_color.join(',')}})`);
scene.fog = new THREE.FogExp2(
  new THREE.Color(`rgb(${{ATMOSPHERE.fog_color.join(',')}})`),
  ATMOSPHERE.fog_density ?? 0.02
);

const camera = new THREE.PerspectiveCamera(
  40, container.clientWidth / container.clientHeight, 0.1, 500
);
camera.position.set(15, 12, 15);
camera.lookAt(0, 0, 0);

const renderer = new THREE.WebGLRenderer({{ antialias: true }});
renderer.setSize(container.clientWidth, container.clientHeight);
renderer.setPixelRatio(1);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
container.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.target.set(0, 1, 0);
controls.maxPolarAngle = Math.PI * 0.49;

// Свет
const ambient = new THREE.AmbientLight(0x8899bb, 0.6);
ambient.color.setRGB(
  ATMOSPHERE.ambient_color[0] / 255,
  ATMOSPHERE.ambient_color[1] / 255,
  ATMOSPHERE.ambient_color[2] / 255
);
scene.add(ambient);

const sun = new THREE.DirectionalLight(0xffeedd, 1.3);
sun.color.setRGB(
  ATMOSPHERE.sun_color[0] / 255,
  ATMOSPHERE.sun_color[1] / 255,
  ATMOSPHERE.sun_color[2] / 255
);
sun.position.set(10, 20, 5);
sun.castShadow = true;
sun.shadow.mapSize.width = 1024;
sun.shadow.mapSize.height = 1024;
sun.shadow.camera.left = -20;
sun.shadow.camera.right = 20;
sun.shadow.camera.top = 20;
sun.shadow.camera.bottom = -20;
scene.add(sun);

const fillLight = new THREE.DirectionalLight(0x6688cc, 0.35);
fillLight.position.set(-10, 5, -10);
scene.add(fillLight);

const worldGroup = new THREE.Group();
scene.add(worldGroup);

// ============================================================
// ЛАНДШАФТ
// ============================================================
"""

JS_TERRAIN = """const HEIGHTMAP_B64 = "{heightmap_b64}";
const COLORMAP_B64 = "{colormap_b64}";

const heightTex = loadB64Texture(HEIGHTMAP_B64);
const colorTex = loadB64Texture(COLORMAP_B64);

const terrainGeo = new THREE.PlaneGeometry(20, 20, 128, 128);
terrainGeo.rotateX(-Math.PI / 2);

const terrainMat = new THREE.MeshStandardMaterial({{
  map: colorTex,
  displacementMap: heightTex,
  displacementScale: 3.0,
  flatShading: true,
  roughness: 0.92,
  metalness: 0.0,
}});

const terrain = new THREE.Mesh(terrainGeo, terrainMat);
terrain.receiveShadow = true;
terrain.castShadow = true;
worldGroup.add(terrain);

"""

# ⚠️ ГЛАВНОЕ ОТЛИЧИЕ: IIFE + именованная переменная propMaterial_<name>
JS_PROP_TEMPLATE = """// ============ PROP: {prop_name} ============
const {material_var} = (function() {{
  const propShader = {{
    uniforms: {{
{uniforms_lines}
    }},
    vertexShader: {vertex_json},
    fragmentShader: {fragment_json},
  }};

  const mat = compileShader(propShader, renderer);
  mat.side = THREE.DoubleSide;

  const propGeometry = {geometry_json};
  const propInstances = {instances_json};

  for (const inst of propInstances) {{
    const propGroup = new THREE.Group();
    for (const prim of propGeometry.primitives || []) {{
      const geo = buildPrimitive(prim);
      if (!geo) continue;
      const mesh = new THREE.Mesh(geo, mat);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      applyTransform(mesh, prim);
      propGroup.add(mesh);
    }}
    if (inst.position) propGroup.position.set(...inst.position);
    if (inst.rotation) propGroup.rotation.set(
      inst.rotation[0] * Math.PI / 180,
      inst.rotation[1] * Math.PI / 180,
      inst.rotation[2] * Math.PI / 180
    );
    if (inst.scale != null) {{
      if (Array.isArray(inst.scale)) propGroup.scale.set(...inst.scale);
      else propGroup.scale.setScalar(inst.scale);
    }}
    worldGroup.add(propGroup);
  }}

  return mat;
}})();

"""

JS_FOOTER = """// ============================================================
// POST-PROCESSING
// ============================================================
{post_process_block}

// ============================================================
// АНИМАЦИЯ
// ============================================================
const clock = new THREE.Clock();
const propMaterials = [{prop_materials_list}];

function animate() {{
  requestAnimationFrame(animate);
  const t = clock.getElapsedTime();

  for (const mat of propMaterials) {{
    if (mat && mat.uniforms && mat.uniforms.uTime) {{
      mat.uniforms.uTime.value = t;
    }}
  }}
{pp_time_update}

  controls.update();
  {render_call}
}}

animate();

// Ресайз
window.addEventListener('resize', () => {{
  const w = container.clientWidth;
  const h = container.clientHeight;
  if (!w || !h) return;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
  {composer_resize}
}});

console.log('✅ World loaded: ' + WORLD_NAME);
"""


# ============================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================

def transpile_to_js(plan: dict, heightmap_b64: str, colormap_b64: str) -> str:
    """
    Принимает JSON-план мира + base64-карты и возвращает готовый JS-код.
    """
    log.info(f'🔧 Транспиляция мира: {plan.get("world_name", "?")}')

    parts = []

    # --- Header ---
    parts.append(JS_HEADER.format(
        world_name=plan.get('world_name', 'Unnamed World'),
        description=plan.get('description', ''),
        world_name_json=json.dumps(
            plan.get('world_name', 'Unnamed World'), ensure_ascii=False
        ),
        description_json=json.dumps(
            plan.get('description', ''), ensure_ascii=False
        ),
        atmosphere_json=json.dumps(plan['atmosphere'], indent=2),
    ))

    # --- Terrain ---
    parts.append(JS_TERRAIN.format(
        heightmap_b64=heightmap_b64,
        colormap_b64=colormap_b64,
    ))

    # --- Props ---
    prop_material_names = []
    props = plan.get('props') or {}

    for prop_name, prop in props.items():
        safe_name = _sanitize_js_identifier(prop_name)
        material_var = f'propMaterial_{safe_name}'

        # Uniforms (гарантируем uTime внутри _build_uniforms_lines)
        uniforms_lines = _build_uniforms_lines(
            prop.get('shader', {}).get('uniforms', {})
        )

        # Geometry
        geometry = prop.get('geometry', {'primitives': []})

        # Instances
        instances = prop.get('instances', []) or []

        # Shader — с fallback на случай отсутствия
        shader = prop.get('shader') or {}
        vertex = shader.get('vertex', '')
        fragment = shader.get('fragment', '')

        prop_code = JS_PROP_TEMPLATE.format(
            prop_name=safe_name,
            material_var=material_var,
            uniforms_lines=uniforms_lines,
            vertex_json=json.dumps(vertex, ensure_ascii=False),
            fragment_json=json.dumps(fragment, ensure_ascii=False),
            geometry_json=json.dumps(geometry, ensure_ascii=False, indent=4),
            instances_json=json.dumps(instances, ensure_ascii=False, indent=4),
        )
        parts.append(prop_code)
        prop_material_names.append(material_var)

    # --- Post-process ---
    pp = plan.get('post_process', {}).get('shader')
    has_pp = bool(pp and pp.get('vertex') and pp.get('fragment'))

    if has_pp:
        pp_block = _build_post_process_block(pp)
        parts.append(JS_FOOTER.format(
            post_process_block=pp_block,
            prop_materials_list=', '.join(prop_material_names) or '',
            pp_time_update=(
                '  if (ppPass && ppPass.uniforms && ppPass.uniforms.uTime) {\n'
                '    ppPass.uniforms.uTime.value = t;\n'
                '  }'
            ),
            render_call='composer.render();',
            composer_resize='if (composer) composer.setSize(w, h);',
        ))
    else:
        parts.append(JS_FOOTER.format(
            post_process_block='const composer = null;\nconst ppPass = null;',
            prop_materials_list=', '.join(prop_material_names) or '',
            pp_time_update='',
            render_call='renderer.render(scene, camera);',
            composer_resize='',
        ))

    js_code = '\n'.join(parts)
    log.info(f'✅ JS код готов ({len(js_code)} символов)')

    # Опционально: валидация через node --check
    _validate_js(js_code)

    return js_code


# ============================================================
# ХЕЛПЕРЫ
# ============================================================

def _sanitize_js_identifier(name: str) -> str:
    """
    Превращает произвольную строку в валидный JS-идентификатор.
    Кириллицу и спецсимволы заменяет на хеш.
    """
    if not name:
        return '_empty'

    # Транслитерация ASCII
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)

    # Если получились только подчёркивания — используем хеш
    if not safe or set(safe) <= {'_'}:
        safe = 'prop_' + hashlib.md5(name.encode('utf-8')).hexdigest()[:8]

    # Не может начинаться с цифры
    if safe[0].isdigit():
        safe = '_' + safe

    # Защита от зарезервированных слов JS
    RESERVED = {
        'class', 'function', 'var', 'let', 'const', 'return', 'new',
        'delete', 'typeof', 'instanceof', 'void', 'this', 'null',
        'true', 'false', 'if', 'else', 'for', 'while', 'do', 'switch',
        'case', 'default', 'break', 'continue', 'try', 'catch', 'finally',
        'throw', 'with', 'in', 'of', 'yield', 'await', 'async',
        'import', 'export', 'from', 'as',
    }
    if safe in RESERVED:
        safe = '_' + safe

    return safe


def _build_uniforms_lines(uniforms: dict) -> str:
    """
    Строит JS-код для uniforms.
    Возвращает строки, разделённые ',\n' — БЕЗ запятой в конце.
    Всегда гарантирует наличие uTime.
    """
    # Копируем, чтобы не мутировать оригинал
    u = dict(uniforms or {})

    # Гарантируем uTime
    if 'uTime' not in u:
        u['uTime'] = {'type': 'float', 'value': 0}

    lines = []
    for name, cfg in u.items():
        if not isinstance(cfg, dict):
            continue

        typ = cfg.get('type', 'float')
        val = cfg.get('value')

        if typ == 'float':
            v = val if val is not None else 0
            lines.append(f'      {name}: {{ value: {v} }}')
        elif typ == 'int':
            v = int(val) if val is not None else 0
            lines.append(f'      {name}: {{ value: {v} }}')
        elif typ == 'vec2':
            v = val or [0, 0]
            lines.append(f'      {name}: {{ value: new THREE.Vector2({v[0]}, {v[1]}) }}')
        elif typ == 'vec3':
            v = val or [0, 0, 0]
            lines.append(f'      {name}: {{ value: new THREE.Vector3({v[0]}, {v[1]}, {v[2]}) }}')
        elif typ == 'vec4':
            v = val or [0, 0, 0, 0]
            lines.append(f'      {name}: {{ value: new THREE.Vector4({v[0]}, {v[1]}, {v[2]}, {v[3]}) }}')
        elif typ == 'color':
            v = val or [1, 1, 1]
            lines.append(f'      {name}: {{ value: new THREE.Color({v[0]}, {v[1]}, {v[2]}) }}')
        else:
            lines.append(f'      {name}: {{ value: {json.dumps(val)} }}')

    # ⚠️ ГЛАВНЫЙ ФИКС: разделяем запятыми
    return ',\n'.join(lines)


def _build_post_process_block(shader: dict) -> str:
    """Строит JS-блок пост-обработки."""
    uniforms_lines = _build_uniforms_lines(shader.get('uniforms', {}))

    return f"""const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));

const ppShader = {{
  uniforms: {{
    tDiffuse: {{ value: null }},
    uResolution: {{ value: new THREE.Vector2(container.clientWidth, container.clientHeight) }},
{uniforms_lines}
  }},
  vertexShader: {json.dumps(shader['vertex'], ensure_ascii=False)},
  fragmentShader: {json.dumps(shader['fragment'], ensure_ascii=False)},
}};

let ppPass = null;
try {{
  ppPass = new ShaderPass(ppShader);
  ppPass.renderToScreen = true;
  composer.addPass(ppPass);
}} catch (e) {{
  console.warn('[World] Post-process failed:', e);
}}
"""


def _validate_js(js_code: str) -> bool:
    """
    Проверяет синтаксис сгенерированного JS через node --check.
    Если node не установлен — просто возвращает True.
    """
    import subprocess
    import tempfile
    import os

    try:
        with tempfile.NamedTemporaryFile(
            'w', suffix='.mjs', delete=False, encoding='utf-8'
        ) as f:
            # Заглушки для модулей (node --check не резолвит импорты, это ок)
            f.write(js_code)
            fpath = f.name

        result = subprocess.run(
            ['node', '--check', fpath],
            capture_output=True, text=True, timeout=10,
        )

        os.unlink(fpath)

        if result.returncode == 0:
            log.info('✅ JS syntax OK')
            return True
        else:
            log.error(f'❌ JS syntax error:\n{result.stderr}')
            return False

    except FileNotFoundError:
        log.warning('⚠️ Node.js не найден — пропускаем проверку синтаксиса')
        return True
    except subprocess.TimeoutExpired:
        log.warning('⚠️ node --check timeout')
        return True
    except Exception as e:
        log.warning(f'⚠️ JS validation failed: {e}')
        return True