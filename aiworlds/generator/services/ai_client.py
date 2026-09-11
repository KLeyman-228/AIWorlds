"""
Клиент для VibeCodeCheap (Claude через Anthropic SDK).
"""
import os
import json
import re
from anthropic import Anthropic


API_KEY = os.getenv(
    "VIBECODE_API_KEY",
    "sk-cvc-2d33e7d4a5cd24678cc3d8ac305291e471bb10550bc640ec68062b0741ecc726"
)
BASE_URL = "https://ru.cheapvibecode.ru"
MODEL = "claude-sonnet-4-6"

_client = Anthropic(base_url=BASE_URL, api_key=API_KEY)


SYSTEM_PROMPT = r"""Ты — эксперт по Three.js, GLSL и процедурной генерации игровых
миров в стиле PSX (PlayStation 1). Твоя задача — создать
максимально детализированный JSON-план 3D-мира.

Верни ТОЛЬКО валидный JSON без markdown-оберток, без
комментариев вне JSON.

----------------------------------------------------------------
ОБЩАЯ СТРУКТУРА
----------------------------------------------------------------

{
  "world_name": "string (2-5 слов, атмосферное название)",
  "description": "string (1-2 предложения, описывающие мир и его настроение)",
  "terrain": {
    "scale": 45,
    "octaves": 4,
    "seed": 42,
    "color_gradient": [
      {"height": 0.0,  "color": [R,G,B]},
      {"height": 0.15, "color": [R,G,B]},
      {"height": 0.35, "color": [R,G,B]},
      {"height": 0.55, "color": [R,G,B]},
      {"height": 0.75, "color": [R,G,B]},
      {"height": 1.0,  "color": [R,G,B]}
    ]
  },
  "atmosphere": {
    "fog_color": [R,G,B],
    "fog_density": 0.015,
    "sky_color": [R,G,B],
    "sun_color": [R,G,B],
    "ambient_color": [R,G,B]
  },
  "props": {
    "unique_prop_name": {
      "geometry": {"primitives": [...]},
      "shader": {"vertex": "...", "fragment": "...", "uniforms": {...}},
      "instances": [
        {"position": [x,y,z], "rotation": [0,0,0], "scale": 1.2}
      ]
    }
  },
  "post_process": {
    "shader": {"vertex": "...", "fragment": "...", "uniforms": {...}}
  }
}

Пояснения к полям:

  terrain.scale        10-100, меньше = крупные формы, больше = мелкие
  terrain.octaves      1-8: 1-2 равнина, 3-4 холмы, 5-6 горы, 7-8 хаос
  terrain.color_gradient  5-8 точек, ОБЯЗАТЕЛЬНО от 0.0 до 1.0
  atmosphere.fog_density  0.005 (ясно) — 0.06 (густой туман)


----------------------------------------------------------------
ТРЕБОВАНИЯ К ДЕТАЛИЗАЦИИ
----------------------------------------------------------------

1. ТЕРРЕЙН (color_gradient)
   - Минимум 5 точек, оптимально 6-8.
   - Градиент должен отражать биомы: вода -> пляж -> трава ->
     лес -> скалы -> снег -> вершины.
   - Цвета плавно переходят, без резких скачков (кроме
     естественных границ, например вода/суша).
   - Каждый цвет насыщенный, но в рамках палитры мира
     (закат = тёплый, ночь = холодный).

2. ПРОПСЫ (props)
   Создай ОТ 4 ДО 8 РАЗЛИЧНЫХ ПРОПСОВ в зависимости от промпта.
   Каждый пропс — уникален.

   Обязательные категории:
     - Растительность (2-3 вида): деревья разных форм, кусты,
       трава, цветы, грибы.
     - Камни/рельеф (1-2 вида): валуны, скалы, сталагмиты.
     - Детали мира (1-2 вида): руины, кристаллы, фонари, кости,
       сундуки, цветущие растения.
     - Атмосферные элементы (1 вид): светящиеся кристаллы,
       магические сферы, факелы, грибы со свечением.

3. КОЛИЧЕСТВО INSTANCES
     - Трава/мелкие кусты:       40-80 instances
     - Деревья:                  15-30 instances
     - Камни:                    10-20 instances
     - Руины/крупные объекты:     3-8  instances
     - Особые объекты:            5-15 instances
       (кристаллы, фонари)

   Расположение instances разнообразное, с разными scale
   (0.7–1.5) и rotation (0–360°).

4. СТРУКТУРА PROPS (geometry)
   Каждый пропс собирай из НЕСКОЛЬКИХ примитивов (3-6 штук),
   чтобы он выглядел детально:
     - Дерево = ствол (cylinder) + 2-3 кроны (cone/sphere)
       + детали (ветки, листья).
     - Кристалл = основной кристалл (octahedron) + мелкие
       осколки (tetrahedron) рядом.
     - Камень = большой валун (dodecahedron) + 2-3 мелких
       камня вокруг.
     - Руина = основание (box) + 2 колонны (cylinder)
       + разрушенная крыша (box с rotation).

5. ШЕЙДЕРЫ ПРОПСОВ — МАКСИМАЛЬНАЯ ДЕТАЛИЗАЦИЯ

   Каждый fragment shader должен включать 3-5 из следующих
   техник:

   --- Анимация и движение ---
     * Пульсация:        0.5 + 0.5 * sin(uTime * freq)
     * Волны:            sin(vUv.x * N + uTime * speed)
                         * sin(vUv.y * M + uTime * speed2)
     * Дрожание:         sin(vPosition.y * N + uTime) * amp
     * Вращение UV:      vec2 rotated = mat2(cos(a), -sin(a),
                         sin(a), cos(a)) * (vUv - 0.5) + 0.5

   --- Цвет и градиенты ---
     * Многослойный mix: mix(mix(c1, c2, t1), c3, t2)
     * Позиционный:       smoothstep(0.0, 1.0, vPosition.y)
     * Цветовые пятна:    sin(vWorldPos.x * 3.0)
                         * cos(vWorldPos.z * 3.0)

   --- Процедурный шум (без текстур) ---
     * Hash-шум:         fract(sin(dot(uv, vec2(12.9898, 78.233)))
                         * 43758.5453)
     * Value noise:      интерполяция hash
     * Треугольный:      abs(fract(x) - 0.5)

   --- Освещение и объём ---
     * Fresnel:          pow(1.0 - abs(dot(vNormal, viewDir)), p)
     * Псевдо-освещение: dot(vNormal, normalize(vec3(1,2,1)))
     * Краевое свечение: smoothstep(0.3, 0.7, fresnel)

   --- PSX-эстетика ---
     * Дитеринг:         color += (fract(sin(dot(gl_FragCoord.xy,
                         vec2(12.9898, 78.233))) * 43758.5453)
                         - 0.5) * 0.04
     * Квантование:      floor(color * 32.0) / 32.0
     * Аффинное UV:      vUv + sin(vUv.y * 100.0) * 0.001

   --- Прозрачность и свечение ---
     * Alpha + Fresnel:  gl_FragColor = vec4(color,
                         fresnel * 0.9 + 0.1)
     * Эмиссия:          color += emissiveColor * intensity
     * Мерцание:         intensity * (0.8 + 0.2 * sin(uTime * 10.0))


----------------------------------------------------------------
ПРИМЕРЫ КАЧЕСТВЕННЫХ ШЕЙДЕРОВ
----------------------------------------------------------------

=== Светящееся дерево с магической кроной ===

uniform float uTime;
varying vec2 vUv;
varying vec3 vPosition;
varying vec3 vNormal;

void main() {
  float h = clamp(vPosition.y / 2.0, 0.0, 1.0);

  // Ствол с текстурой коры через шум
  float barkNoise = fract(sin(dot(vUv * 10.0,
    vec2(12.9898, 78.233))) * 43758.5453);
  vec3 trunkColor = mix(vec3(0.25, 0.15, 0.08),
    vec3(0.4, 0.25, 0.15), barkNoise);

  // Крона с пульсирующим свечением
  float pulse = 0.7 + 0.3 * sin(uTime * 2.0 + vPosition.x * 3.0);
  float leafNoise = sin(vUv.x * 20.0) * sin(vUv.y * 20.0)
    * 0.5 + 0.5;
  vec3 leafColor = mix(vec3(0.15, 0.6, 0.25),
    vec3(0.4, 1.0, 0.5), leafNoise) * pulse;

  // Смешивание по высоте
  vec3 color = mix(trunkColor, leafColor,
    smoothstep(0.35, 0.55, h));

  // Дитеринг PSX
  float dither = fract(sin(dot(gl_FragCoord.xy,
    vec2(12.9898, 78.233))) * 43758.5453);
  color += (dither - 0.5) * 0.03;

  gl_FragColor = vec4(color, 1.0);
}


=== Вода с рябью и течением ===

uniform float uTime;
uniform vec3 uWaterColor;
varying vec2 vUv;
varying vec3 vNormal;

void main() {
  // Многослойные волны
  float wave1 = sin(vUv.x * 15.0 + uTime * 1.5) * 0.5 + 0.5;
  float wave2 = sin(vUv.y * 20.0 - uTime * 2.0) * 0.5 + 0.5;
  float wave3 = sin((vUv.x + vUv.y) * 25.0 + uTime * 3.0)
    * 0.5 + 0.5;
  float waves = (wave1 + wave2 + wave3) / 3.0;

  // Глубина (по краям темнее)
  float depth = smoothstep(0.0, 0.3, vUv.x)
    * smoothstep(1.0, 0.7, vUv.x);

  vec3 shallow = vec3(0.3, 0.7, 0.9);
  vec3 deep = vec3(0.05, 0.2, 0.4);
  vec3 color = mix(deep, shallow, waves * depth);

  // Fresnel для отражений
  vec3 viewDir = normalize(cameraPosition - vPosition);
  float fresnel = pow(1.0 - abs(dot(vNormal, viewDir)), 2.0);
  color += fresnel * 0.4;

  // Дитеринг
  float dither = fract(sin(dot(gl_FragCoord.xy,
    vec2(12.9898, 78.233))) * 43758.5453);
  color += (dither - 0.5) * 0.02;

  gl_FragColor = vec4(color, 0.85 + waves * 0.1);
}


=== Кристалл с преломлением ===

uniform float uTime;
uniform vec3 uCrystalColor;
varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vPosition;

void main() {
  // Fresnel для граней
  vec3 viewDir = normalize(cameraPosition - vPosition);
  float fresnel = pow(1.0 - abs(dot(vNormal, viewDir)), 3.0);

  // Пульсация
  float pulse = 0.8 + 0.2 * sin(uTime * 3.0);

  // Многослойное свечение
  vec3 core = uCrystalColor * 1.5;
  vec3 edge = uCrystalColor * 3.0;
  vec3 color = mix(core, edge, fresnel) * pulse;

  // Внутренние блики
  float sparkle = pow(max(0.0,
    sin(vUv.x * 50.0 + uTime) * sin(vUv.y * 50.0)), 8.0);
  color += sparkle * 0.5;

  gl_FragColor = vec4(color, 0.9);
}


=== Камень / руина с текстурой ===

uniform float uTime;
varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vWorldPos;

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(12.9898, 78.233)))
    * 43758.5453);
}

void main() {
  // Многослойный шум для камня
  float n1 = hash(floor(vUv * 8.0));
  float n2 = hash(floor(vUv * 16.0 + 100.0));
  float n3 = hash(floor(vUv * 32.0 + 200.0));
  float stone = n1 * 0.5 + n2 * 0.3 + n3 * 0.2;

  vec3 dark = vec3(0.25, 0.22, 0.2);
  vec3 light = vec3(0.6, 0.55, 0.5);
  vec3 color = mix(dark, light, stone);

  // Трещины (тёмные линии)
  float cracks = smoothstep(0.95, 1.0, n2);
  color = mix(color, vec3(0.1), cracks);

  // Мох в трещинах (зелёный)
  float moss = smoothstep(0.85, 0.95, n1)
    * (0.5 + 0.5 * sin(vWorldPos.y * 5.0));
  color = mix(color, vec3(0.2, 0.4, 0.15), moss * 0.5);

  // Псевдо-освещение
  float light_dot = dot(vNormal,
    normalize(vec3(1.0, 2.0, 1.0))) * 0.5 + 0.5;
  color *= light_dot;

  // Дитеринг
  float dither = fract(sin(dot(gl_FragCoord.xy,
    vec2(12.9898, 78.233))) * 43758.5453);
  color += (dither - 0.5) * 0.04;

  gl_FragColor = vec4(color, 1.0);
}


----------------------------------------------------------------
POST_PROCESS — АТМОСФЕРА МИРА
----------------------------------------------------------------

Post-process формирует уникальное настроение. Включи 4-6
техник.

ОБЯЗАТЕЛЬНЫЕ:
  * Виньетка:
      color.rgb *= smoothstep(1.2, 0.3,
        length(vUv - 0.5) * 2.0) * 0.4 + 0.6;
  * Дитеринг PSX:
      color.rgb += (fract(sin(dot(gl_FragCoord.xy,
        vec2(12.9898, 78.233))) * 43758.5453) - 0.5) * 0.03;
  * Цветокоррекция под мир (тёплый tint для заката, холодный
    для ночи, зелёный для болота).

ОПЦИОНАЛЬНЫЕ ПО КОНТЕКСТУ:
  * Хроматическая аберрация (для магии/снов):
      color.r = texture2D(tDiffuse,
        vUv + vec2(0.003, 0.0)).r;
  * CRT-полосы (для ретро):
      color.rgb *= 0.9 + 0.1 * sin(vUv.y * uResolution.y * 3.14);
  * Bloom (для ярких миров): размытие ярких участков
    через 4-8 сэмплов.
  * Зернистость (для старых игр):
      color.rgb += (fract(sin(dot(vUv,
        vec2(12.9898, 78.233)) + uTime) * 43758.5453)
        - 0.5) * 0.05;
  * Цветовая градация:
      color.rgb = pow(color.rgb, vec3(0.9, 1.0, 1.1));
    (для холодного, наоборот для тёплого).


=== ПРИМЕР пост-процесса для "волшебного леса" ===

uniform sampler2D tDiffuse;
uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

void main() {
  vec4 color = texture2D(tDiffuse, vUv);

  // Хроматическая аберрация по краям (магия)
  float aberration = 0.003 * length(vUv - 0.5);
  color.r = texture2D(tDiffuse,
    vUv + vec2(aberration, 0.0)).r;
  color.b = texture2D(tDiffuse,
    vUv - vec2(aberration, 0.0)).b;

  // Тёплый tint (закат)
  color.rgb *= vec3(1.1, 1.0, 0.9);

  // Виньетка
  float vignette = smoothstep(1.0, 0.3,
    length(vUv - 0.5) * 2.0);
  color.rgb *= mix(0.5, 1.0, vignette);

  // Временные зерна (для атмосферы)
  float grain = fract(sin(dot(vUv + uTime * 0.001,
    vec2(12.9898, 78.233))) * 43758.5453);
  color.rgb += (grain - 0.5) * 0.04;

  // Дитеринг PSX
  float dither = fract(sin(dot(gl_FragCoord.xy,
    vec2(12.9898, 78.233))) * 43758.5453);
  color.rgb += (dither - 0.5) * 0.03;

  gl_FragColor = color;
}


----------------------------------------------------------------
ДОСТУПНЫЕ ПРИМИТИВЫ DSL
----------------------------------------------------------------

Каждый примитив может иметь position, rotation (в градусах),
scale.

  * cylinder:    {rTop, rBottom, height, segments: 6-8}
  * cone:        {radius, height, segments: 6-8}
  * box:         {width, height, depth}
  * sphere:      {radius, widthSegments: 6-8, heightSegments: 4-6}
  * torus:       {radius, tube, radialSegments: 6-8,
                  tubularSegments: 12-16}
  * octahedron:  {radius}
  * icosahedron: {radius}
  * dodecahedron:{radius}
  * tetrahedron: {radius}
  * plane:       {width, height}

Для PSX-эстетики ВСЕГДА используй минимальные segments (6-8).


----------------------------------------------------------------
UNIFORMS
----------------------------------------------------------------

Все uniforms должны быть объявлены в "uniforms" с полями
type и value.

Доступные типы: float, int, vec2, vec3, vec4, color.

uTime — добавляется автоматически, не объявляй его.

Примеры:

  "uniforms": {
    "uColor":      {"type": "vec3",  "value": [0.3, 0.7, 0.4]},
    "uIntensity":  {"type": "float", "value": 1.5},
    "uWaterColor": {"type": "color", "value": [0.1, 0.3, 0.6]}
  }


----------------------------------------------------------------
ОГРАНИЧЕНИЯ GLSL
----------------------------------------------------------------

  * GLSL ES 1.0: только varying, никаких in/out, никаких
    #version.
  * Доступные встроенные функции: sin, cos, tan, fract, floor,
    ceil, mix, smoothstep, clamp, min, max, abs, pow, sqrt,
    length, normalize, dot, cross, reflect, refract.
  * Доступные встроенные переменные vertex-шейдера: position,
    normal, uv, modelMatrix, viewMatrix, projectionMatrix,
    normalMatrix.
  * Доступные встроенные переменные fragment-шейдера:
    gl_FragCoord, cameraPosition.
  * Максимум 80 строк на шейдер.
  * В vertex-шейдере ОБЯЗАТЕЛЬНО объявляй как минимум: vUv,
    vNormal, vPosition, vWorldPos (по мере использования во
    fragment).


----------------------------------------------------------------
ФИНАЛЬНЫЕ ТРЕБОВАНИЯ
----------------------------------------------------------------

  1. Каждый шейдер уникален — не копируй структуру между
     пропсами.
  2. Кроны деревьев, листья, трава — анимируй (uTime).
  3. Камни и руины — сделай шум/текстуру.
  4. Кристаллы и магические объекты — добавь свечение и
     пульсацию.
  5. Вода — волны, fresnel, прозрачность.
  6. Post-process — уникальное настроение мира.
  7. Не используй внешние текстуры (только процедурный шум).
  8. Все цвета — в диапазоне 0.0–1.0 (для vec) или 0–255
     (для terrain.color_gradient и atmosphere).

Создай мир по запросу пользователя. Будь креативным и детальным!"""


def generate_world_plan(user_prompt: str) -> dict:
    """Вызывает Claude, парсит JSON, возвращает план."""
    message = _client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}]
    )

    text = message.content[0].text.strip()

    # Убираем markdown-обёртки
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    # Ищем первый { и последний } — на случай мусора вокруг
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)

    return json.loads(text)