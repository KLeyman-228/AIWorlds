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
  p.x += sin(uTime * 1.4 + position.y * 2.6 + position.x) * 0.04 * k;
  p.z += cos(uTime * 1.1 + position.x * 2.1) * 0.03 * k;
  vPosition = p;
  vec4 wp = modelMatrix * vec4(p, 1.0);
  vWorldPos = wp.xyz;
  gl_Position = projectionMatrix * viewMatrix * wp;
}"""

PIXEL_GLSL = """
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p){
  vec2 i = floor(p); vec2 f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(hash(i), hash(i+vec2(1.0,0.0)), f.x), mix(hash(i+vec2(0.0,1.0)), hash(i+vec2(1.0,1.0)), f.x), f.y);
}
float fbm(vec2 p){ return noise(p)*0.57 + noise(p*2.13)*0.28 + noise(p*4.27)*0.15; }
vec3 shadeLit(vec3 albedo, vec3 n, vec3 wp){
  vec3 L = normalize(vec3(0.46, 0.84, 0.26));
  float ndl = max(dot(normalize(n), L), 0.0);
  float wrap = ndl * 0.62 + 0.38;
  float band = floor(wrap * 5.0 + 0.35) / 5.0;
  float lit = mix(wrap, band, 0.55);
  vec3 warm = vec3(1.06, 0.97, 0.84);
  vec3 cool = vec3(0.58, 0.68, 0.88);
  vec3 light = mix(cool, warm, lit);
  float hemi = 0.82 + 0.18 * clamp(n.y, 0.0, 1.0);
  float rim = (1.0 - clamp(n.y, 0.0, 1.0)) * 0.1;
  vec3 c = albedo * light * hemi + albedo * rim * warm;
  float grain = (hash(floor(wp.xz * 18.0)) - 0.5) * 0.035;
  c += vec3(grain, grain * 0.9, grain * 0.7);
  c = max(c, vec3(0.06));
  c = floor(c * 20.0 + 0.5) / 20.0;
  return c;
}
"""

EMISSION_TAIL = """
  c = shadeLit(albedo, vNormal, vPosition);
  c += albedo * uEm * (0.85 + 0.35 * (0.5 + 0.5 * sin(uTime * 2.2 + vPosition.y * 3.5)));
  c = min(c, vec3(1.35));
  gl_FragColor = vec4(c, 1.0);
}"""

BARK_FRAGMENT = """varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vPosition;
uniform vec3 uBark;
uniform vec3 uMoss;
uniform float uEm;
uniform float uTime;""" + PIXEL_GLSL + """
void main() {
  float ang = atan(vPosition.x, vPosition.z);
  vec2 g = vec2(ang * 2.4, vPosition.y * 3.2);
  float ridge = abs(fract(vPosition.y * 6.5 + noise(g) * 0.4) - 0.5);
  float flake = fbm(g * 3.1);
  vec3 albedo = mix(uBark * 0.72, uBark * 1.18, flake);
  albedo = mix(albedo, uBark * 0.48, step(0.18, ridge) * 0.55);
  float moss = (1.0 - clamp(vPosition.y * 0.55, 0.0, 1.0)) * smoothstep(0.42, 0.7, fbm(vPosition.xz * 4.0));
  albedo = mix(albedo, uMoss, moss * 0.7);
  vec3 c = albedo;""" + EMISSION_TAIL

LEAF_FRAGMENT = """varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vPosition;
uniform vec3 uLeaf;
uniform vec3 uLeafDark;
uniform float uEm;
uniform float uTime;""" + PIXEL_GLSL + """
void main() {
  float clump = fbm(vPosition.xz * 2.8 + vUv * 5.0);
  float speck = noise(vPosition.xz * 9.0);
  vec3 lite = uLeaf * 1.22;
  vec3 albedo = mix(uLeafDark, uLeaf, smoothstep(0.28, 0.62, clump));
  albedo = mix(albedo, lite, smoothstep(0.62, 0.88, clump) * (0.55 + 0.45 * clamp(vNormal.y, 0.0, 1.0)));
  albedo = mix(albedo, uLeafDark * 0.55, step(0.84, speck) * 0.45);
  vec3 c = albedo;""" + EMISSION_TAIL

ROCK_FRAGMENT = """varying vec3 vNormal;
varying vec3 vPosition;
uniform vec3 uRock;
uniform vec3 uMoss;
uniform float uEm;
uniform float uTime;""" + PIXEL_GLSL + """
void main() {
  float grain = fbm(vPosition.xy * 3.4 + vPosition.z * 2.2);
  float crack = 1.0 - smoothstep(0.0, 0.08, abs(noise(vPosition.xz * 4.5) - 0.5));
  vec3 albedo = mix(uRock * 0.78, uRock * 1.16, grain);
  albedo = mix(albedo, uRock * 0.42, crack * 0.55);
  float moss = smoothstep(0.35, 0.85, vNormal.y) * smoothstep(0.4, 0.75, fbm(vPosition.xz * 3.0));
  albedo = mix(albedo, uMoss, moss * 0.5);
  vec3 c = albedo;""" + EMISSION_TAIL

FLOWER_STEM = """varying vec3 vNormal;
varying vec3 vPosition;
uniform vec3 uStem;
uniform float uEm;
uniform float uTime;""" + PIXEL_GLSL + """
void main() {
  float n = noise(vPosition.xy * 10.0);
  vec3 albedo = mix(uStem * 0.7, uStem * 1.15, n);
  vec3 c = albedo;""" + EMISSION_TAIL

FLOWER_PETAL = """varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vPosition;
uniform vec3 uPetal;
uniform float uEm;
uniform float uTime;""" + PIXEL_GLSL + """
void main() {
  float r = length(vUv - 0.5) * 2.0;
  vec3 core = vec3(0.98, 0.84, 0.22);
  vec3 albedo = mix(core, uPetal, smoothstep(0.18, 0.42, r));
  albedo = mix(albedo, uPetal * 1.18, noise(vUv * 8.0) * 0.35);
  vec3 c = albedo;""" + EMISSION_TAIL

CRYSTAL_FRAGMENT = """varying vec3 vNormal;
varying vec3 vPosition;
uniform vec3 uCrystal;
uniform float uEm;
uniform float uTime;""" + PIXEL_GLSL + """
void main() {
  float band = abs(fract(vPosition.y * 4.5 + vPosition.x * 2.2) - 0.5);
  vec3 albedo = mix(uCrystal * 0.62, uCrystal * 1.28, smoothstep(0.04, 0.28, band));
  float edge = pow(1.0 - abs(normalize(vNormal).y), 1.6);
  albedo += uCrystal * edge * 0.22;
  vec3 c = albedo;""" + EMISSION_TAIL

HAY_FRAGMENT = """varying vec3 vNormal;
varying vec3 vPosition;
uniform vec3 uHay;
uniform float uEm;
uniform float uTime;""" + PIXEL_GLSL + """
void main() {
  float straw = fract(vPosition.y * 14.0 + vPosition.x * 6.0 + noise(vPosition.xz * 4.0));
  vec3 albedo = mix(uHay * 0.72, uHay * 1.18, step(0.45, straw));
  vec3 c = albedo;""" + EMISSION_TAIL

HOUSE_FRAGMENT = """varying vec3 vNormal;
varying vec3 vPosition;
uniform vec3 uWood;
uniform vec3 uRoof;
uniform float uEm;
uniform float uTime;""" + PIXEL_GLSL + """
void main() {
  float plank = step(0.5, fract(vPosition.y * 7.0 + noise(vPosition.xz * 2.0) * 0.2));
  vec3 wood = mix(uWood * 0.74, uWood * 1.12, plank);
  float is_roof = step(1.05, vPosition.y);
  float tile = step(0.5, fract(vPosition.x * 5.0 + vPosition.z * 0.4));
  vec3 roof = mix(uRoof * 0.7, uRoof * 1.16, tile);
  vec3 albedo = mix(wood, roof, is_roof);
  vec3 c = albedo;""" + EMISSION_TAIL

MUSHROOM_CAP = """varying vec3 vNormal;
varying vec3 vPosition;
uniform vec3 uCap;
uniform float uEm;
uniform float uTime;""" + PIXEL_GLSL + """
void main() {
  float spots = step(0.74, noise(vPosition.xz * 6.5 + vPosition.y * 2.0));
  vec3 albedo = mix(uCap, vec3(0.96, 0.9, 0.72), spots * 0.9);
  vec3 c = albedo;""" + EMISSION_TAIL

TERRAIN_FRAGMENT = """varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vWorldPos;
uniform sampler2D uMap;
uniform vec3 uGrass;
uniform vec3 uDirt;
uniform vec3 uRock;
uniform vec3 uSnow;
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p){
  vec2 i = floor(p); vec2 f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(hash(i), hash(i+vec2(1.0,0.0)), f.x), mix(hash(i+vec2(0.0,1.0)), hash(i+vec2(1.0,1.0)), f.x), f.y);
}
void main() {
  vec3 n = normalize(vNormal);
  float h = clamp(vWorldPos.y / 4.0, 0.0, 1.0);
  float slope = 1.0 - clamp(n.y, 0.0, 1.0);
  float n1 = noise(vWorldPos.xz * 1.7);
  float n2 = noise(vWorldPos.xz * 6.4);
  float n3 = noise(vWorldPos.xz * 14.0);
  vec3 pal = texture2D(uMap, vUv).rgb;
  vec3 grass = mix(uGrass * 0.82, uGrass * 1.22, n1);
  grass = mix(grass, uGrass * 1.35, step(0.72, n2) * 0.35);
  vec3 dirt = mix(uDirt * 0.88, uDirt * 1.12, n2);
  vec3 c = mix(dirt, grass, smoothstep(0.06, 0.26, h));
  c = mix(c, pal, 0.32);
  c = mix(c, mix(uGrass, uDirt, 0.45), smoothstep(0.52, 0.76, h) * (1.0 - slope));
  c = mix(c, uRock * (0.85 + 0.2 * n3), smoothstep(0.22, 0.58, slope));
  c = mix(c, uSnow, smoothstep(0.78, 0.94, h) * (1.0 - slope * 0.5));
  float wrap = max(dot(n, normalize(vec3(0.45, 0.85, 0.25))), 0.0) * 0.55 + 0.48;
  float band = floor(wrap * 5.0 + 0.3) / 5.0;
  c *= mix(vec3(0.64, 0.72, 0.88), vec3(1.06, 0.98, 0.86), mix(wrap, band, 0.5));
  c += (hash(floor(vWorldPos.xz * 16.0)) - 0.5) * 0.035;
  c = max(c, vec3(0.07, 0.09, 0.05));
  c = floor(c * 20.0 + 0.5) / 20.0;
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
PINE_GEO = {
    "primitives": [
        {"type": "cylinder", "params": {"rTop": 0.07, "rBottom": 0.13, "height": 2.05, "segments": 6}, "position": [0.0, 1.025, 0.0]},
        {"type": "cone", "params": {"radius": 0.72, "height": 0.85, "segments": 7}, "position": [0.0, 1.15, 0.0]},
        {"type": "cone", "params": {"radius": 0.56, "height": 0.78, "segments": 7}, "position": [0.0, 1.62, 0.0]},
        {"type": "cone", "params": {"radius": 0.40, "height": 0.72, "segments": 6}, "position": [0.0, 2.08, 0.0]},
        {"type": "cone", "params": {"radius": 0.24, "height": 0.55, "segments": 6}, "position": [0.0, 2.48, 0.0]},
    ]
}
FIR_GEO = {
    "primitives": [
        {"type": "cylinder", "params": {"rTop": 0.06, "rBottom": 0.11, "height": 1.7, "segments": 6}, "position": [0.0, 0.85, 0.0]},
        {"type": "cone", "params": {"radius": 0.62, "height": 0.7, "segments": 7}, "position": [0.0, 1.05, 0.0]},
        {"type": "cone", "params": {"radius": 0.48, "height": 0.68, "segments": 7}, "position": [0.0, 1.48, 0.0]},
        {"type": "cone", "params": {"radius": 0.32, "height": 0.62, "segments": 6}, "position": [0.0, 1.92, 0.0]},
        {"type": "cone", "params": {"radius": 0.18, "height": 0.48, "segments": 6}, "position": [0.0, 2.28, 0.0]},
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
MUSHROOM_GEO = {
    "primitives": [
        {"type": "cylinder", "params": {"rTop": 0.06, "rBottom": 0.09, "height": 0.32, "segments": 6}, "position": [0.0, 0.16, 0.0]},
        {"type": "sphere", "params": {"radius": 0.22, "widthSegments": 7, "heightSegments": 4}, "position": [0.0, 0.38, 0.0], "scale": [1.0, 0.55, 1.0]},
        {"type": "cone", "params": {"radius": 0.24, "height": 0.16, "segments": 7}, "position": [0.0, 0.34, 0.0]},
        {"type": "sphere", "params": {"radius": 0.05, "widthSegments": 5, "heightSegments": 4}, "position": [0.12, 0.36, 0.06]},
    ]
}
CRYSTAL_GEO = {
    "primitives": [
        {"type": "octahedron", "params": {"radius": 0.42}, "position": [0.0, 0.46, 0.0]},
        {"type": "octahedron", "params": {"radius": 0.22}, "position": [0.18, 0.28, 0.08], "rotation": [18.0, 25.0, 0.0]},
        {"type": "tetrahedron", "params": {"radius": 0.16}, "position": [-0.16, 0.22, -0.1], "rotation": [12.0, -20.0, 8.0]},
        {"type": "cylinder", "params": {"rTop": 0.04, "rBottom": 0.1, "height": 0.18, "segments": 6}, "position": [0.0, 0.08, 0.0]},
    ]
}
RUIN_GEO = {
    "primitives": [
        {"type": "box", "params": {"width": 1.1, "height": 0.22, "depth": 1.1}, "position": [0.0, 0.11, 0.0]},
        {"type": "cylinder", "params": {"rTop": 0.12, "rBottom": 0.16, "height": 1.05, "segments": 6}, "position": [-0.32, 0.64, -0.28]},
        {"type": "cylinder", "params": {"rTop": 0.11, "rBottom": 0.15, "height": 0.72, "segments": 6}, "position": [0.34, 0.48, 0.26], "rotation": [12.0, 0.0, 8.0]},
        {"type": "box", "params": {"width": 0.7, "height": 0.16, "depth": 0.28}, "position": [0.08, 0.86, -0.1], "rotation": [0.0, 18.0, -14.0]},
        {"type": "box", "params": {"width": 0.22, "height": 0.18, "depth": 0.22}, "position": [0.36, 0.2, -0.34]},
    ]
}
HAY_GEO = {
    "primitives": [
        {"type": "sphere", "params": {"radius": 0.42, "widthSegments": 7, "heightSegments": 5}, "position": [0.0, 0.34, 0.0], "scale": [1.15, 0.72, 0.95]},
        {"type": "sphere", "params": {"radius": 0.28, "widthSegments": 6, "heightSegments": 4}, "position": [0.0, 0.62, 0.0], "scale": [0.9, 0.7, 0.9]},
        {"type": "cylinder", "params": {"rTop": 0.04, "rBottom": 0.05, "height": 0.55, "segments": 5}, "position": [0.0, 0.42, 0.0], "rotation": [90.0, 20.0, 0.0]},
        {"type": "cone", "params": {"radius": 0.12, "height": 0.16, "segments": 6}, "position": [0.0, 0.78, 0.0]},
    ]
}
CACTUS_GEO = {
    "primitives": [
        {"type": "cylinder", "params": {"rTop": 0.12, "rBottom": 0.16, "height": 1.35, "segments": 7}, "position": [0.0, 0.675, 0.0]},
        {"type": "sphere", "params": {"radius": 0.13, "widthSegments": 6, "heightSegments": 4}, "position": [0.0, 1.35, 0.0]},
        {"type": "cylinder", "params": {"rTop": 0.07, "rBottom": 0.08, "height": 0.42, "segments": 6}, "position": [0.22, 0.82, 0.0], "rotation": [0.0, 0.0, 72.0]},
        {"type": "cylinder", "params": {"rTop": 0.06, "rBottom": 0.07, "height": 0.28, "segments": 6}, "position": [0.38, 1.02, 0.0]},
        {"type": "cylinder", "params": {"rTop": 0.06, "rBottom": 0.07, "height": 0.34, "segments": 6}, "position": [-0.2, 0.7, 0.04], "rotation": [0.0, 0.0, -68.0]},
    ]
}

PROP_TEMPLATES = {
    "oak": {"kind": "tree", "geometry": OAK_GEO, "defaults": {"bark": [0.38, 0.22, 0.10], "leaf": [0.22, 0.54, 0.14], "leaf_dark": [0.10, 0.32, 0.07], "moss": [0.18, 0.38, 0.10]}},
    "birch": {"kind": "tree", "geometry": BIRCH_GEO, "defaults": {"bark": [0.88, 0.84, 0.76], "leaf": [0.30, 0.60, 0.16], "leaf_dark": [0.12, 0.32, 0.07], "moss": [0.20, 0.38, 0.12]}},
    "pine": {"kind": "tree", "geometry": PINE_GEO, "defaults": {"bark": [0.34, 0.20, 0.10], "leaf": [0.12, 0.40, 0.18], "leaf_dark": [0.05, 0.22, 0.09], "moss": [0.14, 0.30, 0.10]}},
    "fir": {"kind": "tree", "geometry": FIR_GEO, "defaults": {"bark": [0.30, 0.16, 0.08], "leaf": [0.10, 0.36, 0.16], "leaf_dark": [0.04, 0.18, 0.08], "moss": [0.12, 0.26, 0.10]}},
    "bush": {"kind": "tree", "geometry": BUSH_GEO, "defaults": {"bark": [0.36, 0.20, 0.10], "leaf": [0.20, 0.52, 0.14], "leaf_dark": [0.08, 0.28, 0.07], "moss": [0.16, 0.34, 0.10]}},
    "boulder": {"kind": "rock", "geometry": BOULDER_GEO, "defaults": {"rock": [0.52, 0.48, 0.44], "moss": [0.20, 0.38, 0.12]}},
    "stone": {"kind": "rock", "geometry": BOULDER_GEO, "defaults": {"rock": [0.56, 0.50, 0.42], "moss": [0.18, 0.34, 0.12]}},
    "flower": {"kind": "flower", "geometry": FLOWER_GEO, "defaults": {"petal": [0.90, 0.38, 0.50], "stem": [0.18, 0.48, 0.12]}},
    "mushroom": {"kind": "mushroom", "geometry": MUSHROOM_GEO, "defaults": {"cap": [0.82, 0.18, 0.16], "stem": [0.90, 0.82, 0.66]}},
    "crystal": {"kind": "crystal", "geometry": CRYSTAL_GEO, "defaults": {"crystal": [0.38, 0.72, 0.96], "em": 0.85}},
    "ruin": {"kind": "ruin", "geometry": RUIN_GEO, "defaults": {"rock": [0.58, 0.52, 0.44], "moss": [0.20, 0.38, 0.14]}},
    "hay": {"kind": "hay", "geometry": HAY_GEO, "defaults": {"hay": [0.86, 0.68, 0.22]}},
    "cactus": {"kind": "tree", "geometry": CACTUS_GEO, "defaults": {"bark": [0.20, 0.50, 0.18], "leaf": [0.26, 0.62, 0.18], "leaf_dark": [0.10, 0.34, 0.10], "moss": [0.18, 0.42, 0.14]}},
}

TEMPLATE_ALIASES = {
    "oak": "oak", "tree": "oak", "trees": "oak",
    "birch": "birch",
    "pine": "pine", "ёлка": "pine", "елка": "pine", "ель": "fir",
    "fir": "fir", "spruce": "fir", "christmas": "fir",
    "bush": "bush", "shrub": "bush",
    "boulder": "boulder", "rock": "boulder", "stone": "stone", "rocks": "boulder",
    "flower": "flower", "flowers": "flower",
    "mushroom": "mushroom", "mushrooms": "mushroom", "fungus": "mushroom", "гриб": "mushroom",
    "crystal": "crystal", "crystals": "crystal", "gem": "crystal", "кристалл": "crystal",
    "ruin": "ruin", "ruins": "ruin", "ruined": "ruin", "руина": "ruin", "руины": "ruin",
    "hay": "hay", "haystack": "hay", "haybale": "hay", "стог": "hay",
    "cactus": "cactus", "cacti": "cactus", "кактус": "cactus",
}

TERRAIN_TEMPLATE_UNIFORMS = {
    "uGrass": {"type": "vec3", "value": [0.22, 0.52, 0.16]},
    "uDirt": {"type": "vec3", "value": [0.42, 0.28, 0.12]},
    "uRock": {"type": "vec3", "value": [0.52, 0.48, 0.42]},
    "uSnow": {"type": "vec3", "value": [0.90, 0.92, 0.94]},
    "uTime": {"type": "float", "value": 0},
}


def _match_template(text: str) -> str | None:
    key = str(text or "").lower().strip()
    if not key:
        return None
    if key in PROP_TEMPLATES:
        return key
    if key in TEMPLATE_ALIASES:
        return TEMPLATE_ALIASES[key]
    for alias, tid in sorted(TEMPLATE_ALIASES.items(), key=lambda item: -len(item[0])):
        if alias in key:
            return tid
    return None


def resolve_template_id(name: str, explicit=None) -> str | None:
    return _match_template(explicit) or _match_template(name)


def _em_value(value) -> float:
    while isinstance(value, (list, tuple)) and value:
        value = value[0]
    try:
        return max(0.0, min(2.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _rgb01(value, fallback):
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return list(fallback)
    nums = [float(value[0]), float(value[1]), float(value[2])]
    if max(nums) > 1.5:
        nums = [n / 255.0 for n in nums]
    return [max(0.0, min(1.0, n)) for n in nums]


def _parse_size(value, default=1.0) -> float:
    while isinstance(value, (list, tuple)) and value:
        value = value[0]
    try:
        return max(0.25, min(8.0, float(value)))
    except (TypeError, ValueError):
        return default


def _scale_range_for_size(size: float, explicit=None) -> list[float]:
    if isinstance(explicit, (list, tuple)) and len(explicit) >= 2:
        try:
            lo, hi = float(explicit[0]), float(explicit[1])
            if hi < lo:
                lo, hi = hi, lo
            return [max(0.2, min(8.0, lo)), max(0.2, min(8.0, hi))]
        except (TypeError, ValueError):
            pass
    s = _parse_size(size, 1.0)
    return [max(0.2, s * 0.88), min(8.0, s * 1.12)]


def _scale_geometry(geometry: dict, scale: float) -> dict:
    geo = deepcopy(geometry)
    s = _parse_size(scale, 1.0)
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
    geo_scale = _parse_size(spec.get("size") or params.get("size") or 1.0)
    emission = _em_value(spec.get("em") or spec.get("emission") or params.get("em") or defaults.get("em") or 0)
    uniforms = {
        "uTime": {"type": "float", "value": 0},
        "uEm": {"type": "float", "value": emission},
    }
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
    elif tmpl["kind"] == "rock" or tmpl["kind"] == "ruin":
        rock = _rgb01(spec.get("rock") or spec.get("color") or params.get("rock"), defaults["rock"])
        moss = _rgb01(spec.get("moss") or params.get("moss"), defaults["moss"])
        uniforms.update({
            "uRock": {"type": "vec3", "value": rock},
            "uMoss": {"type": "vec3", "value": moss},
        })
        shader["fragment"] = ROCK_FRAGMENT
    elif tmpl["kind"] == "crystal":
        crystal = _rgb01(spec.get("crystal") or spec.get("color") or params.get("crystal"), defaults["crystal"])
        uniforms["uCrystal"] = {"type": "vec3", "value": crystal}
        shader["fragment"] = CRYSTAL_FRAGMENT
    elif tmpl["kind"] == "hay":
        hay = _rgb01(spec.get("hay") or spec.get("color") or params.get("hay"), defaults["hay"])
        uniforms["uHay"] = {"type": "vec3", "value": hay}
        shader["fragment"] = HAY_FRAGMENT
    elif tmpl["kind"] == "mushroom":
        cap = _rgb01(spec.get("cap") or spec.get("color") or params.get("cap"), defaults["cap"])
        stem = _rgb01(spec.get("stem") or params.get("stem"), defaults["stem"])
        uniforms.update({
            "uCap": {"type": "vec3", "value": cap},
            "uStem": {"type": "vec3", "value": stem},
        })
        shader["fragment"] = FLOWER_STEM
        shader["leaf_fragment"] = MUSHROOM_CAP
        shader["leaf_vertex"] = STANDARD_VERTEX_SHADER
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
            "count": int(spec.get("count") or 18),
            "distribution": spec.get("distribution") or "scattered",
            "scale_range": _scale_range_for_size(geo_scale, spec.get("scale_range") or params.get("scale_range")),
        }
    elif "scale_range" not in instances:
        instances = dict(instances)
        instances["scale_range"] = _scale_range_for_size(geo_scale, spec.get("scale_range"))
    return {
        "name": spec.get("name") or tid,
        "template": tid,
        "size": geo_scale,
        "geometry": deepcopy(tmpl["geometry"]),
        "shader": shader,
        "instances": instances,
        "category": spec.get("category"),
    }


def instantiate_terrain_shader(params=None) -> dict:
    p = dict(params) if isinstance(params, dict) else {}
    uniforms = deepcopy(TERRAIN_TEMPLATE_UNIFORMS)
    for src, dst in (("grass", "uGrass"), ("dirt", "uDirt"), ("rock", "uRock"), ("snow", "uSnow")):
        if p.get(src):
            uniforms[dst]["value"] = _rgb01(p.get(src), uniforms[dst]["value"])
    if p.get("sand") and not p.get("dirt"):
        uniforms["uDirt"]["value"] = _rgb01(p.get("sand"), uniforms["uDirt"]["value"])
    return {
        "vertex": STANDARD_VERTEX_SHADER,
        "fragment": TERRAIN_FRAGMENT,
        "uniforms": uniforms,
    }


BUILDING_WORDS = (
    "house", "home", "hut", "cabin", "cottage", "barn", "mill", "tower",
    "shack", "shed", "temple", "church", "windmill", "дом", "домик", "хижина",
    "изба", "башня", "мельница", "сарай",
)


BIOME_PALETTES = {
    "snow": {
        "grass": [0.78, 0.86, 0.92],
        "dirt": [0.46, 0.44, 0.42],
        "rock": [0.58, 0.60, 0.64],
        "snow": [0.95, 0.97, 0.99],
        "leaf": [0.82, 0.90, 0.96],
        "leaf_dark": [0.42, 0.52, 0.60],
        "bark": [0.28, 0.18, 0.12],
        "moss": [0.55, 0.62, 0.68],
        "rock_prop": [0.62, 0.64, 0.68],
        "gradient": [
            {"height": 0.0, "color": [150, 155, 160]},
            {"height": 0.18, "color": [200, 214, 226]},
            {"height": 0.55, "color": [226, 234, 242]},
            {"height": 1.0, "color": [245, 248, 252]},
        ],
    },
    "desert": {
        "grass": [0.72, 0.58, 0.28],
        "dirt": [0.62, 0.46, 0.22],
        "rock": [0.58, 0.48, 0.34],
        "snow": [0.86, 0.78, 0.58],
        "leaf": [0.42, 0.55, 0.18],
        "leaf_dark": [0.22, 0.32, 0.10],
        "bark": [0.42, 0.28, 0.12],
        "moss": [0.40, 0.36, 0.16],
        "rock_prop": [0.62, 0.50, 0.32],
        "gradient": [
            {"height": 0.0, "color": [140, 100, 48]},
            {"height": 0.4, "color": [186, 148, 72]},
            {"height": 1.0, "color": [150, 122, 86]},
        ],
    },
    "swamp": {
        "grass": [0.22, 0.36, 0.16],
        "dirt": [0.22, 0.18, 0.10],
        "rock": [0.32, 0.30, 0.24],
        "snow": [0.40, 0.44, 0.32],
        "leaf": [0.18, 0.38, 0.14],
        "leaf_dark": [0.08, 0.18, 0.06],
        "bark": [0.22, 0.14, 0.08],
        "moss": [0.20, 0.34, 0.12],
        "rock_prop": [0.30, 0.28, 0.22],
        "gradient": [
            {"height": 0.0, "color": [48, 40, 22]},
            {"height": 0.35, "color": [56, 92, 40]},
            {"height": 1.0, "color": [82, 76, 58]},
        ],
    },
    "autumn": {
        "grass": [0.62, 0.42, 0.14],
        "dirt": [0.40, 0.24, 0.10],
        "rock": [0.48, 0.42, 0.34],
        "snow": [0.72, 0.58, 0.32],
        "leaf": [0.82, 0.38, 0.10],
        "leaf_dark": [0.42, 0.14, 0.06],
        "bark": [0.32, 0.18, 0.08],
        "moss": [0.40, 0.28, 0.10],
        "rock_prop": [0.48, 0.40, 0.32],
        "gradient": [
            {"height": 0.0, "color": [102, 62, 26]},
            {"height": 0.4, "color": [158, 108, 36]},
            {"height": 1.0, "color": [122, 108, 86]},
        ],
    },
}

FOLIAGE_TINTS = (
    (("син", "голуб", "blue", "azure", "cyan"), [0.18, 0.42, 0.95], [0.08, 0.18, 0.48]),
    (("красн", "алы", "red", "crimson"), [0.92, 0.18, 0.14], [0.42, 0.08, 0.06]),
    (("золот", "жёлт", "желт", "gold", "yellow"), [0.95, 0.78, 0.18], [0.48, 0.32, 0.06]),
    (("фиолет", "lilac", "purple", "violet"), [0.62, 0.28, 0.92], [0.28, 0.10, 0.42]),
    (("чёрн", "черн", "black"), [0.12, 0.12, 0.14], [0.05, 0.05, 0.06]),
)


def infer_palette(prompt: str) -> dict:
    text = (prompt or "").lower()
    biome = None
    if any(w in text for w in ("снег", "снежн", "зим", "ледян", "snow", "winter", "frost", "ice", "arctic")):
        biome = "snow"
    elif any(w in text for w in ("пустын", "дюн", "саванн", "desert", "dune", "sahara")):
        biome = "desert"
    elif any(w in text for w in ("болот", "топк", "swamp", "marsh", "bog")):
        biome = "swamp"
    elif any(w in text for w in ("осень", "осенн", "autumn", "fall")):
        biome = "autumn"
    foliage = None
    foliage_dark = None
    for words, leaf, dark in FOLIAGE_TINTS:
        if any(word in text for word in words):
            foliage, foliage_dark = leaf, dark
            break
    if biome == "snow" and foliage is None:
        foliage = BIOME_PALETTES["snow"]["leaf"]
        foliage_dark = BIOME_PALETTES["snow"]["leaf_dark"]
    glow = any(w in text for w in ("свеч", "glow", "emiss", "магич", "glowing", "neon", "сия"))
    return {
        "biome": biome,
        "terrain": dict(BIOME_PALETTES[biome]) if biome else None,
        "leaf": foliage,
        "leaf_dark": foliage_dark,
        "glow": glow,
    }


def apply_palette_to_prop(spec: dict, palette: dict, prompt: str = "") -> dict:
    out = dict(spec or {})
    params = dict(out.get("params") or {}) if isinstance(out.get("params"), dict) else {}
    text = f"{prompt or ''} {out.get('name') or ''} {out.get('template') or ''}".lower()
    leaf = palette.get("leaf") if palette else None
    dark = palette.get("leaf_dark") if palette else None
    if leaf is None:
        for words, tint, tint_dark in FOLIAGE_TINTS:
            if any(word in text for word in words):
                leaf, dark = tint, tint_dark
                break
    if leaf:
        out["leaf"] = leaf
        out["leaf_dark"] = dark or [c * 0.45 for c in leaf]
        params["leaf"] = out["leaf"]
        params["leaf_dark"] = out["leaf_dark"]
        out["petal"] = params["petal"] = out.get("petal") or leaf
        terrain = (palette or {}).get("terrain") or {}
        if terrain.get("bark") and "bark" not in out and "bark" not in params:
            out["bark"] = params["bark"] = terrain["bark"]
        if terrain.get("moss") and "moss" not in out:
            out["moss"] = params["moss"] = terrain["moss"]
        if terrain.get("rock_prop") and "rock" not in out:
            out["rock"] = params["rock"] = terrain["rock_prop"]
        out["crystal"] = params.get("crystal") or out.get("crystal") or leaf
        params["crystal"] = out["crystal"]
    if palette and palette.get("glow"):
        em = max(_em_value(out.get("em") or params.get("em") or 0), 0.85)
        out["em"] = params["em"] = em
    if params:
        out["params"] = params
    return out


def apply_palette_to_terrain(material, palette: dict) -> dict:
    mat = dict(material) if isinstance(material, dict) else {}
    terrain = (palette or {}).get("terrain")
    if not terrain:
        return mat
    for key in ("grass", "dirt", "rock", "snow"):
        if terrain.get(key):
            mat[key] = list(terrain[key])
    return mat


def tint_spec_from_prompt(spec: dict, prompt: str) -> dict:
    return apply_palette_to_prop(spec, infer_palette(prompt), prompt)


def wants_custom(spec: dict) -> bool:
    flag = spec.get("custom") or spec.get("mode") or spec.get("kind")
    tpl = str(spec.get("template") or spec.get("tpl") or "").lower()
    name = str(spec.get("name") or "").lower()
    if str(flag).lower() in ("custom", "gen", "1", "true", "yes") or tpl in ("x", "custom", "gen"):
        return True
    if any(word in name for word in BUILDING_WORDS):
        return True
    if resolve_template_id(spec.get("name"), spec.get("template") or spec.get("tpl")):
        return False
    return True
