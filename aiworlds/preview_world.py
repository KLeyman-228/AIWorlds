"""
Тестовый запуск: промпт → генерация мира → локальная страница в браузере.

Примеры:
  python preview_world.py
  python preview_world.py "Ночной эльфийский лес Warcraft с золотой шахтой"
  python preview_world.py --prompt "Ледяная карта Dota" --port 8765
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DJANGO_DIR = ROOT / "aiworlds"
PREVIEW_DIR = ROOT / "preview"

DEFAULT_PROMPT = (
  "Поляня с травой деревьями и камнями, мягкий свет, дневное небо, река"
)

INDEX_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AI Worlds Preview</title>
  <style>
    html, body {{
      margin: 0;
      height: 100%;
      background: #0b0d10;
      color: #e8e0c8;
      font-family: Segoe UI, Tahoma, sans-serif;
    }}
    #hud {{
      position: absolute;
      z-index: 2;
      left: 16px;
      top: 16px;
      max-width: 420px;
      padding: 12px 14px;
      background: rgba(12, 14, 18, 0.72);
      border: 1px solid #6b5a32;
      pointer-events: none;
    }}
    #hud h1 {{
      margin: 0 0 6px;
      font-size: 18px;
    }}
    #hud p {{
      margin: 0;
      font-size: 13px;
      opacity: 0.85;
    }}
    #world-container {{
      width: 100vw;
      height: 100vh;
    }}
    canvas {{
      display: block;
    }}
  </style>
  <script type="importmap">
  {{
    "imports": {{
      "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
      "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
    }}
  }}
  </script>
</head>
<body>
  <div id="hud">
    <h1>{world_name}</h1>
    <p>{description}</p>
  </div>
  <div id="world-container"></div>
  <script type="module" src="./world.js"></script>
</body>
</html>
"""


def setup_django() -> None:
    sys.path.insert(0, str(DJANGO_DIR))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aiworlds.settings")
    import django

    django.setup()


def generate(prompt: str, model: str | None) -> dict:
    from generator.services.scene_builder import build_world_js

    print(f"Генерация мира: {prompt!r}")
    started = time.perf_counter()
    result = build_world_js(prompt, model=model)
    print(
        f"Готово за {time.perf_counter() - started:.1f}с: "
        f"{result.get('world_name')} ({len(result.get('js_code') or '')} символов JS)"
    )
    return result


def write_preview(result: dict) -> Path:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    (PREVIEW_DIR / "world.js").write_text(result["js_code"], encoding="utf-8")
    html = INDEX_HTML.format(
        world_name=_html(result.get("world_name") or "Unnamed World"),
        description=_html(result.get("description") or ""),
    )
    index_path = PREVIEW_DIR / "index.html"
    index_path.write_text(html, encoding="utf-8")
    print(f"Превью записано: {index_path}")
    return index_path


def _html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def serve_and_open(port: int) -> None:
    handler = SimpleHTTPRequestHandler
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}/index.html"
    print(f"Локальная страница: {url}")
    print("Крутите камеру мышью. Ctrl+C — выход.")
    webbrowser.open(url)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nОстановка сервера")
        server.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description="Сгенерировать мир и открыть локальную страницу")
    parser.add_argument("prompt", nargs="*", help="Текстовый промпт уровня")
    parser.add_argument("--prompt", dest="prompt_flag", default="", help="Промпт (альтернатива)")
    parser.add_argument("--model", default=None, help="Модель, по умолчанию kimi-k3")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    prompt = (args.prompt_flag or " ".join(args.prompt)).strip() or DEFAULT_PROMPT
    setup_django()
    result = generate(prompt, args.model)
    write_preview(result)
    os.chdir(PREVIEW_DIR)
    serve_and_open(args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
