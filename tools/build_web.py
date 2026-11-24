"""Build the browser-playable WebAssembly bundle for Shifting Manor via pygbag.

Stages ONLY the minimal files needed for the browser (keeping the WASM APK
compact and fast to load), generates a gothic lantern favicon, compiles with
``pygbag --build --archive``, and patches ``index.html`` with our dark gothic
theme and right-click contextmenu prevention.

Output:
  dist/web/                    Static site ready for GitHub Pages / Netlify / Cloudflare Pages
  dist/shifting-manor-web.zip  Zip archive ready for itch.io HTML5 upload
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BROWSER_PATCH = """
<style>
  html, body {
    background-color: #0E0B14 !important;
    color: #EEDEB9 !important;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    overflow: hidden;
  }
  #transfer {
    background: #171222;
    border: 1px solid #ECBC5C;
    border-radius: 12px;
    padding: 18px 28px;
    color: #EEDEB9;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.72);
  }
  #status {
    color: #ECBC5C !important;
    font-size: 16px;
  }
  #infobox {
    background: #171222 !important;
    color: #ECBC5C !important;
    border: 2px solid #ECBC5C !important;
    border-radius: 12px !important;
    padding: 16px 30px !important;
    font-size: 19px !important;
    letter-spacing: 0.3px;
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.85);
    cursor: pointer;
  }
  progress { accent-color: #ECBC5C; }
  #home-pill {
    position: fixed;
    top: 10px;
    left: 10px;
    z-index: 999998;
    padding: 6px 13px;
    border-radius: 999px;
    background: rgba(23, 18, 34, 0.72);
    border: 1px solid rgba(236, 188, 92, 0.55);
    color: #ECBC5C;
    text-decoration: none;
    font-size: 13px;
    font-weight: 700;
    backdrop-filter: blur(6px);
    opacity: 0.45;
    transition: opacity 0.2s, background 0.2s;
  }
  #home-pill:hover {
    opacity: 1;
    background: rgba(34, 27, 50, 0.95);
  }
</style>
<script>
  window.addEventListener("contextmenu", function (e) {
    if (e.target && e.target.tagName === "CANVAS") {
      e.preventDefault();
    }
  }, { capture: true });
</script>
"""

LANDING_MEDIA = (
    "gameplay_demo.gif",
    "watch_ai_demo.gif",
    "01_title.png",
    "03_board_fog.png",
    "04_shift_midframe.png",
    "06_result.png",
    "07_live_ai_autonomous.png",
    "08_tutorial.png",
    "10_simlab.png",
    "11_duel_result.png",
    "watch_ai_why.png",
)


def _generate_favicon(dest: Path) -> None:
    """Render a crisp 64x64 gothic golden lantern favicon.png headlessly."""
    env = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
    code = f"""
import pygame
pygame.init()
surf = pygame.Surface((64, 64), pygame.SRCALPHA)
pygame.draw.rect(surf, (14, 11, 20, 255), (0, 0, 64, 64), border_radius=14)
pygame.draw.rect(surf, (236, 188, 92, 255), (2, 2, 60, 60), 3, border_radius=12)
for r in range(24, 0, -2):
    f = (1 - r / 24) ** 1.6
    col = (int(14 + 145 * f), int(11 + 92 * f), int(20 + 30 * f), 255)
    pygame.draw.circle(surf, col, (32, 34), r)
