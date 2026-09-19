"""
Транспайлер: JSON-план мира → готовый JavaScript-код для Three.js.
Фронтендер просто подключает .js файл, и мир рендерится.
"""
import json
import logging
import hashlib
import re

log = logging.getLogger(__name__)

LEAF_VERTEX = """varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vPosition;
varying vec3 vWorldPos;
uniform float uTime;
void main() {
  vUv = uv;
  vNormal = normalize(normalMatrix * normal);
  vec3 pos = position;
  pos.x += sin(uTime * 1.7 + position.y * 3.0) * 0.045;
  pos.z += cos(uTime * 1.3 + position.x * 2.4) * 0.035;
  vPosition = pos;
  vec4 wp = modelMatrix * vec4(pos, 1.0);
  vWorldPos = wp.xyz;
  gl_Position = projectionMatrix * viewMatrix * wp;
}"""

LEAF_FRAGMENT = """varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vPosition;
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float n2(vec2 p){
  vec2 i = floor(p); vec2 f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(hash(i), hash(i+vec2(1.0,0.0)), f.x), mix(hash(i+vec2(0.0,1.0)), hash(i+vec2(1.0,1.0)), f.x), f.y);
}
void main() {
  vec3 n = normalize(vNormal);
  float a = n2(vUv * 7.0);
  float b = n2(vUv * 18.0 + 3.7);
  float c0 = n2(vPosition.xz * 5.0);
  float clumps = step(0.38, a * 0.55 + b * 0.45);
  float holes = step(0.82, b);
  vec3 shade = vec3(0.07, 0.22, 0.06);
  vec3 mid = vec3(0.14, 0.42, 0.10);
  vec3 lite = vec3(0.26, 0.62, 0.16);
  vec3 c = mix(shade, mix(mid, lite, step(0.55, c0)), clumps);
  c = mix(c, shade * 0.6, holes);
  float lamb = 0.55 + 0.45 * max(dot(n, normalize(vec3(0.35, 0.9, 0.2))), 0.0);
  c *= lamb;
  c = floor(c * 8.0 + 0.5) / 8.0;
  c += (hash(floor(gl_FragCoord.xy)) - 0.5) * 0.035;
  gl_FragColor = vec4(c, 1.0);
}"""

TERRAIN_VERTEX = """varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vPosition;
varying vec3 vWorldPos;
void main() {
  vUv = uv;
  vPosition = position;
  vec4 wp = modelMatrix * vec4(position, 1.0);
  vWorldPos = wp.xyz;
  vNormal = normalize(mat3(modelMatrix) * normal);
  gl_Position = projectionMatrix * viewMatrix * wp;
}"""

BARK_FRAGMENT = """varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vPosition;
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
void main() {
  vec3 n = normalize(vNormal);
  float ridges = abs(fract(vPosition.y * 9.0 + vUv.x * 2.0) - 0.5);
  float cracks = step(0.92, hash(floor(vec2(vUv.x * 14.0, vPosition.y * 22.0))));
  float flakes = step(0.62, hash(floor(vUv * 16.0)));
  float moss = step(0.55, 1.0 - clamp(vPosition.y * 0.7, 0.0, 1.0)) * step(0.5, hash(floor(vPosition.xz * 10.0)));
  vec3 dark = vec3(0.18, 0.10, 0.05);
  vec3 mid = vec3(0.34, 0.20, 0.09);
  vec3 lite = vec3(0.48, 0.30, 0.14);
  vec3 c = mix(dark, lite, smoothstep(0.08, 0.28, ridges));
  c = mix(c, mid, flakes * 0.35);
  c = mix(c, dark * 0.45, cracks);
  c = mix(c, vec3(0.16, 0.28, 0.08), moss * 0.7);
  c *= 0.5 + 0.5 * max(dot(n, normalize(vec3(0.4, 0.8, 0.2))), 0.0);
  c = floor(c * 7.0 + 0.5) / 7.0;
  c += (hash(floor(gl_FragCoord.xy)) - 0.5) * 0.03;
  gl_FragColor = vec4(c, 1.0);
}"""


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

