/**
 * AI World Generator — сгенерированный мир: Зелёный Брод
 * Травяная поляна с редколесьем и валунами, мягкий дневной свет, через карту течёт неглубокая река. Тихая пограничная долина для стартовой базы.
 *
 * Подключение:
 *   <div id="world-container"></div>
 *   <script type="importmap">
 *   {
 *     "imports": {
 *       "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
 *       "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
 *     }
 *   }
 *   </script>
 *   <script type="module" src="./world.js"></script>
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';

// ============================================================
// НАСТРОЙКИ МИРА
// ============================================================
const WORLD_NAME = "Зелёный Брод";
const DESCRIPTION = "Травяная поляна с редколесьем и валунами, мягкий дневной свет, через карту течёт неглубокая река. Тихая пограничная долина для стартовой базы.";

const ATMOSPHERE = {
  "time_of_day": "day",
  "clouds": true,
  "fog_color": [
    170,
    200,
    230
  ],
  "fog_density": 0.009,
  "sky_color": [
    135,
    185,
    235
  ],
  "sun_color": [
    255,
    246,
    224
  ],
  "ambient_color": [
    152,
    172,
    200
  ]
};

// ============================================================
// PRIMITIVE BUILDERS
// ============================================================
const PRIMITIVE_BUILDERS = {
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
};

const _loader = new THREE.TextureLoader();
function loadB64Texture(b64, nearest = true) {
  const tex = _loader.load(`data:image/png;base64,${b64}`);
  if (nearest) {
    tex.minFilter = THREE.NearestFilter;
    tex.magFilter = THREE.NearestFilter;
  }
  return tex;
}

function buildPrimitive(prim) {
  const builder = PRIMITIVE_BUILDERS[prim.type];
  if (!builder) {
    console.warn(`[World] Unknown primitive: ${prim.type}`);
    return null;
  }
  try {
    return builder(prim.params || {});
  } catch (e) {
    console.warn(`[World] Failed to build ${prim.type}:`, e);
    return null;
  }
}

function applyTransform(mesh, prim) {
  if (prim.position) mesh.position.set(...prim.position);
  if (prim.rotation) mesh.rotation.set(
    prim.rotation[0] * Math.PI / 180,
    prim.rotation[1] * Math.PI / 180,
    prim.rotation[2] * Math.PI / 180
  );
  if (prim.scale) {
    if (Array.isArray(prim.scale)) mesh.scale.set(...prim.scale);
    else mesh.scale.setScalar(prim.scale);
  }
}

function compileShader(config, fallbackColor = 0x7a9a5a) {
  try {
    const mat = new THREE.ShaderMaterial({
      uniforms: config.uniforms,
      vertexShader: config.vertexShader,
      fragmentShader: config.fragmentShader,
      lights: false,
      side: THREE.DoubleSide,
    });
    mat.needsUpdate = true;
    return mat;
  } catch (e) {
    console.warn('[World] ShaderMaterial failed, solid color used:', e.message);
    return new THREE.MeshStandardMaterial({
      color: fallbackColor,
      flatShading: true,
      roughness: 0.9,
    });
  }
}

function propFallbackColor(uniforms) {
  for (const key of Object.keys(uniforms || {})) {
    const val = uniforms[key] && uniforms[key].value;
    if (val && val.isColor) return val.getHex();
    if (val && val.isVector3) {
      return new THREE.Color(val.x, val.y, val.z).getHex();
    }
  }
  return 0x7a9a5a;
}

// ============================================================
// ИНИЦИАЛИЗАЦИЯ СЦЕНЫ
// ============================================================
const container = document.getElementById('world-container');
if (!container) {
  throw new Error('Element #world-container not found');
}

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

const renderer = new THREE.WebGLRenderer({ antialias: true });
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

const skyUniforms = {
  uTime: { value: 0 },
  uSkyTop: { value: new THREE.Color(0.45, 0.72, 0.98) },
  uSkyHorizon: { value: new THREE.Color(0.78, 0.88, 0.98) },
  uCloud: { value: new THREE.Color(0.95, 0.97, 1.0) },
};
const skyMat = new THREE.ShaderMaterial({
  uniforms: skyUniforms,
  side: THREE.BackSide,
  depthWrite: false,
  fog: false,
  vertexShader: `
    varying vec3 vDir;
    void main() {
      vDir = position;
      vec4 clip = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      gl_Position = clip.xyww;
    }
  `,
  fragmentShader: `
    uniform float uTime;
    uniform vec3 uSkyTop;
    uniform vec3 uSkyHorizon;
    uniform vec3 uCloud;
    varying vec3 vDir;
    float hash(vec2 p) {
      return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
    }
    float noise(vec2 p) {
      vec2 i = floor(p);
      vec2 f = fract(p);
      float a = hash(i);
      float b = hash(i + vec2(1.0, 0.0));
      float c = hash(i + vec2(0.0, 1.0));
      float d = hash(i + vec2(1.0, 1.0));
      vec2 u = f * f * (3.0 - 2.0 * f);
      return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
    }
    float fbm(vec2 p) {
      float v = 0.0;
      float a = 0.5;
      for (int i = 0; i < 5; i++) {
        v += a * noise(p);
        p *= 2.03;
        a *= 0.5;
      }
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
    }
  `,
});
const sky = new THREE.Mesh(new THREE.SphereGeometry(160, 24, 16), skyMat);
sky.renderOrder = -1;
scene.add(sky);

// ============================================================
// ЛАНДШАФТ
// ============================================================

const HEIGHTMAP_B64 = "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";
const COLORMAP_B64 = "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";
const HEIGHTMAP = [0.6428,0.5572,0.5500,0.5505,0.5634,0.6438,0.6567,0.6567,0.6438,0.5640,0.5567,0.5505,0.5567,0.6366,0.6495,0.6495,0.6433,0.6360,0.5567,0.5572,0.6428,0.6572,0.7428,0.7433,0.6634,0.6438,0.5640,0.5573,0.5640,0.6438,0.6567,0.6573,0.6572,0.6500,0.5645,0.5500,0.4645,0.4567,0.4511,0.4634,0.5438,0.5634,0.6433,0.6500,0.6572,0.7428,0.7500,0.7500,0.7428,0.6572,0.6500,0.6500,0.6500,0.6572,0.7433,0.7567,0.7572,0.7500,0.6640,0.6438,0.5567,0.4640,0.4505,0.4567,0.5366,0.5562,0.6360,0.6427,0.6427,0.6427,0.6428,0.6433,0.6495,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6505,0.6567,0.6567,0.6505,0.6500,0.6433,0.5707,0.6433,0.6505,0.6634,0.7433,0.7433,0.6634,0.6433,0.5505,0.4634,0.4505,0.4500,0.4572,0.5428,0.5572,0.6428,0.6572,0.7428,0.7500,0.7500,0.7495,0.7366,0.6562,0.6433,0.6427,0.6427,0.6433,0.6562,0.7366,0.7489,0.7366,0.6562,0.6360,0.5500,0.6500,0.5645,0.5573,0.5634,0.6376,0.6624,0.7366,0.7366,0.6624,0.6438,0.6360,0.5567,0.5505,0.5629,0.6366,0.6366,0.5634,0.5562,0.5443,0.5562,0.6366,0.6567,0.7428,0.7495,0.7371,0.6629,0.6500,0.6433,0.6438,0.6624,0.7371,0.7495,0.7495,0.7366,0.6562,0.6366,0.5562,0.5371,0.4696,0.5371,0.5562,0.6366,0.6495,0.6500,0.6572,0.7428,0.7500,0.7495,0.7366,0.6567,0.6500,0.6500,0.6500,0.6572,0.7495,0.8360,0.8427,0.8360,0.7500,0.6629,0.6371,0.5500,0.4640,0.4573,0.4634,0.5371,0.5495,0.5500,0.5500,0.5505,0.5567,0.5640,0.6433,0.6505,0.6567,0.6572,0.6572,0.6572,0.6572,0.6567,0.6505,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6505,0.6629,0.7366,0.7366,0.6629,0.6505,0.6495,0.6438,0.6500,0.6629,0.7371,0.7495,0.7495,0.7366,0.6500,0.5629,0.5371,0.4567,0.4500,0.4572,0.5428,0.5572,0.6428,0.6567,0.7360,0.7428,0.7427,0.7360,0.6562,0.6366,0.5567,0.5500,0.5505,0.5629,0.6376,0.6624,0.7304,0.6624,0.6371,0.5500,0.4640,0.7355,0.6500,0.6433,0.6500,0.6629,0.7376,0.7562,0.7562,0.7376,0.6629,0.6433,0.5572,0.5495,0.5438,0.5495,0.5495,0.5433,0.5366,0.4696,0.5376,0.5629,0.6505,0.7428,0.7505,0.7557,0.7438,0.7366,0.6634,0.6634,0.7376,0.7624,0.8366,0.8366,0.7624,0.7376,0.6629,0.6438,0.5634,0.5511,0.5567,0.5640,0.6433,0.6500,0.6500,0.6567,0.7360,0.7427,0.7366,0.6629,0.6505,0.6495,0.6433,0.6433,0.6567,0.7500,0.8427,0.8500,0.8495,0.8366,0.7500,0.6634,0.6433,0.5567,0.5371,0.4640,0.4640,0.4640,0.4578,0.4573,0.4634,0.5371,0.5567,0.6428,0.6567,0.7360,0.7428,0.7428,0.7428,0.7428,0.7366,0.6634,0.6572,0.6572,0.6572,0.6572,0.6572,0.6573,0.6634,0.7371,0.7495,0.7495,0.7366,0.6567,0.6500,0.6500,0.6567,0.7366,0.7500,0.7567,0.7567,0.7438,0.6629,0.6371,0.5500,0.4634,0.4505,0.4572,0.5428,0.5567,0.6366,0.6500,0.6567,0.6567,0.6505,0.6433,0.5634,0.5438,0.4640,0.4573,0.4634,0.5376,0.5624,0.6371,0.6489,0.6366,0.5500,0.4629,0.4438,0.7433,0.6640,0.6634,0.7366,0.7438,0.7624,0.8366,0.8360,0.7557,0.7304,0.6489,0.5567,0.5366,0.4567,0.4500,0.4505,0.4567,0.4567,0.4511,0.4634,0.5505,0.6500,0.7428,0.7562,0.8231,0.7562,0.7500,0.7500,0.7505,0.7629,0.8371,0.8495,0.8495,0.8366,0.7562,0.7433,0.7360,0.6567,0.6495,0.6433,0.6433,0.6495,0.6495,0.6433,0.6433,0.6495,0.6500,0.6495,0.6433,0.6428,0.6366,0.5634,0.5640,0.6500,0.7433,0.8360,0.8495,0.8500,0.8495,0.8366,0.7562,0.7366,0.6500,0.5634,0.5500,0.5433,0.5366,0.4629,0.4505,0.4505,0.4634,0.5500,0.6366,0.6562,0.7366,0.7495,0.7500,0.7500,0.7500,0.7495,0.7433,0.7428,0.7428,0.7428,0.7428,0.7433,0.7495,0.7505,0.7562,0.7505,0.7500,0.7428,0.6572,0.6500,0.6500,0.6572,0.7428,0.7567,0.8360,0.8360,0.7562,0.7366,0.6495,0.5567,0.5366,0.4567,0.4572,0.5428,0.5505,0.5629,0.6366,0.6427,0.6360,0.5567,0.5495,0.5371,0.4629,0.4505,0.4500,0.4511,0.4696,0.5443,0.5567,0.5567,0.5438,0.4629,0.4376,0.3634,0.7495,0.7433,0.7433,0.7500,0.7629,0.8371,0.8489,0.8366,0.7500,0.6629,0.6366,0.5433,0.4500,0.3640,0.3573,0.3634,0.4371,0.4495,0.4505,0.4634,0.5505,0.6495,0.7360,0.7438,0.7557,0.7505,0.7567,0.8360,0.8427,0.8433,0.8489,0.8433,0.8427,0.8360,0.7567,0.7505,0.7562,0.7500,0.7371,0.6634,0.6567,0.6500,0.6371,0.5634,0.5572,0.5572,0.5572,0.5572,0.5572,0.5572,0.5567,0.5505,0.5567,0.6366,0.6567,0.7495,0.8360,0.8427,0.8428,0.8427,0.8366,0.7629,0.7433,0.6572,0.6433,0.5640,0.5562,0.5376,0.4629,0.4505,0.4567,0.5371,0.5624,0.6376,0.6624,0.7371,0.7495,0.7500,0.7500,0.7500,0.7500,0.7500,0.7500,0.7505,0.7567,0.7634,0.8366,0.8427,0.8366,0.7629,0.7505,0.7428,0.6572,0.6500,0.6500,0.6572,0.7428,0.7567,0.8360,0.8360,0.7562,0.7366,0.6495,0.5572,0.5428,0.4572,0.4567,0.5366,0.5495,0.5500,0.5500,0.5500,0.5428,0.4572,0.4500,0.4500,0.4500,0.4505,0.4567,0.4640,0.5438,0.5567,0.5567,0.5438,0.4634,0.4438,0.3634,0.3505,0.7500,0.7500,0.7505,0.7629,0.8371,0.8495,0.8433,0.7629,0.7371,0.6500,0.5567,0.4572,0.3634,0.3443,0.3495,0.3511,0.3696,0.4443,0.4629,0.5376,0.5629,0.6438,0.6567,0.6634,0.7371,0.7495,0.7572,0.8427,0.8500,0.8495,0.8371,0.7629,0.7511,0.7562,0.7505,0.7567,0.8360,0.8366,0.7629,0.7500,0.7366,0.6500,0.5634,0.5500,0.5433,0.5428,0.5428,0.5433,0.5495,0.5500,0.5500,0.5500,0.5505,0.5567,0.5640,0.6505,0.7427,0.7500,0.7505,0.7629,0.8366,0.8427,0.8360,0.7567,0.7428,0.6567,0.6371,0.5624,0.5376,0.4629,0.4511,0.4629,0.5376,0.5624,0.6376,0.6624,0.7366,0.7433,0.7495,0.7500,0.7500,0.7500,0.7500,0.7562,0.8298,0.8427,0.8495,0.8500,0.8489,0.8304,0.7557,0.7366,0.6567,0.6500,0.6500,0.6567,0.7366,0.7500,0.7567,0.7567,0.7438,0.6629,0.6371,0.5567,0.5428,0.4578,0.4573,0.4702,0.5438,0.5433,0.4640,0.4567,0.4438,0.3640,0.3573,0.3640,0.4438,0.4629,0.5371,0.5567,0.6428,0.6495,0.6371,0.5562,0.4640,0.4438,0.3634,0.3505,0.7428,0.7433,0.7557,0.8304,0.8489,0.8495,0.8366,0.7500,0.6629,0.6371,0.5489,0.4438,0.3500,0.2707,0.3433,0.3567,0.4371,0.4629,0.5438,0.5629,0.6371,0.6489,0.6433,0.6433,0.6562,0.7366,0.7562,0.8360,0.8427,0.8366,0.7624,0.7376,0.6696,0.7366,0.7433,0.7567,0.8427,0.8495,0.8433,0.8360,0.7495,0.6500,0.5573,0.5433,0.4640,0.4572,0.4572,0.4640,0.5433,0.5500,0.5500,0.5500,0.5500,0.5500,0.5505,0.5634,0.6433,0.6505,0.6629,0.7376,0.7629,0.8433,0.8495,0.8433,0.8360,0.7500,0.6629,0.6371,0.5562,0.5366,0.4567,0.4505,0.4629,0.5376,0.5624,0.6376,0.6562,0.6634,0.7366,0.7428,0.7428,0.7428,0.7433,0.7500,0.7629,0.8366,0.8433,0.8495,0.8433,0.7634,0.7438,0.6634,0.6505,0.6500,0.6500,0.6505,0.6634,0.7433,0.7500,0.7495,0.7366,0.6500,0.5634,0.5505,0.5433,0.4702,0.5366,0.5433,0.5495,0.5433,0.4634,0.4438,0.3634,0.3505,0.3500,0.3573,0.4495,0.5371,0.5629,0.6500,0.7366,0.7427,0.6634,0.6433,0.5505,0.4634,0.4438,0.3640,0.6572,0.6640,0.7438,0.7634,0.8433,0.8433,0.7634,0.7433,0.6505,0.5629,0.5304,0.3702,0.3438,0.2707,0.3438,0.3640,0.4567,0.5500,0.6366,0.6495,0.6500,0.6433,0.5640,0.5573,0.5645,0.6562,0.7376,0.7562,0.7572,0.7562,0.7376,0.6624,0.6449,0.6562,0.6640,0.7500,0.8366,0.8495,0.8500,0.8427,0.7500,0.6505,0.5634,0.5433,0.4573,0.4500,0.4505,0.4634,0.5433,0.5505,0.5567,0.5567,0.5505,0.5500,0.5495,0.5438,0.5500,0.5629,0.6376,0.6629,0.7500,0.8366,0.8495,0.8500,0.8495,0.8360,0.7433,0.6495,0.5572,0.5428,0.4572,0.4500,0.4505,0.4634,0.5438,0.5634,0.6433,0.6505,0.6567,0.6572,0.6572,0.6572,0.6634,0.7366,0.7433,0.7500,0.7629,0.8366,0.8360,0.7567,0.7428,0.6572,0.6500,0.6500,0.6500,0.6500,0.6572,0.7428,0.7500,0.7433,0.6634,0.6433,0.5572,0.5500,0.5495,0.5438,0.5500,0.5567,0.5572,0.5562,0.5376,0.4562,0.3640,0.3505,0.3505,0.3634,0.4505,0.5495,0.6433,0.7366,0.7624,0.8298,0.7562,0.7360,0.6433,0.5562,0.5366,0.4567,0.6500,0.6567,0.7366,0.7562,0.8360,0.8360,0.7567,0.7428,0.6500,0.5505,0.4567,0.3640,0.3500,0.3438,0.3562,0.4433,0.5428,0.6366,0.6624,0.7304,0.6629,0.6433,0.5572,0.5500,0.5567,0.6371,0.6629,0.7433,0.7500,0.7433,0.6634,0.6438,0.5702,0.6371,0.6562,0.7371,0.7629,0.8433,0.8500,0.8428,0.7505,0.6629,0.6371,0.5500,0.4634,0.4505,0.4567,0.5366,0.5500,0.5629,0.6366,0.6366,0.5629,0.5505,0.5433,0.4640,0.4640,0.5438,0.5634,0.6500,0.7371,0.7629,0.8433,0.8500,0.8495,0.8360,0.7433,0.6495,0.5567,0.5366,0.4567,0.4500,0.4500,0.4573,0.5433,0.5634,0.6433,0.6500,0.6500,0.6500,0.6495,0.6433,0.6433,0.6495,0.6505,0.6629,0.7371,0.7500,0.7562,0.7500,0.7366,0.6567,0.6500,0.6500,0.6500,0.6500,0.6572,0.7428,0.7500,0.7428,0.6572,0.6428,0.5572,0.5500,0.5500,0.5505,0.5629,0.6366,0.6428,0.6366,0.5624,0.5366,0.4438,0.3629,0.3573,0.4366,0.4567,0.5500,0.6500,0.7495,0.8366,0.8489,0.8371,0.7562,0.6640,0.6438,0.5634,0.5505,0.6433,0.6500,0.6634,0.7438,0.7567,0.7567,0.7500,0.7366,0.6495,0.5505,0.4629,0.4371,0.3567,0.3505,0.3640,0.4572,0.5572,0.6562,0.7371,0.7489,0.7366,0.6495,0.5572,0.5500,0.5505,0.5634,0.6500,0.7366,0.7489,0.7366,0.6562,0.6366,0.5573,0.5634,0.6438,0.6634,0.7505,0.8427,0.8500,0.8428,0.7567,0.7366,0.6495,0.5562,0.5304,0.4562,0.4572,0.5428,0.5567,0.6366,0.6495,0.6495,0.6366,0.5567,0.5428,0.4573,0.4567,0.5366,0.5562,0.6371,0.6629,0.7500,0.8366,0.8489,0.8371,0.7562,0.6634,0.6371,0.5500,0.4634,0.4505,0.4500,0.4505,0.4634,0.5500,0.6366,0.6495,0.6500,0.6500,0.6495,0.6371,0.5629,0.5505,0.5500,0.5567,0.6366,0.6500,0.6629,0.7366,0.7366,0.6629,0.6505,0.6500,0.6500,0.6500,0.6500,0.6567,0.7366,0.7489,0.7366,0.6562,0.6366,0.5567,0.5500,0.5505,0.5629,0.6376,0.6562,0.6572,0.6567,0.6438,0.5567,0.4634,0.4376,0.3702,0.4438,0.4634,0.5505,0.6500,0.7500,0.8433,0.8567,0.8562,0.8371,0.7562,0.7366,0.6562,0.6433,0.5707,0.6438,0.6572,0.7428,0.7500,0.7500,0.7433,0.6634,0.6433,0.5562,0.5304,0.4495,0.3640,0.3640,0.4505,0.5500,0.6500,0.7433,0.7567,0.7567,0.7433,0.6500,0.5572,0.5500,0.5500,0.5572,0.6433,0.6629,0.7304,0.6629,0.6438,0.5634,0.5505,0.5567,0.6366,0.6562,0.7433,0.8355,0.8427,0.8360,0.7562,0.7360,0.6433,0.5500,0.4634,0.4505,0.4567,0.5366,0.5567,0.6427,0.6500,0.6500,0.6427,0.5572,0.5433,0.4634,0.4511,0.4629,0.5376,0.5624,0.6438,0.7360,0.7562,0.8298,0.7624,0.7371,0.6505,0.5696,0.5443,0.4634,0.4505,0.4500,0.4567,0.5366,0.5567,0.6428,0.6505,0.6567,0.6567,0.6438,0.5629,0.5376,0.4629,0.4505,0.4572,0.5428,0.5567,0.6366,0.6500,0.6562,0.6505,0.6500,0.6500,0.6500,0.6500,0.6500,0.6505,0.6629,0.7304,0.6629,0.6438,0.5634,0.5505,0.5500,0.5567,0.6371,0.6629,0.7433,0.7500,0.7495,0.7360,0.6433,0.5500,0.4629,0.4443,0.4562,0.5371,0.5629,0.6505,0.7500,0.8495,0.9360,0.9360,0.8562,0.8366,0.7562,0.7366,0.6567,0.6433,0.6495,0.6567,0.7360,0.7428,0.7428,0.7355,0.6500,0.6360,0.5505,0.4696,0.4511,0.4500,0.4573,0.5500,0.6500,0.7495,0.8360,0.8427,0.8360,0.7495,0.6500,0.5573,0.5500,0.5500,0.5567,0.6366,0.6500,0.6562,0.6505,0.6428,0.5572,0.5500,0.5505,0.5634,0.6438,0.6634,0.7438,0.7562,0.7500,0.7366,0.6500,0.5629,0.5371,0.4562,0.4433,0.4438,0.4624,0.5438,0.6355,0.6428,0.6428,0.6360,0.5567,0.5495,0.5366,0.4567,0.4505,0.4629,0.5371,0.5567,0.6428,0.6567,0.7360,0.7366,0.6629,0.6500,0.6371,0.5624,0.5376,0.4634,0.4573,0.4640,0.5438,0.5634,0.6438,0.6629,0.7366,0.7366,0.6562,0.5578,0.4702,0.4443,0.3640,0.3640,0.4433,0.4572,0.5428,0.5567,0.6366,0.6495,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6505,0.6562,0.6500,0.6366,0.5567,0.5500,0.5505,0.5640,0.6567,0.7500,0.8360,0.8427,0.8360,0.7500,0.6629,0.6366,0.5438,0.4634,0.4640,0.5500,0.6371,0.6629,0.7505,0.8500,0.9427,0.9427,0.8567,0.8366,0.7562,0.7366,0.6567,0.6500,0.6500,0.6505,0.6567,0.6572,0.6567,0.6438,0.5640,0.5567,0.5500,0.5371,0.4702,0.5433,0.5572,0.6500,0.7495,0.8366,0.8495,0.8500,0.8427,0.7500,0.6505,0.5634,0.5505,0.5500,0.5505,0.5629,0.6371,0.6495,0.6500,0.6428,0.5572,0.5500,0.5500,0.5567,0.6366,0.6500,0.6629,0.7304,0.6629,0.6438,0.5629,0.5376,0.4624,0.4376,0.3634,0.3634,0.4376,0.4629,0.5438,0.5567,0.5572,0.5567,0.5511,0.5562,0.5438,0.4640,0.4567,0.4511,0.4567,0.4640,0.5433,0.5505,0.5634,0.6433,0.6500,0.6500,0.6495,0.6371,0.5629,0.5500,0.5433,0.5433,0.5562,0.6366,0.6562,0.7366,0.7495,0.7495,0.7366,0.6490,0.5438,0.4495,0.3573,0.3505,0.3567,0.3640,0.4438,0.4640,0.5567,0.6433,0.6500,0.6500,0.6500,0.6495,0.6433,0.6428,0.6428,0.6428,0.6366,0.5629,0.5505,0.5500,0.5567,0.6433,0.7428,0.8360,0.8495,0.8500,0.8427,0.7562,0.7304,0.6489,0.5567,0.5433,0.5438,0.5629,0.6500,0.7366,0.7567,0.8495,0.9360,0.9360,0.8500,0.7629,0.7371,0.6562,0.6433,0.6572,0.6567,0.6505,0.6495,0.6433,0.6366,0.5629,0.5505,0.5500,0.5500,0.5500,0.5567,0.6366,0.6567,0.7495,0.8366,0.8495,0.8500,0.8495,0.8366,0.7495,0.6567,0.6366,0.5567,0.5500,0.5500,0.5505,0.5629,0.6371,0.6495,0.6433,0.5640,0.5567,0.5505,0.5505,0.5629,0.6366,0.6433,0.6489,0.6371,0.5629,0.5438,0.4634,0.4438,0.3634,0.3505,0.3505,0.3629,0.4376,0.4624,0.5371,0.5495,0.5505,0.5629,0.6304,0.5629,0.5500,0.5366,0.4567,0.4495,0.4438,0.4495,0.4500,0.4573,0.5495,0.6366,0.6495,0.6505,0.6562,0.6505,0.6433,0.5640,0.5567,0.5572,0.6366,0.6567,0.7427,0.7505,0.7567,0.7567,0.7371,0.5702,0.4578,0.3645,0.3567,0.3505,0.3505,0.3634,0.4505,0.5495,0.6366,0.6495,0.6500,0.6500,0.6433,0.5640,0.5572,0.5572,0.5572,0.5567,0.5505,0.5500,0.5505,0.5634,0.6505,0.7500,0.8427,0.8500,0.8495,0.8366,0.7500,0.6629,0.6371,0.5567,0.5500,0.5567,0.6366,0.6567,0.7428,0.7572,0.8433,0.8567,0.8562,0.8366,0.7438,0.6562,0.5640,0.5505,0.7422,0.7298,0.6562,0.6433,0.5640,0.5567,0.5505,0.5500,0.5500,0.5500,0.5567,0.6371,0.6624,0.7438,0.8360,0.8489,0.8433,0.8427,0.8360,0.7562,0.7366,0.6567,0.6433,0.5640,0.5567,0.5505,0.5500,0.5505,0.5634,0.6433,0.6495,0.6433,0.6366,0.5629,0.5505,0.5505,0.5567,0.5572,0.5573,0.5567,0.5505,0.5428,0.4572,0.4428,0.3573,0.3500,0.3500,0.3505,0.3634,0.4438,0.4634,0.5438,0.5629,0.6376,0.6557,0.6505,0.6433,0.5567,0.4640,0.4443,0.3702,0.3573,0.3511,0.3634,0.4511,0.5562,0.6433,0.6567,0.7360,0.7427,0.7355,0.6500,0.6360,0.5572,0.5634,0.6500,0.7366,0.7562,0.8366,0.8489,0.8360,0.7360,0.5567,0.4573,0.4433,0.3634,0.3505,0.3573,0.4500,0.5433,0.5634,0.6433,0.6500,0.6500,0.6428,0.5572,0.5500,0.5500,0.5500,0.5500,0.5500,0.5500,0.5567,0.6371,0.6629,0.7505,0.8428,0.8495,0.8371,0.7624,0.7366,0.6438,0.5629,0.5505,0.5500,0.5572,0.6428,0.6572,0.7428,0.7567,0.8366,0.8495,0.8433,0.7567,0.6640,0.6433,0.5505,0.4640,0.7366,0.6629,0.6500,0.6366,0.5567,0.5500,0.5500,0.5500,0.5505,0.5567,0.5645,0.6562,0.7371,0.7562,0.8360,0.8366,0.7629,0.7505,0.7433,0.6634,0.6505,0.6500,0.6495,0.6433,0.6366,0.5629,0.5505,0.5500,0.5573,0.6428,0.6500,0.6500,0.6495,0.6371,0.5629,0.5505,0.5500,0.5505,0.5567,0.5572,0.5567,0.5438,0.4640,0.4500,0.3645,0.3567,0.3505,0.3505,0.3634,0.4438,0.4634,0.5500,0.6371,0.6629,0.7433,0.7500,0.7427,0.6500,0.5505,0.4629,0.4371,0.3505,0.2764,0.3382,0.3696,0.5366,0.6360,0.6567,0.7427,0.7500,0.7427,0.6567,0.6366,0.5567,0.5567,0.6371,0.6629,0.7505,0.8495,0.9298,0.8624,0.8298,0.6567,0.5567,0.5360,0.4438,0.3634,0.3640,0.4505,0.5428,0.5572,0.6428,0.6500,0.6500,0.6428,0.5572,0.5500,0.5500,0.5500,0.5500,0.5505,0.5567,0.5640,0.6500,0.7366,0.7567,0.8422,0.8371,0.7624,0.7371,0.6500,0.5629,0.5438,0.5428,0.5433,0.5562,0.6366,0.6562,0.7366,0.7500,0.7634,0.8433,0.8427,0.7505,0.6634,0.6433,0.5500,0.4573,0.6562,0.6438,0.6366,0.5629,0.5505,0.5500,0.5500,0.5505,0.5629,0.6366,0.6500,0.7360,0.7495,0.7505,0.7562,0.7500,0.7371,0.6629,0.6500,0.6371,0.5696,0.6371,0.6495,0.6500,0.6495,0.6371,0.5634,0.5573,0.5640,0.6433,0.6500,0.6500,0.6500,0.6495,0.6366,0.5567,0.5505,0.5629,0.6366,0.6428,0.6366,0.5629,0.5500,0.5366,0.4562,0.4371,0.3634,0.3640,0.4438,0.4634,0.5438,0.5640,0.6567,0.7505,0.8427,0.8495,0.8366,0.7495,0.6500,0.5505,0.4567,0.3634,0.3376,0.2702,0.3511,0.4567,0.5562,0.6438,0.7355,0.7427,0.7360,0.6500,0.5634,0.5505,0.5505,0.5634,0.6505,0.7500,0.8500,0.9422,0.9371,0.8557,0.7505,0.6505,0.5567,0.4634,0.4438,0.4433,0.4567,0.5428,0.5572,0.6428,0.6500,0.6495,0.6366,0.5567,0.5500,0.5500,0.5500,0.5505,0.5629,0.6366,0.6438,0.6629,0.7433,0.7567,0.8298,0.7624,0.7376,0.6562,0.5634,0.5376,0.4634,0.4573,0.4634,0.5376,0.5624,0.6376,0.6624,0.7371,0.7562,0.8366,0.8428,0.7629,0.7376,0.6562,0.5573,0.4645,0.6366,0.5634,0.5567,0.5505,0.5500,0.5500,0.5505,0.5629,0.6376,0.6562,0.6640,0.7433,0.7500,0.7495,0.7371,0.6629,0.6500,0.6366,0.5567,0.5495,0.5443,0.5629,0.6433,0.6500,0.6500,0.6495,0.6433,0.6428,0.6433,0.6495,0.6500,0.6500,0.6500,0.6500,0.6427,0.5578,0.5629,0.6371,0.6500,0.6567,0.6567,0.6505,0.6433,0.5634,0.5438,0.4634,0.4505,0.4567,0.5366,0.5562,0.6366,0.6567,0.7495,0.8433,0.9355,0.9366,0.8624,0.8366,0.7428,0.6428,0.5428,0.4433,0.3500,0.2707,0.3500,0.4433,0.5366,0.5629,0.6438,0.6567,0.6562,0.6371,0.5562,0.5438,0.5495,0.5572,0.6500,0.7500,0.8500,0.9427,0.9495,0.9360,0.8427,0.7428,0.6433,0.5500,0.4640,0.4572,0.4640,0.5433,0.5572,0.6428,0.6500,0.6438,0.5696,0.5511,0.5500,0.5505,0.5567,0.5634,0.6371,0.6495,0.6567,0.7366,0.7500,0.7567,0.7567,0.7438,0.6634,0.6433,0.5505,0.4634,0.4505,0.4500,0.4505,0.4634,0.5438,0.5629,0.6376,0.6624,0.7376,0.7629,0.8427,0.8371,0.7624,0.7371,0.6495,0.5573,0.5562,0.5438,0.5428,0.5433,0.5495,0.5505,0.5629,0.6376,0.6624,0.7366,0.7433,0.7495,0.7500,0.7433,0.6629,0.6371,0.5567,0.5428,0.4572,0.4505,0.4634,0.5500,0.6366,0.6495,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6495,0.6433,0.6360,0.5629,0.6304,0.6495,0.6634,0.7433,0.7500,0.7500,0.7428,0.6572,0.6428,0.5572,0.5500,0.5505,0.5634,0.6438,0.6629,0.7438,0.8366,0.8629,0.9433,0.9495,0.9371,0.8562,0.7572,0.6572,0.5572,0.4572,0.3634,0.3443,0.3500,0.3634,0.4500,0.5371,0.5624,0.6366,0.6366,0.5624,0.5376,0.4696,0.5366,0.5500,0.6428,0.7428,0.8427,0.9360,0.9495,0.9427,0.8505,0.7567,0.6634,0.6371,0.5562,0.5433,0.5438,0.5562,0.5640,0.6433,0.6500,0.6495,0.6371,0.5634,0.5573,0.5634,0.6366,0.6433,0.6500,0.6567,0.6640,0.7438,0.7629,0.8304,0.7629,0.7433,0.6572,0.6428,0.5505,0.4634,0.4505,0.4500,0.4500,0.4573,0.5428,0.5505,0.5629,0.6376,0.6629,0.7500,0.8366,0.8489,0.8366,0.7562,0.7360,0.6500,0.5366,0.4634,0.4573,0.4640,0.5433,0.5567,0.6371,0.6624,0.7376,0.7562,0.7572,0.7567,0.7500,0.7360,0.6433,0.5495,0.4572,0.4433,0.3640,0.3635,0.4438,0.5366,0.5629,0.6438,0.6567,0.6572,0.6567,0.6505,0.6500,0.6500,0.6495,0.6433,0.6366,0.5634,0.5567,0.5510,0.5634,0.6500,0.7433,0.8355,0.8427,0.8427,0.8360,0.7562,0.7366,0.6567,0.6500,0.6500,0.6567,0.7360,0.7433,0.7567,0.8489,0.9304,0.9489,0.9500,0.9489,0.9298,0.8422,0.7433,0.6495,0.5500,0.4500,0.3572,0.3500,0.3505,0.3634,0.4500,0.5366,0.5495,0.5495,0.5371,0.4629,0.4511,0.4567,0.4640,0.5505,0.6500,0.7500,0.8495,0.9360,0.9360,0.8562,0.8366,0.7500,0.6634,0.6438,0.5640,0.5634,0.6371,0.6500,0.6567,0.6572,0.6572,0.6562,0.6438,0.6428,0.6433,0.6500,0.6567,0.6634,0.7366,0.7433,0.7562,0.8366,0.8489,0.8366,0.7500,0.6634,0.6438,0.5629,0.5376,0.4634,0.4573,0.4573,0.4640,0.5433,0.5500,0.5505,0.5629,0.6438,0.7366,0.7624,0.8366,0.8360,0.7562,0.7366,0.6567,0.4634,0.4511,0.4500,0.4567,0.5366,0.5567,0.6495,0.7366,0.7562,0.8360,0.8427,0.8360,0.7500,0.6567,0.5572,0.4573,0.3645,0.3562,0.3443,0.3500,0.3640,0.4567,0.5505,0.6495,0.7360,0.7427,0.7366,0.6629,0.6505,0.6495,0.6371,0.5629,0.5500,0.5433,0.5428,0.5433,0.5567,0.6500,0.7500,0.8427,0.8500,0.8500,0.8495,0.8371,0.7624,0.7438,0.7428,0.7428,0.7433,0.7495,0.7500,0.7567,0.8366,0.8562,0.9360,0.9427,0.9366,0.8629,0.8433,0.7567,0.7360,0.6427,0.5366,0.3702,0.3505,0.3500,0.3505,0.3634,0.4433,0.4505,0.4567,0.4562,0.4438,0.4428,0.4433,0.4500,0.4634,0.5505,0.6500,0.7500,0.8427,0.8500,0.8500,0.8495,0.8366,0.7562,0.7366,0.6567,0.6505,0.6629,0.7366,0.7428,0.7428,0.7428,0.7366,0.6634,0.6572,0.6572,0.6634,0.7366,0.7433,0.7495,0.7500,0.7572,0.8427,0.8500,0.8427,0.7567,0.7371,0.6629,0.6438,0.5634,0.5505,0.5500,0.5500,0.5500,0.5500,0.5500,0.5500,0.5505,0.5634,0.6495,0.7304,0.7489,0.7495,0.7371,0.6624,0.6438,0.5360,0.4567,0.4500,0.4505,0.4634,0.5505,0.6500,0.7427,0.7572,0.8427,0.8500,0.8427,0.7500,0.6500,0.5500,0.4500,0.3573,0.3438,0.2769,0.3438,0.3573,0.4500,0.5500,0.6500,0.7427,0.7500,0.7495,0.7366,0.6567,0.6433,0.5629,0.5376,0.4634,0.4572,0.4572,0.4640,0.5505,0.6500,0.7495,0.8366,0.8495,0.8500,0.8495,0.8427,0.8298,0.7562,0.7500,0.7500,0.7500,0.7500,0.7495,0.7438,0.7495,0.7567,0.8360,0.8427,0.8428,0.8428,0.8360,0.7567,0.7433,0.6567,0.5567,0.4511,0.3634,0.3505,0.3500,0.3505,0.3573,0.3702,0.4438,0.4438,0.3707,0.3645,0.3707,0.4438,0.4505,0.4634,0.5505,0.6500,0.7428,0.7567,0.8360,0.8427,0.8427,0.8366,0.7629,0.7505,0.7500,0.7505,0.7562,0.7510,0.7567,0.7572,0.7562,0.7438,0.7428,0.7428,0.7433,0.7495,0.7500,0.7500,0.7500,0.7567,0.8360,0.8427,0.8360,0.7567,0.7495,0.7433,0.7360,0.6567,0.6500,0.6500,0.6495,0.6371,0.5634,0.5567,0.5505,0.5495,0.5438,0.5500,0.5634,0.6433,0.6500,0.6495,0.6371,0.5634,0.5433,0.4634,0.4505,0.4500,0.4567,0.5433,0.6428,0.7360,0.7562,0.8360,0.8427,0.8360,0.7495,0.6505,0.5567,0.4573,0.3645,0.3567,0.3511,0.3567,0.3645,0.4567,0.5505,0.6495,0.7366,0.7495,0.7495,0.7366,0.6567,0.6428,0.5511,0.4696,0.4511,0.4500,0.4500,0.4573,0.5500,0.6495,0.7371,0.7624,0.8366,0.8427,0.8366,0.7634,0.7567,0.7505,0.7500,0.7500,0.7500,0.7495,0.7371,0.6629,0.6505,0.6505,0.6567,0.6572,0.6640,0.7433,0.7500,0.7500,0.7495,0.7360,0.6433,0.5495,0.4505,0.3640,0.3573,0.3573,0.3634,0.4371,0.4495,0.4495,0.4433,0.4428,0.4433,0.4495,0.4500,0.4505,0.4634,0.5505,0.6428,0.6572,0.7428,0.7505,0.7629,0.8366,0.8427,0.8427,0.8427,0.8422,0.8298,0.7624,0.8293,0.8355,0.8293,0.7562,0.7500,0.7495,0.7433,0.7428,0.7428,0.7433,0.7495,0.7505,0.7567,0.7572,0.7567,0.7505,0.7500,0.7500,0.7495,0.7438,0.7495,0.7500,0.7433,0.6634,0.6500,0.6366,0.5567,0.5433,0.4640,0.4573,0.4640,0.5433,0.5500,0.5505,0.5562,0.5505,0.5562,0.5371,0.4567,0.4500,0.4505,0.4640,0.5572,0.6562,0.7371,0.7500,0.7567,0.7567,0.7438,0.6629,0.6371,0.5495,0.4573,0.4495,0.4433,0.4433,0.4562,0.5366,0.5567,0.6433,0.6629,0.7366,0.7366,0.6629,0.6505,0.6428,0.5567,0.5371,0.4634,0.4573,0.4573,0.4640,0.5505,0.6433,0.6634,0.7438,0.7562,0.7505,0.7495,0.7433,0.7428,0.7428,0.7433,0.7495,0.7495,0.7371,0.6624,0.6376,0.5629,0.5505,0.5500,0.5500,0.5573,0.6433,0.6629,0.7371,0.7495,0.7433,0.6629,0.6371,0.5495,0.4573,0.4500,0.4500,0.4505,0.4567,0.4572,0.4572,0.4572,0.4572,0.4572,0.4572,0.4572,0.4567,0.4511,0.4634,0.5438,0.5634,0.6438,0.6629,0.7376,0.7624,0.8366,0.8427,0.8427,0.8366,0.7629,0.7510,0.7567,0.7572,0.7567,0.7500,0.7433,0.7366,0.6634,0.6572,0.6572,0.6634,0.7366,0.7428,0.7428,0.7428,0.7428,0.7428,0.7433,0.7495,0.7500,0.7567,0.8360,0.8427,0.8355,0.7500,0.7360,0.6500,0.5634,0.5433,0.4572,0.4495,0.4443,0.4562,0.4578,0.4702,0.5438,0.5500,0.6360,0.5495,0.4572,0.4495,0.4438,0.4562,0.5433,0.6366,0.6562,0.6640,0.7433,0.7500,0.7495,0.7371,0.6624,0.6371,0.5567,0.5433,0.4640,0.4634,0.5371,0.5495,0.5572,0.6428,0.6505,0.6567,0.6567,0.6505,0.6500,0.6428,0.5572,0.5495,0.5438,0.5495,0.5500,0.5505,0.5634,0.6433,0.6567,0.7360,0.7366,0.6634,0.6572,0.6572,0.6572,0.6572,0.6640,0.7433,0.7433,0.6634,0.6438,0.5634,0.5438,0.4640,0.4573,0.4573,0.4645,0.5562,0.6376,0.6624,0.7371,0.7489,0.7371,0.6624,0.6371,0.5567,0.5500,0.5500,0.5500,0.5500,0.5500,0.5500,0.5500,0.5500,0.5500,0.5500,0.5495,0.5371,0.4629,0.4511,0.4629,0.5376,0.5624,0.6376,0.6624,0.7376,0.7562,0.7572,0.7567,0.7500,0.7433,0.7428,0.7428,0.7428,0.7428,0.7366,0.6629,0.6500,0.6433,0.6433,0.6495,0.6505,0.6567,0.6572,0.6572,0.6572,0.6572,0.6572,0.6634,0.7366,0.7433,0.7562,0.8366,0.8495,0.8427,0.7572,0.7428,0.6562,0.6304,0.5490,0.4572,0.4438,0.3769,0.4443,0.4629,0.5376,0.5562,0.5572,0.6427,0.5500,0.4572,0.4433,0.3702,0.4376,0.4634,0.5562,0.6371,0.6562,0.7366,0.7495,0.7500,0.7495,0.7371,0.6629,0.6500,0.6366,0.5567,0.5500,0.5500,0.5500,0.5567,0.6360,0.6428,0.6428,0.6433,0.6495,0.6500,0.6433,0.5640,0.5573,0.5634,0.6366,0.6433,0.6495,0.6505,0.6567,0.6572,0.6572,0.6567,0.6500,0.6433,0.6428,0.6433,0.6495,0.6567,0.7366,0.7422,0.6572,0.6428,0.5572,0.5428,0.4572,0.4500,0.4500,0.4572,0.5433,0.5634,0.6438,0.6634,0.7433,0.7495,0.7371,0.6629,0.6500,0.6433,0.6428,0.6428,0.6433,0.6495,0.6500,0.6500,0.6500,0.6495,0.6433,0.6366,0.5624,0.5376,0.4629,0.4511,0.4629,0.5376,0.5624,0.6376,0.6624,0.7366,0.7428,0.7366,0.6629,0.6505,0.6500,0.6500,0.6500,0.6500,0.6495,0.6371,0.5634,0.5573,0.5634,0.6371,0.6495,0.6500,0.6500,0.6495,0.6433,0.6428,0.6428,0.6433,0.6495,0.6567,0.7366,0.7562,0.8360,0.8360,0.7567,0.7428,0.6505,0.5634,0.5433,0.4572,0.4495,0.4443,0.4624,0.5376,0.5624,0.6371,0.6495,0.6427,0.5500,0.4572,0.4428,0.3583,0.3696,0.4511,0.5433,0.5634,0.6438,0.6634,0.7433,0.7500,0.7505,0.7557,0.7438,0.7366,0.6629,0.6500,0.6371,0.5634,0.5567,0.5511,0.5567,0.5572,0.5572,0.5634,0.6366,0.6433,0.6490,0.6433,0.6433,0.6500,0.6567,0.6634,0.7366,0.7428,0.7428,0.7360,0.6567,0.6495,0.6371,0.5634,0.5572,0.5634,0.6371,0.6500,0.6629,0.7298,0.6567,0.6428,0.5572,0.5428,0.4572,0.4500,0.4500,0.4572,0.5428,0.5572,0.6428,0.6572,0.7428,0.7500,0.7495,0.7433,0.7366,0.6634,0.6572,0.6572,0.6634,0.7366,0.7433,0.7495,0.7495,0.7371,0.6634,0.6567,0.6438,0.5629,0.5371,0.4567,0.4505,0.4629,0.5376,0.5624,0.6376,0.6562,0.6567,0.6500,0.6371,0.5629,0.5505,0.5500,0.5500,0.5500,0.5500,0.5500,0.5500,0.5500,0.5505,0.5634,0.6433,0.6500,0.6500,0.6433,0.5640,0.5572,0.5572,0.5572,0.5573,0.5640,0.6438,0.6640,0.7500,0.7567,0.7505,0.7427,0.6500,0.5572,0.5428,0.4572,0.4505,0.4634,0.5438,0.5634,0.6438,0.6634,0.7433,0.6427,0.5505,0.4634,0.4438,0.3702,0.4376,0.4629,0.5438,0.5634,0.6433,0.6572,0.7428,0.7500,0.7562,0.8231,0.7562,0.7495,0.7433,0.7366,0.6624,0.6438,0.6366,0.5634,0.5567,0.5505,0.5500,0.5505,0.5567,0.5640,0.6433,0.6505,0.6629,0.7366,0.7433,0.7500,0.7567,0.7567,0.7505,0.7428,0.6567,0.6371,0.5624,0.5438,0.5428,0.5433,0.5562,0.6360,0.6438,0.6557,0.6500,0.6366,0.5567,0.5433,0.4640,0.4572,0.4573,0.4640,0.5438,0.5634,0.6433,0.6572,0.7428,0.7500,0.7500,0.7500,0.7495,0.7433,0.7428,0.7428,0.7433,0.7500,0.7629,0.8366,0.8366,0.7629,0.7505,0.7500,0.7427,0.6505,0.5567,0.4640,0.4505,0.4505,0.4629,0.5376,0.5624,0.6366,0.6366,0.5634,0.5567,0.5438,0.4640,0.4573,0.4572,0.4572,0.4573,0.4640,0.5433,0.5500,0.5505,0.5634,0.6433,0.6500,0.6500,0.6428,0.5573,0.5500,0.5500,0.5500,0.5500,0.5505,0.5635,0.6500,0.7366,0.7495,0.7495,0.7366,0.6495,0.5572,0.5433,0.4640,0.4640,0.5505,0.6428,0.6572,0.7428,0.7572,0.8427,0.6428,0.5567,0.5371,0.4629,0.4511,0.4634,0.5438,0.5629,0.6376,0.6562,0.6640,0.7433,0.7500,0.7505,0.7562,0.7505,0.7500,0.7500,0.7495,0.7371,0.6634,0.6562,0.6438,0.6366,0.5634,0.5572,0.5567,0.5505,0.5572,0.6428,0.6562,0.7304,0.7489,0.7567,0.8360,0.8427,0.8360,0.7567,0.7428,0.6505,0.5629,0.5376,0.4634,0.4572,0.4572,0.4640,0.5433,0.5567,0.6360,0.6366,0.5629,0.5505,0.5495,0.5433,0.5433,0.5495,0.5505,0.5629,0.6376,0.6562,0.6640,0.7428,0.7433,0.7428,0.7428,0.7428,0.7427,0.7433,0.7495,0.7500,0.7567,0.8366,0.8495,0.8495,0.8433,0.8428,0.8427,0.8355,0.7427,0.6428,0.5433,0.4567,0.4500,0.4505,0.4629,0.5371,0.5500,0.5562,0.5505,0.5500,0.5433,0.4634,0.4505,0.4500,0.4500,0.4500,0.4572,0.5428,0.5505,0.5629,0.6371,0.6495,0.6500,0.6500,0.6433,0.5634,0.5505,0.5500,0.5500,0.5505,0.5567,0.5640,0.6438,0.6629,0.7366,0.7366,0.6629,0.6438,0.5640,0.5567,0.5505,0.5573,0.6495,0.7366,0.7567,0.8428,0.8567,0.9360,0.6428,0.5572,0.5500,0.5500,0.5505,0.5634,0.6433,0.6505,0.6629,0.7366,0.7433,0.7489,0.7433,0.7428,0.7428,0.7433,0.7495,0.7500,0.7500,0.7495,0.7433,0.7366,0.6634,0.6562,0.6438,0.6428,0.6366,0.5629,0.5572,0.6360,0.6438,0.6624,0.7371,0.7562,0.8366,0.8495,0.8427,0.7567,0.7360,0.6433,0.5500,0.4634,0.4505,0.4495,0.4433,0.4433,0.4495,0.4572,0.5428,0.5500,0.5500,0.5500,0.5505,0.5567,0.5640,0.6433,0.6500,0.6505,0.6629,0.7366,0.7427,0.7366,0.6629,0.6505,0.6500,0.6500,0.6505,0.6629,0.7371,0.7495,0.7572,0.8427,0.8500,0.8500,0.8500,0.8500,0.8500,0.8427,0.7500,0.6500,0.5505,0.4634,0.4505,0.4500,0.4505,0.4567,0.4640,0.5433,0.5505,0.5567,0.5562,0.5376,0.4629,0.4505,0.4500,0.4500,0.4572,0.5433,0.5629,0.6371,0.6500,0.6567,0.6572,0.6567,0.6500,0.6371,0.5634,0.5572,0.5572,0.5634,0.6366,0.6433,0.6495,0.6505,0.6567,0.6567,0.6505,0.6495,0.6433,0.6428,0.6433,0.6562,0.7371,0.7624,0.8438,0.9355,0.9433,0.9495,0.6433,0.5640,0.5634,0.6371,0.6557,0.7298,0.7422,0.7428,0.7433,0.7495,0.7495,0.7371,0.6629,0.6505,0.6505,0.6629,0.7366,0.7433,0.7495,0.7505,0.7567,0.7562,0.7438,0.7366,0.6629,0.6505,0.6495,0.6366,0.5572,0.5567,0.5634,0.6376,0.6624,0.7376,0.7624,0.8366,0.8360,0.7500,0.6573,0.5702,0.5438,0.4573,0.4500,0.4438,0.3702,0.3578,0.3573,0.3640,0.4438,0.4629,0.5371,0.5500,0.5634,0.6433,0.6572,0.7428,0.7495,0.7433,0.7433,0.7489,0.7371,0.6624,0.6371,0.5567,0.5500,0.5505,0.5629,0.6376,0.6624,0.7371,0.7562,0.8366,0.8495,0.8500,0.8495,0.8433,0.8428,0.8360,0.7495,0.6505,0.5629,0.5376,0.4629,0.4505,0.4500,0.4505,0.4634,0.5438,0.5629,0.6366,0.6366,0.5624,0.5376,0.4629,0.4505,0.4500,0.4572,0.5495,0.6366,0.6500,0.6629,0.7366,0.7427,0.7360,0.6567,0.6495,0.6433,0.6428,0.6428,0.6438,0.6562,0.6567,0.6505,0.6500,0.6495,0.6438,0.6495,0.6500,0.6500,0.6505,0.6629,0.7371,0.7562,0.8366,0.8562,0.9360,0.9433,0.9495,0.6495,0.6433,0.6438,0.6624,0.7371,0.7500,0.7562,0.7505,0.7500,0.7495,0.7371,0.6624,0.6376,0.5634,0.5634,0.6376,0.6562,0.6634,0.7371,0.7557,0.8298,0.8360,0.7629,0.7500,0.7366,0.6567,0.6495,0.6366,0.5562,0.5433,0.5433,0.5562,0.6371,0.6624,0.7376,0.7562,0.7567,0.7438,0.6629,0.6371,0.5500,0.4640,0.4572,0.4562,0.4376,0.3629,0.3505,0.3505,0.3634,0.4443,0.4696,0.5505,0.6433,0.7360,0.7562,0.8360,0.8360,0.7567,0.7500,0.7433,0.6629,0.6371,0.5500,0.4640,0.4573,0.4634,0.5376,0.5629,0.6438,0.6634,0.7438,0.7629,0.8366,0.8427,0.8366,0.7634,0.7572,0.7562,0.7371,0.6562,0.6366,0.5562,0.5371,0.4634,0.4573,0.4634,0.5376,0.5624,0.6376,0.6562,0.6562,0.6371,0.5557,0.5304,0.4562,0.4500,0.4572,0.5495,0.6366,0.6557,0.7298,0.7422,0.7427,0.7360,0.6567,0.6500,0.6500,0.6500,0.6505,0.6629,0.7360,0.7298,0.6562,0.6495,0.6371,0.5696,0.6371,0.6495,0.6505,0.6629,0.7371,0.7495,0.7567,0.8360,0.8433,0.8495,0.8567,0.9360,0.6500,0.6500,0.6567,0.7366,0.7495,0.7562,0.8231,0.7557,0.7433,0.7360,0.6562,0.6366,0.5562,0.5433,0.5438,0.5624,0.6371,0.6500,0.6634,0.7438,0.7634,0.8422,0.8304,0.7557,0.7366,0.6567,0.6433,0.5629,0.5376,0.4634,0.4573,0.4645,0.5562,0.6376,0.6629,0.7433,0.7500,0.7495,0.7366,0.6500,0.5629,0.5438,0.5428,0.5366,0.4624,0.4376,0.3629,0.3511,0.3634,0.4500,0.5371,0.5634,0.6572,0.7562,0.8371,0.8495,0.8427,0.7567,0.7433,0.7360,0.6500,0.5567,0.4640,0.4505,0.4500,0.4511,0.4696,0.5511,0.6433,0.6634,0.7433,0.7505,0.7567,0.7567,0.7500,0.7433,0.7428,0.7366,0.6629,0.6505,0.6433,0.5640,0.5567,0.5500,0.5433,0.5433,0.5562,0.6366,0.6562,0.7355,0.7298,0.6489,0.5505,0.4629,0.4438,0.4428,0.4500,0.5366,0.5624,0.6376,0.6562,0.6572,0.6572,0.6567,0.6505,0.6500,0.6500,0.6500,0.6562,0.7298,0.7360,0.6629,0.6500,0.6371,0.5629,0.5511,0.5634,0.6433,0.6562,0.7304,0.7489,0.7500,0.7500,0.7500,0.7500,0.7500,0.7572,0.8427,0.6500,0.6500,0.6572,0.7428,0.7500,0.7500,0.7495,0.7371,0.6629,0.6438,0.5634,0.5438,0.4640,0.4573,0.4640,0.5438,0.5634,0.6433,0.6572,0.7428,0.7567,0.8298,0.7629,0.7438,0.6634,0.6500,0.6366,0.5500,0.4634,0.4505,0.4500,0.4572,0.5433,0.5634,0.6505,0.7428,0.7500,0.7500,0.7433,0.6629,0.6376,0.5634,0.5572,0.5562,0.5376,0.4624,0.4376,0.3696,0.4376,0.4634,0.5562,0.6438,0.7428,0.8360,0.8495,0.8495,0.8366,0.7500,0.6634,0.6500,0.6360,0.5433,0.4567,0.4500,0.4500,0.4567,0.5371,0.5629,0.6500,0.7366,0.7495,0.7500,0.7495,0.7371,0.6634,0.6572,0.6572,0.6567,0.6505,0.6500,0.6495,0.6433,0.6428,0.6366,0.5634,0.5572,0.5640,0.6433,0.6567,0.7298,0.6624,0.6366,0.5428,0.4438,0.3629,0.3511,0.3634,0.4500,0.5371,0.5624,0.6366,0.6428,0.6428,0.6428,0.6428,0.6428,0.6428,0.6428,0.6433,0.6495,0.6495,0.6433,0.6366,0.5629,0.5505,0.5500,0.5567,0.6366,0.6500,0.6634,0.7428,0.7433,0.7366,0.6629,0.6505,0.6500,0.6572,0.7428,0.6500,0.6500,0.6572,0.7422,0.7433,0.7366,0.6629,0.6500,0.6366,0.5562,0.5366,0.4562,0.4438,0.4495,0.4573,0.5433,0.5634,0.6438,0.6634,0.7433,0.7505,0.7562,0.7500,0.7366,0.6562,0.6371,0.5629,0.5433,0.4572,0.4500,0.4500,0.4572,0.5433,0.5634,0.6505,0.7428,0.7505,0.7562,0.7500,0.7371,0.6629,0.6500,0.6433,0.6366,0.5624,0.5376,0.4629,0.4511,0.4629,0.5438,0.6366,0.6634,0.7567,0.8433,0.8500,0.8433,0.7629,0.7366,0.6438,0.5629,0.5438,0.4634,0.4505,0.4500,0.4505,0.4640,0.5562,0.6376,0.6629,0.7433,0.7500,0.7500,0.7433,0.6629,0.6438,0.6428,0.6428,0.6428,0.6433,0.6495,0.6500,0.6505,0.6567,0.6562,0.6438,0.6428,0.6433,0.6495,0.6505,0.6557,0.6376,0.5562,0.4572,0.3634,0.3376,0.2696,0.3376,0.3629,0.4500,0.5366,0.5495,0.5500,0.5500,0.5500,0.5500,0.5500,0.5505,0.5567,0.5572,0.5572,0.5572,0.5572,0.5562,0.5438,0.5428,0.5433,0.5500,0.5634,0.6433,0.6567,0.7298,0.6634,0.6562,0.6376,0.5634,0.5573,0.5640,0.6433,0.6500,0.6505,0.6629,0.7304,0.6634,0.6562,0.6371,0.5567,0.5428,0.4572,0.4433,0.3640,0.3640,0.4438,0.4634,0.5500,0.6371,0.6624,0.7371,0.7500,0.7567,0.7567,0.7443,0.6696,0.6449,0.5696,0.5511,0.5428,0.4572,0.4500,0.4505,0.4640,0.5562,0.6376,0.6629,0.7433,0.7567,0.8298,0.7629,0.7500,0.7433,0.7366,0.6634,0.6562,0.6376,0.5624,0.5438,0.5428,0.5438,0.5629,0.6500,0.7427,0.8298,0.8489,0.8500,0.8427,0.7505,0.6567,0.5640,0.5438,0.4634,0.4505,0.4500,0.4500,0.4567,0.5433,0.6360,0.6562,0.7366,0.7495,0.7500,0.7495,0.7360,0.6438,0.5634,0.5572,0.5572,0.5572,0.5640,0.6433,0.6505,0.6629,0.7366,0.7366,0.6634,0.6572,0.6572,0.6567,0.6505,0.6433,0.5629,0.5371,0.4495,0.3505,0.2634,0.2511,0.2629,0.3376,0.3629,0.4433,0.4505,0.4567,0.4572,0.4572,0.4572,0.4573,0.4634,0.5366,0.5428,0.5428,0.5428,0.5428,0.5366,0.4634,0.4578,0.4702,0.5438,0.5572,0.6428,0.6505,0.6562,0.6505,0.6433,0.5634,0.5505,0.5500,0.5505,0.5567,0.6572,0.6634,0.7304,0.6629,0.6500,0.6371,0.5562,0.4640,0.4438,0.3640,0.3567,0.3505,0.3573,0.4495,0.5371,0.5634,0.6562,0.7371,0.7500,0.7629,0.8366,0.8366,0.7624,0.7376,0.6624,0.6376,0.5629,0.5438,0.4640,0.4573,0.4640,0.5505,0.6433,0.6629,0.7376,0.7562,0.7634,0.8360,0.8298,0.7562,0.7495,0.7428,0.7366,0.7355,0.6562,0.6371,0.5634,0.5572,0.5634,0.6371,0.6562,0.7371,0.7624,0.8366,0.8427,0.8360,0.7495,0.6500,0.5573,0.5428,0.4573,0.4500,0.4500,0.4500,0.4573,0.5495,0.6366,0.6562,0.7360,0.7427,0.7427,0.7360,0.6500,0.5629,0.5438,0.5428,0.5428,0.5433,0.5567,0.6433,0.6629,0.7376,0.7562,0.7567,0.7500,0.7433,0.7428,0.7360,0.6567,0.6428,0.5505,0.4634,0.4433,0.3500,0.2573,0.2500,0.2505,0.2629,0.3376,0.3562,0.3634,0.4366,0.4433,0.4495,0.4500,0.4500,0.4505,0.4567,0.4572,0.4572,0.4572,0.4572,0.4567,0.4511,0.4629,0.5371,0.5495,0.5572,0.6428,0.6500,0.6500,0.6500,0.6433,0.5634,0.5505,0.5500,0.5500,0.5500,0.7428,0.7433,0.7422,0.6572,0.6433,0.5634,0.5433,0.4505,0.3635,0.3505,0.3500,0.3505,0.3640,0.4572,0.5567,0.6500,0.7366,0.7500,0.7629,0.8371,0.8495,0.8495,0.8371,0.7624,0.7376,0.6624,0.6376,0.5624,0.5443,0.5495,0.5573,0.6495,0.7366,0.7500,0.7629,0.8360,0.8304,0.7629,0.7562,0.7438,0.7366,0.6634,0.6634,0.7298,0.6572,0.6557,0.6438,0.6428,0.6433,0.6495,0.6505,0.6629,0.7371,0.7495,0.7505,0.7562,0.7433,0.6505,0.5634,0.5438,0.4634,0.4505,0.4500,0.4505,0.4634,0.5438,0.5629,0.6371,0.6495,0.6500,0.6495,0.6366,0.5562,0.5371,0.4634,0.4572,0.4572,0.4640,0.5505,0.6495,0.7371,0.7624,0.8366,0.8427,0.8360,0.7567,0.7500,0.7427,0.6572,0.6428,0.5505,0.4634,0.4438,0.3567,0.2640,0.2505,0.2500,0.2505,0.2629,0.3371,0.3500,0.3573,0.3702,0.4443,0.4567,0.4572,0.4572,0.4572,0.4572,0.4572,0.4572,0.4572,0.4573,0.4634,0.5371,0.5500,0.5567,0.5640,0.6433,0.6500,0.6500,0.6500,0.6495,0.6371,0.5634,0.5573,0.5572,0.5572,0.7495,0.7433,0.7360,0.6567,0.6433,0.5634,0.5438,0.4567,0.3640,0.3505,0.3500,0.3567,0.4433,0.5428,0.6428,0.7360,0.7495,0.7562,0.8304,0.8489,0.8500,0.8500,0.8495,0.8371,0.7624,0.7371,0.6562,0.6371,0.5696,0.6371,0.6562,0.7371,0.7624,0.8366,0.8427,0.8366,0.7624,0.7438,0.7360,0.6567,0.6495,0.6438,0.6500,0.6562,0.6572,0.7298,0.6634,0.6572,0.6567,0.6505,0.6495,0.6438,0.6495,0.6505,0.6629,0.7366,0.7366,0.6624,0.6376,0.5624,0.5376,0.4634,0.4573,0.4634,0.5371,0.5495,0.5505,0.5562,0.5505,0.5500,0.5438,0.4702,0.4578,0.4567,0.4505,0.4500,0.4505,0.4634,0.5505,0.6500,0.7495,0.8366,0.8495,0.8495,0.8366,0.7567,0.7495,0.7366,0.6567,0.6428,0.5567,0.5371,0.4624,0.4371,0.3500,0.2634,0.2505,0.2500,0.2511,0.2696,0.3443,0.3634,0.4438,0.4634,0.5433,0.5500,0.5495,0.5433,0.5428,0.5428,0.5428,0.5428,0.5433,0.5500,0.5567,0.5634,0.6366,0.6433,0.6495,0.6500,0.6500,0.6500,0.6505,0.6562,0.6505,0.6495,0.6433,0.6428,0.7366,0.6634,0.6567,0.6505,0.6495,0.6371,0.5624,0.5371,0.4500,0.3640,0.3573,0.3645,0.4567,0.5505,0.6500,0.7427,0.7500,0.7505,0.7629,0.8371,0.8495,0.8500,0.8500,0.8495,0.8366,0.7495,0.6572,0.6495,0.6438,0.6557,0.7304,0.7551,0.8298,0.8422,0.8366,0.7624,0.7371,0.6567,0.6433,0.5640,0.5573,0.5634,0.6371,0.6495,0.6572,0.7422,0.7433,0.7428,0.7360,0.6562,0.6371,0.5629,0.5505,0.5567,0.6371,0.6562,0.6634,0.7304,0.6624,0.6371,0.5562,0.5433,0.5428,0.5433,0.5495,0.5500,0.5500,0.5433,0.4640,0.4567,0.4500,0.4433,0.4433,0.4495,0.4505,0.4567,0.4634,0.5376,0.5629,0.6505,0.7495,0.8360,0.8427,0.8366,0.7624,0.7438,0.7366,0.6629,0.6505,0.6433,0.5640,0.5562,0.5376,0.4624,0.4371,0.3500,0.2640,0.2573,0.2634,0.3376,0.3629,0.4500,0.5366,0.5567,0.6428,0.6495,0.6371,0.5634,0.5572,0.5572,0.5572,0.5572,0.5634,0.6366,0.6428,0.6433,0.6495,0.6500,0.6495,0.6438,0.6495,0.6500,0.6567,0.7360,0.7427,0.7366,0.6629,0.6505,0.6495,0.6433,0.6428,0.6433,0.6495,0.6495,0.6371,0.5624,0.5371,0.4562,0.4433,0.4500,0.5360,0.5567,0.6500,0.7427,0.7495,0.7433,0.7433,0.7562,0.8360,0.8433,0.8495,0.8495,0.8366,0.7495,0.6567,0.6433,0.6427,0.6438,0.6629,0.7438,0.7567,0.7567,0.7500,0.7366,0.6500,0.5634,0.5500,0.5438,0.5495,0.5505,0.5634,0.6438,0.6634,0.7438,0.7567,0.7567,0.7438,0.6572,0.5702,0.5443,0.4640,0.4645,0.5567,0.6433,0.6572,0.7417,0.7304,0.6489,0.5572,0.5500,0.5505,0.5567,0.5572,0.5572,0.5567,0.5433,0.4572,0.4433,0.3640,0.3578,0.3702,0.4443,0.4629,0.5366,0.5438,0.5624,0.6376,0.6629,0.7438,0.7567,0.7572,0.7562,0.7376,0.6634,0.6562,0.6438,0.6433,0.6490,0.6433,0.6366,0.5624,0.5376,0.4624,0.4366,0.3500,0.3428,0.3438,0.3629,0.4500,0.5371,0.5629,0.6500,0.7360,0.7366,0.6624,0.6438,0.6428,0.6428,0.6428,0.6428,0.6438,0.6562,0.6572,0.6567,0.6505,0.6500,0.6433,0.5702,0.6371,0.6495,0.6572,0.7427,0.7500,0.7489,0.7304,0.6562,0.5500,0.5500,0.5500,0.5567,0.6366,0.6495,0.6495,0.6371,0.5624,0.5376,0.4634,0.4640,0.5433,0.5572,0.6495,0.7360,0.7366,0.6629,0.6511,0.6634,0.7438,0.7629,0.8366,0.8366,0.7624,0.7366,0.6438,0.5629,0.5511,0.5629,0.6438,0.7355,0.7427,0.7366,0.6629,0.6438,0.5629,0.5376,0.4634,0.4640,0.5433,0.5505,0.5634,0.6500,0.7371,0.7624,0.8366,0.8366,0.7624,0.7366,0.6433,0.5500,0.4640,0.4640,0.5505,0.6428,0.6567,0.7298,0.6629,0.6433,0.5572,0.5500,0.5567,0.6360,0.6433,0.6489,0.6371,0.5562,0.4645,0.4500,0.3645,0.3634,0.4376,0.4624,0.5376,0.5562,0.5634,0.6371,0.6562,0.7366,0.7495,0.7500,0.7495,0.7371,0.6624,0.6438,0.6366,0.5634,0.5640,0.6433,0.6500,0.6495,0.6366,0.5562,0.5366,0.4500,0.3634,0.3511,0.3629,0.4438,0.5366,0.5629,0.6500,0.7371,0.7557,0.7500,0.7366,0.6567,0.6500,0.6500,0.6500,0.6500,0.6562,0.7298,0.7422,0.7360,0.6567,0.6500,0.6428,0.5578,0.5634,0.6433,0.6567,0.7360,0.7427,0.7366,0.6624,0.6438,0.4428,0.4433,0.4495,0.4573,0.5495,0.6366,0.6495,0.6495,0.6366,0.5562,0.5433,0.5433,0.5495,0.5567,0.6366,0.6495,0.6495,0.6371,0.5696,0.6376,0.6624,0.7371,0.7495,0.7495,0.7366,0.6495,0.5567,0.5371,0.4696,0.5371,0.5567,0.6428,0.6500,0.6495,0.6366,0.5562,0.5371,0.4629,0.4505,0.4573,0.5433,0.5629,0.6376,0.6629,0.7500,0.8371,0.8562,0.8562,0.8371,0.7500,0.6567,0.5634,0.5438,0.5433,0.5567,0.6428,0.6505,0.6562,0.6500,0.6366,0.5567,0.5500,0.5572,0.6433,0.6629,0.7304,0.6629,0.6433,0.5567,0.5366,0.4562,0.4443,0.4624,0.5376,0.5624,0.6366,0.6433,0.6500,0.6634,0.7433,0.7500,0.7495,0.7371,0.6624,0.6376,0.5634,0.5567,0.5505,0.5567,0.6366,0.6495,0.6500,0.6428,0.5572,0.5428,0.4567,0.4371,0.3696,0.4376,0.4629,0.5500,0.6433,0.7366,0.7624,0.8304,0.7629,0.7433,0.6572,0.6500,0.6500,0.6500,0.6500,0.6505,0.6634,0.7427,0.7366,0.6567,0.6495,0.6366,0.5567,0.5567,0.6360,0.6438,0.6562,0.6567,0.6500,0.6366,0.5567,0.2645,0.2707,0.3443,0.3640,0.4572,0.5567,0.6433,0.6500,0.6433,0.5634,0.5505,0.5500,0.5500,0.5505,0.5567,0.5572,0.5572,0.5567,0.5511,0.5629,0.6371,0.6500,0.6562,0.6505,0.6427,0.5505,0.4634,0.4500,0.4438,0.4500,0.4634,0.5433,0.5500,0.5500,0.5428,0.4572,0.4495,0.4438,0.4500,0.4634,0.5500,0.6371,0.6624,0.7376,0.7629,0.8500,0.9360,0.9366,0.8562,0.7634,0.7371,0.6500,0.5640,0.5573,0.5640,0.6433,0.6500,0.6500,0.6433,0.5634,0.5505,0.5500,0.5572,0.6495,0.7366,0.7489,0.7433,0.7355,0.6438,0.5624,0.5376,0.4696,0.5371,0.5562,0.6366,0.6495,0.6505,0.6629,0.7371,0.7495,0.7500,0.7433,0.6634,0.6438,0.5634,0.5505,0.5500,0.5500,0.5505,0.5634,0.6433,0.6500,0.6428,0.5572,0.5433,0.4634,0.4500,0.4443,0.4624,0.5376,0.5634,0.6567,0.7500,0.8366,0.8489,0.8366,0.7495,0.6572,0.6495,0.6433,0.6433,0.6495,0.6500,0.6567,0.7298,0.6629,0.6505,0.6433,0.5634,0.5505,0.5505,0.5567,0.5634,0.6366,0.6360,0.5567,0.5428,0.4572,0.2573,0.2573,0.2640,0.3500,0.4433,0.5428,0.6360,0.6495,0.6495,0.6371,0.5634,0.5572,0.5567,0.5505,0.5500,0.5500,0.5500,0.5500,0.5500,0.5505,0.5567,0.5634,0.6304,0.5629,0.5438,0.4629,0.4376,0.3634,0.3573,0.3640,0.4438,0.4567,0.4567,0.4505,0.4433,0.3634,0.3511,0.3634,0.4500,0.5371,0.5629,0.6500,0.7366,0.7562,0.8366,0.8567,0.9427,0.9495,0.9360,0.8438,0.7624,0.7371,0.6567,0.6500,0.6505,0.6567,0.6567,0.6505,0.6428,0.5572,0.5500,0.5500,0.5572,0.6500,0.7427,0.7500,0.7500,0.7427,0.6567,0.6366,0.5562,0.5438,0.5495,0.5572,0.6428,0.6500,0.6562,0.7304,0.7489,0.7500,0.7500,0.7433,0.6634,0.6438,0.5634,0.5505,0.5500,0.5500,0.5500,0.5573,0.6428,0.6500,0.6433,0.5634,0.5500,0.5366,0.4573,0.4629,0.5376,0.5629,0.6500,0.7371,0.7629,0.8433,0.8500,0.8427,0.7500,0.6567,0.6371,0.5634,0.5634,0.6371,0.6495,0.6505,0.6557,0.6438,0.6428,0.6360,0.5567,0.5500,0.5500,0.5495,0.5438,0.5495,0.5428,0.4572,0.4428,0.3573,0.3495,0.3371,0.2702,0.3443,0.3702,0.4578,0.5562,0.6371,0.6495,0.6495,0.6433,0.6428,0.6366,0.5629,0.5505,0.5500,0.5500,0.5500,0.5500,0.5500,0.5500,0.5500,0.5495,0.5371,0.4629,0.4443,0.3702,0.3578,0.3573,0.3640,0.4433,0.4495,0.4371,0.3634,0.3562,0.3376,0.2702,0.3500,0.4438,0.5489,0.6371,0.6629,0.7433,0.7572,0.8428,0.8567,0.9366,0.9495,0.9427,0.8567,0.8371,0.7629,0.7505,0.7500,0.7500,0.7495,0.7371,0.6629,0.6433,0.5572,0.5500,0.5500,0.5567,0.6433,0.7360,0.7495,0.7495,0.7366,0.6567,0.6428,0.5572,0.5500,0.5500,0.5572,0.6428,0.6500,0.6505,0.6629,0.7371,0.7495,0.7500,0.7495,0.7371,0.6624,0.6371,0.5567,0.5500,0.5500,0.5505,0.5634,0.6433,0.6500,0.6495,0.6366,0.5567,0.5433,0.4702,0.5371,0.5562,0.6433,0.7360,0.7562,0.8366,0.8495,0.8495,0.8366,0.7495,0.6505,0.5634,0.5505,0.5505,0.5629,0.6366,0.6427,0.6366,0.5634,0.5572,0.5567,0.5505,0.5500,0.5500,0.5433,0.4640,0.4567,0.4438,0.3634,0.3438,0.2640,0.4366,0.3629,0.3511,0.3629,0.4376,0.4629,0.5443,0.5696,0.6438,0.6500,0.6500,0.6500,0.6495,0.6366,0.5567,0.5500,0.5505,0.5567,0.5572,0.5567,0.5505,0.5433,0.4640,0.4567,0.4505,0.4495,0.4438,0.4495,0.4500,0.4505,0.4567,0.4505,0.3702,0.3511,0.3438,0.2696,0.2583,0.3438,0.3769,0.5438,0.6489,0.7304,0.7489,0.7567,0.8360,0.8438,0.8624,0.9366,0.9360,0.8567,0.8495,0.8433,0.8433,0.8495,0.8495,0.8371,0.7624,0.7371,0.6500,0.5634,0.5505,0.5500,0.5505,0.5634,0.6500,0.7360,0.7366,0.6629,0.6500,0.6366,0.5567,0.5500,0.5500,0.5567,0.6366,0.6489,0.6438,0.6500,0.6634,0.7438,0.7567,0.7572,0.7562,0.7371,0.6500,0.5634,0.5505,0.5500,0.5567,0.6366,0.6495,0.6500,0.6500,0.6433,0.5634,0.5500,0.5438,0.5500,0.5634,0.6505,0.7428,0.7572,0.8427,0.8500,0.8433,0.7629,0.7371,0.6495,0.5573,0.5505,0.5562,0.5511,0.5567,0.5572,0.5562,0.5438,0.5428,0.5433,0.5495,0.5500,0.5500,0.5433,0.4634,0.4438,0.3634,0.3438,0.2634,0.2505,0.4567,0.4505,0.4500,0.4505,0.4629,0.5371,0.5557,0.6304,0.6489,0.6500,0.6500,0.6495,0.6433,0.6360,0.5567,0.5500,0.5562,0.6298,0.6422,0.6360,0.5562,0.5366,0.4562,0.4438,0.4495,0.4505,0.4634,0.5433,0.5505,0.5562,0.5505,0.5428,0.4505,0.3640,0.3562,0.3376,0.2702,0.3500,0.4438,0.5489,0.6371,0.6624,0.7371,0.7500,0.7567,0.7634,0.8371,0.8495,0.8495,0.8433,0.8433,0.8495,0.8567,0.9360,0.9366,0.8624,0.8371,0.7495,0.6567,0.6366,0.5567,0.5495,0.5433,0.5438,0.5629,0.6433,0.6495,0.6433,0.6366,0.5629,0.5505,0.5500,0.5500,0.5505,0.5629,0.6304,0.5696,0.6371,0.6567,0.7495,0.8360,0.8427,0.8360,0.7500,0.6629,0.6371,0.5567,0.5500,0.5572,0.6428,0.6505,0.6562,0.6505,0.6495,0.6366,0.5567,0.5500,0.5562,0.6304,0.6562,0.7428,0.7567,0.8360,0.8427,0.8360,0.7500,0.6634,0.6433,0.5572,0.5567,0.6298,0.5629,0.5505,0.5495,0.5371,0.4634,0.4578,0.4702,0.5443,0.5567,0.5572,0.5567,0.5438,0.4567,0.3645,0.3500,0.2645,0.2573,0.5500,0.5495,0.5433,0.5428,0.5428,0.5433,0.5500,0.5634,0.6433,0.6500,0.6500,0.6438,0.5702,0.5567,0.5438,0.5428,0.5438,0.5624,0.6365,0.6355,0.5438,0.4624,0.4376,0.3702,0.4438,0.4634,0.5505,0.6428,0.6567,0.7293,0.6567,0.6428,0.5500,0.4572,0.4433,0.3634,0.3511,0.3634,0.4500,0.5371,0.5629,0.6438,0.6629,0.7366,0.7428,0.7433,0.7495,0.7500,0.7500,0.7505,0.7629,0.8371,0.8567,0.9427,0.9495,0.9366,0.8495,0.7505,0.6634,0.6433,0.5572,0.5433,0.4640,0.4640,0.5438,0.5567,0.5572,0.5572,0.5567,0.5505,0.5500,0.5500,0.5505,0.5562,0.5511,0.5562,0.5511,0.5634,0.6505,0.7500,0.8427,0.8500,0.8427,0.7562,0.7304,0.6489,0.5572,0.5500,0.5572,0.6428,0.6562,0.7231,0.6562,0.6495,0.6366,0.5567,0.5500,0.5505,0.5634,0.6500,0.7360,0.7438,0.7562,0.7572,0.7562,0.7371,0.6567,0.6428,0.5578,0.5634,0.6427,0.6366,0.5567,0.5433,0.4634,0.4505,0.4567,0.5366,0.5562,0.6366,0.6495,0.6500,0.6427,0.5500,0.4572,0.4428,0.3572,0.3500,0.6427,0.6366,0.5629,0.5505,0.5433,0.4702,0.5366,0.5500,0.6360,0.6495,0.6500,0.6495,0.6366,0.5500,0.4640,0.4567,0.4567,0.5304,0.5489,0.5427,0.4567,0.4371,0.3629,0.3578,0.4495,0.5433,0.6427,0.7360,0.7562,0.8293,0.7562,0.7366,0.6495,0.5567,0.5366,0.4562,0.4433,0.4433,0.4505,0.4696,0.5505,0.6366,0.6500,0.6567,0.6572,0.6567,0.6505,0.6500,0.6500,0.6567,0.7366,0.7562,0.8433,0.9360,0.9495,0.9427,0.8500,0.7562,0.7304,0.6489,0.5572,0.5428,0.4573,0.4573,0.5428,0.5500,0.5505,0.5567,0.5572,0.5572,0.5572,0.5572,0.5634,0.6304,0.5634,0.5573,0.5572,0.5640,0.6505,0.7495,0.8366,0.8489,0.8366,0.7500,0.6629,0.6371,0.5562,0.5438,0.5562,0.6366,0.6500,0.6562,0.6505,0.6433,0.5634,0.5500,0.5433,0.5433,0.5562,0.6371,0.6562,0.6634,0.7366,0.7428,0.7366,0.6629,0.6505,0.6428,0.5640,0.6366,0.6495,0.6428,0.5572,0.5433,0.4634,0.4511,0.4634,0.5438,0.5640,0.6562,0.7371,0.7489,0.7366,0.6495,0.5572,0.5428,0.4572,0.4500,0.6500,0.6495,0.6366,0.5562,0.5366,0.4572,0.4567,0.4645,0.5562,0.6371,0.6495,0.6500,0.6427,0.5500,0.4567,0.4371,0.3640,0.3702,0.4433,0.4366,0.3567,0.3495,0.3433,0.3500,0.4428,0.5428,0.6433,0.7489,0.8365,0.8489,0.8371,0.7624,0.7366,0.6438,0.5624,0.5376,0.4629,0.4505,0.4567,0.5366,0.5500,0.5634,0.6433,0.6500,0.6495,0.6371,0.5629,0.5505,0.5505,0.5634,0.6438,0.6640,0.7567,0.8500,0.9360,0.9360,0.8495,0.7505,0.6629,0.6371,0.5562,0.5366,0.4567,0.4573,0.5433,0.5567,0.5634,0.6366,0.6428,0.6428,0.6428,0.6428,0.6433,0.6490,0.6433,0.6428,0.6428,0.6433,0.6567,0.7433,0.7629,0.8304,0.7624,0.7366,0.6438,0.5624,0.5376,0.4696,0.5376,0.5629,0.6433,0.6500,0.6495,0.6366,0.5562,0.5371,0.4634,0.4634,0.5376,0.5624,0.6371,0.6500,0.6567,0.6572,0.6567,0.6505,0.6495,0.6371,0.5702,0.6433,0.6500,0.6433,0.5634,0.5500,0.5371,0.4696,0.5376,0.5624,0.6438,0.7366,0.7624,0.8304,0.7629,0.7433,0.6572,0.6428,0.5572,0.5500,0.6500,0.6500,0.6427,0.5505,0.4629,0.4438,0.4428,0.4500,0.5366,0.5624,0.6366,0.6427,0.6355,0.5433,0.4500,0.3634,0.3505,0.3505,0.3500,0.2707,0.2573,0.2505,0.2505,0.2640,0.3572,0.4572,0.5634,0.7366,0.8360,0.8495,0.8495,0.8366,0.7500,0.6629,0.6376,0.5624,0.5376,0.4634,0.4640,0.5433,0.5500,0.5573,0.6428,0.6500,0.6433,0.5629,0.5376,0.4634,0.4634,0.5371,0.5562,0.6433,0.7366,0.7629,0.8438,0.8557,0.8371,0.7495,0.6505,0.5634,0.5443,0.4702,0.4578,0.4640,0.5500,0.6360,0.6438,0.6557,0.6505,0.6500,0.6505,0.6567,0.6572,0.6567,0.6505,0.6500,0.6500,0.6505,0.6634,0.7433,0.7505,0.7562,0.7438,0.6567,0.5634,0.5376,0.4629,0.4511,0.4634,0.5500,0.6366,0.6489,0.6371,0.5629,0.5438,0.4634,0.4505,0.4505,0.4629,0.5376,0.5624,0.6366,0.6433,0.6495,0.6495,0.6433,0.6366,0.5691,0.6309,0.6489,0.6500,0.6495,0.6366,0.5567,0.5495,0.5443,0.5624,0.6376,0.6629,0.7500,0.8371,0.8557,0.8500,0.8366,0.7562,0.7366,0.6567,0.6500,0.6500,0.6500,0.6428,0.5500,0.4505,0.3640,0.3573,0.3645,0.4562,0.5376,0.5562,0.5572,0.5500,0.4634,0.4371,0.3562,0.3433,0.3428,0.3360,0.2567,0.2433,0.1640,0.1640,0.2500,0.3433,0.4428,0.5433,0.6495,0.7495,0.8366,0.8495,0.8427,0.7567,0.7371,0.6624,0.6376,0.5629,0.5500,0.5438,0.5495,0.5505,0.5634,0.6433,0.6495,0.6366,0.5500,0.4634,0.4505,0.4505,0.4567,0.4640,0.5505,0.6495,0.7371,0.7624,0.8304,0.7629,0.7433,0.6505,0.5634,0.5500,0.5433,0.5433,0.5500,0.5640,0.6500,0.6634,0.7304,0.6634,0.6567,0.6567,0.7293,0.7360,0.7360,0.6634,0.6567,0.6511,0.6629,0.7371,0.7495,0.7500,0.7500,0.7428,0.6500,0.5511,0.4696,0.4511,0.4500,0.4573,0.5433,0.5629,0.6304,0.5629,0.5505,0.5428,0.4573,0.4500,0.4500,0.4505,0.4629,0.5376,0.5562,0.5634,0.6366,0.6366,0.5634,0.5567,0.5511,0.5629,0.6366,0.6433,0.6495,0.6433,0.5640,0.5573,0.5634,0.6376,0.6624,0.7376,0.7629,0.8500,0.9360,0.9365,0.8624,0.8376,0.7629,0.7505,0.7500,0.6500,0.6500,0.6428,0.5500,0.4505,0.3634,0.3505,0.3573,0.4433,0.4634,0.5433,0.5495,0.5366,0.4500,0.3634,0.3438,0.2640,0.2573,0.2567,0.2505,0.2433,0.1640,0.1640,0.2443,0.2702,0.3578,0.4567,0.5505,0.6500,0.7495,0.8360,0.8360,0.7567,0.7495,0.7366,0.6562,0.6433,0.6366,0.5634,0.5573,0.5634,0.6371,0.6495,0.6433,0.5634,0.5433,0.4573,0.4500,0.4500,0.4500,0.4505,0.4634,0.5505,0.6495,0.7366,0.7495,0.7500,0.7433,0.6629,0.6376,0.5634,0.5573,0.5634,0.6371,0.6562,0.7360,0.7433,0.7484,0.7366,0.7293,0.6567,0.6567,0.6634,0.7360,0.7360,0.7293,0.6629,0.7366,0.7495,0.7500,0.7500,0.7500,0.7428,0.6505,0.5629,0.5376,0.4634,0.4573,0.4640,0.5433,0.5505,0.5562,0.5505,0.5500,0.5433,0.4640,0.4567,0.4505,0.4500,0.4505,0.4634,0.5433,0.5505,0.5567,0.5562,0.5438,0.5428,0.5428,0.5438,0.5562,0.5634,0.6371,0.6489,0.6433,0.6428,0.6438,0.6624,0.7371,0.7562,0.8366,0.8562,0.9360,0.9422,0.9298,0.8557,0.8433,0.8428,0.8428,0.6567,0.6505,0.6428,0.5500,0.4567,0.4371,0.3634,0.3640,0.4433,0.4572,0.5428,0.5433,0.4634,0.4438,0.3634,0.3438,0.2640,0.2567,0.2505,0.2500,0.2495,0.2433,0.2438,0.2624,0.3376,0.3629,0.4443,0.4702,0.5573,0.6500,0.7366,0.7489,0.7433,0.7427,0.7360,0.6567,0.6505,0.6562,0.6500,0.6433,0.6433,0.6495,0.6495,0.6366,0.5567,0.5433,0.4640,0.4567,0.4505,0.4500,0.4500,0.4505,0.4634,0.5505,0.6433,0.6629,0.7371,0.7489,0.7371,0.6629,0.6505,0.6500,0.6505,0.6629,0.7371,0.7495,0.7495,0.7371,0.6634,0.6562,0.6438,0.6428,0.6438,0.6562,0.6572,0.6567,0.6572,0.7366,0.7495,0.7500,0.7500,0.7500,0.7433,0.6629,0.6376,0.5629,0.5500,0.5433,0.5433,0.5495,0.5500,0.5505,0.5567,0.5572,0.5567,0.5500,0.5371,0.4634,0.4567,0.4511,0.4634,0.5433,0.5500,0.5495,0.5371,0.4634,0.4567,0.4511,0.4629,0.5371,0.5500,0.5634,0.6433,0.6500,0.6505,0.6629,0.7371,0.7495,0.7567,0.8366,0.8495,0.8500,0.8500,0.8495,0.8438,0.8495,0.8500,0.8500,0.7360,0.6567,0.6428,0.5505,0.4640,0.4567,0.4505,0.4505,0.4567,0.4640,0.5433,0.5433,0.4640,0.4562,0.4376,0.3629,0.3505,0.3433,0.2640,0.2567,0.2505,0.2500,0.2567,0.3371,0.3624,0.4371,0.4562,0.5366,0.5500,0.5573,0.5702,0.6433,0.6438,0.6495,0.6495,0.6438,0.6557,0.7298,0.7360,0.6629,0.6505,0.6495,0.6371,0.5629,0.5505,0.5495,0.5433,0.5366,0.4634,0.4572,0.4567,0.4505,0.4505,0.4634,0.5500,0.6371,0.6629,0.7433,0.7495,0.7433,0.7428,0.7433,0.7495,0.7505,0.7562,0.7505,0.7433,0.6634,0.6500,0.6371,0.5629,0.5511,0.5629,0.6371,0.6495,0.6500,0.6505,0.6629,0.7371,0.7495,0.7500,0.7500,0.7495,0.7371,0.6629,0.6500,0.6371,0.5634,0.5567,0.5505,0.5500,0.5567,0.6360,0.6428,0.6428,0.6366,0.5629,0.5500,0.5371,0.4696,0.5371,0.5495,0.5500,0.5433,0.4634,0.4500,0.4371,0.3702,0.4438,0.4634,0.5438,0.5634,0.6438,0.6567,0.6634,0.7371,0.7495,0.7500,0.7505,0.7629,0.8298,0.7567,0.7500,0.7500,0.7567,0.8360,0.8433,0.8495,0.7360,0.6562,0.6366,0.5562,0.5433,0.5428,0.5433,0.5495,0.5495,0.5438,0.5495,0.5495,0.5433,0.5366,0.4629,0.4505,0.4495,0.4366,0.3567,0.3433,0.2640,0.2573,0.2640,0.3500,0.4371,0.4562,0.4640,0.5438,0.5562,0.5505,0.5505,0.5500,0.4774,0.5438,0.5500,0.5567,0.6371,0.6624,0.7360,0.7298,0.6557,0.6371,0.5624,0.5438,0.5428,0.5433,0.5495,0.5500,0.5495,0.5433,0.5360,0.4567,0.4495,0.4443,0.4629,0.5500,0.6433,0.7360,0.7495,0.7500,0.7500,0.7567,0.8360,0.8427,0.8360,0.7562,0.7366,0.6562,0.6371,0.5624,0.5376,0.4696,0.5376,0.5624,0.6371,0.6495,0.6500,0.6505,0.6629,0.7366,0.7433,0.7495,0.7500,0.7495,0.7433,0.7366,0.6624,0.6438,0.6360,0.5567,0.5500,0.5572,0.6428,0.6505,0.6567,0.6567,0.6500,0.6371,0.5624,0.5443,0.5495,0.5505,0.5562,0.5438,0.4634,0.4438,0.3634,0.3578,0.4433,0.4634,0.5500,0.6371,0.6624,0.7366,0.7433,0.7489,0.7433,0.7428,0.7428,0.7433,0.7422,0.6572,0.6500,0.6500,0.6572,0.7428,0.7567,0.8360,0.6562,0.6376,0.5629,0.5505,0.5500,0.5505,0.5629,0.6366,0.6366,0.5634,0.5572,0.5572,0.5572,0.5567,0.5505,0.5500,0.5433,0.4634,0.4500,0.4366,0.3562,0.3438,0.3500,0.3640,0.4562,0.5371,0.5500,0.5629,0.6304,0.5629,0.5505,0.5433,0.4640,0.4573,0.4573,0.4640,0.5500,0.6366,0.6495,0.6495,0.6371,0.5624,0.5376,0.4629,0.4511,0.4634,0.5433,0.5567,0.6298,0.5629,0.5433,0.4572,0.4433,0.3702,0.4376,0.4634,0.5567,0.6500,0.7360,0.7433,0.7495,0.7572,0.8427,0.8500,0.8427,0.7505,0.6634,0.6438,0.5629,0.5376,0.4629,0.4511,0.4629,0.5376,0.5624,0.6371,0.6495,0.6500,0.6505,0.6567,0.6634,0.7366,0.7427,0.7428,0.7428,0.7422,0.7298,0.6557,0.6366,0.5567,0.5500,0.5572,0.6428,0.6567,0.7360,0.7427,0.7360,0.6562,0.6371,0.5634,0.5573,0.5634,0.6298,0.5562,0.5366,0.4500,0.3640,0.3640,0.4500,0.5371,0.5634,0.6562,0.7371,0.7495,0.7500,0.7433,0.6640,0.6572,0.6572,0.6567,0.6438,0.5634,0.5505,0.5500,0.5572,0.6433,0.6640,0.7500,0.6433,0.5629,0.5438,0.5433,0.5495,0.5567,0.6366,0.6495,0.6495,0.6428,0.6366,0.6422,0.6428,0.6428,0.6428,0.6428,0.6360,0.5562,0.5371,0.4624,0.4376,0.3696,0.4366,0.4500,0.5366,0.5624,0.6366,0.6433,0.6489,0.6371,0.5629,0.5500,0.5366,0.4567,0.4500,0.4511,0.4702,0.5505,0.5572,0.5567,0.5500,0.5366,0.4562,0.4371,0.3696,0.4438,0.5360,0.5562,0.6355,0.6298,0.5489,0.4567,0.4366,0.3572,0.3629,0.4438,0.5360,0.5567,0.6428,0.6567,0.7360,0.7500,0.8355,0.8427,0.8360,0.7500,0.6634,0.6433,0.5511,0.4696,0.4511,0.4500,0.4505,0.4634,0.5443,0.5696,0.6438,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6505,0.6567,0.6572,0.6562,0.6376,0.5629,0.5505,0.5500,0.5567,0.6366,0.6562,0.7366,0.7495,0.7428,0.6572,0.6495,0.6433,0.6428,0.6433,0.6428,0.5634,0.5438,0.4629,0.4438,0.4438,0.4634,0.5567,0.6500,0.7371,0.7562,0.7567,0.7500,0.7366,0.6567,0.6500,0.6500,0.6433,0.5629,0.5376,0.4634,0.4573,0.4645,0.5567,0.6505,0.7427,0.6360,0.5500,0.4640,0.4634,0.5371,0.5562,0.6366,0.6495,0.6500,0.6438,0.5769,0.6438,0.6500,0.6505,0.6567,0.6572,0.6562,0.6376,0.5624,0.5376,0.4624,0.4449,0.4562,0.4645,0.5562,0.6376,0.6562,0.6572,0.6572,0.6562,0.6371,0.5567,0.5433,0.4640,0.4573,0.4634,0.5371,0.5500,0.5562,0.5443,0.4702,0.4505,0.3640,0.3500,0.3438,0.3567,0.4495,0.5371,0.5562,0.5562,0.5371,0.4500,0.3629,0.3438,0.3433,0.3567,0.4428,0.4572,0.5428,0.5572,0.6428,0.6572,0.7433,0.7567,0.7567,0.7500,0.7366,0.6495,0.5567,0.5366,0.4567,0.4500,0.4505,0.4634,0.5500,0.6366,0.6495,0.6500,0.6500,0.6495,0.6371,0.5634,0.5573,0.5634,0.6366,0.6427,0.6366,0.5624,0.5438,0.5428,0.5433,0.5500,0.5634,0.6438,0.6629,0.7371,0.7422,0.6572,0.6500,0.6500,0.6500,0.6500,0.6495,0.6366,0.5562,0.5371,0.4634,0.4640,0.5500,0.6433,0.7366,0.7624,0.8366,0.8360,0.7500,0.6634,0.6500,0.6433,0.6428,0.6360,0.5500,0.4634,0.4505,0.4500,0.4573,0.5495,0.6433,0.7355,0.5634,0.5438,0.4573,0.4511,0.4696,0.5449,0.5696,0.6438,0.6500,0.6495,0.6438,0.6500,0.6567,0.6634,0.7366,0.7428,0.7366,0.6629,0.6438,0.5629,0.5376,0.4696,0.5371,0.5562,0.6371,0.6624,0.7371,0.7495,0.7495,0.7371,0.6562,0.5640,0.5500,0.5433,0.5428,0.5433,0.5500,0.5629,0.6304,0.5624,0.5371,0.4495,0.3505,0.2640,0.2573,0.2645,0.3567,0.4500,0.5360,0.5360,0.4562,0.4360,0.3438,0.2629,0.2505,0.2567,0.3366,0.3562,0.4366,0.4562,0.5366,0.5567,0.6495,0.7366,0.7495,0.7495,0.7366,0.6495,0.5572,0.5428,0.4572,0.4500,0.4567,0.5366,0.5567,0.6428,0.6500,0.6500,0.6500,0.6433,0.5629,0.5438,0.5428,0.5433,0.5495,0.5500,0.5495,0.5371,0.4634,0.4573,0.4634,0.5371,0.5562,0.6366,0.6500,0.6629,0.7298,0.6567,0.6500,0.6500,0.6500,0.6500,0.6500,0.6433,0.5640,0.5567,0.5505,0.5567,0.6371,0.6634,0.7562,0.8371,0.8495,0.8427,0.7500,0.6572,0.6433,0.5640,0.5572,0.5567,0.5433,0.4567,0.4433,0.4433,0.4562,0.5371,0.5634,0.6500,0.6366,0.5562,0.4645,0.4634,0.5371,0.5562,0.6366,0.6495,0.6500,0.6500,0.6505,0.6629,0.7371,0.7500,0.7567,0.7572,0.7562,0.7438,0.7360,0.6500,0.5634,0.5511,0.5629,0.6376,0.6624,0.7376,0.7624,0.8366,0.8366,0.7624,0.7371,0.6500,0.5640,0.5567,0.5505,0.5505,0.5629,0.6371,0.6484,0.6304,0.5489,0.4500,0.3505,0.2634,0.2505,0.2573,0.3433,0.3634,0.4433,0.4433,0.3634,0.3433,0.2567,0.2366,0.1567,0.1505,0.1634,0.2438,0.2634,0.3438,0.3634,0.4511,0.5567,0.6562,0.7366,0.7366,0.6629,0.6433,0.5567,0.5366,0.4567,0.4500,0.4572,0.5428,0.5572,0.6428,0.6500,0.6500,0.6495,0.6366,0.5500,0.4634,0.4505,0.4500,0.4500,0.4500,0.4500,0.4495,0.4438,0.4495,0.4505,0.4629,0.5376,0.5624,0.6371,0.6500,0.6567,0.6572,0.6572,0.6572,0.6572,0.6572,0.6567,0.6500,0.6433,0.6428,0.6433,0.6500,0.6634,0.7500,0.8366,0.8495,0.8500,0.8428,0.7500,0.6572,0.6428,0.5572,0.5500,0.5495,0.5366,0.4500,0.3640,0.3640,0.4438,0.4634,0.5505,0.6428,0.6562,0.6371,0.5562,0.5438,0.5495,0.5572,0.6428,0.6500,0.6505,0.6567,0.6640,0.7438,0.7629,0.8366,0.8428,0.8428,0.8366,0.7629,0.7500,0.7366,0.6562,0.6438,0.6500,0.6629,0.7376,0.7624,0.8371,0.8495,0.8495,0.8371,0.7624,0.7371,0.6562,0.6371,0.5634,0.5634,0.6371,0.6489,0.6371,0.5629,0.5433,0.4505,0.3629,0.3376,0.2634,0.2640,0.3433,0.3505,0.3567,0.3567,0.3443,0.2634,0.1712,0.1511,0.0707,0.0578,0.0640,0.1433,0.1573,0.2433,0.2640,0.3634,0.5366,0.6366,0.6562,0.6567,0.6500,0.6366,0.5500,0.4634,0.4500,0.4438,0.4562,0.5366,0.5567,0.6428,0.6500,0.6500,0.6433,0.5634,0.5433,0.4505,0.3640,0.3573,0.3572,0.3572,0.3573,0.3573,0.3640,0.4433,0.4500,0.4505,0.4629,0.5376,0.5624,0.6371,0.6562,0.7360,0.7428,0.7428,0.7428,0.7428,0.7366,0.6634,0.6572,0.6572,0.6634,0.7371,0.7562,0.8366,0.8495,0.8500,0.8500,0.8427,0.7500,0.6572,0.6428,0.5572,0.5500,0.5433,0.4634,0.4433,0.3573,0.3573,0.4428,0.4572,0.5500,0.6427,0.7366,0.6624,0.6376,0.5629,0.5505,0.5572,0.6428,0.6500,0.6567,0.7366,0.7562,0.8360,0.8438,0.8557,0.8505,0.8500,0.8489,0.8304,0.7562,0.7495,0.7371,0.6696,0.7366,0.7433,0.7562,0.8366,0.8495,0.8505,0.8567,0.8562,0.8376,0.7624,0.7376,0.6624,0.6438,0.6433,0.6489,0.6371,0.5629,0.5505,0.5428,0.4567,0.4371,0.3624,0.3438,0.3433,0.3495,0.3500,0.3500,0.3500,0.3495,0.3366,0.2505,0.1696,0.1443,0.0640,0.0578,0.0640,0.0712,0.1573,0.2505,0.3505,0.4567,0.5562,0.6366,0.6427,0.6360,0.5562,0.5360,0.4500,0.4366,0.3696,0.4376,0.4629,0.5500,0.6366,0.6495,0.6500,0.6428,0.5572,0.5428,0.4500,0.3573,0.3500,0.3500,0.3505,0.3567,0.3573,0.3640,0.4433,0.4500,0.4500,0.4505,0.4634,0.5438,0.5634,0.6505,0.7433,0.7567,0.7567,0.7505,0.7500,0.7489,0.7366,0.7360,0.7422,0.7433,0.7562,0.8366,0.8495,0.8495,0.8433,0.8427,0.8360,0.7495,0.6572,0.6433,0.5634,0.5505,0.5433,0.4634,0.4433,0.3573,0.3573,0.4428,0.4572,0.5500,0.6427,0.7495,0.7371,0.6624,0.6371,0.5567,0.5567,0.6366,0.6495,0.6572,0.7495,0.8366,0.8500,0.8624,0.9236,0.8557,0.8433,0.8366,0.7629,0.7505,0.7495,0.7428,0.7366,0.7428,0.7495,0.7567,0.8360,0.8433,0.8557,0.9293,0.9293,0.8557,0.8371,0.7624,0.7371,0.6567,0.6495,0.6371,0.5629,0.5505,0.5500,0.5433,0.4640,0.4562,0.4376,0.3629,0.3505,0.3500,0.3500,0.3500,0.3505,0.3567,0.3567,0.3500,0.3366,0.2500,0.1634,0.1505,0.1500,0.1511,0.1702,0.2578,0.3572,0.4567,0.5438,0.5562,0.5505,0.5428,0.4572,0.4433,0.3634,0.3500,0.3443,0.3624,0.4438,0.5366,0.5624,0.6371,0.6495,0.6428,0.5572,0.5428,0.4505,0.3640,0.3572,0.3573,0.3634,0.4371,0.4495,0.4505,0.4567,0.4572,0.4572,0.4572,0.4640,0.5433,0.5573,0.6500,0.7495,0.8360,0.8360,0.7567,0.7495,0.7371,0.6634,0.6634,0.7371,0.7495,0.7567,0.8360,0.8427,0.8366,0.7629,0.7505,0.7495,0.7366,0.6567,0.6495,0.6371,0.5629,0.5500,0.5366,0.4500,0.3640,0.3640,0.4438,0.4634,0.5505,0.6427,0.7500,0.7489,0.7304,0.6489,0.5572,0.5505,0.5629,0.6371,0.6567,0.7500,0.8427,0.8562,0.9236,0.8624,0.8438,0.7634,0.7500,0.7433,0.7428,0.7366,0.6634,0.6572,0.6634,0.7366,0.7433,0.7500,0.7629,0.8376,0.8562,0.8567,0.8505,0.8489,0.8304,0.7489,0.6572,0.6433,0.5634,0.5505,0.5500,0.5500,0.5495,0.5433,0.5366,0.4624,0.4376,0.3629,0.3505,0.3505,0.3567,0.3634,0.4371,0.4495,0.4500,0.4428,0.3567,0.3366,0.2567,0.2505,0.2629,0.3376,0.3629,0.4505,0.5433,0.5567,0.5505,0.4707,0.4505,0.3640,0.3500,0.3366,0.2567,0.2567,0.3366,0.3567,0.4495,0.5366,0.5562,0.6360,0.6360,0.5567,0.5433,0.4629,0.4438,0.4433,0.4495,0.4505,0.4629,0.5371,0.5495,0.5500,0.5495,0.5433,0.5428,0.5433,0.5500,0.5634,0.6505,0.7495,0.8360,0.8360,0.7562,0.7371,0.6624,0.6438,0.6438,0.6624,0.7371,0.7500,0.7562,0.7505,0.7495,0.7371,0.6634,0.6572,0.6567,0.6505,0.6500,0.6495,0.6366,0.5567,0.5428,0.4567,0.4433,0.4433,0.4562,0.5366,0.5567,0.6428,0.7427,0.7360,0.6562,0.6360,0.5500,0.5428,0.5438,0.5629,0.6500,0.7433,0.8360,0.8500,0.8562,0.8500,0.8360,0.7438,0.6634,0.6572,0.6567,0.6500,0.6433,0.6428,0.6433,0.6500,0.6567,0.6634,0.7371,0.7562,0.8360,0.8433,0.8489,0.8371,0.7624,0.7371,0.6562,0.6366,0.5567,0.5500,0.5500,0.5505,0.5567,0.5572,0.5562,0.5376,0.4624,0.4376,0.3634,0.3634,0.4371,0.4500,0.4634,0.5433,0.5500,0.5428,0.4572,0.4428,0.3572,0.3567,0.4366,0.4562,0.5371,0.5629,0.6433,0.6500,0.6428,0.5505,0.4567,0.3578,0.2707,0.2511,0.1707,0.1645,0.2438,0.2634,0.3505,0.4433,0.4634,0.5433,0.5500,0.5500,0.5495,0.5371,0.4634,0.4634,0.5366,0.5433,0.5500,0.5629,0.6366,0.6427,0.6366,0.5634,0.5572,0.5572,0.5634,0.6371,0.6567,0.7433,0.7567,0.7562,0.7376,0.6624,0.6376,0.5634,0.5634,0.6376,0.6624,0.7366,0.7366,0.6634,0.6567,0.6500,0.6433,0.6433,0.6495,0.6500,0.6500,0.6500,0.6428,0.5572,0.5428,0.4572,0.4500,0.4500,0.4572,0.5433,0.5634,0.6433,0.6500,0.6433,0.5634,0.5438,0.4634,0.4511,0.4629,0.5438,0.6366,0.6634,0.7562,0.8366,0.8428,0.8366,0.7562,0.6640,0.6500,0.6433,0.6366,0.5634,0.5572,0.5572,0.5572,0.5634,0.6366,0.6433,0.6500,0.6634,0.7438,0.7629,0.8304,0.7624,0.7376,0.6624,0.6371,0.5562,0.5433,0.5433,0.5495,0.5567,0.6360,0.6428,0.6366,0.5629,0.5438,0.4634,0.4505,0.4505,0.4634,0.5433,0.5572,0.6428,0.6500,0.6428,0.5572,0.5428,0.4572,0.4567,0.5366,0.5567,0.6489,0.7304,0.7489,0.7495,0.7366,0.6495,0.5500,0.4500,0.3505,0.2629,0.2376,0.1640,0.1702,0.2443,0.2640,0.3562,0.4371,0.4500,0.4629,0.5366,0.5427,0.5422,0.5366,0.5428,0.5495,0.5567,0.6360,0.6433,0.6495,0.6500,0.6495,0.6433,0.6428,0.6428,0.6433,0.6500,0.6634,0.7433,0.7495,0.7371,0.6624,0.6376,0.5624,0.5438,0.5438,0.5624,0.6376,0.6562,0.6567,0.6500,0.6371,0.5634,0.5573,0.5634,0.6371,0.6495,0.6500,0.6500,0.6428,0.5572,0.5428,0.4572,0.4500,0.4500,0.4572,0.5495,0.6366,0.6495,0.5500,0.5495,0.5366,0.4562,0.4371,0.3696,0.4376,0.4629,0.5500,0.6433,0.7360,0.7500,0.7567,0.7562,0.7371,0.6562,0.6371,0.5634,0.5567,0.5505,0.5495,0.5433,0.5428,0.5433,0.5500,0.5567,0.5634,0.6376,0.6624,0.7376,0.7551,0.7376,0.6624,0.6376,0.5562,0.4645,0.4573,0.4640,0.5438,0.5634,0.6438,0.6567,0.6562,0.6438,0.6360,0.5567,0.5500,0.5500,0.5567,0.6366,0.6562,0.7366,0.7495,0.7428,0.6567,0.6366,0.5567,0.5505,0.5634,0.6500,0.7371,0.7629,0.8433,0.8433,0.7629,0.7366,0.6428,0.5433,0.4495,0.3505,0.2634,0.2500,0.2443,0.2562,0.2640,0.3438,0.3567,0.3640,0.4438,0.4562,0.4511,0.4567,0.4634,0.5371,0.5495,0.5567,0.6366,0.6495,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6562,0.7304,0.7484,0.7371,0.6624,0.6376,0.5624,0.5376,0.4634,0.4640,0.5438,0.5634,0.6433,0.6495,0.6371,0.5629,0.5505,0.5500,0.5505,0.5629,0.6371,0.6495,0.6500,0.6428,0.5572,0.5428,0.4572,0.4500,0.4500,0.4572,0.5500,0.6427,0.6500,0.4500,0.4500,0.4433,0.3634,0.3500,0.3443,0.3624,0.4376,0.4629,0.5505,0.6428,0.6567,0.7360,0.7366,0.6629,0.6438,0.5634,0.5505,0.5500,0.5495,0.5371,0.4634,0.4572,0.4572,0.4634,0.5366,0.5438,0.5629,0.6438,0.6629,0.7304,0.6629,0.6438,0.5634,0.5438,0.4634,0.4511,0.4634,0.5500,0.6371,0.6624,0.7366,0.7366,0.6634,0.6567,0.6500,0.6438,0.6495,0.6505,0.6634,0.7438,0.7629,0.8366,0.8360,0.7500,0.6634,0.6505,0.6500,0.6567,0.7371,0.7629,0.8500,0.9360,0.9360,0.8500,0.7567,0.6572,0.5634,0.5371,0.4495,0.3567,0.3371,0.2696,0.3366,0.3433,0.3500,0.3567,0.3640,0.4433,0.4438,0.3769,0.4438,0.4505,0.4629,0.5366,0.5438,0.5624,0.6366,0.6433,0.6495,0.6500,0.6500,0.6500,0.6500,0.6500,0.6505,0.6629,0.7304,0.6629,0.6438,0.5634,0.5438,0.4634,0.4505,0.4573,0.5428,0.5572,0.6428,0.6438,0.5696,0.5511,0.5500,0.5500,0.5500,0.5505,0.5629,0.6366,0.6427,0.6360,0.5567,0.5428,0.4572,0.4500,0.4500,0.4572,0.5495,0.6366,0.6495,0.3572,0.3572,0.3567,0.3438,0.2640,0.2640,0.3438,0.3629,0.4376,0.4629,0.5438,0.5634,0.6433,0.6500,0.6500,0.6433,0.5640,0.5572,0.5567,0.5438,0.4634,0.4500,0.4433,0.4433,0.4500,0.4567,0.4640,0.5505,0.6428,0.6505,0.6562,0.6505,0.6433,0.5634,0.5500,0.5371,0.4696,0.5376,0.5629,0.6495,0.7304,0.7489,0.7495,0.7433,0.7428,0.7366,0.6696,0.7371,0.7495,0.7567,0.8360,0.8433,0.8495,0.8495,0.8360,0.7500,0.7428,0.7428,0.7438,0.7624,0.8438,0.9360,0.9495,0.9495,0.9360,0.8428,0.7433,0.6500,0.5629,0.5366,0.4438,0.3624,0.3443,0.3495,0.3505,0.3629,0.4366,0.4433,0.4495,0.4500,0.4505,0.4562,0.4505,0.4505,0.4562,0.4572,0.5366,0.5495,0.5567,0.6360,0.6427,0.6428,0.6428,0.6428,0.6428,0.6428,0.6438,0.6557,0.6505,0.6428,0.5572,0.5433,0.4640,0.4573,0.4640,0.5438,0.5634,0.6433,0.6495,0.6371,0.5634,0.5567,0.5505,0.5500,0.5500,0.5505,0.5567,0.5572,0.5567,0.5505,0.5433,0.4640,0.4567,0.4505,0.4567,0.5371,0.5624,0.6366,0.3500,0.3500,0.3500,0.3433,0.2640,0.2640,0.3433,0.3505,0.3629,0.4376,0.4624,0.5371,0.5500,0.5634,0.6433,0.6495,0.6433,0.6428,0.6360,0.5500,0.4634,0.4438,0.3640,0.3640,0.4433,0.4505,0.4634,0.5505,0.6428,0.6505,0.6567,0.6567,0.6500,0.6371,0.5634,0.5567,0.5511,0.5629,0.6371,0.6500,0.6634,0.7433,0.7500,0.7500,0.7505,0.7562,0.7511,0.7629,0.8366,0.8433,0.8495,0.8500,0.8500,0.8500,0.8427,0.7572,0.7500,0.7505,0.7629,0.8371,0.8567,0.9427,0.9500,0.9500,0.9427,0.8505,0.7629,0.7366,0.6438,0.5562,0.4634,0.4376,0.3629,0.3511,0.3629,0.4371,0.4495,0.4500,0.4505,0.4629,0.5366,0.5366,0.4634,0.4567,0.4443,0.3769,0.4438,0.4500,0.4572,0.5428,0.5500,0.5500,0.5500,0.5500,0.5500,0.5505,0.5629,0.6366,0.6433,0.6428,0.5634,0.5500,0.5433,0.5428,0.5438,0.5624,0.6376,0.6562,0.6572,0.6562,0.6438,0.6366,0.5629,0.5505,0.5500,0.5500,0.5500,0.5500,0.5505,0.5567,0.5567,0.5500,0.5371,0.4629,0.4511,0.4629,0.5371,0.5495,0.3572,0.3572,0.3572,0.3567,0.3505,0.3505,0.3567,0.3572,0.3578,0.3702,0.4443,0.4567,0.4640,0.5500,0.6366,0.6495,0.6500,0.6500,0.6433,0.5629,0.5371,0.4500,0.3640,0.3640,0.4438,0.4629,0.5376,0.5629,0.6438,0.6629,0.7366,0.7360,0.6567,0.6500,0.6500,0.6495,0.6433,0.6433,0.6495,0.6500,0.6567,0.7360,0.7433,0.7495,0.7567,0.8360,0.8427,0.8433,0.8489,0.8433,0.8428,0.8428,0.8428,0.8427,0.8360,0.7567,0.7500,0.7562,0.8304,0.8489,0.8567,0.9366,0.9495,0.9500,0.9428,0.8567,0.8366,0.7495,0.6567,0.6360,0.5433,0.4562,0.4371,0.3696,0.4371,0.4495,0.4505,0.4567,0.4634,0.5376,0.5562,0.5562,0.5438,0.5360,0.4562,0.4376,0.3696,0.3578,0.3640,0.4433,0.4500,0.4500,0.4500,0.4500,0.4500,0.4567,0.5366,0.5500,0.5629,0.6366,0.6360,0.5567,0.5500,0.5505,0.5629,0.6376,0.6624,0.7366,0.7427,0.7366,0.6629,0.6500,0.6366,0.5567,0.5500,0.5500,0.5500,0.5505,0.5629,0.6366,0.6428,0.6366,0.5624,0.5376,0.4629,0.4511,0.4567,0.4572,0.4500,0.4500,0.4500,0.4500,0.4500,0.4500,0.4500,0.4500,0.4495,0.4438,0.4495,0.4500,0.4573,0.5433,0.5634,0.6433,0.6500,0.6500,0.6495,0.6366,0.5495,0.4567,0.4433,0.4433,0.4562,0.5371,0.5629,0.6438,0.6629,0.7371,0.7495,0.7427,0.6572,0.6567,0.7360,0.7365,0.6629,0.6505,0.6495,0.6433,0.6438,0.6562,0.6640,0.7433,0.7572,0.8427,0.8500,0.8495,0.8371,0.7634,0.7572,0.7567,0.7505,0.7500,0.7495,0.7433,0.7433,0.7500,0.7629,0.8366,0.8433,0.8562,0.9360,0.9427,0.9360,0.8562,0.8366,0.7495,0.6567,0.6366,0.5495,0.4572,0.4495,0.4438,0.4500,0.4567,0.4634,0.5366,0.5438,0.5624,0.6366,0.6366,0.5629,0.5438,0.4634,0.4500,0.4371,0.3634,0.3578,0.3640,0.3645,0.3640,0.3573,0.3505,0.3500,0.3572,0.4428,0.4567,0.5371,0.5624,0.6298,0.5567,0.5500,0.5567,0.6366,0.6557,0.7304,0.7489,0.7500,0.7489,0.7304,0.6557,0.6366,0.5562,0.5433,0.5433,0.5495,0.5567,0.6366,0.6500,0.6567,0.6567,0.6438,0.5629,0.5376,0.4634,0.4567,0.4505,0.5428,0.5433,0.5495,0.5500,0.5500,0.5500,0.5500,0.5495,0.5371,0.4634,0.4572,0.4572,0.4640,0.5433,0.5572,0.6428,0.6500,0.6500,0.6500,0.6427,0.5500,0.4572,0.4500,0.4505,0.4634,0.5500,0.6433,0.7355,0.7433,0.7495,0.7495,0.7366,0.6567,0.6567,0.7360,0.7422,0.7298,0.6562,0.6433,0.5640,0.5640,0.6433,0.6572,0.7428,0.7567,0.8366,0.8489,0.8371,0.7624,0.7438,0.7428,0.7366,0.6634,0.6572,0.6572,0.6572,0.6634,0.7366,0.7433,0.7495,0.7505,0.7634,0.8433,0.8500,0.8495,0.8371,0.7624,0.7371,0.6500,0.5634,0.5433,0.4572,0.4505,0.4567,0.4634,0.5366,0.5438,0.5562,0.5634,0.6376,0.6562,0.6562,0.6376,0.5624,0.5376,0.4629,0.4500,0.4438,0.4495,0.4500,0.4495,0.4371,0.3567,0.2712,0.2640,0.2645,0.3438,0.3634,0.4500,0.5366,0.5489,0.5433,0.5433,0.5562,0.6360,0.6433,0.6562,0.7360,0.7427,0.7366,0.6629,0.6438,0.5634,0.5438,0.4640,0.4640,0.5433,0.5572,0.6433,0.6629,0.7366,0.7428,0.7360,0.6500,0.5634,0.5500,0.5371,0.4634,0.5572,0.5634,0.6371,0.6495,0.6500,0.6500,0.6500,0.6433,0.5634,0.5500,0.5433,0.5428,0.5433,0.5495,0.5567,0.6360,0.6433,0.6495,0.6495,0.6366,0.5495,0.4572,0.4500,0.4567,0.5371,0.5629,0.6505,0.7427,0.7500,0.7495,0.7371,0.6624,0.6438,0.6438,0.6562,0.6572,0.6567,0.6500,0.6366,0.5567,0.5573,0.6428,0.6572,0.7428,0.7505,0.7629,0.8304,0.7629,0.7438,0.6640,0.6572,0.6562,0.6438,0.6428,0.6428,0.6428,0.6433,0.6495,0.6500,0.6505,0.6629,0.7371,0.7500,0.7567,0.7572,0.7562,0.7376,0.6624,0.6371,0.5562,0.5366,0.4572,0.4629,0.5371,0.5500,0.5567,0.5634,0.6371,0.6500,0.6629,0.7366,0.7366,0.6624,0.6376,0.5624,0.5376,0.4634,0.4634,0.5371,0.5495,0.5433,0.4634,0.4433,0.3572,0.3433,0.2645,0.2702,0.3443,0.3634,0.4433,0.4500,0.4500,0.4562,0.5304,0.5489,0.5500,0.5572,0.6428,0.6500,0.6495,0.6433,0.6355,0.5500,0.5360,0.4567,0.4573,0.5428,0.5572,0.6495,0.7366,0.7500,0.7567,0.7562,0.7371,0.6562,0.6371,0.5629,0.5505,0.6428,0.6438,0.6624,0.7366,0.7433,0.7489,0.7433,0.7360,0.6567,0.6433,0.5640,0.5567,0.5505,0.5500,0.5505,0.5567,0.5634,0.6366,0.6366,0.5624,0.5371,0.4567,0.4500,0.4572,0.5495,0.6366,0.6567,0.7428,0.7500,0.7433,0.6629,0.6376,0.5634,0.5634,0.6366,0.6428,0.6428,0.6366,0.5629,0.5505,0.5572,0.6428,0.6572,0.7428,0.7500,0.7505,0.7562,0.7500,0.7366,0.6562,0.6433,0.6366,0.5634,0.5572,0.5572,0.5572,0.5572,0.5572,0.5573,0.5634,0.6376,0.6562,0.6634,0.7366,0.7427,0.7360,0.6562,0.6366,0.5562,0.5371,0.4629,0.4572,0.5366,0.5562,0.6360,0.6433,0.6500,0.6629,0.7366,0.7438,0.7557,0.7500,0.7371,0.6624,0.6376,0.5629,0.5505,0.5505,0.5629,0.6366,0.6360,0.5567,0.5428,0.4567,0.4366,0.3567,0.3500,0.3500,0.3505,0.3567,0.3567,0.3505,0.3505,0.3634,0.4433,0.4500,0.4572,0.5428,0.5500,0.5500,0.5500,0.5433,0.4640,0.4567,0.4505,0.4572,0.5433,0.5634,0.6505,0.7428,0.7567,0.8360,0.8366,0.7624,0.7376,0.6629,0.6500,0.6433,0.6500,0.6567,0.7366,0.7500,0.7629,0.8304,0.7634,0.7567,0.7500,0.7366,0.6562,0.6371,0.5629,0.5505,0.5495,0.5433,0.5433,0.5495,0.5495,0.5371,0.4629,0.4505,0.4500,0.4572,0.5495,0.6366,0.6562,0.7360,0.7427,0.7355,0.6438,0.5624,0.5438,0.5438,0.5562,0.5572,0.5572,0.5567,0.5505,0.5500,0.5572,0.6428,0.6572,0.7428,0.7500,0.7500,0.7495,0.7371,0.6624,0.6376,0.5629,0.5500,0.5433,0.5428,0.5428,0.5433,0.5495,0.5500,0.5500,0.5505,0.5629,0.6371,0.6500,0.6562,0.6505,0.6433,0.5634,0.5438,0.4634,0.4505,0.4500,0.4572,0.5433,0.5640,0.6500,0.6634,0.7366,0.7438,0.7562,0.7634,0.8304,0.7629,0.7500,0.7366,0.6562,0.6433,0.6428,0.6428,0.6438,0.6562,0.6567,0.6500,0.6360,0.5438,0.4624,0.4438,0.4360,0.3567,0.3500,0.3500,0.3438,0.2702,0.2578,0.2640,0.3433,0.3505,0.3634,0.4433,0.4500,0.4500,0.4500,0.4495,0.4438,0.4495,0.4505,0.4634,0.5500,0.6366,0.6567,0.7428,0.7572,0.8427,0.8489,0.8304,0.7557,0.7433,0.7360,0.6567,0.6500,0.6567,0.7366,0.7557,0.8304,0.8484,0.8433,0.8428,0.8366,0.7624,0.7376,0.6624,0.6371,0.5567,0.5433,0.4640,0.4572,0.4572,0.4567,0.4500,0.4433,0.4433,0.4495,0.4572,0.5433,0.5629,0.6376,0.6557,0.6505,0.6433,0.5629,0.5376,0.4634,0.4634,0.5371,0.5495,0.5500,0.5500,0.5500,0.5505,0.5634,0.6433,0.6567,0.7366,0.7495,0.7500,0.7433,0.6629,0.6376,0.5624,0.5376,0.4629,0.4505,0.4505,0.4567,0.4640,0.5433,0.5505,0.5567,0.5572,0.5578,0.5702,0.6433,0.6371,0.5629,0.5500,0.5366,0.4562,0.4371,0.3696,0.4371,0.4567,0.5495,0.6433,0.7355,0.7433,0.7495,0.7567,0.8360,0.8433,0.8484,0.8304,0.7562,0.7428,0.6572,0.6500,0.6500,0.6500,0.6567,0.7360,0.7427,0.7360,0.6500,0.5629,0.5371,0.4567,0.4428,0.3572,0.3500,0.3500,0.3495,0.3371,0.2634,0.2578,0.2640,0.2707,0.3443,0.3567,0.3573,0.3572,0.3572,0.3573,0.3640,0.4433,0.4567,0.5371,0.5629,0.6433,0.6572,0.7428,0.7567,0.8360,0.8365,0.7624,0.7438,0.7427,0.7360,0.6567,0.6500,0.6505,0.6629,0.7376,0.7629,0.8433,0.8500,0.8500,0.8495,0.8366,0.7562,0.7366,0.6495,0.5572,0.5428,0.4573,0.4500,0.4495,0.4371,0.3634,0.3578,0.3702,0.4438,0.4572,0.5428,0.5505,0.5629,0.6298,0.5567,0.5495,0.5371,0.4629,0.4505,0.4511,0.4696,0.5438,0.5500,0.5505,0.5567,0.5634,0.6371,0.6495,0.6505,0.6634,0.7433,0.7495,0.7366,0.6500,0.5634,0.5438,0.4629,0.4376,0.3634,0.3634,0.4371,0.4567,0.5433,0.5629,0.6366,0.6428,0.6428,0.6433,0.6428,0.5634,0.5438,0.4640,0.4500,0.3645,0.3567,0.3511,0.3634,0.4505,0.5500,0.6500,0.7427,0.7500,0.7500,0.7567,0.8366,0.8489,0.8371,0.7629,0.7500,0.7366,0.6567,0.6500,0.6500,0.6500,0.6567,0.7366,0.7489,0.7366,0.6557,0.6304,0.5489,0.4572,0.4428,0.3572,0.3500,0.3505,0.3567,0.3567,0.3505,0.3500,0.3500,0.3505,0.3567,0.3573,0.3567,0.3505,0.3500,0.3505,0.3634,0.4438,0.4634,0.5500,0.6366,0.6495,0.6567,0.7360,0.7433,0.7489,0.7427,0.7298,0.6562,0.6500,0.6495,0.6433,0.6428,0.6428,0.6433,0.6562,0.7433,0.8360,0.8495,0.8500,0.8500,0.8427,0.7572,0.7427,0.6505,0.5634,0.5438,0.4634,0.4505,0.4433,0.3634,0.3505,0.3567,0.4366,0.4500,0.4634,0.5433,0.5495,0.5438,0.5428,0.4640,0.4572,0.4567,0.4505,0.4505,0.4629,0.5371,0.5500,0.5567,0.5634,0.6366,0.6433,0.6495,0.6500,0.6500,0.6567,0.7366,0.7433,0.6696,0.6443,0.5634,0.5433,0.4505,0.3634,0.3505,0.3505,0.3634,0.4505,0.5495,0.6371,0.6562,0.6572,0.6567,0.6505,0.6428,0.5572,0.5428,0.4572,0.4433,0.3634,0.3505,0.3505,0.3634,0.4505,0.5500,0.6500,0.7427,0.7500,0.7500,0.7505,0.7629,0.8304,0.7629,0.7505,0.7433,0.6634,0.6500,0.6433,0.6433,0.6495,0.6505,0.6629,0.7304,0.6629,0.6438,0.5629,0.5371,0.4562,0.4366,0.3567,0.3505,0.3629,0.4366,0.4428,0.4433,0.4495,0.4505,0.4567,0.4572,0.4567,0.4443,0.3702,0.3578,0.3634,0.4371,0.4562,0.5366,0.5562,0.6360,0.6428,0.6433,0.6495,0.6495,0.6371,0.5634,0.5567,0.5505,0.5505,0.5567,0.5572,0.5572,0.5572,0.5572,0.5645,0.6567,0.7500,0.8360,0.8428,0.8427,0.8360,0.7562,0.7366,0.6562,0.6371,0.5624,0.5376,0.4629,0.4438,0.3640,0.3573,0.3640,0.4438,0.4629,0.5371,0.5495,0.5433,0.4640,0.4567,0.4500,0.4438,0.4495,0.4505,0.4629,0.5376,0.5562,0.5634,0.6371,0.6500,0.6567,0.6572,0.6572,0.6572,0.6567,0.6516,0.6696,0.7433,0.7371,0.6624,0.6376,0.5562,0.4573,0.3640,0.3505,0.3505,0.3640,0.4572,0.5572,0.6562,0.7366,0.7427,0.7366,0.6629,0.6438,0.5634,0.5438,0.4634,0.4500,0.4371,0.3634,0.3634,0.4376,0.4629,0.5505,0.6495,0.7360,0.7428,0.7428,0.7428,0.7438,0.7557,0.7505,0.7495,0.7366,0.6567,0.6433,0.5640,0.5640,0.6433,0.6500,0.6505,0.6562,0.6500,0.6366,0.5500,0.4634,0.4438,0.3634,0.3511,0.3629,0.4376,0.4562,0.4572,0.4640,0.5433,0.5567,0.6360,0.6422,0.6298,0.5551,0.5304,0.4562,0.4505,0.4567,0.4640,0.5433,0.5505,0.5567,0.5567,0.5505,0.5495,0.5371,0.4629,0.4505,0.4500,0.4505,0.4629,0.5366,0.5428,0.5500,0.5500,0.5500,0.5567,0.6371,0.6629,0.7438,0.7562,0.7505,0.7495,0.7371,0.6629,0.6505,0.6495,0.6371,0.5629,0.5438,0.4634,0.4500,0.4438,0.4500,0.4634,0.5438,0.5567,0.5567,0.5438,0.4634,0.4505,0.4438,0.3769,0.4443,0.4629,0.5376,0.5624,0.6366,0.6438,0.6624,0.7366,0.7428,0.7428,0.7428,0.7428,0.7366,0.6696,0.7371,0.7495,0.7500,0.7433,0.6634,0.6433,0.5500,0.4505,0.3640,0.3634,0.4438,0.5422,0.6360,0.7293,0.7489,0.7495,0.7427,0.7298,0.6557,0.6371,0.5624,0.5376,0.4634,0.4567,0.4505,0.4505,0.4629,0.5371,0.5567,0.6433,0.6567,0.6572,0.6572,0.6572,0.6634,0.7366,0.7427,0.7366,0.6629,0.6505,0.6428,0.5573,0.5573,0.6428,0.6500,0.6500,0.6500,0.6438,0.5696,0.5438,0.4572,0.4428,0.3573,0.3567,0.4371,0.4624,0.5371,0.5495,0.5567,0.6366,0.6562,0.7360,0.7365,0.6624,0.6376,0.5624,0.5438,0.5428,0.5428,0.5438,0.5557,0.5505,0.5495,0.5366,0.4562,0.4371,0.3629,0.3505,0.3500,0.3505,0.3634,0.4438,0.4567,0.4572,0.5567,0.5505,0.5500,0.5505,0.5634,0.6438,0.6629,0.7304,0.6634,0.6567,0.6505,0.6500,0.6500,0.6505,0.6562,0.6500,0.6366,0.5562,0.5371,0.4696,0.5371,0.5562,0.6360,0.6428,0.6366,0.5624,0.5376,0.4629,0.4500,0.4438,0.4562,0.5366,0.5562,0.6366,0.6500,0.6629,0.7371,0.7500,0.7567,0.7572,0.7567,0.7505,0.7495,0.7438,0.7500,0.7567,0.7634,0.8298,0.7567,0.7428,0.6500,0.5500,0.4567,0.4438,0.4567,0.5433,0.5640,0.6562,0.7365,0.7366,0.6634,0.6567,0.6505,0.6495,0.6371,0.5629,0.5505,0.5500,0.5500,0.5500,0.5505,0.5567,0.5640,0.6433,0.6500,0.6500,0.6500,0.6500,0.6505,0.6567,0.6572,0.6567,0.6505,0.6500,0.6428,0.5573,0.5573,0.6428,0.6505,0.6567,0.6567,0.6500,0.6366,0.5500,0.4634,0.4438,0.3640,0.3640,0.4500,0.5366,0.5562,0.6360,0.6438,0.6624,0.7371,0.7495,0.7489,0.7304,0.6551,0.6304,0.5562,0.5500,0.5500,0.5567,0.6298,0.5629,0.5438,0.4567,0.3578,0.2702,0.2511,0.2500,0.2505,0.2634,0.3505,0.4428,0.4505,0.4567,0.6366,0.5629,0.5505,0.5500,0.5567,0.6366,0.6500,0.6557,0.6438,0.6366,0.5696,0.6371,0.6500,0.6629,0.7366,0.7366,0.6624,0.6376,0.5629,0.5511,0.5629,0.6376,0.6562,0.6572,0.6562,0.6376,0.5624,0.5376,0.4634,0.4572,0.4640,0.5438,0.5634,0.6433,0.6567,0.7366,0.7500,0.7629,0.8366,0.8427,0.8360,0.7567,0.7500,0.7500,0.7567,0.8360,0.8438,0.8557,0.8500,0.8366,0.7495,0.6500,0.5505,0.4640,0.4634,0.5371,0.5562,0.6366,0.6495,0.6495,0.6433,0.6428,0.6433,0.6495,0.6495,0.6433,0.6428,0.6428,0.6428,0.6428,0.6428,0.6428,0.6433,0.6495,0.6500,0.6500,0.6500,0.6500,0.6500,0.6505,0.6567,0.6567,0.6505,0.6500,0.6433,0.5640,0.5640,0.6433,0.6567,0.7360,0.7366,0.6629,0.6438,0.5629,0.5371,0.4562,0.4433,0.4433,0.4567,0.5433,0.5634,0.6433,0.6567,0.7366,0.7495,0.7495,0.7371,0.6624,0.6376,0.5629,0.5505,0.5500,0.5500,0.5572,0.6422,0.6365,0.5495,0.4500,0.3500,0.2511,0.1702,0.1578,0.1640,0.2505,0.3500,0.4428,0.4567,0.5360,0.6562,0.6376,0.5629,0.5505,0.5505,0.5629,0.6366,0.6366,0.5629,0.5500,0.5443,0.5629,0.6500,0.7366,0.7495,0.7495,0.7371,0.6624,0.6438,0.6433,0.6500,0.6629,0.7371,0.7489,0.7371,0.6629,0.6438,0.5634,0.5500,0.5433,0.5438,0.5624,0.6371,0.6495,0.6572,0.7428,0.7562,0.8304,0.8489,0.8500,0.8427,0.7572,0.7500,0.7500,0.7572,0.8433,0.8629,0.9366,0.9366,0.8624,0.8366,0.7433,0.6495,0.5567,0.5376,0.4764,0.5443,0.5567,0.5567,0.5505,0.5500,0.5505,0.5629,0.6371,0.6500,0.6567,0.6572,0.6572,0.6572,0.6572,0.6567,0.6505,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6505,0.6629,0.7366,0.7366,0.6629,0.6505,0.6495,0.6433,0.6433,0.6500,0.6634,0.7433,0.7495,0.7371,0.6624,0.6371,0.5500,0.4634,0.4505,0.4505,0.4634,0.5495,0.6304,0.6489,0.6567,0.7360,0.7427,0.7366,0.6624,0.6376,0.5624,0.5438,0.5428,0.5433,0.5495,0.5567,0.6360,0.6360,0.5495,0.4500,0.3500,0.2567,0.2371,0.1634,0.1645,0.2567,0.3505,0.4428,0.4567,0.5360,0.7360,0.6562,0.6366,0.5567,0.5495,0.5438,0.5495,0.5495,0.5371,0.4634,0.4640,0.5505,0.6495,0.7366,0.7495,0.7500,0.7495,0.7371,0.6634,0.6634,0.7371,0.7500,0.7629,0.8304,0.7624,0.7438,0.7360,0.6562,0.6371,0.5634,0.5634,0.6371,0.6495,0.6500,0.6567,0.7366,0.7500,0.7629,0.8366,0.8427,0.8360,0.7567,0.7500,0.7500,0.7572,0.8489,0.9304,0.9489,0.9495,0.9371,0.8562,0.7634,0.7371,0.6500,0.5629,0.5443,0.5495,0.5500,0.5433,0.4640,0.4573,0.4640,0.5438,0.5634,0.6500,0.7360,0.7428,0.7428,0.7428,0.7428,0.7366,0.6634,0.6572,0.6572,0.6572,0.6572,0.6572,0.6572,0.6634,0.7371,0.7495,0.7495,0.7371,0.6629,0.6505,0.6500,0.6500,0.6567,0.7366,0.7500,0.7562,0.7500,0.7366,0.6500,0.5629,0.5371,0.4567,0.4562,0.5304,0.5495,0.5629,0.6371,0.6500,0.6562,0.6505,0.6495,0.6366,0.5562,0.5371,0.4634,0.4573,0.4640,0.5433,0.5505,0.5567,0.5562,0.5371,0.4495,0.3500,0.2572,0.2495,0.2433,0.2500,0.3366,0.3629,0.4438,0.4572,0.4640,0.7427,0.6567,0.6366,0.5562,0.5366,0.4567,0.4500,0.4505,0.4562,0.4505,0.4573,0.5495,0.6371,0.6629,0.7433,0.7500,0.7500,0.7500,0.7500,0.7505,0.7629,0.8366,0.8433,0.8489,0.8371,0.7629,0.7500,0.7371,0.6629,0.6505,0.6505,0.6562,0.6505,0.6500,0.6505,0.6629,0.7366,0.7433,0.7495,0.7505,0.7562,0.7505,0.7500,0.7500,0.7567,0.8371,0.8624,0.9371,0.9495,0.9495,0.9360,0.8438,0.7629,0.7433,0.6511,0.5702,0.5573,0.5505,0.5433,0.4634,0.4505,0.4567,0.5366,0.5562,0.6433,0.7360,0.7495,0.7500,0.7500,0.7500,0.7495,0.7433,0.7428,0.7428,0.7428,0.7428,0.7428,0.7433,0.7500,0.7567,0.7567,0.7505,0.7495,0.7366,0.6567,0.6500,0.6500,0.6572,0.7428,0.7567,0.8293,0.7567,0.7428,0.6567,0.6366,0.5495,0.4572,0.4505,0.4634,0.5433,0.5505,0.5629,0.6366,0.6360,0.5567,0.5500,0.5433,0.4640,0.4567,0.4505,0.4505,0.4634,0.5433,0.5500,0.5500,0.5433,0.4629,0.4371,0.3495,0.2572,0.2500,0.2500,0.2572,0.3495,0.4366,0.4562,0.5360,0.5428,0.7427,0.6505,0.5629,0.5371,0.4500,0.3640,0.3573,0.3640,0.4433,0.4505,0.4634,0.5438,0.5634,0.6500,0.7366,0.7495,0.7500,0.7567,0.8360,0.8427,0.8433,0.8495,0.8495,0.8433,0.8422,0.8298,0.7567,0.7562,0.7505,0.7495,0.7433,0.7366,0.6629,0.6505,0.6495,0.6438,0.6495,0.6505,0.6567,0.6634,0.7366,0.7428,0.7428,0.7428,0.7433,0.7562,0.8366,0.8562,0.9360,0.9427,0.9360,0.8562,0.8433,0.8360,0.7562,0.7366,0.6500,0.5640,0.5562,0.5376,0.4629,0.4511,0.4629,0.5376,0.5634,0.6562,0.7366,0.7433,0.7495,0.7500,0.7500,0.7500,0.7500,0.7500,0.7500,0.7505,0.7567,0.7634,0.8366,0.8427,0.8360,0.7567,0.7495,0.7366,0.6567,0.6500,0.6500,0.6572,0.7428,0.7567,0.8293,0.7567,0.7428,0.6567,0.6366,0.5495,0.4572,0.4500,0.4573,0.5428,0.5500,0.5500,0.5500,0.5433,0.4634,0.4505,0.4500,0.4500,0.4500,0.4505,0.4629,0.5376,0.5562,0.5572,0.5567,0.5433,0.4505,0.3634,0.3433,0.2572,0.2500,0.2500,0.2573,0.3500,0.4428,0.4572,0.5428,0.5500,0.7355,0.6428,0.5433,0.4500,0.3629,0.3443,0.3495,0.3573,0.4433,0.4629,0.5376,0.5562,0.5640,0.6438,0.6629,0.7366,0.7433,0.7562,0.8366,0.8495,0.8495,0.8433,0.8366,0.7629,0.7511,0.7562,0.7567,0.8298,0.8422,0.8366,0.7629,0.7500,0.7366,0.6567,0.6433,0.5640,0.5573,0.5634,0.6366,0.6438,0.6562,0.6572,0.6572,0.6572,0.6572,0.6640,0.7433,0.7572,0.8428,0.8500,0.8500,0.8500,0.8500,0.8495,0.8433,0.8360,0.7495,0.6567,0.6371,0.5624,0.5371,0.4567,0.4505,0.4629,0.5438,0.6366,0.6562,0.6634,0.7366,0.7433,0.7495,0.7500,0.7500,0.7500,0.7500,0.7567,0.8360,0.8433,0.8495,0.8500,0.8427,0.7572,0.7433,0.6634,0.6505,0.6500,0.6500,0.6572,0.7428,0.7505,0.7562,0.7500,0.7366,0.6500,0.5634,0.5433,0.4572,0.4505,0.4634,0.5433,0.5495,0.5371,0.4634,0.4562,0.4376,0.3634,0.3640,0.4433,0.4505,0.4634,0.5438,0.5634,0.6433,0.6495,0.6366,0.5500,0.4567,0.3645,0.3500,0.2645,0.2567,0.2511,0.2634,0.3505,0.4428,0.4572,0.5428,0.5500,0.6500,0.5572,0.4572,0.3634,0.3376,0.2702,0.3438,0.3640,0.4562,0.5376,0.5624,0.6366,0.6428,0.6428,0.6433,0.6500,0.6629,0.7376,0.7624,0.8366,0.8366,0.7629,0.7500,0.7371,0.6696,0.7371,0.7500,0.7634,0.8433,0.8495,0.8371,0.7629,0.7433,0.6572,0.6428,0.5572,0.5500,0.5505,0.5567,0.5640,0.6433,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6572,0.7428,0.7505,0.7629,0.8371,0.8495,0.8505,0.8567,0.8562,0.8366,0.7438,0.6624,0.6371,0.5495,0.4572,0.4500,0.4505,0.4640,0.5562,0.6371,0.6500,0.6567,0.6634,0.7366,0.7428,0.7428,0.7428,0.7433,0.7562,0.8360,0.8433,0.8495,0.8495,0.8366,0.7567,0.7428,0.6572,0.6500,0.6500,0.6500,0.6572,0.7428,0.7500,0.7500,0.7433,0.6634,0.6433,0.5572,0.5433,0.4640,0.4634,0.5371,0.5495,0.5438,0.4696,0.4511,0.4433,0.3634,0.3505,0.3572,0.4433,0.4629,0.5438,0.6360,0.6562,0.7366,0.7427,0.6567,0.5634,0.5371,0.4562,0.4366,0.3567,0.3433,0.2702,0.3371,0.3567,0.4428,0.4572,0.5428,0.5500,0.6428,0.5500,0.4500,0.3511,0.2702,0.2645,0.3500,0.4433,0.5366,0.5629,0.6438,0.6562,0.6438,0.5640,0.5573,0.5634,0.6376,0.6629,0.7438,0.7567,0.7567,0.7438,0.6640,0.6562,0.6449,0.6624,0.7371,0.7567,0.8428,0.8500,0.8495,0.8366,0.7495,0.6572,0.6428,0.5572,0.5500,0.5500,0.5500,0.5573,0.6428,0.6500,0.6500,0.6500,0.6500,0.6433,0.5640,0.5640,0.6438,0.6629,0.7376,0.7624,0.8371,0.8557,0.9298,0.9355,0.8495,0.7562,0.7304,0.6489,0.5500,0.4572,0.4500,0.4500,0.4572,0.5433,0.5634,0.6433,0.6500,0.6505,0.6567,0.6572,0.6572,0.6572,0.6634,0.7371,0.7500,0.7629,0.8366,0.8366,0.7629,0.7500,0.7366,0.6567,0.6500,0.6500,0.6500,0.6567,0.7366,0.7495,0.7500,0.7428,0.6567,0.6366,0.5567,0.5495,0.5433,0.5433,0.5500,0.5567,0.5562,0.5376,0.4629,0.4438,0.3634,0.3505,0.3572,0.4495,0.5371,0.5629,0.6500,0.7371,0.7624,0.8298,0.7495,0.6505,0.5634,0.5438,0.4634,0.4500,0.4366,0.3572,0.3567,0.3640,0.4438,0.4634,0.5438,0.5567,0.6427,0.5500,0.4500,0.3567,0.3433,0.3438,0.3634,0.4572,0.5567,0.6500,0.7360,0.7360,0.6500,0.5634,0.5505,0.5505,0.5634,0.6500,0.7366,0.7495,0.7495,0.7366,0.6562,0.6371,0.5702,0.6438,0.6634,0.7505,0.8427,0.8500,0.8500,0.8427,0.7505,0.6634,0.6433,0.5572,0.5500,0.5500,0.5505,0.5634,0.6438,0.6567,0.6572,0.6567,0.6505,0.6428,0.5572,0.5505,0.5629,0.6376,0.6624,0.7376,0.7629,0.8438,0.8629,0.9298,0.8495,0.7505,0.6629,0.6371,0.5495,0.4572,0.4500,0.4500,0.4572,0.5428,0.5572,0.6428,0.6500,0.6500,0.6500,0.6495,0.6433,0.6428,0.6433,0.6495,0.6567,0.7366,0.7500,0.7562,0.7505,0.7433,0.6634,0.6505,0.6500,0.6500,0.6500,0.6505,0.6634,0.7433,0.7495,0.7366,0.6500,0.5634,0.5505,0.5500,0.5500,0.5505,0.5629,0.6366,0.6366,0.5629,0.5438,0.4629,0.4376,0.3629,0.3578,0.4500,0.5495,0.6366,0.6567,0.7495,0.8366,0.8489,0.8366,0.7495,0.6567,0.6366,0.5567,0.5433,0.4634,0.4500,0.4438,0.4500,0.4634,0.5438,0.5634,0.6433,0.6427,0.5500,0.4505,0.3634,0.3511,0.3629,0.4438,0.5428,0.6428,0.7366,0.7557,0.7438,0.6629,0.6371,0.5567,0.5500,0.5572,0.6433,0.6634,0.7433,0.7433,0.6634,0.6438,0.5634,0.5573,0.6366,0.6562,0.7433,0.8360,0.8495,0.8500,0.8428,0.7562,0.7304,0.6489,0.5572,0.5500,0.5500,0.5567,0.6366,0.6562,0.7360,0.7427,0.7360,0.6567,0.6428,0.5572,0.5500,0.5505,0.5629,0.6376,0.6624,0.7438,0.8360,0.8500,0.8557,0.8371,0.7495,0.6505,0.5634,0.5433,0.4572,0.4500,0.4500,0.4572,0.5428,0.5572,0.6428,0.6500,0.6500,0.6500,0.6433,0.5634,0.5505,0.5500,0.5500,0.5572,0.6428,0.6567,0.7360,0.7427,0.7360,0.6567,0.6500,0.6500,0.6500,0.6500,0.6500,0.6572,0.7427,0.7433,0.6634,0.6433,0.5572,0.5500,0.5500,0.5505,0.5634,0.6438,0.6567,0.6567,0.6500,0.6366,0.5500,0.4629,0.4376,0.3702,0.4505,0.5500,0.6433,0.6634,0.7505,0.8433,0.8567,0.8562,0.8366,0.7438,0.6629,0.6500,0.6366,0.5562,0.5371,0.4696,0.5366,0.5500,0.6360,0.6562,0.7360,0.6360,0.5495,0.4567,0.4371,0.3702,0.4438,0.4640,0.5572,0.6572,0.7562,0.8304,0.7624,0.7371,0.6495,0.5572,0.5500,0.5567,0.6366,0.6562,0.7360,0.7360,0.6562,0.6366,0.5567,0.5505,0.5634,0.6438,0.6640,0.7562,0.8366,0.8427,0.8360,0.7500,0.6629,0.6371,0.5562,0.5433,0.5433,0.5562,0.6366,0.6562,0.7360,0.7427,0.7360,0.6567,0.6428,0.5572,0.5500,0.5500,0.5505,0.5629,0.6376,0.6629,0.7500,0.8360,0.8366,0.7624,0.7371,0.6495,0.5573,0.5428,0.4572,0.4500,0.4500,0.4572,0.5433,0.5634,0.6438,0.6567,0.6567,0.6505,0.6428,0.5505,0.4640,0.4567,0.4505,0.4572,0.5428,0.5572,0.6428,0.6505,0.6562,0.6505,0.6500,0.6500,0.6500,0.6500,0.6500,0.6567,0.7360,0.7360,0.6567,0.6428,0.5572,0.5500,0.5505,0.5634,0.6500,0.7366,0.7495,0.7495,0.7371,0.6624,0.6366,0.5438,0.4624,0.4449,0.4629,0.5505,0.6495,0.7371,0.7629,0.8500,0.9360,0.9360,0.8495,0.7567,0.7433,0.7360,0.6557,0.6304,0.5557,0.5438,0.5500,0.5634,0.6500,0.7365,0.7495,0.5567,0.5433,0.4578,0.4562,0.4578,0.5433,0.5634,0.6505,0.7495,0.8366,0.8489,0.8366,0.7495,0.6500,0.5572,0.5500,0.5505,0.5629,0.6376,0.6562,0.6567,0.6438,0.5634,0.5505,0.5500,0.5567,0.6366,0.6562,0.7371,0.7562,0.7567,0.7500,0.7360,0.6438,0.5624,0.5376,0.4634,0.4634,0.5371,0.5562,0.6366,0.6500,0.6567,0.6567,0.6505,0.6428,0.5572,0.5500,0.5495,0.5433,0.5433,0.5562,0.6366,0.6562,0.7366,0.7489,0.7371,0.6629,0.6438,0.5640,0.5500,0.4645,0.4573,0.4572,0.4640,0.5500,0.6366,0.6562,0.7360,0.7366,0.6629,0.6433,0.5500,0.4567,0.4371,0.3634,0.3640,0.4433,0.4572,0.5433,0.5629,0.6371,0.6495,0.6500,0.6500,0.6500,0.6500,0.6500,0.6505,0.6567,0.6567,0.6500,0.6366,0.5567,0.5500,0.5567,0.6433,0.7366,0.7624,0.8366,0.8366,0.7624,0.7371,0.6500,0.5629,0.5376,0.4696,0.5376,0.5629,0.6505,0.7495,0.8366,0.8567,0.9422,0.9365,0.8495,0.7567,0.7433,0.7355,0.6438,0.5629,0.5500,0.5438,0.5557,0.6304,0.6557,0.7366,0.7495,0.5500,0.5433,0.4702,0.5371,0.5567,0.6489,0.7304,0.7557,0.8366,0.8495,0.8500,0.8427,0.7500,0.6500,0.5573,0.5500,0.5500,0.5505,0.5629,0.6371,0.6495,0.6428,0.5573,0.5500,0.5500,0.5505,0.5629,0.6376,0.6624,0.7366,0.7366,0.6629,0.6438,0.5629,0.5376,0.4624,0.4438,0.4433,0.4500,0.4634,0.5438,0.5629,0.6366,0.6433,0.6495,0.6433,0.5640,0.5567,0.5443,0.4702,0.4578,0.4640,0.5433,0.5505,0.5629,0.6371,0.6495,0.6500,0.6495,0.6433,0.6360,0.5567,0.5495,0.5433,0.5433,0.5567,0.6428,0.6572,0.7428,0.7495,0.7371,0.6562,0.5572,0.4578,0.3702,0.3511,0.3505,0.3567,0.3640,0.4500,0.5371,0.5629,0.6433,0.6500,0.6500,0.6500,0.6495,0.6433,0.6428,0.6428,0.6428,0.6366,0.5629,0.5505,0.5505,0.5634,0.6505,0.7495,0.8366,0.8495,0.8495,0.8366,0.7495,0.6562,0.6304,0.5557,0.5443,0.5624,0.6376,0.6629,0.7505,0.8428,0.8567,0.9298,0.8624,0.8371,0.7500,0.6634,0.6438,0.5629,0.5438,0.5366,0.4696,0.5376,0.5629,0.6438,0.6629,0.7366,0.5500,0.5495,0.5443,0.5629,0.6500,0.7371,0.7624,0.8371,0.8495,0.8495,0.8433,0.8355,0.7433,0.6500,0.5634,0.5505,0.5500,0.5500,0.5505,0.5629,0.6371,0.6428,0.5640,0.5572,0.5567,0.5505,0.5505,0.5629,0.6371,0.6495,0.6495,0.6371,0.5624,0.5376,0.4624,0.4376,0.3634,0.3573,0.3634,0.4376,0.4624,0.5376,0.5562,0.5640,0.6433,0.6495,0.6433,0.6366,0.5624,0.5371,0.4567,0.4500,0.4500,0.4500,0.4511,0.4696,0.5505,0.6366,0.6500,0.6567,0.6567,0.6500,0.6371,0.5629,0.5505,0.5572,0.6428,0.6572,0.7433,0.7567,0.7567,0.7433,0.6500,0.5500,0.4505,0.3634,0.3505,0.3500,0.3505,0.3640,0.4567,0.5505,0.6428,0.6500,0.6500,0.6500,0.6433,0.5640,0.5572,0.5572,0.5572,0.5567,0.5505,0.5500,0.5567,0.6371,0.6634,0.7567,0.8433,0.8500,0.8495,0.8360,0.7433,0.6500,0.5634,0.5505,0.5567,0.6366,0.6562,0.7366,0.7567,0.8428,0.8505,0.8562,0.8438,0.7629,0.7366,0.6438,0.5624,0.5371,0.4567,0.4495,0.4443,0.4624,0.5438,0.6355,0.6438,0.6562,0.5500,0.5505,0.5629,0.6438,0.7366,0.7624,0.8371,0.8489,0.8433,0.8366,0.7629,0.7438,0.6634,0.6500,0.6371,0.5634,0.5567,0.5505,0.5500,0.5505,0.5634,0.6428,0.6433,0.6428,0.6366,0.5629,0.5505,0.5505,0.5567,0.5572,0.5573,0.5567,0.5443,0.4696,0.4449,0.3696,0.3511,0.3500,0.3505,0.3634,0.4438,0.4634,0.5433,0.5572,0.6433,0.6567,0.6572,0.6567,0.6438,0.5567,0.4640,0.4438,0.3640,0.3567,0.3572,0.4371,0.4634,0.5567,0.6500,0.7360,0.7427,0.7366,0.6624,0.6371,0.5567,0.5567,0.6366,0.6567,0.7495,0.8360,0.8433,0.8422,0.7500,0.6500,0.5500,0.4505,0.3640,0.3567,0.3505,0.3573,0.4500,0.5500,0.6428,0.6500,0.6500,0.6495,0.6366,0.5567,0.5500,0.5500,0.5500,0.5500,0.5500,0.5505,0.5634,0.6500,0.7433,0.8360,0.8495,0.8495,0.8366,0.7500,0.6629,0.6371,0.5567,0.5500,0.5567,0.6366,0.6562,0.7366,0.7562,0.8366,0.8495,0.8500,0.8428,0.7505,0.6567,0.5640,0.5438,0.4567,0.3645,0.3573,0.3640,0.4438,0.4640,0.5500,0.5640,0.6433,0.5505,0.5629,0.6376,0.6629,0.7495,0.8298,0.8422,0.8360,0.7567,0.7495,0.7366,0.6562,0.6438,0.6495,0.6495,0.6433,0.6366,0.5629,0.5505,0.5505,0.5634,0.6433,0.6500,0.6500,0.6495,0.6366,0.5567,0.5500,0.5500,0.5505,0.5567,0.5572,0.5562,0.5376,0.4624,0.4376,0.3634,0.3567,0.3511,0.3634,0.4438,0.4634,0.5438,0.5640,0.6567,0.7433,0.7500,0.7495,0.7366,0.6495,0.5505,0.4567,0.3640,0.3438,0.2712,0.3562,0.4443,0.5495,0.6495,0.7366,0.7495,0.7489,0.7304,0.6489,0.5572,0.5505,0.5634,0.6505,0.7495,0.8366,0.8562,0.9293,0.8495,0.7500,0.6500,0.5500,0.4567,0.4371,0.3634,0.3640,0.4505,0.5500,0.6427,0.6500,0.6500,0.6433,0.5634,0.5505,0.5500,0.5500,0.5500,0.5500,0.5505,0.5629,0.6376,0.6629,0.7505,0.8427,0.8495,0.8371,0.7562,0.6634,0.6376,0.5624,0.5438,0.5433,0.5500,0.5634,0.6438,0.6629,0.7376,0.7624,0.8371,0.8495,0.8428,0.7500,0.6505,0.5634,0.5433,0.4500,0.3573,0.3500,0.3573,0.4428,0.4572,0.5428,0.5572,0.6428,0.5634,0.6376,0.6624,0.7371,0.7500,0.7567,0.7567,0.7438,0.6634,0.6505,0.6433,0.5640,0.5634,0.6371,0.6495,0.6500,0.6495,0.6371,0.5634,0.5634,0.6371,0.6495,0.6500,0.6500,0.6500,0.6433,0.5634,0.5511,0.5567,0.5634,0.6366,0.6428,0.6366,0.5629,0.5438,0.4634,0.4500,0.4371,0.3696,0.4376,0.4624,0.5376,0.5629,0.6500,0.7433,0.8360,0.8495,0.8433,0.7629,0.7366,0.6428,0.5428,0.4433,0.3500,0.2707,0.3438,0.3702,0.5366,0.6366,0.6624,0.7366,0.7366,0.6629,0.6433,0.5572,0.5500,0.5573,0.6495,0.7371,0.7629,0.8505,0.9422,0.9360,0.8428,0.7428,0.6428,0.5438,0.4624,0.4438,0.4433,0.4567,0.5495,0.6366,0.6495,0.6500,0.6428,0.5572,0.5500,0.5500,0.5500,0.5505,0.5567,0.5634,0.6371,0.6562,0.7366,0.7567,0.8422,0.8371,0.7624,0.7371,0.6500,0.5629,0.5376,0.4634,0.4634,0.5371,0.5562,0.6366,0.6500,0.6629,0.7376,0.7629,0.8433,0.8433,0.7567,0.6634,0.6376,0.5562,0.4572,0.3645,0.3573,0.3640,0.4438,0.4640,0.5500,0.5640,0.6433,0.6438,0.6624,0.7371,0.7495,0.7500,0.7495,0.7371,0.6624,0.6376,0.5629,0.5500,0.5438,0.5500,0.5634,0.6433,0.6500,0.6500,0.6495,0.6433,0.6433,0.6495,0.6500,0.6500,0.6500,0.6500,0.6489,0.6304,0.5629,0.6360,0.6438,0.6562,0.6572,0.6567,0.6505,0.6428,0.5572,0.5433,0.4634,0.4511,0.4634,0.5438,0.5634,0.6500,0.7371,0.7634,0.8562,0.9365,0.9360,0.8500,0.7567,0.6572,0.5572,0.4572,0.3634,0.3443,0.3495,0.3578,0.4562,0.5500,0.6371,0.6562,0.6567,0.6500,0.6366,0.5562,0.5438,0.5562,0.6371,0.6629,0.7505,0.8500,0.9427,0.9433,0.8567,0.7572,0.6572,0.5634,0.5376,0.4634,0.4572,0.4640,0.5443,0.5696,0.6438,0.6500,0.6428,0.5572,0.5500,0.5500,0.5505,0.5629,0.6366,0.6433,0.6500,0.6634,0.7433,0.7572,0.8360,0.7634,0.7438,0.6629,0.6371,0.5500,0.4634,0.4505,0.4505,0.4629,0.5376,0.5624,0.6366,0.6438,0.6629,0.7505,0.8427,0.8495,0.8366,0.7500,0.6629,0.6366,0.5433,0.4562,0.4433,0.4438,0.4624,0.5438,0.6355,0.6438,0.6562,0.6634,0.7371,0.7495,0.7500,0.7495,0.7366,0.6562,0.6366,0.5562,0.5366,0.4573,0.4629,0.5371,0.5567,0.6428,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6500,0.6495,0.6371,0.5629,0.5578,0.6428,0.6567,0.7366,0.7495,0.7500,0.7495,0.7366,0.6567,0.6428,0.5572,0.5500,0.5567,0.6366,0.6562,0.7371,0.7624,0.8438,0.9360,0.9495,0.9495,0.9360,0.8428,0.7433,0.6495,0.5500,0.4500,0.3572,0.3500,0.3567,0.4371,0.4629,0.5500,0.6360,0.6427,0.6360,0.5562,0.5371,0.4696,0.5376,0.5624,0.6438,0.7433,0.8495,0.9427,0.9495,0.9360,0.8428,0.7433,0.6500,0.5634,0.5500,0.5433,0.5438,0.5624,0.6371,0.6495,0.6500,0.6433,0.5640,0.5572,0.5572,0.5634,0.6371,0.6495,0.6505,0.6629,0.7371,0.7500,0.7634,0.8360,0.7572,0.7428,0.6511,0.5696,0.5443,0.4634,0.4505,0.4500,0.4505,0.4634,0.5438,0.5567,0.5640,0.6500,0.7433,0.8360,0.8495,0.8495,0.8360,0.7433,0.6500,0.5629,0.5376,0.4634,0.4634,0.5376,0.5629,0.6438,0.6629,0.7366,0.7438,0.7562,0.7572,0.7567,0.7438,0.6567,0.5640,0.5433,0.4572,0.4433,0.3702,0.4376,0.4629,0.5505,0.6428,0.6505,0.6567,0.6567,0.6505,0.6500,0.6500,0.6495,0.6433,0.6428,0.6366,0.5629,0.5505,0.5567,0.6366,0.6567,0.7495,0.8360,0.8427,0.8366,0.7629,0.7500,0.7366,0.6567,0.6500,0.6505,0.6629,0.7371,0.7562,0.8366,0.8562,0.9366,0.9495,0.9500,0.9427,0.8505,0.7629,0.7366,0.6427,0.5366,0.3702,0.3505,0.3505,0.3629,0.4371,0.4567,0.5428,0.5500,0.5433,0.4640,0.4567,0.4511,0.4629,0.5376,0.5634,0.6634,0.8365,0.9355,0.9427,0.9360,0.8500,0.7629,0.7371,0.6567,0.6433,0.5640,0.5640,0.6438,0.6567,0.6572,0.6572,0.6567,0.6500,0.6433,0.6428,0.6433,0.6500,0.6567,0.6634,0.7371,0.7500,0.7629,0.8371,0.8428,0.7634,0.7438,0.6629,0.6376,0.5624,0.5376,0.4634,0.4573,0.4573,0.4640,0.5433,0.5500,0.5567,0.6371,0.6629,0.7500,0.8360,0.8427,0.8360,0.7495,0.6567,0.6366,0.5562,0.5433,0.5433,0.5562,0.6371,0.6624,0.7371,0.7495,0.7634,0.8366,0.8427,0.8360,0.7495,0.6500,0.5505,0.4567,0.3645,0.3567,0.3511,0.3634,0.4505,0.5500,0.6433,0.6629,0.7366,0.7366,0.6629,0.6505,0.6500,0.6433,0.5640,0.5567,0.5500,0.5433,0.5428,0.5438,0.5629,0.6505,0.7500,0.8427,0.8500,0.8495,0.8433,0.8360,0.7562,0.7433,0.7428,0.7428,0.7433,0.7495,0.7567,0.8360,0.8433,0.8562,0.9360,0.9427,0.9360,0.8562,0.8366,0.7500,0.6567,0.5567,0.4511,0.3634,0.3505,0.3505,0.3567,0.3640,0.4438,0.4567,0.4562,0.4438,0.4428,0.4428,0.4438,0.4624,0.5438,0.6428,0.7428,0.8360,0.8500,0.8562,0.8500,0.8371,0.7624,0.7438,0.7360,0.6567,0.6567,0.7360,0.7428,0.7428,0.7428,0.7428,0.7366,0.6634,0.6572,0.6572,0.6634,0.7366,0.7433,0.7495,0.7567,0.8366,0.8495,0.8495,0.8366,0.7562,0.7371,0.6624,0.6376,0.5629,0.5505,0.5500,0.5495,0.5438,0.5495,0.5500,0.5505,0.5629,0.6371,0.6567,0.7427,0.7500,0.7495,0.7366,0.6562,0.6366,0.5567,0.5500,0.5500,0.5572,0.6495,0.7366,0.7495,0.7500,0.8366,0.8489,0.8500,0.8427,0.7500,0.6500,0.5500,0.4500,0.3573,0.3500,0.3500,0.3573,0.4500,0.5500,0.6489,0.7304,0.7489,0.7495,0.7366,0.6567,0.6495,0.6366,0.5562,0.5371,0.4634,0.4572,0.4572,0.4640,0.5505,0.6500,0.7500,0.8427,0.8500,0.8500,0.8495,0.8366,0.7567,0.7500,0.7500,0.7500,0.7500,0.7500,0.7500,0.7500,0.7500,0.7567,0.8360,0.8433,0.8489,0.8433,0.8360,0.7562,0.7360,0.6433,0.5495,0.4505,0.3634,0.3505,0.3500,0.3505,0.3634,0.4433,0.4438,0.3707,0.3645,0.3645,0.3707,0.4443,0.4634,0.5443,0.5702,0.6572,0.7500,0.8360,0.8427,0.8427,0.8366,0.7634,0.7567,0.7505,0.7505,0.7567,0.7572,0.7572,0.7572,0.7572,0.7562,0.7438,0.7428,0.7428,0.7433,0.7495,0.7500,0.7500,0.7567,0.8360,0.8428,0.8428,0.8360,0.7567,0.7495,0.7371,0.6629,0.6505,0.6500,0.6500,0.6433,0.5640,0.5567,0.5505,0.5500,0.5500,0.5500,0.5567,0.6366,0.6495,0.6500,0.6495,0.6371,0.5629,0.5505,0.5500,0.5500,0.5572,0.6495,0.7366,0.7495,0.7500,0.7634,0.8366,0.8427,0.8360,0.7495,0.6500,0.5500,0.4505,0.3640,0.3573,0.3572,0.3640,0.4505,0.5500,0.6433,0.6634,0.7433,0.7500,0.7427,0.6572,0.6433,0.5634,0.5438,0.4634,0.4505,0.4500,0.4505,0.4634,0.5505,0.6500,0.7495,0.8360,0.8428,0.8427,0.8366,0.7629,0.7505,0.7500,0.7500,0.7500,0.7495,0.7433,0.7366,0.6629,0.6505,0.6505,0.6567,0.6634,0.7371,0.7495,0.7500,0.7500,0.7433,0.6629,0.6366,0.5433,0.4500,0.3640,0.3573,0.3573,0.3640,0.4433,0.4495,0.4433,0.4428,0.4428,0.4433,0.4495,0.4505,0.4629,0.5371,0.5567,0.6500,0.7427,0.7505,0.7629,0.8360,0.8366,0.8422,0.8427,0.8427,0.8422,0.8360,0.8355,0.8355,0.8355,0.8293,0.7562,0.7495,0.7433,0.7428,0.7428,0.7433,0.7495,0.7505,0.7567,0.7572,0.7572,0.7567,0.7505,0.7500,0.7495,0.7433,0.7433,0.7495,0.7495,0.7366,0.6562,0.6371,0.5629,0.5505,0.5433,0.4640,0.4578,0.4702,0.5438,0.5505,0.5567,0.5567,0.5505,0.5500,0.5500,0.5500,0.5567,0.6371,0.6624,0.7371,0.7495,0.7438,0.7562,0.7572,0.7567,0.7438,0.6567,0.5573,0.4640,0.4505,0.4495,0.4433,0.4438,0.4629,0.5505,0.6428,0.6567,0.7360,0.7427,0.7360,0.6567,0.6428,0.5572,0.5433,0.4640,0.4572,0.4573,0.4634,0.5376,0.5629,0.6500,0.7371,0.7562,0.7567,0.7505,0.7495,0.7433,0.7428,0.7433,0.7495,0.7500,0.7433,0.6640,0.6562,0.6376,0.5629,0.5505,0.5500,0.5511,0.5696,0.6443,0.6629,0.7371,0.7489,0.7371,0.6562,0.5634,0.5371,0.4567,0.4500,0.4500,0.4505,0.4567,0.4572,0.4572,0.4572,0.4572,0.4572,0.4572,0.4567,0.4511,0.4567,0.4640,0.5505,0.6428,0.6567,0.7371,0.7562,0.7634,0.8366,0.8427,0.8427,0.8366,0.7634,0.7572,0.7572,0.7572,0.7567,0.7500,0.7371,0.6634,0.6572,0.6572,0.6634,0.7366,0.7428,0.7428,0.7428,0.7428,0.7428,0.7428,0.7433,0.7495,0.7500,0.7567,0.8360,0.8366,0.7624,0.7376,0.6624,0.6371,0.5567,0.5428,0.4567,0.4433,0.4438,0.4562,0.4640,0.5433,0.5500,0.5500,0.5500,0.5500,0.5500,0.5505,0.5629,0.6376,0.6629,0.7433,0.6634,0.7371,0.7495,0.7500,0.7495,0.7366,0.6495,0.5573,0.5495,0.5371,0.4634,0.4634,0.5371,0.5562,0.6366,0.6500,0.6567,0.6572,0.6567,0.6505,0.6433,0.5634,0.5500,0.5433,0.5433,0.5495,0.5505,0.5629,0.6371,0.6500,0.6629,0.7366,0.7366,0.6634,0.6572,0.6572,0.6572,0.6634,0.7371,0.7495,0.7428,0.6572,0.6433,0.5629,0.5376,0.4634,0.4573,0.4634,0.5376,0.5629,0.6438,0.6634,0.7433,0.7495,0.7366,0.6500,0.5634,0.5505,0.5500,0.5500,0.5500,0.5500,0.5500,0.5500,0.5500,0.5500,0.5500,0.5495,0.5371,0.4634,0.4567,0.4511,0.4634,0.5438,0.5634,0.6500,0.7366,0.7500,0.7567,0.7572,0.7567,0.7500,0.7433,0.7428,0.7428,0.7428,0.7428,0.7366,0.6629,0.6505,0.6500,0.6500,0.6505,0.6567,0.6572,0.6572,0.6572,0.6572,0.6572,0.6572,0.6634,0.7366,0.7433,0.7562,0.8366,0.8489,0.8366,0.7562,0.7366,0.6495,0.5567,0.5366,0.4505,0.3707,0.3707,0.4443,0.4634,0.5438,0.5567,0.5572,0.5567,0.5505,0.5500,0.5500,0.5505,0.5634,0.6500,0.7360,0.6438,0.6624,0.7371,0.7495,0.7500,0.7495,0.7366,0.6562,0.6371,0.5629,0.5505,0.5500,0.5500,0.5505,0.5629,0.6366,0.6428,0.6428,0.6433,0.6495,0.6495,0.6371,0.5634,0.5573,0.5634,0.6366,0.6433,0.6500,0.6567,0.6572,0.6572,0.6572,0.6567,0.6500,0.6433,0.6428,0.6433,0.6500,0.6634,0.7433,0.7427,0.6572,0.6428,0.5511,0.4696,0.4511,0.4500,0.4505,0.4634,0.5500,0.6366,0.6562,0.7366,0.7495,0.7495,0.7366,0.6562,0.6433,0.6428,0.6428,0.6428,0.6433,0.6495,0.6500,0.6500,0.6500,0.6495,0.6371,0.5629,0.5500,0.5371,0.4629,0.4511,0.4634,0.5438,0.5640,0.6562,0.7366,0.7428,0.7428,0.7366,0.6629,0.6505,0.6500,0.6500,0.6500,0.6500,0.6495,0.6433,0.6428,0.6428,0.6433,0.6495,0.6500,0.6500,0.6500,0.6495,0.6433,0.6428,0.6428,0.6433,0.6500,0.6629,0.7376,0.7624,0.8366,0.8360,0.7562,0.7366,0.6495,0.5505,0.4634,0.4500,0.4433,0.4438,0.4629,0.5438,0.5634,0.6433,0.6495,0.6371,0.5629,0.5505,0.5500,0.5500,0.5572,0.6433,0.6567,0.5707,0.6443,0.6634,0.7433,0.7505,0.7562,0.7500,0.7371,0.6629,0.6500,0.6433,0.6366,0.5629,0.5505,0.5505,0.5567,0.5572,0.5572,0.5634,0.6371,0.6495,0.6495,0.6438,0.6495,0.6505,0.6567,0.6634,0.7366,0.7428,0.7422,0.7298,0.6557,0.6433,0.6366,0.5634,0.5572,0.5634,0.6371,0.6562,0.7360,0.7360,0.6567,0.6428,0.5567,0.5366,0.4567,0.4500,0.4500,0.4573,0.5438,0.5696,0.6443,0.6634,0.7433,0.7500,0.7495,0.7371,0.6634,0.6572,0.6572,0.6572,0.6634,0.7366,0.7433,0.7495,0.7495,0.7371,0.6629,0.6505,0.6433,0.5629,0.5371,0.4567,0.4567,0.5360,0.5500,0.6360,0.6500,0.6567,0.6572,0.6562,0.6376,0.5634,0.5573,0.5572,0.5572,0.5572,0.5572,0.5572,0.5572,0.5573,0.5640,0.6433,0.6500,0.6500,0.6495,0.6371,0.5634,0.5572,0.5572,0.5572,0.5634,0.6376,0.6624,0.7376,0.7562,0.7567,0.7438,0.6634,0.6433,0.5505,0.4634,0.4511,0.4567,0.4640,0.5505,0.6428,0.6572,0.7428,0.7433,0.6634,0.6438,0.5634,0.5505,0.5500,0.5572,0.6428,0.6500,0.6433,0.6500,0.6634,0.7433,0.7562,0.8231,0.7562,0.7495,0.7433,0.7366,0.6634,0.6562,0.6376,0.5634,0.5567,0.5505,0.5500,0.5500,0.5505,0.5634,0.6433,0.6500,0.6567,0.7360,0.7427,0.7433,0.7500,0.7562,0.7505,0.7433,0.6634,0.6438,0.5634,0.5500,0.5433,0.5428,0.5438,0.5624,0.6371,0.6500,0.6562,0.6500,0.6366,0.5567,0.5433,0.4640,0.4572,0.4573,0.4645,0.5562,0.6371,0.6500,0.6634,0.7433,0.7500,0.7500,0.7495,0.7433,0.7428,0.7428,0.7428,0.7438,0.7562,0.7634,0.8366,0.8366,0.7629,0.7505,0.7495,0.7360,0.6433,0.5495,0.4573,0.4505,0.4567,0.4640,0.5438,0.5629,0.6366,0.6428,0.6366,0.5629,0.5505,0.5500,0.5500,0.5500,0.5500,0.5500,0.5500,0.5505,0.5567,0.5640,0.6433,0.6500,0.6500,0.6438,0.5696,0.5511,0.5500,0.5500,0.5500,0.5505,0.5634,0.6438,0.6634,0.7433,0.7500,0.7428,0.6572,0.6428,0.5567,0.5371,0.4696,0.5371,0.5567,0.6500,0.7428,0.7572,0.8427,0.8427,0.7572,0.7428,0.6505,0.5640,0.5573,0.5640,0.6433,0.6500,0.6572,0.6634,0.7371,0.7495,0.7505,0.7562,0.7505,0.7500,0.7500,0.7495,0.7433,0.7366,0.6629,0.6500,0.6371,0.5634,0.5572,0.5567,0.5505,0.5567,0.6366,0.6495,0.6572,0.7427,0.7500,0.7567,0.8360,0.8366,0.7629,0.7433,0.6567,0.6360,0.5438,0.4634,0.4572,0.4572,0.4634,0.5371,0.5495,0.5567,0.6360,0.6366,0.5629,0.5505,0.5495,0.5433,0.5433,0.5495,0.5567,0.6366,0.6500,0.6629,0.7366,0.7428,0.7428,0.7428,0.7428,0.7427,0.7427,0.7433,0.7495,0.7567,0.8360,0.8433,0.8495,0.8495,0.8433,0.8427,0.8366,0.7562,0.6572,0.5572,0.4640,0.4505,0.4500,0.4505,0.4629,0.5376,0.5562,0.5578,0.5634,0.5578,0.5567,0.5505,0.5500,0.5500,0.5500,0.5500,0.5505,0.5629,0.6366,0.6438,0.6562,0.6572,0.6567,0.6500,0.6371,0.5629,0.5505,0.5500,0.5500,0.5505,0.5634,0.6433,0.6567,0.7360,0.7427,0.7360,0.6567,0.6433,0.5640,0.5567,0.5511,0.5634,0.6505,0.7495,0.8366,0.8562,0.9360,0.9360,0.8567,0.8428,0.7500,0.6573,0.6500,0.6505,0.6567,0.6572,0.7428,0.7433,0.7489,0.7433,0.7428,0.7428,0.7433,0.7495,0.7500,0.7500,0.7500,0.7495,0.7433,0.7366,0.6624,0.6438,0.6428,0.6366,0.5629,0.5511,0.5629,0.6366,0.6500,0.7360,0.7495,0.7567,0.8366,0.8484,0.8304,0.7489,0.6505,0.5567,0.4640,0.4505,0.4500,0.4495,0.4438,0.4495,0.4505,0.4634,0.5433,0.5500,0.5500,0.5505,0.5567,0.5578,0.5702,0.6438,0.6505,0.6567,0.6634,0.7371,0.7427,0.6640,0.6567,0.6505,0.6500,0.6500,0.6505,0.6629,0.7371,0.7562,0.8366,0.8495,0.8500,0.8500,0.8500,0.8500,0.8495,0.8360,0.7428,0.6428,0.5433,0.4567,0.4500,0.4500,0.4505,0.4634,0.5433,0.5567,0.6360,0.6433,0.6428,0.5640,0.5572,0.5567,0.5505,0.5505,0.5629,0.6376,0.6562,0.6634,0.7366,0.7427,0.7366,0.6629,0.6500,0.6371,0.5634,0.5572,0.5572,0.5634,0.6371,0.6495,0.6505,0.6567,0.6572,0.6567,0.6505,0.6495,0.6433,0.6428,0.6433,0.6562,0.7433,0.8360,0.8562,0.9366,0.9495,0.9495,0.9433,0.9360,0.8495,0.7572,0.7495,0.7433,0.7422,0.7360,0.7500,0.7495,0.7371,0.6634,0.6567,0.6505,0.6567,0.7360,0.7433,0.7495,0.7500,0.7505,0.7567,0.7562,0.7376,0.6629,0.6505,0.6495,0.6366,0.5567,0.5505,0.5567,0.5640,0.6500,0.7360,0.7438,0.7624,0.8304,0.7629,0.7433,0.6500,0.5505,0.4634,0.4505,0.4500,0.4438,0.3702,0.3578,0.3634,0.4376,0.4562,0.4640,0.5433,0.5567,0.6366,0.6557,0.7304,0.7489,0.7495,0.7433,0.7433,0.7489,0.7366,0.6562,0.6366,0.5567,0.5500,0.5505,0.5629,0.6376,0.6629,0.7438,0.7634,0.8433,0.8500,0.8500,0.8495,0.8433,0.8428,0.8360,0.7495,0.6500,0.5505,0.4634,0.4505,0.4500,0.4500,0.4573,0.5433,0.5640,0.6500,0.6634,0.7298,0.6562,0.6433,0.6366,0.5629,0.5572,0.6366,0.6562,0.7360,0.7433,0.7495,0.7500,0.7495,0.7366,0.6567,0.6495,0.6433,0.6428,0.6433,0.6500,0.6562,0.6505,0.6500,0.6500,0.6495,0.6438,0.6495,0.6500,0.6505,0.6567,0.6634,0.7371,0.7567,0.8428,0.8567,0.9360,0.9433,0.9495,0.9500,0.9495,0.9366,0.8562,0.8366,0.7567,0.7433,0.6640,0.7500,0.7433,0.6629,0.6438,0.6366,0.5634,0.5640,0.6438,0.6629,0.7371,0.7495,0.7567,0.8360,0.8360,0.7562,0.7366,0.6567,0.6500,0.6427,0.5572,0.5495,0.5433,0.5438,0.5629,0.6438,0.6629,0.7376,0.7557,0.7505,0.7428,0.6505,0.5629,0.5376,0.4634,0.4567,0.4500,0.4366,0.3567,0.3505,0.3634,0.4433,0.4572,0.5433,0.5640,0.6567,0.7438,0.7629,0.8366,0.8360,0.7567,0.7495,0.7371,0.6624,0.6371,0.5500,0.4640,0.4573,0.4640,0.5438,0.5634,0.6500,0.7366,0.7562,0.8360,0.8428,0.8427,0.8366,0.7634,0.7572,0.7562,0.7371,0.6500,0.5629,0.5376,0.4634,0.4573,0.4572,0.4645,0.5562,0.6438,0.7360,0.7500,0.7557,0.7376,0.6629,0.6495,0.6304,0.5629,0.6366,0.6562,0.7366,0.7495,0.7500,0.7495,0.7433,0.7360,0.6567,0.6500,0.6500,0.6500,0.6567,0.7360,0.7360,0.6567,0.6495,0.6433,0.6366,0.5696,0.6371,0.6495,0.6567,0.7360,0.7433,0.7495,0.7567,0.8360,0.8433,0.8495,0.8567,0.9360,0.9433,0.9495,0.9495,0.9365,0.8495,0.7572,0.7428,0.6572,0.7427,0.7355,0.6438,0.5629,0.5500,0.5433,0.5438,0.5629,0.6438,0.6634,0.7433,0.7572,0.8427,0.8427,0.7572,0.7428,0.6572,0.6495,0.6366,0.5562,0.5371,0.4634,0.4634,0.5376,0.5629,0.6438,0.6634,0.7433,0.7500,0.7433,0.6629,0.6376,0.5624,0.5438,0.5366,0.4634,0.4500,0.3640,0.3505,0.3573,0.4433,0.4634,0.5500,0.6433,0.7428,0.8355,0.8433,0.8489,0.8366,0.7562,0.7371,0.6624,0.6371,0.5500,0.4629,0.4443,0.4495,0.4573,0.5433,0.5634,0.6443,0.6696,0.7443,0.7567,0.7567,0.7505,0.7495,0.7433,0.7428,0.7366,0.6629,0.6500,0.6371,0.5629,0.5505,0.5495,0.5433,0.5500,0.6366,0.6629,0.7495,0.8293,0.8293,0.7551,0.7298,0.6433,0.5629,0.5511,0.5629,0.6376,0.6624,0.7366,0.7427,0.7366,0.6634,0.6567,0.6505,0.6500,0.6500,0.6500,0.6567,0.7360,0.7360,0.6562,0.6371,0.5634,0.5567,0.5511,0.5634,0.6433,0.6572,0.7427,0.7500,0.7495,0.7438,0.7495,0.7500,0.7500,0.7572,0.8428,0.8567,0.9360,0.9427,0.9360,0.8495,0.7567,0.7360,0.6500,0.6500,0.6428,0.5567,0.5371,0.4634,0.4573,0.4640,0.5505,0.6428,0.6572,0.7428,0.7567,0.8360,0.8360,0.7562,0.7366,0.6567,0.6433,0.5634,0.5438,0.4634,0.4505,0.4505,0.4634,0.5505,0.6428,0.6572,0.7428,0.7500,0.7495,0.7371,0.6624,0.6376,0.5634,0.5567,0.5500,0.5366,0.4500,0.3640,0.3640,0.4500,0.5371,0.5634,0.6572,0.7567,0.8433,0.8500,0.8433,0.7629,0.7376,0.6624,0.6376,0.5562,0.4640,0.4443,0.3769,0.4443,0.4634,0.5500,0.6371,0.6624,0.7371,0.7495,0.7500,0.7433,0.6640,0.6572,0.6572,0.6572,0.6567,0.6505,0.6500,0.6495,0.6433,0.6428,0.6366,0.5634,0.5640,0.6500,0.7366,0.7500,0.7567,0.7562,0.7371,0.6500,0.5629,0.5438,0.5428,0.5438,0.5624,0.6371,0.6500,0.6562,0.6500,0.6433,0.6428,0.6428,0.6428,0.6428,0.6428,0.6433,0.6495,0.6495,0.6371,0.5629,0.5505,0.5500,0.5500,0.5572,0.6428,0.6567,0.7360,0.7427,0.7366,0.6629,0.6505,0.6500,0.6505,0.6634,0.7438,0.7634,0.8438,0.8567,0.8562,0.8366,0.7438,0.6562,0.5645,0.5500,0.5433,0.4634,0.4500,0.4438,0.4495,0.4573,0.5500,0.6428,0.6572,0.7428,0.7505,0.7567,0.7567,0.7438,0.6634,0.6500,0.6366,0.5562,0.5366,0.4567,0.4500,0.4505,0.4634,0.5505,0.6428,0.6572,0.7428,0.7505,0.7562,0.7500,0.7371,0.6629,0.6500,0.6433,0.6366,0.5624,0.5371,0.4567,0.4505,0.4640,0.5562,0.6438,0.7428,0.8360,0.8495,0.8500,0.8427,0.7505,0.6629,0.6376,0.5624,0.5371,0.4567,0.4495,0.4438,0.4562,0.5371,0.5629,0.6500,0.7366,0.7495,0.7500,0.7495,0.7366,0.6562,0.6433,0.6428,0.6428,0.6433,0.6495,0.6500,0.6505,0.6567,0.6572,0.6562,0.6438,0.6438,0.6629,0.7433,0.7500,0.7495,0.7366,0.6500,0.5629,0.5376,0.4629,0.4505,0.4567,0.5366,0.5500,0.5629,0.6304,0.5629,0.5505,0.5500,0.5500,0.5500,0.5505,0.5567,0.5572,0.5572,0.5572,0.5562,0.5438,0.5428,0.5433,0.5495,0.5567,0.6366,0.6500,0.6567,0.6572,0.6562,0.6376,0.5634,0.5573,0.5634,0.6371,0.6562,0.7371,0.7624,0.8366,0.8366,0.7562,0.6634,0.6366,0.5500,0.4567,0.4500,0.4371,0.3634,0.3640,0.4438,0.4640,0.5567,0.6438,0.6634,0.7438,0.7567,0.7572,0.7567,0.7433,0.6572,0.6433,0.5634,0.5443,0.4696,0.4511,0.4505,0.4629,0.5376,0.5629,0.6438,0.6634,0.7438,0.7629,0.8298,0.7567,0.7495,0.7433,0.7366,0.6634,0.6562,0.6376,0.5624,0.5438,0.5428,0.5500,0.6360,0.6567,0.7500,0.8427,0.8500,0.8495,0.8360,0.7433,0.6500,0.5634,0.5438,0.4634,0.4505,0.4500,0.4500,0.4573,0.5495,0.6366,0.6567,0.7427,0.7500,0.7495,0.7371,0.6624,0.6376,0.5634,0.5572,0.5572,0.5634,0.6371,0.6500,0.6629,0.7366,0.7428,0.7366,0.6634,0.6634,0.7371,0.7495,0.7495,0.7371,0.6562,0.5634,0.5376,0.4624,0.4376,0.3634,0.3640,0.4433,0.4567,0.5366,0.5489,0.5371,0.4634,0.4573,0.4572,0.4573,0.4634,0.5366,0.5428,0.5428,0.5428,0.5366,0.4634,0.4573,0.4640,0.5433,0.5505,0.5634,0.6433,0.6500,0.6500,0.6433,0.5634,0.5505,0.5500,0.5505,0.5567,0.5645,0.6562,0.7376,0.7557,0.7500,0.7360,0.6438,0.5562,0.4645,0.4366,0.3634,0.3567,0.3505,0.3578,0.4562,0.5500,0.6371,0.6624,0.7376,0.7624,0.8366,0.8427,0.8366,0.7562,0.6640,0.6438,0.5634,0.5500,0.5371,0.4634,0.4634,0.5376,0.5629,0.6438,0.6629,0.7376,0.7624,0.8366,0.8360,0.7567,0.7495,0.7433,0.7422,0.7366,0.7355,0.6562,0.6371,0.5634,0.5572,0.5640,0.6433,0.6567,0.7433,0.8355,0.8427,0.8366,0.7562,0.6640,0.6433,0.5572,0.5428,0.4573,0.4500,0.4500,0.4505,0.4634,0.5505,0.6427,0.6567,0.7360,0.7427,0.7360,0.6562,0.6366,0.5562,0.5433,0.5428,0.5433,0.5500,0.5634,0.6500,0.7366,0.7500,0.7567,0.7562,0.7438,0.7433,0.7495,0.7500,0.7433,0.6629,0.6371,0.5500,0.4634,0.4438,0.3634,0.3500,0.3443,0.3562,0.3640,0.4433,0.4505,0.4562,0.4505,0.4500,0.4500,0.4500,0.4505,0.4567,0.4572,0.4572,0.4572,0.4567,0.4511,0.4567,0.4640,0.5433,0.5500,0.5573,0.6428,0.6500,0.6500,0.6433,0.5634,0.5505,0.5500,0.5500,0.5500,0.5573,0.6433,0.6629,0.7304,0.6629,0.6438,0.5629,0.5371,0.4567,0.3567,0.3505,0.3500,0.3505,0.3702,0.5366,0.6366,0.6624,0.7371,0.7562,0.8366,0.8495,0.8500,0.8495,0.8366,0.7500,0.6629,0.6376,0.5629,0.5500,0.5438,0.5500,0.5634,0.6500,0.7366,0.7500,0.7629,0.8366,0.8366,0.7624,0.7438,0.7366,0.6634,0.6572,0.6634,0.7298,0.6572,0.6557,0.6438,0.6428,0.6433,0.6495,0.6505,0.6634,0.7433,0.7500,0.7500,0.7428,0.6572,0.6433,0.5634,0.5438,0.4634,0.4505,0.4500,0.4567,0.5366,0.5562,0.6360,0.6433,0.6495,0.6500,0.6428,0.5572,0.5433,0.4640,0.4572,0.4572,0.4640,0.5433,0.5573,0.6500,0.7433,0.7629,0.8366,0.8366,0.7629,0.7505,0.7500,0.7495,0.7366,0.6505,0.5696,0.5443,0.4634,0.4433,0.3572,0.3433,0.2702,0.3371,0.3500,0.3567,0.3640,0.4433,0.4500,0.4505,0.4567,0.4572,0.4572,0.4572,0.4572,0.4572,0.4572,0.4573,0.4634,0.5366,0.5433,0.5500,0.5567,0.5640,0.6433,0.6500,0.6500,0.6495,0.6371,0.5634,0.5573,0.5572,0.5572,0.5640,0.6433,0.6505,0.6562,0.6438,0.5634,0.5438,0.4634,0.4505,0.3567,0.3505,0.3505,0.3629,0.4449,0.5562,0.6562,0.7371,0.7495,0.7567,0.8366,0.8495,0.8500,0.8500,0.8495,0.8360,0.7438,0.6624,0.6376,0.5634,0.5634,0.6371,0.6562,0.7371,0.7624,0.8366,0.8427,0.8366,0.7624,0.7376,0.6629,0.6500,0.6433,0.6433,0.6500,0.6562,0.6572,0.7298,0.6634,0.6567,0.6505,0.6495,0.6433,0.6433,0.6495,0.6505,0.6629,0.7304,0.6629,0.6500,0.6366,0.5562,0.5371,0.4634,0.4573,0.4640,0.5433,0.5505,0.5567,0.5567,0.5505,0.5500,0.5428,0.4578,0.4562,0.4505,0.4500,0.4500,0.4573,0.5433,0.5640,0.6567,0.7500,0.8366,0.8495,0.8489,0.8304,0.7562,0.7495,0.7371,0.6629,0.6500,0.6366,0.5562,0.5371,0.4562,0.3640,0.3438,0.2645,0.2702,0.3438,0.3505,0.3634,0.4438,0.4567,0.4640,0.5433,0.5495,0.5433,0.5428,0.5428,0.5428,0.5428,0.5433,0.5500,0.5567,0.5572,0.5634,0.6366,0.6433,0.6495,0.6500,0.6500,0.6505,0.6562,0.6505,0.6500,0.6495,0.6433,0.6433,0.6495,0.6500,0.6495,0.6366,0.5567,0.5433,0.4634,0.4505,0.4433,0.3640,0.3634,0.4376,0.4696,0.6366,0.7360,0.7495,0.7500,0.7505,0.7629,0.8371,0.8495,0.8500,0.8500,0.8428,0.7567,0.7366,0.6562,0.6433,0.6433,0.6562,0.7366,0.7562,0.8360,0.8427,0.8366,0.7624,0.7371,0.6562,0.6371,0.5634,0.5573,0.5634,0.6371,0.6500,0.6634,0.7428,0.7433,0.7366,0.6629,0.6438,0.5640,0.5567,0.5511,0.5629,0.6376,0.6624,0.7304,0.6629,0.6438,0.5634,0.5500,0.5433,0.5428,0.5433,0.5495,0.5500,0.5500,0.5433,0.4634,0.4505,0.4433,0.3707,0.4433,0.4500,0.4505,0.4567,0.4640,0.5500,0.6433,0.7360,0.7567,0.8422,0.8433,0.8366,0.7624,0.7438,0.7366,0.6629,0.6505,0.6500,0.6433,0.5640,0.5562,0.5371,0.4500,0.3629,0.3438,0.3433,0.3500,0.3629,0.4376,0.4629,0.5433,0.5572,0.6427,0.6433,0.5640,0.5572,0.5572,0.5572,0.5572,0.5634,0.6366,0.6428,0.6428,0.6433,0.6495,0.6500,0.6495,0.6438,0.6495,0.6567,0.7360,0.7427,0.7427,0.7366,0.6629,0.6505,0.6500,0.6495,0.6371,0.5629,0.5505,0.5495,0.5371,0.4634,0.5360,0.4562,0.4443,0.4624,0.5443,0.6489,0.7366,0.7495,0.7495,0.7433,0.7438,0.7624,0.8371,0.8495,0.8500,0.8428,0.7567,0.7366,0.6562,0.6433,0.6433,0.6562,0.7366,0.7562,0.8298,0.7629,0.7500,0.7366,0.6500,0.5634,0.5500,0.5438,0.5495,0.5511,0.5696,0.6505,0.7371,0.7562,0.7572,0.7562,0.7371,0.6495,0.5573,0.5433,0.4702,0.5376,0.5629,0.6505,0.7422,0.7366,0.6562,0.6366,0.5567,0.5500,0.5505,0.5567,0.5572,0.5572,0.5567,0.5433,0.4511,0.3702,0.3573,0.3578,0.4428,0.4505,0.4629,0.5366,0.5438,0.5629,0.6505,0.7428,0.7567,0.8298,0.7629,0.7500,0.7371,0.6634,0.6567,0.6505,0.6500,0.6500,0.6495,0.6433,0.6360,0.5562,0.5360,0.4438,0.3629,0.3511,0.3629,0.4376,0.4629,0.5500,0.6366,0.6562,0.7360,0.7360,0.6562,0.6433,0.6428,0.6428,0.6428,0.6433,0.6500,0.6567,0.6572,0.6567,0.6505,0.6495,0.6371,0.5702,0.6433,0.6572,0.7427,0.7500,0.7500,0.7489,0.7304,0.6557,0.6433,0.6366,0.5629,0.5511,0.5567,0.5572,0.5562,0.5438,0.5562,0.5376,0.4696,0.5371,0.5562,0.6371,0.6624,0.7366,0.7366,0.6634,0.6634,0.7371,0.7562,0.8360,0.8427,0.8355,0.7438,0.6624,0.6371,0.5567,0.5567,0.6366,0.6562,0.7366,0.7489,0.7366,0.6567,0.6428,0.5567,0.5371,0.4640,0.4702,0.5443,0.5629,0.6371,0.6567,0.7495,0.8360,0.8428,0.8366,0.7562,0.6572,0.5640,0.5438,0.4645,0.4702,0.5511,0.6495,0.7360,0.7360,0.6562,0.6366,0.5567,0.5500,0.5567,0.6360,0.6433,0.6489,0.6371,0.5562,0.4634,0.4376,0.3635,0.3640,0.4438,0.4629,0.5376,0.5562,0.5634,0.6376,0.6629,0.7433,0.7505,0.7557,0.7376,0.6634,0.6562,0.6438,0.6428,0.6428,0.6433,0.6495,0.6500,0.6500,0.6428,0.5572,0.5428,0.4567,0.4371,0.3696,0.4376,0.4624,0.5438,0.6366,0.6624,0.7376,0.7557,0.7500,0.7366,0.6567,0.6500,0.6500,0.6500,0.6500,0.6567,0.7360,0.7427,0.7360,0.6567,0.6433,0.5634,0.5573,0.6366,0.6562,0.7360,0.7428,0.7427,0.7366,0.6624,0.6376,0.5634,0.5567,0.5505,0.5567,0.6360,0.6427,0.6366,0.5634,0.6366,0.5624,0.5443,0.5495,0.5505,0.5629,0.6371,0.6495,0.6495,0.6433,0.6433,0.6500,0.6634,0.7433,0.7500,0.7433,0.6629,0.6371,0.5500,0.4640,0.4640,0.5438,0.5634,0.6433,0.6500,0.6433,0.5634,0.5438,0.4640,0.4567,0.4572,0.5366,0.5562,0.6366,0.6500,0.6640,0.7567,0.8438,0.8567,0.8562,0.8366,0.7428,0.6433,0.5562,0.5433,0.5433,0.5567,0.6433,0.6567,0.6567,0.6438,0.5634,0.5505,0.5505,0.5634,0.6438,0.6629,0.7304,0.6624,0.6371,0.5500,0.4634,0.4500,0.4443,0.4624,0.5376,0.5624,0.6366,0.6438,0.6624,0.7371,0.7495,0.7500,0.7433,0.6634,0.6500,0.6371,0.5634,0.5572,0.5572,0.5640,0.6433,0.6500,0.6500,0.6428,0.5572,0.5428,0.4572,0.4495,0.4438,0.4562,0.5371,0.5634,0.6562,0.7376,0.7624,0.8298,0.7567,0.7428,0.6572,0.6500,0.6500,0.6500,0.6500,0.6567,0.7366,0.7489,0.7366,0.6567,0.6428,0.5572,0.5505,0.5629,0.6371,0.6500,0.6562,0.6505,0.6495,0.6366,0.5562,0.5433,0.5433,0.5495,0.5572,0.6428,0.6500,0.6495,0.6433,0.6495,0.6366,0.5567,0.5500,0.5500,0.5505,0.5567,0.5573,0.5573,0.5572,0.5573,0.5640,0.6438,0.6567,0.6573,0.6567,0.6438,0.5567,0.4640,0.4505,0.4505,0.4634,0.5438,0.5567,0.5573,0.5567,0.5438,0.4634,0.4505,0.4500,0.4572,0.5428,0.5572,0.6428,0.6567,0.7433,0.8360,0.8562,0.9360,0.9360,0.8495,0.7500,0.6500,0.5572,0.5500,0.5500,0.5572,0.6428,0.6500,0.6500,0.6428,0.5572,0.5500,0.5567,0.6366,0.6562,0.7366,0.7489,0.7366,0.6562,0.6360,0.5500,0.5360,0.4634,0.5366,0.5562,0.6366,0.6495,0.6567,0.7366,0.7495,0.7500,0.7500,0.7428,0.6572,0.6433,0.5634,0.5505,0.5500,0.5500,0.5572,0.6428,0.6500,0.6500,0.6428,0.5572,0.5428,0.4572,0.4500,0.4500,0.4572,0.5495,0.6433,0.7360,0.7562,0.8366,0.8422,0.7572,0.7428,0.6572,0.6500,0.6500,0.6500,0.6500,0.6505,0.6634,0.7366,0.6634,0.6505,0.6428,0.5572,0.5500,0.5505,0.5567,0.5640,0.6366,0.5640,0.5573,0.5500,0.4645,0.4573,0.4640,0.5433,0.5572,0.6428,0.6500,0.6500,0.6500];
const HEIGHTMAP_RES = 128;
const TERRAIN_SIZE = 20;
const HEIGHT_SCALE = 4.0;
const WATER_LEVEL = 0.22;

function heightAt(x, z) {
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
}

const colorTex = loadB64Texture(COLORMAP_B64);
const terrainGeo = new THREE.PlaneGeometry(TERRAIN_SIZE, TERRAIN_SIZE, HEIGHTMAP_RES - 1, HEIGHTMAP_RES - 1);
terrainGeo.rotateX(-Math.PI / 2);
const tPos = terrainGeo.attributes.position;
for (let i = 0; i < tPos.count; i++) {
  tPos.setY(i, heightAt(tPos.getX(i), tPos.getZ(i)));
}
tPos.needsUpdate = true;
terrainGeo.computeVertexNormals();

const terrainMat = new THREE.MeshStandardMaterial({
  map: colorTex,
  flatShading: true,
  roughness: 0.92,
  metalness: 0.0,
});

const terrain = new THREE.Mesh(terrainGeo, terrainMat);
terrain.receiveShadow = true;
terrain.castShadow = true;
worldGroup.add(terrain);

if (WATER_LEVEL != null) {
  const water = new THREE.Mesh(
    new THREE.PlaneGeometry(TERRAIN_SIZE, TERRAIN_SIZE, 1, 1),
    new THREE.MeshStandardMaterial({
      color: 0x3a7ebd,
      transparent: true,
      opacity: 0.62,
      roughness: 0.2,
      metalness: 0.1,
    })
  );
  water.rotation.x = -Math.PI / 2;
  water.position.y = WATER_LEVEL * HEIGHT_SCALE;
  worldGroup.add(water);
}


// ============ PROP: grass_tuft ============
const propMaterial_grass_tuft = (function() {
  const propShader = {
    uniforms: {
      uColorA: { value: new THREE.Vector3(0.13, 0.28, 0.1) },
      uColorB: { value: new THREE.Vector3(0.34, 0.55, 0.19) },
      uColorTip: { value: new THREE.Vector3(0.72, 0.78, 0.34) },
      uTime: { value: 0 }
    },
    vertexShader: "varying vec2 vUv;\nvarying vec3 vNormal;\nvarying vec3 vPosition;\nvarying vec3 vWorldPos;\nvoid main() {\n  vUv = uv;\n  vNormal = normalize(normalMatrix * normal);\n  vPosition = position;\n  vec4 wp = modelMatrix * vec4(position, 1.0);\n  vWorldPos = wp.xyz;\n  gl_Position = projectionMatrix * viewMatrix * wp;\n}",
    fragmentShader: "uniform float uTime;\nuniform vec3 uColorA;\nuniform vec3 uColorB;\nuniform vec3 uColorTip;\nvarying vec2 vUv;\nvarying vec3 vNormal;\nvarying vec3 vPosition;\nvarying vec3 vWorldPos;\n\nfloat hash(vec2 p) {\n  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);\n}\n\nfloat noise(vec2 p) {\n  vec2 i = floor(p);\n  vec2 f = fract(p);\n  vec2 u = f * f * (3.0 - 2.0 * f);\n  float a = hash(i);\n  float b = hash(i + vec2(1.0, 0.0));\n  float c = hash(i + vec2(0.0, 1.0));\n  float d = hash(i + vec2(1.0, 1.0));\n  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);\n}\n\nvoid main() {\n  vec3 n = normalize(vNormal);\n  vec3 viewDir = normalize(cameraPosition - vWorldPos);\n  float fres = pow(1.0 - max(dot(n, viewDir), 0.0), 2.5);\n\n  vec2 wuv = vUv * vec2(7.0, 2.5);\n  vec2 warp = vec2(noise(wuv + uTime * 0.13), noise(wuv.yx - uTime * 0.09));\n  float streaks = noise(wuv + warp * 1.7);\n  float blade = smoothstep(0.30, 0.85, streaks);\n\n  float h = clamp(vPosition.y * 1.9, 0.0, 1.0);\n\n  vec3 L = normalize(vec3(0.35, 0.90, 0.25));\n  float lam = 0.52 + 0.48 * max(dot(n, L), 0.0);\n\n  vec3 col = mix(uColorA, uColorB, smoothstep(0.0, 0.58, h));\n  col = mix(col, uColorTip, smoothstep(0.58, 1.0, h) * (0.55 + 0.45 * blade));\n  col *= lam;\n  col += fres * vec3(0.10, 0.18, 0.08);\n\n  float sway = sin(uTime * 1.9 + vWorldPos.x * 3.1 + vWorldPos.z * 2.4);\n  col += 0.035 * sway * h;\n  col += 0.05 * (blade - 0.5) * (1.0 - h);\n\n  float levels = 6.0;\n  float dith = (hash(floor(gl_FragCoord.xy)) - 0.5) * (1.0 / levels);\n  col = floor((col + dith) * levels + 0.5) / levels;\n  col = clamp(col, 0.0, 1.0);\n\n  gl_FragColor = vec4(col, 1.0);\n}",
  };

  const mat = compileShader(propShader, propFallbackColor(propShader.uniforms));
  mat.side = THREE.DoubleSide;

  const propGeometry = {
    "primitives": [
        {
            "type": "cone",
            "params": {
                "radius": 0.055,
                "height": 0.46,
                "segments": 6
            },
            "position": [
                0.0,
                0.23,
                0.0
            ],
            "rotation": [
                0.0,
                0.0,
                0.0
            ],
            "scale": 1
        },
        {
            "type": "cone",
            "params": {
                "radius": 0.042,
                "height": 0.38,
                "segments": 6
            },
            "position": [
                0.07,
                0.19,
                0.03
            ],
            "rotation": [
                0.16,
                0.0,
                0.26
            ],
            "scale": 1
        },
        {
            "type": "cone",
            "params": {
                "radius": 0.045,
                "height": 0.42,
                "segments": 6
            },
            "position": [
                -0.06,
                0.21,
                -0.04
            ],
            "rotation": [
                -0.14,
                0.0,
                -0.23
            ],
            "scale": 1
        },
        {
            "type": "cone",
            "params": {
                "radius": 0.034,
                "height": 0.3,
                "segments": 6
            },
            "position": [
                0.02,
                0.15,
                0.09
            ],
            "rotation": [
                0.3,
                0.0,
                -0.1
            ],
            "scale": 1
        },
        {
            "type": "cone",
            "params": {
                "radius": 0.03,
                "height": 0.26,
                "segments": 6
            },
            "position": [
                -0.03,
                0.13,
                -0.09
            ],
            "rotation": [
                -0.28,
                0.0,
                0.12
            ],
            "scale": 1
        }
    ]
};
  const propInstances = [
    {
        "position": [
            -4.972474271537296,
            3.051543968718593,
            -1.7178620074085522
        ],
        "rotation": [
            0.0,
            309.7366156364515,
            0.0
        ],
        "scale": 1.3976562465310183
    },
    {
        "position": [
            -1.05031635976352,
            2.991802464790811,
            1.130169064636533
        ],
        "rotation": [
            0.0,
            52.38614712472263,
            0.0
        ],
        "scale": 1.287856513411567
    },
    {
        "position": [
            2.694752088935104,
            3.0077667575841884,
            3.65583626449369
        ],
        "rotation": [
            0.0,
            62.574237377254356,
            0.0
        ],
        "scale": 0.9212193036906322
    },
    {
        "position": [
            6.335029077830537,
            2.2001899021432347,
            -8.721283050364686
        ],
        "rotation": [
            0.0,
            217.22861089076918,
            0.0
        ],
        "scale": 1.060321953699224
    },
    {
        "position": [
            0.19709686123300152,
            2.72549225276086,
            0.5736416087482024
        ],
        "rotation": [
            0.0,
            139.2545777193341,
            0.0
        ],
        "scale": 0.8963301488426675
    },
    {
        "position": [
            0.039041702060300665,
            3.203437330600532,
            0.7401384581251893
        ],
        "rotation": [
            0.0,
            211.85637198055122,
            0.0
        ],
        "scale": 1.034632640886382
    },
    {
        "position": [
            3.8172124829183325,
            1.4411425128725441,
            1.4438354514990657
        ],
        "rotation": [
            0.0,
            276.25649478515857,
            0.0
        ],
        "scale": 1.033549494972087
    },
    {
        "position": [
            1.8251873635720202,
            2.370301072294497,
            -3.473249199295098
        ],
        "rotation": [
            0.0,
            103.58809846016467,
            0.0
        ],
        "scale": 0.767295295468953
    },
    {
        "position": [
            3.3489938927717233,
            2.644101194010154,
            -2.3968404219382933
        ],
        "rotation": [
            0.0,
            35.99086463396699,
            0.0
        ],
        "scale": 1.2703326535496986
    },
    {
        "position": [
            1.7171641471481074,
            1.8010658713699221,
            7.926382048555865
        ],
        "rotation": [
            0.0,
            293.33407807676826,
            0.0
        ],
        "scale": 1.0862486161231413
    },
    {
        "position": [
            -7.226035136007442,
            2.6187701326592627,
            -4.692107740587264
        ],
        "rotation": [
            0.0,
            272.3350277886706,
            0.0
        ],
        "scale": 1.0916842272583818
    },
    {
        "position": [
            -4.176884866280332,
            1.8134457439988076,
            -3.3000437604053
        ],
        "rotation": [
            0.0,
            330.8379734598952,
            0.0
        ],
        "scale": 1.181569891439727
    },
    {
        "position": [
            -0.5181698033484157,
            2.1057743059084304,
            4.607229139630677
        ],
        "rotation": [
            0.0,
            263.02172354312324,
            0.0
        ],
        "scale": 0.8390152223815415
    },
    {
        "position": [
            8.197136478222582,
            2.9582057414446994,
            -5.738561384600355
        ],
        "rotation": [
            0.0,
            22.04398626977809,
            0.0
        ],
        "scale": 0.9141845154770288
    },
    {
        "position": [
            -3.235613335176293,
            2.2330795749102226,
            5.473852909045162
        ],
        "rotation": [
            0.0,
            353.08469345246823,
            0.0
        ],
        "scale": 0.8672789209403375
    },
    {
        "position": [
            -0.9022515968979476,
            2.473740940413972,
            8.798096281977188
        ],
        "rotation": [
            0.0,
            37.46319766010019,
            0.0
        ],
        "scale": 1.0309718262778296
    },
    {
        "position": [
            -1.7107363973570466,
            3.0880699776488982,
            0.7550754369945398
        ],
        "rotation": [
            0.0,
            253.8722831175675,
            0.0
        ],
        "scale": 1.1755706861486481
    },
    {
        "position": [
            -7.692814274309222,
            2.6315800747330007,
            0.831782895632406
        ],
        "rotation": [
            0.0,
            197.17781588765337,
            0.0
        ],
        "scale": 0.9398386447759028
    },
    {
        "position": [
            7.239914302016096,
            2.5475240002523822,
            -1.8054021602459756
        ],
        "rotation": [
            0.0,
            56.30411512456915,
            0.0
        ],
        "scale": 1.3091717800641014
    },
    {
        "position": [
            3.054435426282488,
            2.6812937936541115,
            2.632275531550949
        ],
        "rotation": [
            0.0,
            189.07797892108707,
            0.0
        ],
        "scale": 0.7323795280875396
    },
    {
        "position": [
            -5.680773323823698,
            2.9313604526128163,
            -1.8847480439150335
        ],
        "rotation": [
            0.0,
            70.46610927283255,
            0.0
        ],
        "scale": 0.8254685830544871
    },
    {
        "position": [
            3.6021700091718074,
            2.610841212268944,
            3.8606003105927886
        ],
        "rotation": [
            0.0,
            228.2797719803618,
            0.0
        ],
        "scale": 0.7401790585006174
    },
    {
        "position": [
            0.9640457609346775,
            2.3005082100321044,
            1.5324964486042667
        ],
        "rotation": [
            0.0,
            43.55463614186618,
            0.0
        ],
        "scale": 1.1331220420417123
    },
    {
        "position": [
            7.124688626826785,
            2.568496515608844,
            8.137937963699077
        ],
        "rotation": [
            0.0,
            14.73864530029211,
            0.0
        ],
        "scale": 1.3450632389222754
    },
    {
        "position": [
            4.8635609146227665,
            3.127308563192218,
            6.559884550352079
        ],
        "rotation": [
            0.0,
            354.8044164455291,
            0.0
        ],
        "scale": 1.3046407361118668
    },
    {
        "position": [
            4.937423545372765,
            2.4716855232584294,
            -7.069047592914728
        ],
        "rotation": [
            0.0,
            19.321640482205588,
            0.0
        ],
        "scale": 1.2151470776286852
    },
    {
        "position": [
            -6.090475940476667,
            2.2178054005256067,
            6.327676730131193
        ],
        "rotation": [
            0.0,
            281.4416112755152,
            0.0
        ],
        "scale": 1.3599282402399853
    },
    {
        "position": [
            0.6838552673030396,
            2.047510178836304,
            -3.486559980015185
        ],
        "rotation": [
            0.0,
            60.746089824098156,
            0.0
        ],
        "scale": 0.8801027215132942
    },
    {
        "position": [
            5.437816650735021,
            3.3610364179850727,
            5.68807937034849
        ],
        "rotation": [
            0.0,
            264.67372198001203,
            0.0
        ],
        "scale": 1.2329650786581445
    },
    {
        "position": [
            5.46485395761553,
            2.6708605681142252,
            -6.91188837564083
        ],
        "rotation": [
            0.0,
            343.11160628909875,
            0.0
        ],
        "scale": 1.2279988638408978
    },
    {
        "position": [
            0.4417376731726925,
            2.858644507605591,
            -8.785259772598183
        ],
        "rotation": [
            0.0,
            150.23570732327045,
            0.0
        ],
        "scale": 0.9794667475762957
    },
    {
        "position": [
            7.089795800442072,
            1.4603869401049223,
            2.2701420541438395
        ],
        "rotation": [
            0.0,
            81.8360442508003,
            0.0
        ],
        "scale": 1.2855093652675655
    },
    {
        "position": [
            -6.395979106099412,
            1.0672908348437904,
            -1.9764753354523066
        ],
        "rotation": [
            0.0,
            108.80974547158694,
            0.0
        ],
        "scale": 0.9171807929813587
    },
    {
        "position": [
            -3.0515423980218364,
            3.4519695995611315,
            6.176474804485521
        ],
        "rotation": [
            0.0,
            161.18854763338157,
            0.0
        ],
        "scale": 0.8261582342572072
    },
    {
        "position": [
            1.4465174151096036,
            1.993590772396261,
            -0.9783985289423853
        ],
        "rotation": [
            0.0,
            358.8416492880915,
            0.0
        ],
        "scale": 1.3076446070189456
    },
    {
        "position": [
            -4.830007738042772,
            2.423973960444934,
            -6.100699837690459
        ],
        "rotation": [
            0.0,
            358.6015080277302,
            0.0
        ],
        "scale": 1.065840372219843
    },
    {
        "position": [
            0.7777298344648216,
            2.590602490719821,
            1.3430525430540552
        ],
        "rotation": [
            0.0,
            117.95275864201899,
            0.0
        ],
        "scale": 1.3939503614298254
    },
    {
        "position": [
            -4.672231663132357,
            3.312584161344741,
            -4.042109465207758
        ],
        "rotation": [
            0.0,
            211.2554600339186,
            0.0
        ],
        "scale": 1.0248738068264114
    },
    {
        "position": [
            -3.95483417268642,
            2.206165181652903,
            0.054177453818017085
        ],
        "rotation": [
            0.0,
            313.87514119512366,
            0.0
        ],
        "scale": 1.3873659845818858
    },
    {
        "position": [
            -3.6459805251173947,
            2.7358969136485563,
            4.745393728535136
        ],
        "rotation": [
            0.0,
            192.643937347168,
            0.0
        ],
        "scale": 0.7023179138985038
    }
];

  for (const inst of propInstances) {
    const propGroup = new THREE.Group();
    for (const prim of propGeometry.primitives || []) {
      const geo = buildPrimitive(prim);
      if (!geo) continue;
      const mesh = new THREE.Mesh(geo, mat);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      applyTransform(mesh, prim);
      propGroup.add(mesh);
    }
    if (inst.position) propGroup.position.set(...inst.position);
    if (inst.rotation) propGroup.rotation.set(
      inst.rotation[0] * Math.PI / 180,
      inst.rotation[1] * Math.PI / 180,
      inst.rotation[2] * Math.PI / 180
    );
    if (inst.scale != null) {
      if (Array.isArray(inst.scale)) propGroup.scale.set(...inst.scale);
      else propGroup.scale.setScalar(inst.scale);
    }
    worldGroup.add(propGroup);
  }

  return mat;
})();


// ============ PROP: young_pine ============
const propMaterial_young_pine = (function() {
  const propShader = {
    uniforms: {
      uColorA: { value: new THREE.Vector3(0.16, 0.42, 0.18) },
      uColorB: { value: new THREE.Vector3(0.35, 0.58, 0.22) },
      uTime: { value: 0 }
    },
    vertexShader: "uniform float uTime;\nvarying vec2 vUv;\nvarying vec3 vNormal;\nvarying vec3 vPosition;\nvarying vec3 vWorldPos;\nvoid main() {\n  vUv = uv;\n  vNormal = normalize(normalMatrix * normal);\n  vPosition = position;\n  vec3 p = position;\n  float sway = sin(uTime * 1.6 + wp_seed()) * 0.015 * max(p.y, 0.0);\n  p.x += sway;\n  vec4 wp = modelMatrix * vec4(p, 1.0);\n  vWorldPos = wp.xyz;\n  gl_Position = projectionMatrix * viewMatrix * wp;\n}",
    fragmentShader: "uniform float uTime;\nvarying vec2 vUv;\nvarying vec3 vNormal;\nvarying vec3 vPosition;\nvarying vec3 vWorldPos;\nfloat hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }\nvoid main() {\n  vec3 lush = vec3(0.16, 0.42, 0.18);\n  vec3 deep = vec3(0.06, 0.22, 0.10);\n  vec3 tip  = vec3(0.35, 0.58, 0.22);\n  vec3 bark = vec3(0.32, 0.22, 0.12);\n  float h = clamp(vPosition.y / 2.5, 0.0, 1.0);\n  float needles = smoothstep(0.35, 0.9, fract(vPosition.y * 6.0 + hash(floor(vWorldPos.xz * 8.0)) * 2.0));\n  vec3 base = mix(bark, mix(deep, lush, h), step(0.35, vPosition.y));\n  base = mix(base, tip, needles * 0.45 * step(0.35, vPosition.y));\n  vec3 L = normalize(vec3(0.5, 0.8, 0.35));\n  float diff = max(dot(normalize(vNormal), L), 0.0);\n  float shade = 0.35 + 0.65 * diff;\n  vec3 col = base * shade;\n  float dith = hash(floor(gl_FragCoord.xy * 0.5)) * 0.08 - 0.04;\n  col += dith;\n  col = floor(col * 12.0) / 12.0;\n  float rim = pow(1.0 - abs(dot(normalize(vNormal), vec3(0.0, 0.0, 1.0))), 2.0);\n  col += rim * vec3(0.03, 0.06, 0.02);\n  gl_FragColor = vec4(col, 1.0);\n}",
  };

  const mat = compileShader(propShader, propFallbackColor(propShader.uniforms));
  mat.side = THREE.DoubleSide;

  const propGeometry = {
    "primitives": [
        {
            "type": "cylinder",
            "params": {
                "rTop": 0.04,
                "rBottom": 0.08,
                "height": 0.7,
                "segments": 6
            },
            "position": [
                0.0,
                0.35,
                0.0
            ],
            "rotation": [
                0.0,
                0.0,
                0.0
            ],
            "scale": 1
        },
        {
            "type": "cone",
            "params": {
                "radius": 0.42,
                "height": 1.0,
                "segments": 7
            },
            "position": [
                0.0,
                1.1,
                0.0
            ],
            "rotation": [
                0.0,
                0.0,
                0.0
            ],
            "scale": 1
        },
        {
            "type": "cone",
            "params": {
                "radius": 0.32,
                "height": 0.9,
                "segments": 7
            },
            "position": [
                0.0,
                1.65,
                0.0
            ],
            "rotation": [
                0.0,
                0.4,
                0.0
            ],
            "scale": 1
        },
        {
            "type": "cone",
            "params": {
                "radius": 0.2,
                "height": 0.7,
                "segments": 6
            },
            "position": [
                0.0,
                2.15,
                0.0
            ],
            "rotation": [
                0.0,
                0.9,
                0.0
            ],
            "scale": 1
        }
    ]
};
  const propInstances = [
    {
        "position": [
            -4.869503253202665,
            2.0490503024173794,
            5.395655569463864
        ],
        "rotation": [
            0.0,
            139.559542619296,
            0.0
        ],
        "scale": 1.1037871226222549
    },
    {
        "position": [
            -6.096807306592408,
            2.5162678432519714,
            6.09054809800824
        ],
        "rotation": [
            0.0,
            294.6431861271994,
            0.0
        ],
        "scale": 1.1510353487691818
    },
    {
        "position": [
            4.259986181053656,
            3.0191352044384585,
            3.551956875009899
        ],
        "rotation": [
            0.0,
            66.57554298420365,
            0.0
        ],
        "scale": 0.8710483904750157
    },
    {
        "position": [
            -6.097253651370855,
            2.4581493347497125,
            3.1607013801580184
        ],
        "rotation": [
            0.0,
            210.99120285849068,
            0.0
        ],
        "scale": 1.2396700894514825
    },
    {
        "position": [
            -2.8080653343654496,
            2.4345649407484653,
            6.7622867753647045
        ],
        "rotation": [
            0.0,
            61.44216760116191,
            0.0
        ],
        "scale": 0.9973320073253028
    },
    {
        "position": [
            4.651460676747647,
            2.660572359235729,
            6.057810482570064
        ],
        "rotation": [
            0.0,
            213.097769263151,
            0.0
        ],
        "scale": 0.7215939104399066
    },
    {
        "position": [
            -3.760342932559592,
            3.368074192145711,
            3.4648160731910913
        ],
        "rotation": [
            0.0,
            30.51993579937253,
            0.0
        ],
        "scale": 0.7046075499323916
    },
    {
        "position": [
            -5.209498570595092,
            2.4428189080615197,
            8.022861092287664
        ],
        "rotation": [
            0.0,
            159.63793763958316,
            0.0
        ],
        "scale": 0.6059286878804419
    },
    {
        "position": [
            3.8085466050521926,
            2.131517186357682,
            1.0577380999111499
        ],
        "rotation": [
            0.0,
            190.6563344766848,
            0.0
        ],
        "scale": 0.7503978805253159
    },
    {
        "position": [
            -8.767488658267716,
            2.850765372125764,
            2.050893409509071
        ],
        "rotation": [
            0.0,
            102.8686097837417,
            0.0
        ],
        "scale": 1.033239720607492
    },
    {
        "position": [
            -2.591022741291213,
            3.3539348335134482,
            8.572504932594553
        ],
        "rotation": [
            0.0,
            298.84236287806664,
            0.0
        ],
        "scale": 0.6935101963845022
    },
    {
        "position": [
            2.7261776555731774,
            1.9414773798753953,
            0.6546680338180084
        ],
        "rotation": [
            0.0,
            250.83292172208184,
            0.0
        ],
        "scale": 1.2423264846054793
    },
    {
        "position": [
            -5.81381744613268,
            3.023518307274813,
            3.8522604278948993
        ],
        "rotation": [
            0.0,
            175.0066274491224,
            0.0
        ],
        "scale": 0.9310631925416406
    },
    {
        "position": [
            -2.100077574693177,
            2.710084537072541,
            8.379691033692952
        ],
        "rotation": [
            0.0,
            163.87057521916643,
            0.0
        ],
        "scale": 1.0012310615133682
    },
    {
        "position": [
            3.54367879802587,
            2.361500075352382,
            0.8069694496414157
        ],
        "rotation": [
            0.0,
            65.59994626172687,
            0.0
        ],
        "scale": 1.0646862332224927
    },
    {
        "position": [
            -5.491776064505457,
            2.218092915491929,
            5.652752015513817
        ],
        "rotation": [
            0.0,
            93.0269687776037,
            0.0
        ],
        "scale": 1.0395780441189106
    },
    {
        "position": [
            -1.5862785514610227,
            2.776724448546258,
            6.824550278295892
        ],
        "rotation": [
            0.0,
            165.63299324545972,
            0.0
        ],
        "scale": 1.2159794570804223
    },
    {
        "position": [
            4.925994874301085,
            2.5886476337623314,
            0.9329161438853195
        ],
        "rotation": [
            0.0,
            208.4547471523158,
            0.0
        ],
        "scale": 0.7468024981953395
    }
];

  for (const inst of propInstances) {
    const propGroup = new THREE.Group();
    for (const prim of propGeometry.primitives || []) {
      const geo = buildPrimitive(prim);
      if (!geo) continue;
      const mesh = new THREE.Mesh(geo, mat);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      applyTransform(mesh, prim);
      propGroup.add(mesh);
    }
    if (inst.position) propGroup.position.set(...inst.position);
    if (inst.rotation) propGroup.rotation.set(
      inst.rotation[0] * Math.PI / 180,
      inst.rotation[1] * Math.PI / 180,
      inst.rotation[2] * Math.PI / 180
    );
    if (inst.scale != null) {
      if (Array.isArray(inst.scale)) propGroup.scale.set(...inst.scale);
      else propGroup.scale.setScalar(inst.scale);
    }
    worldGroup.add(propGroup);
  }

  return mat;
})();


// ============ PROP: oak_tree ============
const propMaterial_oak_tree = (function() {
  const propShader = {
    uniforms: {
      uBarkDark: { value: new THREE.Vector3(0.23, 0.14, 0.08) },
      uBarkLight: { value: new THREE.Vector3(0.42, 0.28, 0.15) },
      uLeafDark: { value: new THREE.Vector3(0.13, 0.32, 0.1) },
      uLeafLight: { value: new THREE.Vector3(0.42, 0.62, 0.22) },
      uTime: { value: 0 }
    },
    vertexShader: "uniform float uTime;\nvarying vec2 vUv;\nvarying vec3 vNormal;\nvarying vec3 vPosition;\nvarying vec3 vWorldPos;\nvoid main() {\n  vUv = uv;\n  vNormal = normalize(normalMatrix * normal);\n  vPosition = position;\n  float sway = smoothstep(1.2, 2.8, position.y);\n  vec4 wp = modelMatrix * vec4(position, 1.0);\n  wp.x += sin(uTime * 1.3 + wp.x * 0.5 + wp.z * 0.7) * 0.06 * sway;\n  wp.z += cos(uTime * 1.1 + wp.z * 0.6 + wp.x * 0.3) * 0.045 * sway;\n  vWorldPos = wp.xyz;\n  gl_Position = projectionMatrix * viewMatrix * wp;\n}",
    fragmentShader: "uniform float uTime;\nuniform vec3 uBarkDark;\nuniform vec3 uBarkLight;\nuniform vec3 uLeafDark;\nuniform vec3 uLeafLight;\nvarying vec2 vUv;\nvarying vec3 vNormal;\nvarying vec3 vPosition;\nvarying vec3 vWorldPos;\nfloat hash(vec3 p) { return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }\nvoid main() {\n  vec3 n = normalize(vNormal);\n  vec3 sunDir = normalize(vec3(0.5, 0.85, 0.35));\n  float diff = max(dot(n, sunDir), 0.0);\n  diff = floor(diff * 3.0 + 0.5) / 3.0;\n  float radial = length(vPosition.xz);\n  float leafMask = clamp(step(0.28, radial) + step(1.68, vPosition.y), 0.0, 1.0);\n  float ang = atan(vPosition.z, vPosition.x);\n  float groove = 0.5 + 0.5 * sin(ang * 6.0 + vPosition.y * 3.5);\n  groove = floor(groove * 3.0) / 3.0;\n  vec3 bark = mix(uBarkDark, uBarkLight, 0.3 + 0.45 * groove);\n  float cl = hash(floor(vPosition * 6.0));\n  cl = floor(cl * 4.0 + 0.5) / 4.0;\n  float leafGrad = smoothstep(1.5, 3.1, vPosition.y) * 0.25;\n  vec3 leaf = mix(uLeafDark, uLeafLight, 0.25 + 0.5 * cl + leafGrad);\n  vec3 base = mix(bark, leaf, leafMask);\n  vec3 viewDir = normalize(cameraPosition - vWorldPos);\n  float fres = pow(1.0 - max(dot(n, viewDir), 0.0), 2.0);\n  vec3 rim = vec3(0.5, 0.72, 0.3) * fres * 0.3 * leafMask;\n  vec3 color = base * (0.45 + 0.55 * diff) + rim;\n  float d = fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453);\n  color += (d - 0.5) * 0.035;\n  gl_FragColor = vec4(color, 1.0);\n}",
  };

  const mat = compileShader(propShader, propFallbackColor(propShader.uniforms));
  mat.side = THREE.DoubleSide;

  const propGeometry = {
    "primitives": [
        {
            "type": "cylinder",
            "params": {
                "rTop": 0.14,
                "rBottom": 0.26,
                "height": 1.7,
                "segments": 6
            },
            "position": [
                0.0,
                0.85,
                0.0
            ],
            "rotation": [
                0.0,
                0.0,
                0.0
            ],
            "scale": 1
        },
        {
            "type": "cylinder",
            "params": {
                "rTop": 0.26,
                "rBottom": 0.4,
                "height": 0.3,
                "segments": 6
            },
            "position": [
                0.0,
                0.15,
                0.0
            ],
            "rotation": [
                0.0,
                0.0,
                0.0
            ],
            "scale": 1
        },
        {
            "type": "icosahedron",
            "params": {
                "radius": 1.05,
                "detail": 0
            },
            "position": [
                0.0,
                2.35,
                0.0
            ],
            "rotation": [
                0.0,
                0.0,
                0.0
            ],
            "scale": 1
        },
        {
            "type": "icosahedron",
            "params": {
                "radius": 0.75,
                "detail": 0
            },
            "position": [
                0.62,
                1.95,
                0.25
            ],
            "rotation": [
                0.0,
                0.6,
                0.0
            ],
            "scale": 1
        },
        {
            "type": "icosahedron",
            "params": {
                "radius": 0.7,
                "detail": 0
            },
            "position": [
                -0.55,
                2.05,
                -0.3
            ],
            "rotation": [
                0.3,
                1.2,
                0.0
            ],
            "scale": 1
        }
    ]
};
  const propInstances = [
    {
        "position": [
            -3.483316964144092,
            2.7305834216676343,
            -7.267611130137123
        ],
        "rotation": [
            0.0,
            351.66885599494947,
            0.0
        ],
        "scale": 0.848175124952757
    },
    {
        "position": [
            6.574216513468909,
            2.843063911954755,
            -0.13841028052873705
        ],
        "rotation": [
            0.0,
            62.59163337338579,
            0.0
        ],
        "scale": 1.2483793554624651
    },
    {
        "position": [
            3.1072836459546562,
            2.5972536414298757,
            3.3026259880561377
        ],
        "rotation": [
            0.0,
            2.994830672976434,
            0.0
        ],
        "scale": 1.422755790926841
    },
    {
        "position": [
            4.031044378314843,
            2.9837071019695234,
            4.431082997545013
        ],
        "rotation": [
            0.0,
            235.3468052110466,
            0.0
        ],
        "scale": 0.9554202235882816
    },
    {
        "position": [
            5.822538728230165,
            2.984209023294018,
            -0.16713738112405235
        ],
        "rotation": [
            0.0,
            16.757159981314743,
            0.0
        ],
        "scale": 0.8121594916114264
    },
    {
        "position": [
            -6.133687840992492,
            2.5730908470232765,
            -5.432515731291701
        ],
        "rotation": [
            0.0,
            159.72851107559174,
            0.0
        ],
        "scale": 0.9045213315220414
    },
    {
        "position": [
            2.371398376445957,
            2.9816476912013523,
            -1.3771646865937228
        ],
        "rotation": [
            0.0,
            347.4522424672005,
            0.0
        ],
        "scale": 0.9249375645467695
    },
    {
        "position": [
            2.8026887157964824,
            3.013932348942138,
            3.97411717332884
        ],
        "rotation": [
            0.0,
            15.806296993096147,
            0.0
        ],
        "scale": 1.0689487343258102
    },
    {
        "position": [
            5.694781015737722,
            2.7329340121341397,
            6.085440832472187
        ],
        "rotation": [
            0.0,
            25.76036072801895,
            0.0
        ],
        "scale": 1.0713990210879518
    },
    {
        "position": [
            4.222885452904962,
            1.6752947575028694,
            1.395897701505624
        ],
        "rotation": [
            0.0,
            183.7396701046013,
            0.0
        ],
        "scale": 0.9455628923753913
    },
    {
        "position": [
            -6.172258923488647,
            2.5854171595322275,
            -4.623617709216243
        ],
        "rotation": [
            0.0,
            350.9117169011541,
            0.0
        ],
        "scale": 1.3534139291377998
    },
    {
        "position": [
            5.599659669150488,
            2.5562438639811385,
            0.8781306020299628
        ],
        "rotation": [
            0.0,
            331.74064507475555,
            0.0
        ],
        "scale": 0.9071260668076957
    },
    {
        "position": [
            -0.6069290661956024,
            1.967532537356804,
            3.8652817723225863
        ],
        "rotation": [
            0.0,
            51.456807312135034,
            0.0
        ],
        "scale": 1.1133998343085985
    },
    {
        "position": [
            5.848079537016379,
            2.0773874185222074,
            4.093779328265436
        ],
        "rotation": [
            0.0,
            349.96815639517234,
            0.0
        ],
        "scale": 1.251149510109006
    },
    {
        "position": [
            4.55951514605976,
            2.499867185619319,
            -0.7954135647431768
        ],
        "rotation": [
            0.0,
            134.2223584319356,
            0.0
        ],
        "scale": 0.9560952135741507
    },
    {
        "position": [
            -6.365614281521877,
            3.0093567628838604,
            -4.943333788356386
        ],
        "rotation": [
            0.0,
            203.71031180595128,
            0.0
        ],
        "scale": 1.3687857815586917
    },
    {
        "position": [
            7.286505168872655,
            2.2516288665600253,
            -3.064339831508116
        ],
        "rotation": [
            0.0,
            32.68595742022584,
            0.0
        ],
        "scale": 1.009831771183661
    },
    {
        "position": [
            3.044465840727398,
            2.600293005067143,
            4.816385907982689
        ],
        "rotation": [
            0.0,
            125.89468044796487,
            0.0
        ],
        "scale": 0.8464090399302985
    },
    {
        "position": [
            6.81197172495295,
            1.898534689879936,
            6.024779508685785
        ],
        "rotation": [
            0.0,
            165.88057291016761,
            0.0
        ],
        "scale": 1.382505587571627
    },
    {
        "position": [
            4.447194048074833,
            1.8654161166800345,
            -0.2541634665866146
        ],
        "rotation": [
            0.0,
            307.63368921991884,
            0.0
        ],
        "scale": 1.1860461259412773
    },
    {
        "position": [
            -7.801676837674382,
            2.566563908262891,
            -6.357739118365745
        ],
        "rotation": [
            0.0,
            190.5472009650994,
            0.0
        ],
        "scale": 1.1511683969804856
    },
    {
        "position": [
            7.394366503911842,
            2.6663534325936924,
            -0.9092066393504774
        ],
        "rotation": [
            0.0,
            138.61780630359928,
            0.0
        ],
        "scale": 1.4219899720316576
    },
    {
        "position": [
            1.13781106679434,
            1.9266967737174843,
            1.5815923969906773
        ],
        "rotation": [
            0.0,
            70.56639423470166,
            0.0
        ],
        "scale": 1.0913921775687139
    },
    {
        "position": [
            4.879890891635954,
            2.345792809277408,
            0.3462758817581264
        ],
        "rotation": [
            0.0,
            184.7880531344555,
            0.0
        ],
        "scale": 1.3700154542160499
    },
    {
        "position": [
            4.017443635230474,
            3.0235541070715097,
            3.666805934955695
        ],
        "rotation": [
            0.0,
            42.93677282524555,
            0.0
        ],
        "scale": 0.8507148490281609
    },
    {
        "position": [
            -3.512971542571853,
            3.2896826574595166,
            -7.040153869271293
        ],
        "rotation": [
            0.0,
            220.056886288337,
            0.0
        ],
        "scale": 1.0785060961134412
    },
    {
        "position": [
            5.254140982125049,
            1.3819577262993832,
            -3.670304556943457
        ],
        "rotation": [
            0.0,
            244.60769353767327,
            0.0
        ],
        "scale": 0.9662426247897524
    },
    {
        "position": [
            1.3846278389955664,
            2.930792888179855,
            5.4519461257822694
        ],
        "rotation": [
            0.0,
            69.69011304286418,
            0.0
        ],
        "scale": 0.8527192278760051
    },
    {
        "position": [
            6.158773491660976,
            2.2117889650546494,
            1.4484008626997338
        ],
        "rotation": [
            0.0,
            184.64210743488954,
            0.0
        ],
        "scale": 0.9597111798794513
    },
    {
        "position": [
            6.924006189539533,
            2.3971799237769087,
            3.3948283036140365
        ],
        "rotation": [
            0.0,
            205.28022654481006,
            0.0
        ],
        "scale": 1.3343262825297666
    },
    {
        "position": [
            -4.712054508047736,
            1.4226839205495545,
            -2.867845342184806
        ],
        "rotation": [
            0.0,
            136.57160684734004,
            0.0
        ],
        "scale": 1.3376579582229673
    },
    {
        "position": [
            3.717594998868659,
            2.234297752013907,
            -3.4802896413020363
        ],
        "rotation": [
            0.0,
            244.80002475063287,
            0.0
        ],
        "scale": 1.4502670213966966
    },
    {
        "position": [
            1.8413915954958173,
            2.9932396814624393,
            2.3929220386282504
        ],
        "rotation": [
            0.0,
            56.71659974780543,
            0.0
        ],
        "scale": 1.4898876994122727
    },
    {
        "position": [
            6.5639498497646915,
            1.4070103165839358,
            4.297339466535835
        ],
        "rotation": [
            0.0,
            79.22114664891441,
            0.0
        ],
        "scale": 0.9592616618223451
    }
];

  for (const inst of propInstances) {
    const propGroup = new THREE.Group();
    for (const prim of propGeometry.primitives || []) {
      const geo = buildPrimitive(prim);
      if (!geo) continue;
      const mesh = new THREE.Mesh(geo, mat);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      applyTransform(mesh, prim);
      propGroup.add(mesh);
    }
    if (inst.position) propGroup.position.set(...inst.position);
    if (inst.rotation) propGroup.rotation.set(
      inst.rotation[0] * Math.PI / 180,
      inst.rotation[1] * Math.PI / 180,
      inst.rotation[2] * Math.PI / 180
    );
    if (inst.scale != null) {
      if (Array.isArray(inst.scale)) propGroup.scale.set(...inst.scale);
      else propGroup.scale.setScalar(inst.scale);
    }
    worldGroup.add(propGroup);
  }

  return mat;
})();


// ============ PROP: grey_boulder ============
const propMaterial_grey_boulder = (function() {
  const propShader = {
    uniforms: {
      uColorA: { value: new THREE.Vector3(0.47, 0.47, 0.45) },
      uColorB: { value: new THREE.Vector3(0.31, 0.32, 0.31) },
      uMoss: { value: new THREE.Vector3(0.32, 0.45, 0.19) },
      uTime: { value: 0 }
    },
    vertexShader: "varying vec2 vUv;\nvarying vec3 vNormal;\nvarying vec3 vPosition;\nvarying vec3 vWorldPos;\nvoid main() {\n  vUv = uv;\n  vNormal = normalize(normalMatrix * normal);\n  vPosition = position;\n  vec4 wp = modelMatrix * vec4(position, 1.0);\n  vWorldPos = wp.xyz;\n  gl_Position = projectionMatrix * viewMatrix * wp;\n}",
    fragmentShader: "uniform float uTime;\nuniform vec3 uColorA;\nuniform vec3 uColorB;\nuniform vec3 uMoss;\nvarying vec2 vUv;\nvarying vec3 vNormal;\nvarying vec3 vPosition;\nvarying vec3 vWorldPos;\nfloat hash(vec3 p) {\n  p = fract(p * 0.3183099 + vec3(0.1, 0.17, 0.13));\n  p *= 17.0;\n  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));\n}\nfloat vnoise(vec3 p) {\n  vec3 i = floor(p);\n  vec3 f = fract(p);\n  f = f * f * (3.0 - 2.0 * f);\n  float a = hash(i);\n  float b = hash(i + vec3(1.0, 0.0, 0.0));\n  float c = hash(i + vec3(0.0, 1.0, 0.0));\n  float d = hash(i + vec3(1.0, 1.0, 0.0));\n  float e = hash(i + vec3(0.0, 0.0, 1.0));\n  float g = hash(i + vec3(1.0, 0.0, 1.0));\n  float h = hash(i + vec3(0.0, 1.0, 1.0));\n  float k = hash(i + vec3(1.0, 1.0, 1.0));\n  return mix(mix(mix(a, b, f.x), mix(c, d, f.x), f.y), mix(mix(e, g, f.x), mix(h, k, f.x), f.y), f.z);\n}\nfloat dither8(vec2 pix) {\n  vec2 c = floor(mod(pix, 4.0));\n  float m = c.x + c.y * 4.0;\n  float t = fract(0.5 + m * 0.6180339887);\n  return (t - 0.5) * 0.02;\n}\nvoid main() {\n  vec3 N = normalize(vNormal);\n  vec3 V = normalize(cameraPosition - vWorldPos);\n  float fres = pow(clamp(1.0 - abs(dot(N, V)), 0.0, 1.0), 3.0);\n  vec3 sun = normalize(vec3(0.5, 0.85, 0.3));\n  vec3 lamber = vec3(0.55) + vec3(0.45) * clamp(dot(N, sun), 0.0, 1.0);\n  float warp = vnoise(vPosition * 3.5);\n  float strata = vnoise(vPosition * vec3(2.0, 7.0, 2.0) + warp * 1.8);\n  vec3 rock = mix(uColorA, uColorB, strata);\n  float grain = vnoise(vPosition * 26.0);\n  rock *= 0.88 + grain * 0.24;\n  float vein = smoothstep(0.66, 0.74, vnoise(vPosition * 8.0 + vec3(7.3)));\n  rock += vec3(0.10, 0.11, 0.12) * vein;\n  float mossMask = smoothstep(0.45, 0.62, vnoise(vWorldPos * 2.2 + vec3(0.0, 1.7, 0.0)));\n  float upness = clamp(vPosition.y * 1.1, 0.0, 1.0);\n  float moss = mossMask * (1.0 - upness * 0.85);\n  float pulse = 0.9 + 0.1 * sin(uTime * 1.3);\n  vec3 col = mix(rock, uMoss * pulse, moss * 0.75);\n  col *= lamber;\n  col += uMoss * 0.10 * moss * (0.5 + 0.5 * dot(N, sun));\n  col += vec3(0.06, 0.07, 0.09) * fres;\n  col = floor(col * 12.0 + dither8(gl_FragCoord.xy)) / 12.0;\n  gl_FragColor = vec4(col, 1.0);\n}",
  };

  const mat = compileShader(propShader, propFallbackColor(propShader.uniforms));
  mat.side = THREE.DoubleSide;

  const propGeometry = {
    "primitives": [
        {
            "type": "icosahedron",
            "params": {
                "radius": 0.62,
                "detail": 0
            },
            "position": [
                0.0,
                0.42,
                0.0
            ],
            "rotation": [
                0.0,
                0.35,
                0.0
            ],
            "scale": 1
        },
        {
            "type": "dodecahedron",
            "params": {
                "radius": 0.4,
                "detail": 0
            },
            "position": [
                0.38,
                0.26,
                0.12
            ],
            "rotation": [
                0.3,
                0.6,
                0.2
            ],
            "scale": 0.95
        },
        {
            "type": "icosahedron",
            "params": {
                "radius": 0.34,
                "detail": 0
            },
            "position": [
                -0.32,
                0.24,
                -0.18
            ],
            "rotation": [
                0.5,
                0.2,
                0.8
            ],
            "scale": 1
        },
        {
            "type": "octahedron",
            "params": {
                "radius": 0.24,
                "detail": 0
            },
            "position": [
                0.02,
                0.66,
                -0.22
            ],
            "rotation": [
                0.2,
                0.9,
                0.1
            ],
            "scale": 1
        }
    ]
};
  const propInstances = [
    {
        "position": [
            -7.370028665990365,
            2.630162550988749,
            -8.527686858373121
        ],
        "rotation": [
            0.0,
            281.9937812612517,
            0.0
        ],
        "scale": 0.7024082142304967
    },
    {
        "position": [
            4.765052875429058,
            2.6043403147468274,
            -7.059485660758083
        ],
        "rotation": [
            0.0,
            209.89132770260207,
            0.0
        ],
        "scale": 1.0553031492339486
    },
    {
        "position": [
            -5.9085911229454116,
            2.494316406552847,
            0.5990146672769541
        ],
        "rotation": [
            0.0,
            59.98664872858994,
            0.0
        ],
        "scale": 1.010728958614778
    },
    {
        "position": [
            -8.586014603427433,
            2.3177096662758725,
            3.332722193833053
        ],
        "rotation": [
            0.0,
            217.8938915152052,
            0.0
        ],
        "scale": 1.2743823265374943
    },
    {
        "position": [
            6.982093973903055,
            2.605511160214333,
            1.0769989155923376
        ],
        "rotation": [
            0.0,
            179.02608406881947,
            0.0
        ],
        "scale": 1.0957676715525342
    },
    {
        "position": [
            5.578244863388571,
            2.2538275629799083,
            1.4892252817264922
        ],
        "rotation": [
            0.0,
            3.8703166425684588,
            0.0
        ],
        "scale": 0.7911186053120727
    },
    {
        "position": [
            1.01873580988088,
            1.8172714538896482,
            -8.647216524543317
        ],
        "rotation": [
            0.0,
            180.49594861907147,
            0.0
        ],
        "scale": 0.9472763713642797
    },
    {
        "position": [
            -8.927039396210567,
            2.98203254638618,
            2.9498855219537266
        ],
        "rotation": [
            0.0,
            176.0095412329798,
            0.0
        ],
        "scale": 0.8020519416006088
    },
    {
        "position": [
            7.986991435609308,
            2.199997114982588,
            1.3170766163894339
        ],
        "rotation": [
            0.0,
            1.1336054941620377,
            0.0
        ],
        "scale": 1.1613519708264313
    },
    {
        "position": [
            8.18017713797608,
            2.6262646510904677,
            -0.6864224424496808
        ],
        "rotation": [
            0.0,
            265.45500444034036,
            0.0
        ],
        "scale": 1.1916645765624057
    },
    {
        "position": [
            4.748239672156174,
            1.7520116107395842,
            -3.877257901569478
        ],
        "rotation": [
            0.0,
            42.324957013636435,
            0.0
        ],
        "scale": 1.311176216676068
    },
    {
        "position": [
            -5.0621372363098445,
            2.529953534450554,
            -5.239904589566159
        ],
        "rotation": [
            0.0,
            7.378485123571927,
            0.0
        ],
        "scale": 0.9877422482365976
    },
    {
        "position": [
            4.674310019107937,
            2.2281722954425525,
            -1.4980321017468343
        ],
        "rotation": [
            0.0,
            295.1529909510145,
            0.0
        ],
        "scale": 1.1561612117642275
    },
    {
        "position": [
            -7.335665695756081,
            2.993122349056412,
            -5.634020901489318
        ],
        "rotation": [
            0.0,
            151.16234775012455,
            0.0
        ],
        "scale": 1.3809114507063462
    },
    {
        "position": [
            -7.747856824444022,
            2.0939546195237093,
            -6.610627487112946
        ],
        "rotation": [
            0.0,
            69.19151969357138,
            0.0
        ],
        "scale": 1.0837283970852192
    },
    {
        "position": [
            6.581766812125068,
            2.1933730848058546,
            8.46803384780954
        ],
        "rotation": [
            0.0,
            4.218989777835587,
            0.0
        ],
        "scale": 1.0580352041574488
    }
];

  for (const inst of propInstances) {
    const propGroup = new THREE.Group();
    for (const prim of propGeometry.primitives || []) {
      const geo = buildPrimitive(prim);
      if (!geo) continue;
      const mesh = new THREE.Mesh(geo, mat);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      applyTransform(mesh, prim);
      propGroup.add(mesh);
    }
    if (inst.position) propGroup.position.set(...inst.position);
    if (inst.rotation) propGroup.rotation.set(
      inst.rotation[0] * Math.PI / 180,
      inst.rotation[1] * Math.PI / 180,
      inst.rotation[2] * Math.PI / 180
    );
    if (inst.scale != null) {
      if (Array.isArray(inst.scale)) propGroup.scale.set(...inst.scale);
      else propGroup.scale.setScalar(inst.scale);
    }
    worldGroup.add(propGroup);
  }

  return mat;
})();


// ============ PROP: river_reeds ============
const propMaterial_river_reeds = (function() {
  const propShader = {
    uniforms: {
      uColorA: { value: new THREE.Vector3(0.16, 0.34, 0.12) },
      uColorB: { value: new THREE.Vector3(0.45, 0.62, 0.22) },
      uTime: { value: 0 }
    },
    vertexShader: "varying vec2 vUv;\nvarying vec3 vNormal;\nvarying vec3 vPosition;\nvarying vec3 vWorldPos;\nvoid main() {\n  vUv = uv;\n  vNormal = normalize(normalMatrix * normal);\n  vPosition = position;\n  vec4 wp = modelMatrix * vec4(position, 1.0);\n  vWorldPos = wp.xyz;\n  gl_Position = projectionMatrix * viewMatrix * wp;\n}",
    fragmentShader: "uniform float uTime;\nvarying vec2 vUv;\nvarying vec3 vNormal;\nvarying vec3 vPosition;\nvarying vec3 vWorldPos;\nfloat hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }\nfloat noise(vec2 p) { vec2 i = floor(p); vec2 f = fract(p); f = f * f * (3.0 - 2.0 * f); float a = hash(i); float b = hash(i + vec2(1.0, 0.0)); float c = hash(i + vec2(0.0, 1.0)); float d = hash(i + vec2(1.0, 1.0)); return mix(mix(a, b, f.x), mix(c, d, f.x), f.y); }\nfloat dither(vec2 p) { return hash(p) * 0.5 + hash(p * 1.7 + 13.3) * 0.5; }\nvoid main() {\n  vec3 reedLow = vec3(0.16, 0.34, 0.12);\n  vec3 reedHigh = vec3(0.45, 0.62, 0.22);\n  vec3 cattail = vec3(0.42, 0.26, 0.10);\n  vec3 cattailTip = vec3(0.55, 0.40, 0.16);\n  float h = clamp(vPosition.y / 1.4, 0.0, 1.0);\n  vec3 base = mix(reedLow, reedHigh, h);\n  float isHead = smoothstep(0.85, 1.0, vPosition.y);\n  vec3 headCol = mix(cattail, cattailTip, smoothstep(1.2, 1.4, vPosition.y));\n  base = mix(base, headCol, isHead);\n  float warp = noise(vWorldPos.xz * 3.0 + uTime * 0.4) - 0.5;\n  float stripes = noise(vec2(vUv.x * 14.0, vPosition.y * 6.0 + warp * 2.0));\n  base *= 0.9 + stripes * 0.2;\n  vec3 L = normalize(vec3(0.5, 0.8, 0.3));\n  float lam = 0.55 + 0.45 * max(dot(vNormal, L), 0.0);\n  vec3 V = vec3(0.0, 0.0, 1.0);\n  float fres = pow(1.0 - abs(dot(vNormal, V)), 2.0);\n  base += vec3(0.35, 0.45, 0.18) * fres * 0.4;\n  float pulse = sin(uTime * 1.6 + vWorldPos.x * 2.0 + vWorldPos.z * 1.7) * 0.5 + 0.5;\n  base += vec3(0.06, 0.09, 0.02) * pulse * h;\n  base *= lam;\n  vec3 q = floor(base * 7.0) / 7.0;\n  float dth = dither(gl_FragCoord.xy);\n  base = mix(q, base, 0.35) + (dth - 0.5) * 0.04;\n  gl_FragColor = vec4(base, 1.0);\n}",
  };

  const mat = compileShader(propShader, propFallbackColor(propShader.uniforms));
  mat.side = THREE.DoubleSide;

  const propGeometry = {
    "primitives": [
        {
            "type": "cylinder",
            "params": {
                "rTop": 0.015,
                "rBottom": 0.035,
                "height": 1.1,
                "segments": 6
            },
            "position": [
                0.0,
                0.55,
                0.0
            ],
            "rotation": [
                0.0,
                0.0,
                0.08
            ],
            "scale": 1
        },
        {
            "type": "cylinder",
            "params": {
                "rTop": 0.012,
                "rBottom": 0.03,
                "height": 0.95,
                "segments": 6
            },
            "position": [
                0.14,
                0.48,
                0.05
            ],
            "rotation": [
                0.0,
                0.0,
                -0.14
            ],
            "scale": 1
        },
        {
            "type": "cylinder",
            "params": {
                "rTop": 0.012,
                "rBottom": 0.028,
                "height": 0.8,
                "segments": 6
            },
            "position": [
                -0.12,
                0.4,
                -0.06
            ],
            "rotation": [
                0.12,
                0.0,
                0.1
            ],
            "scale": 1
        },
        {
            "type": "cylinder",
            "params": {
                "rTop": 0.05,
                "rBottom": 0.07,
                "height": 0.28,
                "segments": 6
            },
            "position": [
                0.03,
                1.18,
                0.0
            ],
            "rotation": [
                0.0,
                0.0,
                0.08
            ],
            "scale": 1
        },
        {
            "type": "cone",
            "params": {
                "radius": 0.035,
                "height": 0.12,
                "segments": 6
            },
            "position": [
                0.05,
                1.36,
                0.0
            ],
            "rotation": [
                0.0,
                0.0,
                0.08
            ],
            "scale": 1
        },
        {
            "type": "cylinder",
            "params": {
                "rTop": 0.04,
                "rBottom": 0.055,
                "height": 0.22,
                "segments": 6
            },
            "position": [
                0.17,
                0.98,
                0.05
            ],
            "rotation": [
                0.0,
                0.0,
                -0.14
            ],
            "scale": 0.9
        }
    ]
};
  const propInstances = [
    {
        "position": [
            -0.2018973018799265,
            3.394522194743523,
            -9.0
        ],
        "rotation": [
            0.0,
            61.36698507256598,
            0.0
        ],
        "scale": 0.8005817935270649
    },
    {
        "position": [
            -1.3808441332336365,
            2.1826342889896457,
            -8.142857142857142
        ],
        "rotation": [
            0.0,
            36.450976641424596,
            0.0
        ],
        "scale": 1.1917533836651144
    },
    {
        "position": [
            -1.849469715775489,
            2.9894374516824556,
            -7.285714285714286
        ],
        "rotation": [
            0.0,
            169.10464132402853,
            0.0
        ],
        "scale": 1.2180503889239622
    },
    {
        "position": [
            -2.0698028607256496,
            2.6875800642217595,
            -6.428571428571429
        ],
        "rotation": [
            0.0,
            356.82895719188235,
            0.0
        ],
        "scale": 0.9312658422012501
    },
    {
        "position": [
            -3.154679000731309,
            1.8238043857765023,
            -5.571428571428571
        ],
        "rotation": [
            0.0,
            44.56574786310555,
            0.0
        ],
        "scale": 1.0541362757053787
    },
    {
        "position": [
            -3.0459589538718608,
            2.1767819581204386,
            -4.714285714285714
        ],
        "rotation": [
            0.0,
            334.9698800694917,
            0.0
        ],
        "scale": 1.2986837188022364
    },
    {
        "position": [
            -3.4998261896579503,
            2.3342450392068104,
            -3.8571428571428577
        ],
        "rotation": [
            0.0,
            45.35236675103469,
            0.0
        ],
        "scale": 0.828563870315978
    },
    {
        "position": [
            -2.5621054194032182,
            3.7882477548145683,
            -3.0
        ],
        "rotation": [
            0.0,
            337.07757692515105,
            0.0
        ],
        "scale": 1.0551153450068005
    },
    {
        "position": [
            -1.91995518722978,
            2.8090094059737174,
            -2.1428571428571432
        ],
        "rotation": [
            0.0,
            217.55044738661266,
            0.0
        ],
        "scale": 1.0620549461891118
    },
    {
        "position": [
            -1.2471695675706607,
            2.5439380859436964,
            -1.2857142857142865
        ],
        "rotation": [
            0.0,
            256.76838807983154,
            0.0
        ],
        "scale": 1.1644248120630296
    },
    {
        "position": [
            -0.6500234554688484,
            1.5240504522183218,
            -0.4285714285714288
        ],
        "rotation": [
            0.0,
            178.8787556624439,
            0.0
        ],
        "scale": 0.9613626952697909
    },
    {
        "position": [
            0.3057278935134556,
            2.1219264037696113,
            0.4285714285714288
        ],
        "rotation": [
            0.0,
            72.98803927232997,
            0.0
        ],
        "scale": 1.1961177859823993
    },
    {
        "position": [
            0.8145330873157522,
            2.4934832369923656,
            1.2857142857142847
        ],
        "rotation": [
            0.0,
            309.69068252160923,
            0.0
        ],
        "scale": 1.0631386326339094
    },
    {
        "position": [
            1.7529531601846706,
            2.669022997098342,
            2.1428571428571423
        ],
        "rotation": [
            0.0,
            289.86304798863665,
            0.0
        ],
        "scale": 1.0020237838178736
    },
    {
        "position": [
            2.8373219552080418,
            2.6950203675364706,
            3.0
        ],
        "rotation": [
            0.0,
            63.22496629341349,
            0.0
        ],
        "scale": 1.1201582182208973
    },
    {
        "position": [
            3.348288574530467,
            2.6064187787570803,
            3.857142857142856
        ],
        "rotation": [
            0.0,
            268.3174094200637,
            0.0
        ],
        "scale": 0.8602386006278557
    },
    {
        "position": [
            2.763382513375705,
            2.7960188754106072,
            4.7142857142857135
        ],
        "rotation": [
            0.0,
            94.87128880016867,
            0.0
        ],
        "scale": 1.206123251728592
    },
    {
        "position": [
            2.575869403965141,
            1.7518420914843669,
            5.571428571428571
        ],
        "rotation": [
            0.0,
            173.63538068604217,
            0.0
        ],
        "scale": 1.1656520199268354
    },
    {
        "position": [
            2.2190546223147636,
            2.98289295738265,
            6.428571428571427
        ],
        "rotation": [
            0.0,
            29.15022649464592,
            0.0
        ],
        "scale": 0.785918158275932
    },
    {
        "position": [
            1.8807524986740372,
            2.3681313034407743,
            7.285714285714285
        ],
        "rotation": [
            0.0,
            114.13896784205332,
            0.0
        ],
        "scale": 0.9313807146815919
    },
    {
        "position": [
            1.206766443009209,
            2.5532468924125284,
            8.142857142857142
        ],
        "rotation": [
            0.0,
            105.44794363054058,
            0.0
        ],
        "scale": 0.8814126101667337
    },
    {
        "position": [
            -0.25432842829693275,
            2.7048458100739627,
            9.0
        ],
        "rotation": [
            0.0,
            234.01767649300658,
            0.0
        ],
        "scale": 0.8751663277741321
    }
];

  for (const inst of propInstances) {
    const propGroup = new THREE.Group();
    for (const prim of propGeometry.primitives || []) {
      const geo = buildPrimitive(prim);
      if (!geo) continue;
      const mesh = new THREE.Mesh(geo, mat);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      applyTransform(mesh, prim);
      propGroup.add(mesh);
    }
    if (inst.position) propGroup.position.set(...inst.position);
    if (inst.rotation) propGroup.rotation.set(
      inst.rotation[0] * Math.PI / 180,
      inst.rotation[1] * Math.PI / 180,
      inst.rotation[2] * Math.PI / 180
    );
    if (inst.scale != null) {
      if (Array.isArray(inst.scale)) propGroup.scale.set(...inst.scale);
      else propGroup.scale.setScalar(inst.scale);
    }
    worldGroup.add(propGroup);
  }

  return mat;
})();


// ============ PROP: watchtower ============
const propMaterial_watchtower = (function() {
  const propShader = {
    uniforms: {
      uColorA: { value: new THREE.Vector3(0.34, 0.24, 0.15) },
      uColorB: { value: new THREE.Vector3(0.52, 0.38, 0.22) },
      uColorC: { value: new THREE.Vector3(0.72, 0.82, 0.95) },
      uTime: { value: 0 }
    },
    vertexShader: "varying vec2 vUv;\nvarying vec3 vNormal;\nvarying vec3 vPosition;\nvarying vec3 vWorldPos;\nvoid main() {\n  vUv = uv;\n  vNormal = normalize(normalMatrix * normal);\n  vPosition = position;\n  vec4 wp = modelMatrix * vec4(position, 1.0);\n  vWorldPos = wp.xyz;\n  gl_Position = projectionMatrix * viewMatrix * wp;\n}",
    fragmentShader: "uniform float uTime;\nuniform vec3 uColorA;\nuniform vec3 uColorB;\nuniform vec3 uColorC;\nvarying vec2 vUv;\nvarying vec3 vNormal;\nvarying vec3 vPosition;\nvarying vec3 vWorldPos;\nfloat hash(vec2 p) {\n  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);\n}\nfloat noise(vec2 p) {\n  vec2 i = floor(p);\n  vec2 f = fract(p);\n  f = f * f * (3.0 - 2.0 * f);\n  float a = hash(i);\n  float b = hash(i + vec2(1.0, 0.0));\n  float c = hash(i + vec2(0.0, 1.0));\n  float d = hash(i + vec2(1.0, 1.0));\n  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);\n}\nfloat dither2(vec2 p) {\n  vec2 c = floor(mod(p, 2.0));\n  return mod(c.x + c.y * 2.0, 4.0) * 0.25 - 0.375;\n}\nvoid main() {\n  vec2 wuv = vUv + vec2(noise(vUv * 5.0 + uTime * 0.05) * 0.09, 0.0);\n  float plank = step(0.5, fract(wuv.y * 6.0));\n  float grain = noise(vec2(wuv.x * 22.0, wuv.y * 90.0));\n  float knot = smoothstep(0.86, 1.0, noise(vUv * 7.0 + 4.3));\n  vec3 wood = mix(uColorA, uColorB, clamp(plank * 0.55 + grain * 0.35 + knot * 0.25, 0.0, 1.0));\n  float baseMask = 1.0 - smoothstep(0.48, 0.58, vPosition.y);\n  float speck = noise(vPosition.xz * 34.0);\n  vec3 stone = mix(vec3(0.42, 0.44, 0.42), vec3(0.68, 0.69, 0.64), speck * 0.85 + plank * 0.15);\n  vec3 col = mix(wood, stone, baseMask);\n  float mossNoise = noise(vPosition.xz * 3.2 + 11.0);\n  float mossMask = smoothstep(0.55, 0.95, mossNoise) * smoothstep(1.35, 0.15, vPosition.y) * 0.55;\n  col = mix(col, vec3(0.26, 0.42, 0.18), mossMask);\n  vec3 lightDir = normalize(vec3(0.42, 0.86, 0.32));\n  float nl = 0.5 + 0.5 * dot(vNormal, lightDir);\n  col *= mix(0.58, 1.0, nl);\n  float fr = pow(1.0 - abs(dot(normalize(vNormal), normalize(vPosition + vec3(0.0001)))), 2.0);\n  col += uColorC * fr * 0.35;\n  float d = distance(vPosition, vec3(0.0, 2.9, 0.52));\n  float pulse = 0.72 + 0.28 * sin(uTime * 3.1);\n  float glow = exp(-d * 4.2) * pulse;\n  col += vec3(1.0, 0.72, 0.28) * glow * 1.35;\n  float fog = smoothstep(6.0, 46.0, length(vWorldPos - vPosition));\n  col = mix(col, vec3(0.67, 0.78, 0.90), fog * 0.18);\n  float dth = dither2(gl_FragCoord.xy);\n  col = floor(col * 6.0 + dth) / 6.0;\n  gl_FragColor = vec4(clamp(col, 0.0, 1.0), 1.0);\n}",
  };

  const mat = compileShader(propShader, propFallbackColor(propShader.uniforms));
  mat.side = THREE.DoubleSide;

  const propGeometry = {
    "primitives": [
        {
            "type": "cylinder",
            "params": {
                "rTop": 0.56,
                "rBottom": 0.72,
                "height": 0.5,
                "segments": 8
            },
            "position": [
                0.0,
                0.25,
                0.0
            ],
            "rotation": [
                0.0,
                0.0,
                0.0
            ],
            "scale": 1
        },
        {
            "type": "cylinder",
            "params": {
                "rTop": 0.36,
                "rBottom": 0.44,
                "height": 2.05,
                "segments": 8
            },
            "position": [
                0.0,
                1.52,
                0.0
            ],
            "rotation": [
                0.0,
                0.0,
                0.0
            ],
            "scale": 1
        },
        {
            "type": "box",
            "params": {
                "width": 1.3,
                "height": 0.18,
                "depth": 1.3
            },
            "position": [
                0.0,
                2.62,
                0.0
            ],
            "rotation": [
                0.0,
                0.3927,
                0.0
            ],
            "scale": 1
        },
        {
            "type": "cone",
            "params": {
                "radius": 1.0,
                "height": 0.92,
                "segments": 8
            },
            "position": [
                0.0,
                3.16,
                0.0
            ],
            "rotation": [
                0.0,
                0.3927,
                0.0
            ],
            "scale": 1
        },
        {
            "type": "octahedron",
            "params": {
                "radius": 0.17
            },
            "position": [
                0.0,
                2.9,
                0.52
            ],
            "rotation": [
                0.0,
                0.0,
                0.0
            ],
            "scale": 1
        }
    ]
};
  const propInstances = [
    {
        "position": [
            -6.668553674091873,
            2.483980891927856,
            0.4338924983463439
        ],
        "rotation": [
            0.0,
            351.55967957978334,
            0.0
        ],
        "scale": 0.948768843629038
    },
    {
        "position": [
            -6.061242173080154,
            2.2381914831080905,
            4.915229129824478
        ],
        "rotation": [
            0.0,
            155.52759884490038,
            0.0
        ],
        "scale": 0.9247220619782452
    },
    {
        "position": [
            7.6043124148595425,
            2.407573935047989,
            -2.0685471582311843
        ],
        "rotation": [
            0.0,
            275.9614665241357,
            0.0
        ],
        "scale": 0.928208790326034
    },
    {
        "position": [
            -5.403349998735714,
            2.14060887797004,
            -4.200141516189728
        ],
        "rotation": [
            0.0,
            91.1125382211417,
            0.0
        ],
        "scale": 0.9853237721220249
    }
];

  for (const inst of propInstances) {
    const propGroup = new THREE.Group();
    for (const prim of propGeometry.primitives || []) {
      const geo = buildPrimitive(prim);
      if (!geo) continue;
      const mesh = new THREE.Mesh(geo, mat);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      applyTransform(mesh, prim);
      propGroup.add(mesh);
    }
    if (inst.position) propGroup.position.set(...inst.position);
    if (inst.rotation) propGroup.rotation.set(
      inst.rotation[0] * Math.PI / 180,
      inst.rotation[1] * Math.PI / 180,
      inst.rotation[2] * Math.PI / 180
    );
    if (inst.scale != null) {
      if (Array.isArray(inst.scale)) propGroup.scale.set(...inst.scale);
      else propGroup.scale.setScalar(inst.scale);
    }
    worldGroup.add(propGroup);
  }

  return mat;
})();


// ============ PROP: gold_mine ============
const propMaterial_gold_mine = (function() {
  const propShader = {
    uniforms: {
      uGoldDeep: { value: new THREE.Vector3(0.62, 0.42, 0.09) },
      uGoldLit: { value: new THREE.Vector3(1.0, 0.86, 0.36) },
      uTime: { value: 0 }
    },
    vertexShader: "varying vec2 vUv;\nvarying vec3 vNormal;\nvarying vec3 vPosition;\nvarying vec3 vWorldPos;\nvoid main() {\n  vUv = uv;\n  vNormal = normalize(normalMatrix * normal);\n  vPosition = position;\n  vec4 wp = modelMatrix * vec4(position, 1.0);\n  vWorldPos = wp.xyz;\n  gl_Position = projectionMatrix * viewMatrix * wp;\n}",
    fragmentShader: "uniform float uTime;\nuniform vec3 uGoldDeep;\nuniform vec3 uGoldLit;\nvarying vec2 vUv;\nvarying vec3 vNormal;\nvarying vec3 vPosition;\nvarying vec3 vWorldPos;\nfloat hash(vec2 p) {\n  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);\n}\nfloat noise(vec2 p) {\n  vec2 i = floor(p);\n  vec2 f = fract(p);\n  f = f * f * (3.0 - 2.0 * f);\n  float a = hash(i);\n  float b = hash(i + vec2(1.0, 0.0));\n  float c = hash(i + vec2(0.0, 1.0));\n  float d = hash(i + vec2(1.0, 1.0));\n  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);\n}\nfloat fbm(vec2 p) {\n  float s = 0.0;\n  float a = 0.5;\n  for (int i = 0; i < 4; i++) {\n    s += a * noise(p);\n    p *= 2.03;\n    a *= 0.5;\n  }\n  return s;\n}\nvoid main() {\n  vec2 uv = vUv * 3.2;\n  vec2 warp = vec2(fbm(uv + 0.7), fbm(uv + 3.1));\n  vec2 wuv = uv + warp * 0.6;\n  float vein = fbm(wuv * 2.3);\n  float moss = fbm(uv * 1.5);\n  vec3 N = normalize(vNormal);\n  vec3 V = normalize(cameraPosition - vWorldPos);\n  float fres = pow(1.0 - max(dot(N, V), 0.0), 2.4);\n  float lam = max(dot(N, normalize(vec3(0.45, 0.82, 0.35))), 0.0);\n  float banded = floor(lam * 4.0) / 4.0;\n  vec3 rock = mix(vec3(0.28, 0.29, 0.25), vec3(0.46, 0.47, 0.41), banded);\n  rock = mix(rock, vec3(0.21, 0.31, 0.17), smoothstep(0.34, 0.78, moss) * 0.5);\n  float goldMask = smoothstep(0.55, 0.67, vein);\n  float pulse = 0.82 + 0.18 * sin(uTime * 1.6 + vPosition.y * 6.0 + warp.x * 2.0);\n  vec3 gold = mix(uGoldDeep, uGoldLit, pulse);\n  gold += fres * 0.55;\n  gold += banded * 0.15;\n  vec3 col = mix(rock, gold, goldMask);\n  col = mix(col, vec3(0.24, 0.36, 0.19), clamp(vPosition.y * 0.16 + 0.12, 0.0, 0.28));\n  col += fres * 0.08 * vec3(0.9, 0.95, 1.0);\n  float dith = hash(gl_FragCoord.xy + uTime * 0.6 + 41.0);\n  col += (dith - 0.5) * (1.0 / 24.0);\n  col = floor(col * 24.0 + 0.5) / 24.0;\n  gl_FragColor = vec4(col, 1.0);\n}",
  };

  const mat = compileShader(propShader, propFallbackColor(propShader.uniforms));
  mat.side = THREE.DoubleSide;

  const propGeometry = {
    "primitives": [
        {
            "type": "cylinder",
            "params": {
                "rTop": 0.92,
                "rBottom": 1.28,
                "height": 1.0,
                "segments": 8
            },
            "position": [
                0.0,
                0.5,
                0.0
            ],
            "rotation": [
                0.0,
                0.0,
                0.0
            ],
            "scale": 1
        },
        {
            "type": "cone",
            "params": {
                "rTop": 0.06,
                "rBottom": 0.86,
                "height": 1.05,
                "segments": 7
            },
            "position": [
                0.0,
                1.02,
                0.0
            ],
            "rotation": [
                0.0,
                0.4,
                0.0
            ],
            "scale": 1
        },
        {
            "type": "box",
            "params": {
                "width": 0.86,
                "height": 0.9,
                "depth": 0.34
            },
            "position": [
                0.0,
                0.46,
                0.98
            ],
            "rotation": [
                0.0,
                0.0,
                0.0
            ],
            "scale": 1
        },
        {
            "type": "icosahedron",
            "params": {
                "radius": 0.19,
                "segments": 6
            },
            "position": [
                0.56,
                0.34,
                0.72
            ],
            "rotation": [
                0.3,
                0.9,
                0.1
            ],
            "scale": 1
        },
        {
            "type": "octahedron",
            "params": {
                "radius": 0.16,
                "segments": 6
            },
            "position": [
                -0.52,
                0.26,
                0.78
            ],
            "rotation": [
                0.2,
                0.5,
                0.4
            ],
            "scale": 1
        },
        {
            "type": "dodecahedron",
            "params": {
                "radius": 0.24,
                "segments": 7
            },
            "position": [
                0.72,
                0.2,
                -0.46
            ],
            "rotation": [
                0.5,
                0.2,
                0.3
            ],
            "scale": 1
        }
    ]
};
  const propInstances = [
    {
        "position": [
            -2.2839058556932517,
            1.5167983158538394,
            -0.27712036981563204
        ],
        "rotation": [
            0.0,
            72.02857557744555,
            0.0
        ],
        "scale": 1.0563715073849484
    },
    {
        "position": [
            -0.9989523055311135,
            0.5095335108163707,
            -0.2007591222928483
        ],
        "rotation": [
            0.0,
            127.39313762054492,
            0.0
        ],
        "scale": 0.9047174978828217
    }
];

  for (const inst of propInstances) {
    const propGroup = new THREE.Group();
    for (const prim of propGeometry.primitives || []) {
      const geo = buildPrimitive(prim);
      if (!geo) continue;
      const mesh = new THREE.Mesh(geo, mat);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      applyTransform(mesh, prim);
      propGroup.add(mesh);
    }
    if (inst.position) propGroup.position.set(...inst.position);
    if (inst.rotation) propGroup.rotation.set(
      inst.rotation[0] * Math.PI / 180,
      inst.rotation[1] * Math.PI / 180,
      inst.rotation[2] * Math.PI / 180
    );
    if (inst.scale != null) {
      if (Array.isArray(inst.scale)) propGroup.scale.set(...inst.scale);
      else propGroup.scale.setScalar(inst.scale);
    }
    worldGroup.add(propGroup);
  }

  return mat;
})();


// ============================================================
// POST-PROCESSING
// ============================================================
const composer = null;
const ppPass = null;

// ============================================================
// АНИМАЦИЯ
// ============================================================
const clock = new THREE.Clock();
const propMaterials = [propMaterial_grass_tuft, propMaterial_young_pine, propMaterial_oak_tree, propMaterial_grey_boulder, propMaterial_river_reeds, propMaterial_watchtower, propMaterial_gold_mine];

function animate() {
  requestAnimationFrame(animate);
  const t = clock.getElapsedTime();

  if (skyUniforms && skyUniforms.uTime) skyUniforms.uTime.value = t;
  for (const mat of propMaterials) {
    if (mat && mat.uniforms && mat.uniforms.uTime) {
      mat.uniforms.uTime.value = t;
    }
  }


  controls.update();
  renderer.render(scene, camera);
}

animate();

// Ресайз
window.addEventListener('resize', () => {
  const w = container.clientWidth;
  const h = container.clientHeight;
  if (!w || !h) return;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
  
});

console.log('✅ World loaded: ' + WORLD_NAME);