pygame.draw.rect(surf, (236, 188, 92, 255), (21, 20, 22, 26), border_radius=4)
pygame.draw.rect(surf, (255, 240, 196, 255), (25, 24, 14, 18), border_radius=2)
pygame.draw.arc(surf, (236, 188, 92, 255), (23, 10, 18, 16), 0.0, 3.14159, 3)
pygame.draw.rect(surf, (182, 140, 68, 255), (18, 45, 28, 5), border_radius=2)
pygame.image.save(surf, {str(dest)!r})
pygame.quit()
"""
    subprocess.run([sys.executable, "-c", code], env=env, check=True)


def stage_web_app(stage_dir: Path) -> Path:
    """Copy only the files required at runtime into a clean staging folder."""
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    # 1. Web entry script + custom gothic lantern favicon
    shutil.copy2(ROOT / "web" / "main.py", stage_dir / "main.py")
    _generate_favicon(stage_dir / "favicon.png")

    # 2. Core Python package (skip caches)
    shutil.copytree(
        ROOT / "shifting_manor",
        stage_dir / "shifting_manor",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )

    # 3. Exact posterior module so B5 Exact Bayesian agent also works in browser
    tools_dst = stage_dir / "tools"
    tools_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "tools" / "__init__.py", tools_dst / "__init__.py")
    shutil.copy2(ROOT / "tools" / "posterior.py", tools_dst / "posterior.py")

    # 4. Bundled crisp fonts (Emscripten has no system fonts)
    fonts_src = ROOT / "assets" / "fonts"
    fonts_dst = stage_dir / "assets" / "fonts"
    fonts_dst.mkdir(parents=True, exist_ok=True)
    for ttf in fonts_src.glob("*.ttf"):
        shutil.copy2(ttf, fonts_dst / ttf.name)

    # 5. Compact ~7 KB simulation summary for Simulation Lab (instead of 2.2 MB raw records)
    sim_dst = stage_dir / "sim"
    sim_dst.mkdir(parents=True, exist_ok=True)
    summary_src = ROOT / "sim" / "results_summary.json"
    if summary_src.is_file():
        shutil.copy2(summary_src, sim_dst / "results_summary.json")

    return stage_dir


def _patch_player_html(html_path: Path) -> None:
    if not html_path.is_file():
        return
    html = html_path.read_text(encoding="utf-8")
    html = html.replace('"#7f7f7f"', '"#0E0B14"')
    html = html.replace(
        "Ready to start ! Please click/touch page",
        "Shifting Manor is ready — Click or Tap anywhere to enter!",
    )
    html = html.replace(
        "Loading, please wait ...", "Lighting the lantern — Loading Shifting Manor..."
    )
    if 'window.addEventListener("contextmenu"' not in html:
        if "</head>" in html:
            html = html.replace("</head>", BROWSER_PATCH + "\n</head>", 1)
        else:
            html += BROWSER_PATCH
    if 'id="home-pill"' not in html and "<body>" in html:
        html = html.replace(
            "<body>",
            '<body>\n    <a id="home-pill" href="index.html">← Home</a>',
            1,
        )
    html_path.write_text(html, encoding="utf-8")


def _install_landing_site(target: Path) -> None:
    """Move pygbag's player to play.html and install web/landing.html as index.html."""
    pygbag_index = target / "index.html"
    play_html = target / "play.html"
    if pygbag_index.is_file():
        shutil.move(str(pygbag_index), str(play_html))
    _patch_player_html(play_html)

    landing_src = ROOT / "web" / "landing.html"
    if landing_src.is_file():
        shutil.copy2(landing_src, target / "index.html")
    else:
        shutil.copy2(play_html, target / "index.html")

    media_dst = target / "media"
    media_dst.mkdir(parents=True, exist_ok=True)
    screens_src = ROOT / "docs" / "screens"
    for name in LANDING_MEDIA:
        src = screens_src / name
        if src.is_file():
            shutil.copy2(src, media_dst / name)


def build_web(out_dir: Path | None = None, *, stage_dir: Path | None = None) -> Path:
    stage = stage_dir or (ROOT / "build" / "shifting_manor")
    target = out_dir or (ROOT / "dist" / "web")
    stage_web_app(stage)

    cmd = [
        sys.executable,
        "-m",
        "pygbag",
        "--build",
        "--archive",
        "--title",
        "Shifting Manor",
        "--app_name",
        "shifting_manor",
        "--icon",
        "favicon.png",
        "--ume_block",
        "1",
        "--can_close",
        "0",
        "--width",
        "1280",
        "--height",
        "720",
        str(stage),
    ]
    subprocess.run(cmd, cwd=str(ROOT), check=True)

    built_web = stage / "build" / "web"
    if not built_web.is_dir():
        raise RuntimeError(f"pygbag did not produce expected output directory: {built_web}")

    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(built_web, target)

    # Replace pygbag's default snake favicon with our gothic lantern icon
    custom_icon = stage / "favicon.png"
    if custom_icon.is_file():
        shutil.copy2(custom_icon, target / "favicon.png")

    # Install interactive landing page at index.html and WASM game player at play.html
    _install_landing_site(target)

    # Prevent GitHub Pages Jekyll from skipping dotfiles/assets
    (target / ".nojekyll").write_text("", encoding="utf-8")

    # Copy itch.io archive if produced (keeps pygbag's own index.html inside the zip)
    zip_src = stage / "build" / "web.zip"
    if zip_src.is_file():
        shutil.copy2(zip_src, target.parent / "shifting-manor-web.zip")

    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Shifting Manor WebAssembly web bundle.")
    parser.add_argument("--out", default=str(ROOT / "dist" / "web"), help="Output directory")
    args = parser.parse_args(argv)
    out = build_web(Path(args.out))
    apk_files = list(out.glob("*.apk"))
    apk_kb = apk_files[0].stat().st_size / 1024 if apk_files else 0.0
    print(f"Web bundle ready at: {out}")
    print(f"APK payload size: {apk_kb:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