function compileShader(config, fallbackColor = 0x7a9a5a) {{
  try {{
    const mat = new THREE.ShaderMaterial({{
      uniforms: config.uniforms,
      vertexShader: config.vertexShader,
      fragmentShader: config.fragmentShader,
      lights: false,
      side: THREE.DoubleSide,
    }});
    mat.needsUpdate = true;
    return mat;
  }} catch (e) {{
    console.warn('[World] ShaderMaterial failed, solid color used:', e.message);
    return new THREE.MeshStandardMaterial({{
      color: fallbackColor,
      flatShading: true,
      roughness: 0.9,
    }});
  }}
}}

function propFallbackColor(uniforms) {{
  for (const key of Object.keys(uniforms || {{}})) {{
    const val = uniforms[key] && uniforms[key].value;
    if (val && val.isColor) return val.getHex();
    if (val && val.isVector3) {{
      return new THREE.Color(val.x, val.y, val.z).getHex();
    }}
  }}
  return 0x7a9a5a;
}}

// ============================================================
// ИНИЦИАЛИЗАЦИЯ СЦЕНЫ
// ============================================================
const container = document.getElementById('world-container');
if (!container) {{
  throw new Error('Element #world-container not found');
}}

const scene = new THREE.Scene();
const skyDay = new THREE.Color(
  (ATMOSPHERE.sky_color?.[0] ?? 135) / 255,
  (ATMOSPHERE.sky_color?.[1] ?? 185) / 255,
  (ATMOSPHERE.sky_color?.[2] ?? 235) / 255
);
scene.background = skyDay;
scene.fog = new THREE.FogExp2(
  new THREE.Color(
    (ATMOSPHERE.fog_color?.[0] ?? 170) / 255,
    (ATMOSPHERE.fog_color?.[1] ?? 200) / 255,
    (ATMOSPHERE.fog_color?.[2] ?? 230) / 255
  ),
  Math.min(ATMOSPHERE.fog_density ?? 0.012, 0.02)
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
controls.maxPolarAngle = Math.PI * 0.9;

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

const skyUniforms = {{
  uTime: {{ value: 0 }},
  uSkyTop: {{ value: new THREE.Color(0.45, 0.72, 0.98) }},
  uSkyHorizon: {{ value: new THREE.Color(0.78, 0.88, 0.98) }},
  uCloud: {{ value: new THREE.Color(0.95, 0.97, 1.0) }},
}};
const skyMat = new THREE.ShaderMaterial({{
  uniforms: skyUniforms,
  side: THREE.BackSide,
  depthWrite: false,
  fog: false,
  vertexShader: `
    varying vec3 vDir;
    void main() {{
      vDir = position;
      vec4 clip = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      gl_Position = clip.xyww;
    }}
  `,
  fragmentShader: `
    uniform float uTime;
    uniform vec3 uSkyTop;
    uniform vec3 uSkyHorizon;
    uniform vec3 uCloud;
    varying vec3 vDir;
    float hash(vec2 p) {{
      return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
    }}
    float noise(vec2 p) {{
      vec2 i = floor(p);
      vec2 f = fract(p);
      float a = hash(i);
      float b = hash(i + vec2(1.0, 0.0));
      float c = hash(i + vec2(0.0, 1.0));
      float d = hash(i + vec2(1.0, 1.0));
      vec2 u = f * f * (3.0 - 2.0 * f);
      return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
    }}
    float fbm(vec2 p) {{
      float v = 0.0;
      float a = 0.5;
      for (int i = 0; i < 5; i++) {{
        v += a * noise(p);
        p *= 2.03;
        a *= 0.5;
      }}
      return v;
    }}
    void main() {{
      vec3 dir = normalize(vDir);
      float h = clamp(dir.y * 0.5 + 0.5, 0.0, 1.0);
      vec3 col = mix(uSkyHorizon, uSkyTop, pow(h, 0.65));
      vec2 uv = dir.xz / max(dir.y + 0.25, 0.05);
      float clouds = fbm(uv * 1.6 + vec2(uTime * 0.012, 0.0));
      clouds = smoothstep(0.52, 0.78, clouds) * smoothstep(0.02, 0.28, dir.y);
      col = mix(col, uCloud, clouds * 0.85);
      gl_FragColor = vec4(col, 1.0);
    }}
  `,
}});
const sky = new THREE.Mesh(new THREE.SphereGeometry(160, 24, 16), skyMat);
sky.renderOrder = -1;
scene.add(sky);

// ============================================================
// ЛАНДШАФТ
// ============================================================
"""

JS_TERRAIN = """const HEIGHTMAP = {heightmap_js};
const HEIGHTMAP_RES = {heightmap_res};
const TERRAIN_SIZE = {terrain_size};
const HEIGHT_SCALE = {height_scale};
const WATER_LEVEL = {water_level};
const COLORMAP_B64 = "{colormap_b64}";
const RIVER_PATHS = {river_paths_json};
const LAKE_SPOTS = {lake_spots_json};

function heightAt(x, z) {{
  const u = THREE.MathUtils.clamp(x / TERRAIN_SIZE + 0.5, 0, 1);
  const v = THREE.MathUtils.clamp(z / TERRAIN_SIZE + 0.5, 0, 1);
  const fx = u * (HEIGHTMAP_RES - 1);
  const fy = v * (HEIGHTMAP_RES - 1);
  const x0 = Math.floor(fx);
  const y0 = Math.floor(fy);
  const x1 = Math.min(HEIGHTMAP_RES - 1, x0 + 1);
  const y1 = Math.min(HEIGHTMAP_RES - 1, y0 + 1);
  const tx = fx - x0;
  const ty = fy - y0;
  const a = HEIGHTMAP[y0 * HEIGHTMAP_RES + x0] * (1 - tx) + HEIGHTMAP[y0 * HEIGHTMAP_RES + x1] * tx;
  const b = HEIGHTMAP[y1 * HEIGHTMAP_RES + x0] * (1 - tx) + HEIGHTMAP[y1 * HEIGHTMAP_RES + x1] * tx;
  return (a * (1 - ty) + b * ty) * HEIGHT_SCALE;
}}

const colorTex = loadB64Texture(COLORMAP_B64, true);
colorTex.colorSpace = THREE.SRGBColorSpace;
const terrainGeo = new THREE.PlaneGeometry(TERRAIN_SIZE, TERRAIN_SIZE, HEIGHTMAP_RES - 1, HEIGHTMAP_RES - 1);
terrainGeo.rotateX(-Math.PI / 2);
const tPos = terrainGeo.attributes.position;
for (let i = 0; i < tPos.count; i++) {{
  tPos.setY(i, heightAt(tPos.getX(i), tPos.getZ(i)));
}}
tPos.needsUpdate = true;
terrainGeo.computeVertexNormals();

const terrainShader = {{
  uniforms: {{
    uTime: {{ value: 0 }},
    uMap: {{ value: colorTex }},
    uGrass: {{ value: new THREE.Vector3({u_grass}) }},
    uDirt: {{ value: new THREE.Vector3({u_dirt}) }},
    uRock: {{ value: new THREE.Vector3({u_rock}) }},
{terrain_extra_uniforms}
  }},
  vertexShader: {terrain_vertex_json},
  fragmentShader: {terrain_fragment_json},
}};
const terrainMat = compileShader(terrainShader, 0x3d7a32);
if (terrainMat.uniforms && !terrainMat.uniforms.uMap) {{
  terrainMat.map = colorTex;
}}
terrainMat.side = THREE.FrontSide;

const terrain = new THREE.Mesh(terrainGeo, terrainMat);
terrain.receiveShadow = true;
terrain.castShadow = true;
worldGroup.add(terrain);

if (WATER_LEVEL != null) {{
  const water = new THREE.Mesh(
    new THREE.PlaneGeometry(TERRAIN_SIZE, TERRAIN_SIZE, 1, 1),
    new THREE.MeshStandardMaterial({{
      color: 0x2a78b8,
      transparent: true,
      opacity: 0.7,
      roughness: 0.35,
      metalness: 0.05,
      flatShading: true,
    }})
  );
  water.rotation.x = -Math.PI / 2;
  water.position.y = WATER_LEVEL * HEIGHT_SCALE;
  water.renderOrder = 1;
  worldGroup.add(water);
}}

"""

# ⚠️ ГЛАВНОЕ ОТЛИЧИЕ: IIFE + именованная переменная propMaterial_<name>
JS_PROP_TEMPLATE = """// ============ PROP: {prop_name} ============
const {material_var} = (function() {{
  const isTree = {is_tree};
  const barkShader = {{
    uniforms: {{ {uniforms_lines} }},
    vertexShader: {vertex_json},
    fragmentShader: {fragment_json},
  }};
  const leafShader = {{
    uniforms: {{ {uniforms_lines} }},
    vertexShader: {leaf_vertex_json},
    fragmentShader: {leaf_fragment_json},
  }};
  const barkMat = compileShader(barkShader, propFallbackColor(barkShader.uniforms));
  barkMat.side = THREE.DoubleSide;
  const leafMat = isTree
    ? compileShader(leafShader, 0x3d8a32)
    : barkMat;
  if (leafMat) leafMat.side = THREE.DoubleSide;

  const propGeometry = {geometry_json};
  const propInstances = {instances_json};

  for (const inst of propInstances) {{
    const propGroup = new THREE.Group();
    for (const prim of propGeometry.primitives || []) {{
      const geo = buildPrimitive(prim);
      if (!geo) continue;
      const useLeaf = isTree && (prim.type === 'sphere' || prim.type === 'cone' || prim.type === 'icosahedron');
      const mesh = new THREE.Mesh(geo, useLeaf ? leafMat : barkMat);
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

  return isTree ? leafMat : barkMat;
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

  if (skyUniforms && skyUniforms.uTime) skyUniforms.uTime.value = t;
  if (terrainMat && terrainMat.uniforms && terrainMat.uniforms.uTime) {{
    terrainMat.uniforms.uTime.value = t;
  }}
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

def transpile_to_js(plan: dict, heightmap_b64: str = "", colormap_b64: str = "", heightmap_js: str = "[]") -> str:
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
    water = plan.get("terrain", {}).get("water_level")
    rivers = []
    lakes = []
    for feat in plan.get("terrain", {}).get("features") or []:
        if feat.get("type") == "river" and feat.get("points"):
            rivers.append({"points": feat["points"], "width": feat.get("width", 0.05)})
        if feat.get("type") in ("lake", "basin") and feat.get("center"):
            lakes.append({"center": feat["center"], "radius": feat.get("radius", 0.12)})
    tsh = (plan.get("terrain") or {}).get("shader") or {}
    terrain_fragment = _stabilize_terrain_fragment(tsh.get("fragment") or """varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vWorldPos;
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
  vec3 mud = vec3(0.22, 0.18, 0.10);
  vec3 sand = vec3(0.55, 0.46, 0.24);
  vec3 grassA = vec3(0.16, 0.40, 0.12);
  vec3 grassB = vec3(0.28, 0.58, 0.16);
  vec3 dry = vec3(0.42, 0.40, 0.16);
  vec3 rock = vec3(0.38, 0.36, 0.32);
  vec3 c = mix(mud, sand, step(0.12, h));
  c = mix(c, mix(grassA, grassB, step(0.5, patches)), step(0.22, h));
  c = mix(c, dry, step(0.62, h));
  c = mix(c, rock, step(0.82, h));
  c = mix(c, grassA * 0.75, blades * (1.0 - step(0.7, h)) * 0.45);
  c = mix(c, mud, step(0.62, tufts) * 0.2);
  c = mix(c, rock, smoothstep(0.25, 0.55, slope));
  c *= 0.55 + 0.45 * max(dot(n, normalize(vec3(0.4, 0.85, 0.2))), 0.0);
  c = floor(c * 8.0 + 0.5) / 8.0;
  c += (hash(floor(gl_FragCoord.xy)) - 0.5) * 0.03;
  gl_FragColor = vec4(c, 1.0);
}""")
    tu = (tsh.get("uniforms") or {}) if isinstance(tsh, dict) else {}
    grass = _vec3_uniform(tu.get("uGrass"), (0.22, 0.52, 0.16))
    dirt = _vec3_uniform(tu.get("uDirt"), (0.32, 0.22, 0.12))
    rock = _vec3_uniform(tu.get("uRock"), (0.42, 0.40, 0.36))
    extra = {k: v for k, v in tu.items() if k not in ("uTime", "uMap", "uGrass", "uDirt", "uRock")}
    extra_lines = _build_uniforms_lines(extra)
    parts.append(JS_TERRAIN.format(
        heightmap_js=heightmap_js,
        heightmap_res=128,
        terrain_size=20,
        height_scale=4.0,
        water_level="null" if water is None else float(water),
        colormap_b64=colormap_b64 or "",
        river_paths_json="[]",
        lake_spots_json="[]",
        terrain_vertex_json=json.dumps(TERRAIN_VERTEX),
        terrain_fragment_json=json.dumps(terrain_fragment),
        u_grass=f"{grass[0]}, {grass[1]}, {grass[2]}",
        u_dirt=f"{dirt[0]}, {dirt[1]}, {dirt[2]}",
        u_rock=f"{rock[0]}, {rock[1]}, {rock[2]}",
        terrain_extra_uniforms=(extra_lines + ",") if extra_lines else "",
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

        shader = prop.get('shader') or {}
        vertex = shader.get('vertex', '')
        fragment = shader.get('fragment', '')
        is_tree = _is_tree_prop(prop_name, geometry, prop.get("template"))
        leaf_fragment = (shader.get("leaf_fragment") or "").strip()
        leaf_vertex = (shader.get("leaf_vertex") or "").strip()
        if is_tree:
            if not leaf_fragment:
                leaf_fragment = LEAF_FRAGMENT
            if not leaf_vertex:
                leaf_vertex = LEAF_VERTEX
        else:
            leaf_vertex = vertex
            leaf_fragment = fragment

        prop_code = JS_PROP_TEMPLATE.format(
            prop_name=safe_name,
            material_var=material_var,
            uniforms_lines=uniforms_lines,
            vertex_json=json.dumps(vertex, ensure_ascii=False),
            fragment_json=json.dumps(fragment, ensure_ascii=False),
            leaf_vertex_json=json.dumps(leaf_vertex, ensure_ascii=False),
            leaf_fragment_json=json.dumps(leaf_fragment, ensure_ascii=False),
            is_tree='true' if is_tree else 'false',
            geometry_json=json.dumps(geometry, ensure_ascii=False, indent=4),
            instances_json=json.dumps(instances, ensure_ascii=False, indent=4),
        )
        parts.append(prop_code)
        prop_material_names.append(material_var)

    # --- Post-process ---
    pp = plan.get('post_process', {}).get('shader')
    time_of_day = (plan.get('atmosphere') or {}).get('time_of_day') or 'day'
    has_pp = bool(pp and pp.get('vertex') and pp.get('fragment') and time_of_day != 'day')

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

def _vec3_uniform(cfg, fallback):
    if isinstance(cfg, dict):
        val = cfg.get("value")
        if isinstance(val, (list, tuple)) and len(val) >= 3:
            nums = [float(val[0]), float(val[1]), float(val[2])]
            if max(nums) > 1.5:
                nums = [n / 255.0 for n in nums]
            return nums
    return list(fallback)


def _stabilize_terrain_fragment(src: str) -> str:
    """Цвет ландшафта только от мира, не от камеры/экрана."""
    text = src or ""
    text = text.replace("cameraPosition", "vWorldPos")
    text = text.replace("gl_FragCoord.xy", "(vWorldPos.xz * 32.0)")
    text = text.replace("gl_FragCoord.x", "(vWorldPos.x * 32.0)")
    text = text.replace("gl_FragCoord.y", "(vWorldPos.z * 32.0)")
    if "vWorldPos.y" not in text and "vPosition.y" not in text:
        text = text.replace(
            "void main()",
            "void main() /* height: use vWorldPos.y */",
            1,
        )
    return text


def _is_tree_prop(name: str, geometry: dict, template: str | None = None) -> bool:
    lowered = str(name or "").lower()
    tmpl = str(template or "").lower()
    if tmpl in ("oak", "birch", "pine", "bush", "flower", "mushroom", "cactus"):
        return True
    if any(word in lowered for word in ("tree", "oak", "pine", "birch", "fir", "spruce", "willow", "bush", "flower", "mushroom", "cactus")):
        return True
    types = [str(p.get("type") or "") for p in (geometry or {}).get("primitives") or []]
    has_trunk = "cylinder" in types
    has_crown = any(t in types for t in ("sphere", "cone", "icosahedron"))
    return has_trunk and has_crown


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