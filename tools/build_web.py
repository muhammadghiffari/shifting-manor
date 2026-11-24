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
    display: inline-flex;
    align-items: center;
    gap: 6px;
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
    """Render an ornate 4x-supersampled gothic lantern emblem (128x128 favicon.png)."""
    env = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
    code = f"""
import math
import pygame

pygame.init()
S = 512  # 4x supersample for crisp anti-aliased bevels and flame curves
surf = pygame.Surface((S, S), pygame.SRCALPHA)

def pt(x, y):
    return (int(round(x * S / 64.0)), int(round(y * S / 64.0)))

def sc(v):
    return max(1, int(round(v * S / 64.0)))

# 1. Deep obsidian architectural crest with subtle vignette
pygame.draw.rect(surf, (11, 8, 18, 255), (sc(2), sc(2), sc(60), sc(60)), border_radius=sc(14))
for r in range(sc(30), 0, -4):
    t = (1.0 - r / sc(30)) ** 1.4
    col = (int(11 + 22 * t), int(8 + 16 * t), int(18 + 32 * t), 255)
    pygame.draw.circle(surf, col, pt(32, 30), r)

# Clip crisp outer squircle mask so vignette stays inside rounded border
mask = pygame.Surface((S, S), pygame.SRCALPHA)
pygame.draw.rect(mask, (255, 255, 255, 255), (sc(2), sc(2), sc(60), sc(60)), border_radius=sc(14))
surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)

# Outer antique-gold frame + softly alpha-blended inner filigree & blueprint details
pygame.draw.rect(surf, (236, 188, 92, 255), (sc(2), sc(2), sc(60), sc(60)), sc(2.2), border_radius=sc(14))

filigree = pygame.Surface((S, S), pygame.SRCALPHA)
pygame.draw.rect(filigree, (236, 188, 92, 68), (sc(6), sc(6), sc(52), sc(52)), sc(1.0), border_radius=sc(10.5))
for a, b in [((8.5, 32), (13.5, 32)), ((50.5, 32), (55.5, 32))]:
    pygame.draw.line(filigree, (236, 188, 92, 72), pt(*a), pt(*b), sc(1.0))
pygame.draw.arc(filigree, (148, 228, 244, 96), (sc(10.2), sc(10.2), sc(43.6), sc(43.6)), math.radians(118), math.radians(156), sc(1.2))
pygame.draw.arc(filigree, (148, 228, 244, 52), (sc(10.2), sc(10.2), sc(43.6), sc(43.6)), math.radians(24), math.radians(62), sc(1.1))
for rx, ry in [(10.5, 10.5), (53.5, 10.5), (10.5, 53.5), (53.5, 53.5)]:
    pygame.draw.circle(filigree, (236, 188, 92, 165), pt(rx, ry), sc(1.15))
surf.blit(filigree, (0, 0))

# 3. Warm volumetric amber lantern aura (properly alpha-blended onto dark crest)
aura = pygame.Surface((S, S), pygame.SRCALPHA)
for r in range(sc(25), 0, -4):
    f = (1.0 - r / sc(25)) ** 2.0
    col = (255, int(172 + 40 * f), int(76 + 34 * f), int(18 * f))
    pygame.draw.circle(aura, col, pt(32, 35.0), r)
surf.blit(aura, (0, 0))

# 4. Hanging brass bail ring & finial
pygame.draw.circle(surf, (240, 194, 98, 255), pt(32, 12.4), sc(3.4), sc(1.9))
pygame.draw.polygon(surf, (230, 178, 78, 255), [pt(32, 15.2), pt(35.3, 18.2), pt(28.7, 18.2)])

# 5. Gothic cupola dome & eaves brim
dome_pts = []
for i in range(17):
    ang = math.pi * i / 16.0
    x = 32 - 9.2 * math.cos(ang)
    y = 22.5 - 4.9 * math.sin(ang)
    dome_pts.append(pt(x, y))
pygame.draw.polygon(surf, (226, 174, 76, 255), dome_pts)
pygame.draw.rect(surf, (245, 206, 114, 255), (sc(19.2), sc(21.9), sc(25.6), sc(3.0)), border_radius=sc(1.4))
pygame.draw.line(surf, (255, 234, 174, 255), pt(20.8, 22.6), pt(43.2, 22.6), sc(0.8))

# 6. Tapered warm glass chamber with vertical glow gradient
glass_poly = [pt(23.0, 24.9), pt(41.0, 24.9), pt(39.0, 45.6), pt(25.0, 45.6)]
pygame.draw.polygon(surf, (252, 214, 134, 255), glass_poly)
inner_glass = [pt(25.1, 26.2), pt(38.9, 26.2), pt(37.5, 44.2), pt(26.5, 44.2)]
pygame.draw.polygon(surf, (255, 244, 204, 255), inner_glass)

# Subtle alpha-blended gothic arch window tracery & vertical mullions
tracery = pygame.Surface((S, S), pygame.SRCALPHA)
pygame.draw.arc(tracery, (176, 118, 36, 95), (sc(23.4), sc(25.3), sc(17.2), sc(18.6)), math.radians(15), math.radians(165), sc(1.1))
pygame.draw.line(tracery, (186, 132, 46, 115), pt(27.3, 25.0), pt(28.0, 45.4), sc(1.0))
pygame.draw.line(tracery, (186, 132, 46, 115), pt(36.7, 25.0), pt(36.0, 45.4), sc(1.0))
surf.blit(tracery, (0, 0))

# 7. Sculpted teardrop flame (amber outer + cream core)
flame_outer = [
    pt(32.0, 28.0), pt(34.4, 31.8), pt(36.0, 35.6), pt(35.7, 39.1),
    pt(34.0, 41.2), pt(32.0, 41.8), pt(30.0, 41.2), pt(28.3, 39.1),
    pt(28.0, 35.6), pt(29.6, 31.8),
]
pygame.draw.polygon(surf, (242, 138, 48, 255), flame_outer)
flame_mid = [
    pt(32.0, 30.2), pt(33.8, 33.4), pt(34.7, 36.6), pt(34.0, 39.4),
    pt(32.0, 40.4), pt(30.0, 39.4), pt(29.3, 36.6), pt(30.2, 33.4),
]
pygame.draw.polygon(surf, (255, 208, 102, 255), flame_mid)
flame_core = [
    pt(32.0, 32.8), pt(33.3, 35.6), pt(33.4, 38.2), pt(32.0, 39.5),
    pt(30.6, 38.2), pt(30.7, 35.6),
]
pygame.draw.polygon(surf, (255, 253, 240, 255), flame_core)

# 8. Brass tapered outer cage frame
pygame.draw.lines(surf, (232, 180, 82, 255), True, glass_poly, sc(2.3))

# 9. Stepped antique-brass plinth base
pygame.draw.rect(surf, (238, 190, 96, 255), (sc(21.2), sc(45.4), sc(21.6), sc(2.8)), border_radius=sc(1.2))
pygame.draw.rect(surf, (166, 113, 36, 255), (sc(18.6), sc(48.0), sc(26.8), sc(3.5)), border_radius=sc(1.6))
pygame.draw.line(surf, (250, 222, 144, 255), pt(20.4, 48.8), pt(43.6, 48.8), sc(0.85))

out = pygame.transform.smoothscale(surf, (128, 128))
pygame.image.save(out, {str(dest)!r})
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
        arrow_svg = (
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" '
            'stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"/>'
            '<polyline points="12 19 5 12 12 5"/></svg>'
        )
        html = html.replace(
            "<body>",
            f'<body>\n    <a id="home-pill" href="index.html">{arrow_svg}<span>Home</span></a>',
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

    logo_src = ROOT / "web" / "logo.svg"
    if logo_src.is_file():
        shutil.copy2(logo_src, target / "logo.svg")

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
