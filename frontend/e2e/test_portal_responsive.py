"""
Responsive Guard — portal mobile regression test.

WHY THIS EXISTS
---------------
The client portal (CRA) shipped with a fixed `w-60` sidebar + `<main class="ml-60">`
and NO responsive override, so at mobile widths content overflowed horizontally
(dashboard scrollWidth 527 vs 390, deliverable detail 557 vs 390) and the
Bunny playback/download controls were half-cut. A PRD claim that "mobile
optimization" was done sat unverified because nothing was actually checking it.

This test converts that silent failure mode into a visible one: it asserts the
portal has ZERO horizontal overflow at a phone viewport across the shell-driven
pages, and that the mobile drawer opens/closes. If someone reintroduces a fixed
margin/width without a responsive override, CI fails here instead of a human
discovering it months later by manually measuring scrollWidth.

RUN
---
    pip install playwright && playwright install chromium
    PORTAL_URL=https://<preview-or-portal-host> \
    PORTAL_TEST_EMAIL=... PORTAL_TEST_PASSWORD=... \
    pytest -v frontend/e2e/test_portal_responsive.py

Defaults target the preview host + the Bunny seed client (see
memory/test_credentials.md). Override via env for other environments.
"""
import os
import pytest
from playwright.sync_api import sync_playwright

PORTAL_URL = os.environ.get("PORTAL_URL", "https://db-bridge-5.preview.emergentagent.com").rstrip("/")
EMAIL = os.environ.get("PORTAL_TEST_EMAIL", "bunny.owner@seed.flyboytest.com")
PASSWORD = os.environ.get("PORTAL_TEST_PASSWORD", "SeedTest#2026!")
DELIVERABLE_ID = os.environ.get("PORTAL_TEST_DELIVERABLE_ID", "c9c6ce46-3847-4b46-8772-e565d4cb3bf1")

MOBILE = {"width": 390, "height": 844}
# Pages whose layout is driven by the portal shell (sidebar + main).
GUARDED_PATHS = ["/", "/deliverables", f"/deliverables/{DELIVERABLE_ID}"]


def _login(page):
    page.goto(f"{PORTAL_URL}/auth", wait_until="networkidle")
    page.fill('input[type="email"]', EMAIL)
    page.fill('input[type="password"]', PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_url(f"{PORTAL_URL}/**", timeout=15000)
    page.wait_for_timeout(3500)


@pytest.fixture(scope="module")
def page_ctx():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=MOBILE)
        _login(page)
        yield page
        browser.close()


@pytest.mark.parametrize("path", GUARDED_PATHS)
def test_no_horizontal_overflow_at_390(page_ctx, path):
    page = page_ctx
    page.goto(f"{PORTAL_URL}{path}", wait_until="networkidle")
    page.wait_for_timeout(2500)
    m = page.evaluate(
        "() => ({scrollW: document.documentElement.scrollWidth,"
        " clientW: document.documentElement.clientWidth})"
    )
    # Allow a 1px rounding tolerance; the regression this guards was +137/+167px.
    assert m["scrollW"] <= m["clientW"] + 1, (
        f"Horizontal overflow at {path}: scrollWidth={m['scrollW']} > "
        f"clientWidth={m['clientW']}. The portal shell likely lost its "
        f"responsive override (e.g. a hard `ml-60`/`w-60` without `md:`)."
    )


def test_mobile_drawer_opens_and_closes(page_ctx):
    page = page_ctx
    page.goto(f"{PORTAL_URL}/", wait_until="networkidle")
    page.wait_for_timeout(2500)

    # Hamburger must exist at mobile width.
    assert page.is_visible('[data-testid="mobile-nav-open"]'), "Mobile hamburger missing at 390px"

    page.click('[data-testid="mobile-nav-open"]', force=True)
    page.wait_for_timeout(500)
    assert page.get_attribute('[data-testid="portal-sidebar"]', "data-open") == "true", "Drawer did not open"

    # Closing via a nav link should dismiss the drawer.
    page.click('[data-testid="mobile-nav-close"]', force=True)
    page.wait_for_timeout(500)
    assert page.get_attribute('[data-testid="portal-sidebar"]', "data-open") == "false", "Drawer did not close"
