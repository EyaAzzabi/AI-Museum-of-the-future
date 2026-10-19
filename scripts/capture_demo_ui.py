"""Capture a full UX demo: visitor front (warm UI), login, 3D rooms, then each agent lab test."""
from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "demo" / "ui"
BASE = "http://127.0.0.1:5000"
AGENTS = [
    ("historian", "Historian"),
    ("sociologist", "Sociologist"),
    ("technology", "Technology"),
    ("culture_art", "Culture & Art"),
    ("visual", "Visual"),
]


def _shot(page, name: str) -> None:
    dest = OUT / f"{name}.png"
    page.screenshot(path=str(dest), full_page=False)
    print("saved", dest.name)


def _login(page) -> None:
    page.goto(f"{BASE}/connexion", wait_until="networkidle")
    page.fill("#username", "visiteur")
    page.fill("#password", "musee2126")
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    time.sleep(0.6)


def _open_agentlab(page) -> None:
    page.goto(f"{BASE}/tableau-de-bord#agentlab", wait_until="networkidle")
    time.sleep(0.8)
    # Force-show Agent lab (hash routing may leave section hidden)
    page.evaluate(
        """() => {
          if (typeof activateSection === 'function') activateSection('agentlab');
          document.querySelector('[data-section="agentlab"]')?.click();
          const sec = document.getElementById('section-agentlab');
          if (sec) { sec.classList.add('active'); sec.style.display = 'block'; }
        }"""
    )
    time.sleep(0.6)
    page.wait_for_selector("#agentLabTabs .btn-preset", state="attached", timeout=15000)
    page.wait_for_selector("#historianPresets .btn-preset", state="attached", timeout=15000)
    page.locator("#agentLabTabs .btn-preset").first.wait_for(state="visible", timeout=15000)


def _run_agent(page, agent_key: str) -> None:
    tab = page.locator(f'#agentLabTabs .btn-preset[data-agent="{agent_key}"]')
    tab.scroll_into_view_if_needed()
    tab.click()
    time.sleep(0.6)
    presets = page.locator("#historianPresets .btn-preset")
    if presets.count() > 0:
        presets.first.click()
        time.sleep(0.4)
    page.locator("#btnRunHistorian").scroll_into_view_if_needed()
    page.click("#btnRunHistorian")
    page.wait_for_function(
        """() => {
          const el = document.getElementById('historianResultContainer');
          const placeholder = document.getElementById('historianPlaceholder');
          const hasResult = el && !el.classList.contains('hidden');
          const loading = document.getElementById('historianLoadingStatus');
          const stillLoading = loading && !loading.classList.contains('hidden');
          return hasResult && !stillLoading;
        }""",
        timeout=120000,
    )
    # Ensure result panel is in view
    page.evaluate("document.getElementById('historianResultContainer')?.scrollIntoView({block:'center'})")
    time.sleep(1.0)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # ── Visitor front (warm / clear, not blue dashboard look) ──
        page.goto(f"{BASE}/", wait_until="networkidle")
        time.sleep(1.2)
        _shot(page, "01_accueil")

        # 3D carousel on home — scroll into view
        page.evaluate("document.querySelector('#visite3d')?.scrollIntoView({behavior:'instant', block:'start'})")
        time.sleep(1.0)
        _shot(page, "02_salles_3d")

        # Rotate through specialist rooms (4 rooms, no blue Visual tile)
        for i, key in enumerate(["historian", "sociologist", "technology", "culture_art"]):
            if i > 0:
                page.click("#roomNext")
                time.sleep(1.0)
            _shot(page, f"03_salle_{key}")

        # Login screen
        page.goto(f"{BASE}/connexion", wait_until="networkidle")
        time.sleep(0.8)
        _shot(page, "04_connexion")

        _login(page)

        # Immersive visit
        page.goto(f"{BASE}/visite-virtuelle", wait_until="networkidle")
        time.sleep(3.0)
        _shot(page, "05_visite_immersive")

        # Dashboard — agents overview (clear cards)
        page.goto(f"{BASE}/tableau-de-bord#agents", wait_until="networkidle")
        time.sleep(0.6)
        page.evaluate(
            """() => {
              if (typeof activateSection === 'function') activateSection('agents');
              document.querySelector('[data-section="agents"]')?.click();
            }"""
        )
        time.sleep(1.0)
        _shot(page, "06_agents_overview")

        # Agent lab intro (before runs)
        _open_agentlab(page)
        _shot(page, "07_agentlab_intro")

        # Each specialist, one by one, with result visible
        for key, _label in AGENTS:
            _run_agent(page, key)
            _shot(page, f"08_test_{key}")

        # Exhibition board
        page.goto(f"{BASE}/tableau-de-bord#exhibition", wait_until="networkidle")
        time.sleep(0.6)
        page.evaluate(
            """() => {
              if (typeof activateSection === 'function') activateSection('exhibition');
              document.querySelector('[data-section=\"exhibition\"]')?.click();
            }"""
        )
        time.sleep(1.2)
        _shot(page, "09_exhibition")

        browser.close()
        print("done —", len(list(OUT.glob("*.png"))), "shots in", OUT)


if __name__ == "__main__":
    main()
