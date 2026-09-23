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
float noise(vec2 p){
  vec2 i = floor(p); vec2 f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(hash(i), hash(i+vec2(1.0,0.0)), f.x), mix(hash(i+vec2(0.0,1.0)), hash(i+vec2(1.0,1.0)), f.x), f.y);
}
float fbm(vec2 p){ return noise(p)*0.57 + noise(p*2.13)*0.28 + noise(p*4.27)*0.15; }
vec3 shadeLit(vec3 albedo, vec3 n, vec3 wp){
  vec3 L = normalize(vec3(0.46, 0.84, 0.26));
  float wrap = max(dot(normalize(n), L), 0.0) * 0.62 + 0.38;
  float band = floor(wrap * 5.0 + 0.35) / 5.0;
  float lit = mix(wrap, band, 0.55);
  vec3 light = mix(vec3(0.58, 0.68, 0.88), vec3(1.06, 0.97, 0.84), lit);
  vec3 c = albedo * light * (0.82 + 0.18 * clamp(n.y, 0.0, 1.0));
  c += (hash(floor(wp.xz * 18.0)) - 0.5) * 0.04;
  return floor(max(c, vec3(0.02)) * 20.0 + 0.5) / 20.0;
}
void main() {
  float clump = fbm(vPosition.xz * 2.8 + vUv * 5.0);
  vec3 c = mix(vec3(0.10, 0.32, 0.08), vec3(0.22, 0.58, 0.14), smoothstep(0.28, 0.62, clump));
  c = mix(c, vec3(0.34, 0.72, 0.18), smoothstep(0.62, 0.88, clump));
  gl_FragColor = vec4(shadeLit(c, vNormal, vPosition), 1.0);
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
float noise(vec2 p){
  vec2 i = floor(p); vec2 f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(hash(i), hash(i+vec2(1.0,0.0)), f.x), mix(hash(i+vec2(0.0,1.0)), hash(i+vec2(1.0,1.0)), f.x), f.y);
}
vec3 shadeLit(vec3 albedo, vec3 n, vec3 wp){
  vec3 L = normalize(vec3(0.46, 0.84, 0.26));
  float wrap = max(dot(normalize(n), L), 0.0) * 0.62 + 0.38;
  float band = floor(wrap * 5.0 + 0.35) / 5.0;
  float lit = mix(wrap, band, 0.55);
  vec3 light = mix(vec3(0.58, 0.68, 0.88), vec3(1.06, 0.97, 0.84), lit);
  vec3 c = albedo * light * (0.82 + 0.18 * clamp(n.y, 0.0, 1.0));
  c += (hash(floor(wp.xz * 18.0)) - 0.5) * 0.04;
  return floor(max(c, vec3(0.02)) * 20.0 + 0.5) / 20.0;
}
void main() {
  float ridge = abs(fract(vPosition.y * 6.5 + noise(vPosition.xz * 2.0) * 0.4) - 0.5);
  vec3 c = mix(vec3(0.28, 0.16, 0.07), vec3(0.48, 0.28, 0.12), noise(vPosition.xy * 3.0));
  c = mix(c, vec3(0.18, 0.10, 0.04), step(0.18, ridge) * 0.5);
  gl_FragColor = vec4(shadeLit(c, vNormal, vPosition), 1.0);
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
      fog: false,
      toneMapped: false,
      side: THREE.DoubleSide,
    }});
    mat.needsUpdate = true;
    return mat;
  }} catch (e) {{
    console.warn('[World] ShaderMaterial failed, solid color used:', e.message);
    return new THREE.MeshLambertMaterial({{
      color: fallbackColor,
      flatShading: true,
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
  Math.min(ATMOSPHERE.fog_density ?? 0.008, 0.014)
);

const camera = new THREE.PerspectiveCamera(
  40, container.clientWidth / container.clientHeight, 0.1, 500
);
camera.position.set(15, 12, 15);
camera.lookAt(0, 0, 0);

THREE.ColorManagement.enabled = false;
const renderer = new THREE.WebGLRenderer({{ antialias: false }});
renderer.setSize(container.clientWidth, container.clientHeight);
renderer.setPixelRatio(1);
renderer.outputColorSpace = THREE.LinearSRGBColorSpace;
renderer.toneMapping = THREE.NoToneMapping;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
container.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.target.set(0, 1, 0);
controls.maxPolarAngle = Math.PI * 0.9;

// Свет
const ambient = new THREE.AmbientLight(0x9aacc8, 0.72);
ambient.color.setRGB(
  ATMOSPHERE.ambient_color[0] / 255,
  ATMOSPHERE.ambient_color[1] / 255,
  ATMOSPHERE.ambient_color[2] / 255
);
scene.add(ambient);

const sun = new THREE.DirectionalLight(0xffe6b8, 1.25);
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

const fillLight = new THREE.DirectionalLight(0x6e88b8, 0.28);
fillLight.position.set(-10, 5, -10);
scene.add(fillLight);

const worldGroup = new THREE.Group();
scene.add(worldGroup);

{sky_block}

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
colorTex.colorSpace = THREE.NoColorSpace;
colorTex.wrapS = THREE.ClampToEdgeWrapping;
colorTex.wrapT = THREE.ClampToEdgeWrapping;
const terrainGeo = new THREE.PlaneGeometry(TERRAIN_SIZE, TERRAIN_SIZE, HEIGHTMAP_RES - 1, HEIGHTMAP_RES - 1);
terrainGeo.rotateX(-Math.PI / 2);
const tPos = terrainGeo.attributes.position;
const tCols = new Float32Array(tPos.count * 3);
const gCol = new THREE.Color({u_grass});
const dCol = new THREE.Color({u_dirt});
const rCol = new THREE.Color({u_rock});
const sCol = new THREE.Color({u_snow});
for (let i = 0; i < tPos.count; i++) {{
  const y = heightAt(tPos.getX(i), tPos.getZ(i));
  tPos.setY(i, y);
  const h = THREE.MathUtils.clamp(y / HEIGHT_SCALE, 0, 1);
  const c = dCol.clone().lerp(gCol, THREE.MathUtils.smoothstep(h, 0.08, 0.32));
  if (h > 0.62) c.lerp(rCol, THREE.MathUtils.smoothstep(h, 0.62, 0.82));
  if (h > 0.84) c.lerp(sCol, THREE.MathUtils.smoothstep(h, 0.84, 0.96));
  tCols[i * 3] = Math.round(c.r * 20) / 20;
  tCols[i * 3 + 1] = Math.round(c.g * 20) / 20;
  tCols[i * 3 + 2] = Math.round(c.b * 20) / 20;
}}
tPos.needsUpdate = true;
terrainGeo.setAttribute('color', new THREE.BufferAttribute(tCols, 3));
terrainGeo.computeVertexNormals();
terrainGeo.computeBoundingSphere();
terrainGeo.computeBoundingBox();

const terrainFallback = new THREE.MeshLambertMaterial({{
  color: 0xffffff,
  vertexColors: true,
  flatShading: true,
  side: THREE.DoubleSide,
  fog: true,
}});
const terrainShader = {{
  uniforms: {{
    uTime: {{ value: 0 }},
    uMap: {{ value: colorTex }},
    uGrass: {{ value: new THREE.Vector3({u_grass_vec}) }},
    uDirt: {{ value: new THREE.Vector3({u_dirt_vec}) }},
    uRock: {{ value: new THREE.Vector3({u_rock_vec}) }},
    uSnow: {{ value: new THREE.Vector3({u_snow_vec}) }},
  }},
  vertexShader: {terrain_vertex_json},
  fragmentShader: {terrain_fragment_json},
}};
let terrainMat = compileShader(terrainShader, 0x4a8a3a);
if (!terrainMat.isShaderMaterial) {{
  terrainMat = terrainFallback;
}} else {{
  terrainMat.side = THREE.DoubleSide;
  terrainMat.fog = false;
  terrainMat.toneMapped = false;
}}
const terrain = new THREE.Mesh(terrainGeo, terrainMat);
terrain.receiveShadow = true;
terrain.castShadow = false;
terrain.frustumCulled = false;
worldGroup.add(terrain);
requestAnimationFrame(() => {{
  const gl = renderer.getContext();
  const prog = terrainMat.program && terrainMat.program.program;
  if (terrainMat.isShaderMaterial && prog && gl && gl.getProgramParameter(prog, gl.LINK_STATUS) === false) {{
    console.warn('[World] Terrain shader failed, vertex-color Lambert used');
    terrain.material = terrainFallback;
  }}
}});

const waterMat = new THREE.MeshLambertMaterial({{
  color: 0x3a8ec8,
  transparent: true,
  opacity: 0.82,
  flatShading: true,
}});
function addRiverWater(path, widthUv) {{
  if (!path || path.length < 2) return;
  const halfW = Math.max(0.35, (widthUv || 0.05) * TERRAIN_SIZE * 0.7);
  const left = [];
  const right = [];
  for (let i = 0; i < path.length; i++) {{
    const p = path[i];
    const x = (p[0] - 0.5) * TERRAIN_SIZE;
    const z = (p[1] - 0.5) * TERRAIN_SIZE;
    const prev = path[Math.max(0, i - 1)];
    const next = path[Math.min(path.length - 1, i + 1)];
    const dx = (next[0] - prev[0]) * TERRAIN_SIZE;
    const dz = (next[1] - prev[1]) * TERRAIN_SIZE;
    const len = Math.max(0.0001, Math.hypot(dx, dz));
    const nx = -dz / len;
    const nz = dx / len;
    const y = heightAt(x, z) + 0.08;
    left.push(new THREE.Vector3(x + nx * halfW, y, z + nz * halfW));
    right.push(new THREE.Vector3(x - nx * halfW, y, z - nz * halfW));
  }}
  const geo = new THREE.BufferGeometry();
  const verts = [];
  const idx = [];
  for (let i = 0; i < left.length; i++) {{
    verts.push(left[i].x, left[i].y, left[i].z);
    verts.push(right[i].x, right[i].y, right[i].z);
    if (i < left.length - 1) {{
      const a = i * 2;
      idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
    }}
  }}
  geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
  geo.setIndex(idx);
  geo.computeVertexNormals();
  const mesh = new THREE.Mesh(geo, waterMat);
  mesh.renderOrder = 1;
  worldGroup.add(mesh);
}}
for (const river of RIVER_PATHS) addRiverWater(river.points, river.width);
for (const lake of LAKE_SPOTS) {{
  const x = (lake.center[0] - 0.5) * TERRAIN_SIZE;
  const z = (lake.center[1] - 0.5) * TERRAIN_SIZE;
  const mesh = new THREE.Mesh(
    new THREE.CircleGeometry(Math.max(0.7, (lake.radius || 0.12) * TERRAIN_SIZE), 14),
    waterMat
  );
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.set(x, heightAt(x, z) + 0.07, z);
  worldGroup.add(mesh);
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

DEFAULT_SKY_VERTEX = """varying vec3 vDir;
void main() {
  vDir = position;
  vec4 clip = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  gl_Position = clip.xyww;
}"""

DEFAULT_SKY_FRAGMENT = """uniform float uTime;
uniform vec3 uSkyTop;
uniform vec3 uSkyHorizon;
uniform vec3 uCloud;
varying vec3 vDir;
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p){
  vec2 i = floor(p); vec2 f = fract(p);
  float a = hash(i); float b = hash(i + vec2(1.0, 0.0));
  float c = hash(i + vec2(0.0, 1.0)); float d = hash(i + vec2(1.0, 1.0));
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}
float fbm(vec2 p){
  float v = 0.0; float a = 0.5;
  for (int i = 0; i < 5; i++) { v += a * noise(p); p *= 2.03; a *= 0.5; }
  return v;
}
void main() {
  vec3 dir = normalize(vDir);
  float h = clamp(dir.y * 0.5 + 0.5, 0.0, 1.0);
  vec3 col = mix(uSkyHorizon, uSkyTop, pow(h, 0.65));
  vec2 uv = dir.xz / max(dir.y + 0.25, 0.05);
  float clouds = fbm(uv * 1.6 + vec2(uTime * 0.012, 0.0));
  clouds = smoothstep(0.52, 0.78, clouds) * smoothstep(0.02, 0.28, dir.y);
  col = mix(col, uCloud, clouds * 0.85);
  gl_FragColor = vec4(col, 1.0);
}"""


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
        sky_block=_build_sky_block(plan.get("atmosphere") or {}),
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
    tu = dict((tsh.get("uniforms") or {}) if isinstance(tsh, dict) else {})
    grass = _vec3_uniform(tu.get("uGrass"), (0.22, 0.52, 0.16))
    dirt = _vec3_uniform(tu.get("uDirt"), (0.42, 0.28, 0.12))
    rock = _vec3_uniform(tu.get("uRock"), (0.52, 0.48, 0.42))
    snow = _vec3_uniform(tu.get("uSnow"), (0.90, 0.92, 0.94))
    def _hex(rgb):
        return f"0x{int(rgb[0]*255):02x}{int(rgb[1]*255):02x}{int(rgb[2]*255):02x}"
    from .templates import TERRAIN_FRAGMENT
    terrain_fragment = _stabilize_terrain_fragment((tsh.get("fragment") if isinstance(tsh, dict) else None) or "")
    if "gl_FragColor" not in terrain_fragment or "precision" in terrain_fragment:
        terrain_fragment = TERRAIN_FRAGMENT
    parts.append(JS_TERRAIN.format(
        heightmap_js=heightmap_js,
        heightmap_res=128,
        terrain_size=20,
        height_scale=4.0,
        water_level="null" if water is None else float(water),
        colormap_b64=colormap_b64 or "",
        river_paths_json=json.dumps(rivers),
        lake_spots_json=json.dumps(lakes),
        terrain_vertex_json=json.dumps(TERRAIN_VERTEX),
        terrain_fragment_json=json.dumps(terrain_fragment),
        u_grass=_hex(grass),
        u_dirt=_hex(dirt),
        u_rock=_hex(rock),
        u_snow=_hex(snow),
        u_grass_vec=f"{grass[0]}, {grass[1]}, {grass[2]}",
        u_dirt_vec=f"{dirt[0]}, {dirt[1]}, {dirt[2]}",
        u_rock_vec=f"{rock[0]}, {rock[1]}, {rock[2]}",
        u_snow_vec=f"{snow[0]}, {snow[1]}, {snow[2]}",
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


def _rgb01_from_255(value, fallback):
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            nums = [float(value[0]), float(value[1]), float(value[2])]
            if max(nums) > 1.5:
                nums = [n / 255.0 for n in nums]
            return [max(0.0, min(1.0, n)) for n in nums]
        except (TypeError, ValueError):
            pass
    return list(fallback)


def _build_sky_block(atmo: dict) -> str:
    top = _rgb01_from_255(atmo.get("sky_color"), [0.45, 0.72, 0.98])
    horizon = _rgb01_from_255(atmo.get("horizon_color"), [0.78, 0.88, 0.98])
    cloud = _rgb01_from_255(atmo.get("cloud_color"), [0.95, 0.97, 1.0])
    mode = str(atmo.get("sky_mode") or "default").lower()
    shader = atmo.get("sky_shader") if isinstance(atmo.get("sky_shader"), dict) else {}
    fragment = (shader.get("fragment") or "").strip()
    vertex = (shader.get("vertex") or "").strip() or DEFAULT_SKY_VERTEX
    if mode == "custom" and "gl_FragColor" in fragment and "vDir" in fragment:
        extra = {k: v for k, v in (shader.get("uniforms") or {}).items() if k not in ("uTime", "uSkyTop", "uSkyHorizon", "uCloud")}
        extra_lines = _build_uniforms_lines(extra, ensure_time=False)
        extra_js = (extra_lines + ",") if extra_lines else ""
        frag_js = json.dumps(fragment, ensure_ascii=False)
        vert_js = json.dumps(vertex, ensure_ascii=False)
    else:
        extra_js = ""
        frag_js = json.dumps(DEFAULT_SKY_FRAGMENT, ensure_ascii=False)
        vert_js = json.dumps(DEFAULT_SKY_VERTEX, ensure_ascii=False)
    return f"""const skyUniforms = {{
  uTime: {{ value: 0 }},
  uSkyTop: {{ value: new THREE.Color({top[0]}, {top[1]}, {top[2]}) }},
  uSkyHorizon: {{ value: new THREE.Color({horizon[0]}, {horizon[1]}, {horizon[2]}) }},
  uCloud: {{ value: new THREE.Color({cloud[0]}, {cloud[1]}, {cloud[2]}) }},
{extra_js}
}};
const skyMat = new THREE.ShaderMaterial({{
  uniforms: skyUniforms,
  side: THREE.BackSide,
  depthWrite: false,
  fog: false,
  toneMapped: false,
  vertexShader: {vert_js},
  fragmentShader: {frag_js},
}});
const sky = new THREE.Mesh(new THREE.SphereGeometry(160, 24, 16), skyMat);
sky.renderOrder = -1;
scene.add(sky);
"""
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
    if any(word in lowered for word in ("house", "hut", "cabin", "cottage", "barn", "tower", "дом", "хижина", "изба")):
        return False
    if tmpl in ("oak", "birch", "pine", "fir", "bush", "flower", "mushroom", "cactus"):
        return True
    if any(word in lowered for word in ("tree", "oak", "pine", "birch", "fir", "spruce", "ёлка", "елка", "ель", "willow", "bush", "flower", "mushroom", "cactus")):
        return True
    types = [str(p.get("type") or "") for p in (geometry or {}).get("primitives") or []]
    has_box = "box" in types
    has_trunk = "cylinder" in types
    has_crown = any(t in types for t in ("sphere", "cone", "icosahedron"))
    if has_box:
        return False
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


def _build_uniforms_lines(uniforms: dict, ensure_time: bool = True) -> str:
    """
    Строит JS-код для uniforms.
    Возвращает строки, разделённые ',\n' — БЕЗ запятой в конце.
    Всегда гарантирует наличие uTime.
    """
    # Копируем, чтобы не мутировать оригинал
    u = dict(uniforms or {})

    # Гарантируем uTime
    if ensure_time and 'uTime' not in u:
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