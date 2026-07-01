import inspect
import re

import pytest

from rtt.app import _page_parts, page_assets


class TestAssetManifestMatchesDisk:
    def test_js_modules_list_matches_the_assets_on_disk(self):
        on_disk = {path.name for path in page_assets._ASSETS.glob("*.js")}
        assert set(page_assets._JS_MODULES) == on_disk, (
            "_JS_MODULES has drifted from assets/*.js — an unlisted module never loads in the browser"
        )

    def test_css_files_list_matches_the_stylesheets_on_disk(self):
        on_disk = {path.name for path in page_assets._ASSETS.glob("*.css")}
        assert set(page_assets._CSS_FILES) == on_disk, (
            "_CSS_FILES has drifted from assets/*.css — an unlisted stylesheet never loads"
        )

    def test_preload_fonts_exist_on_disk(self):
        for file in page_assets._PRELOAD_FONTS:
            assert (page_assets._ASSETS / "fonts" / file).exists(), (
                f"{file} is preloaded but not present in assets/fonts"
            )


class TestSetupPageHeadWiring:
    def test_setup_page_head_injects_head_html_and_no_body_scripts(self):
        source = inspect.getsource(_page_parts.setup_page_head)
        assert "ui.add_head_html(HEAD_HTML)" in source, (
            "setup_page_head must inject the cache-busted HEAD_HTML into the document head"
        )
        assert "add_body_html" not in source, (
            "the per-client inline <script> body injection must not return"
        )
        assert "add_css" not in source, "the full-CSS inline blob must not return"


class TestHeadHtmlDelivery:
    def test_every_js_module_is_a_deferred_static_script(self):
        head = page_assets.HEAD_HTML
        for name in page_assets._JS_MODULES:
            assert re.search(
                rf'<script defer src="/rtt-assets/{re.escape(name)}\?v=[0-9a-f]+"></script>', head
            ), f"{name} is not delivered as a cache-busted, deferred static <script>"

    def test_no_large_asset_body_is_inlined(self):
        head = page_assets.HEAD_HTML
        for blob in (page_assets._FREEZE_JS, page_assets._TOUR_JS):
            assert blob.strip() not in head, "a JS module body is still inlined into the page head"
        rtt_css_body = (page_assets._ASSETS / "rtt.css").read_text(encoding="utf-8")
        assert rtt_css_body not in head, (
            "rtt.css is still inlined instead of served as a static file"
        )

    def test_stylesheets_are_cache_busted_links(self):
        head = page_assets.HEAD_HTML
        for name in page_assets._CSS_FILES:
            assert re.search(
                rf'<link rel="stylesheet" href="/rtt-assets/{re.escape(name)}\?v=[0-9a-f]+">', head
            ), f"{name} is not delivered as a cache-busted stylesheet link"

    def test_only_dynamic_css_stays_inline(self):
        head = page_assets.HEAD_HTML
        assert f"<style>{page_assets._FONT_FACE}" in head
        assert page_assets._FONT_FALLBACK in head
        assert "--rtt-serif" in head

    def test_first_paint_fonts_are_preloaded_with_crossorigin(self):
        head = page_assets.HEAD_HTML
        for file in page_assets._PRELOAD_FONTS:
            assert re.search(
                rf'<link rel="preload" as="font" type="font/woff2" '
                rf'href="/rtt-fonts/{re.escape(file)}\?v=[0-9a-f]+" crossorigin>',
                head,
            ), f"{file} is not preloaded"
        assert head.index("preload") < head.index("stylesheet"), (
            "font preload must precede the stylesheet so the fetch starts during head parse"
        )

    def test_font_faces_reference_the_subset_files(self):
        for file in (
            "STIXTwoText-Regular-subset.woff2",
            "STIXTwoText-Italic-subset.woff2",
            "STIXTwoText-Bold-subset.woff2",
            "STIXTwoText-BoldItalic-subset.woff2",
        ):
            assert re.search(rf"/rtt-fonts/{re.escape(file)}\?v=", page_assets._FONT_FACE)

    def test_fallback_face_matches_stix_vertical_metrics(self):
        fallback = page_assets._FONT_FALLBACK
        assert "src:local('Georgia')" in fallback
        assert "ascent-override:76.2%" in fallback
        assert "descent-override:23.8%" in fallback
        assert "line-gap-override:25%" in fallback

    def test_audio_glyphs_and_tour_config_are_set_before_deferred_modules(self):
        head = page_assets.HEAD_HTML
        assert "window.__rttAudioGlyphs=" in head
        assert "autostart:true" in head
        assert head.index("__rttAudioGlyphs") < head.index("audio.js"), (
            "the glyph data must be set inline before the deferred audio.js reads it"
        )

    def test_audio_js_reads_the_preset_glyph_global(self):
        audio_js = (page_assets._ASSETS / "audio.js").read_text(encoding="utf-8")
        assert "window.__rttAudioGlyphs" in audio_js


class TestStaticServing:
    @pytest.fixture
    def client(self):
        from nicegui import core
        from starlette.testclient import TestClient

        return TestClient(core.app, raise_server_exceptions=False)

    @pytest.mark.parametrize(
        "path",
        [
            "/rtt-assets/rtt.css",
            "/rtt-assets/audio.js",
            "/rtt-fonts/STIXTwoText-Regular-subset.woff2",
        ],
    )
    def test_asset_is_served_with_a_one_year_cache(self, client, path):
        response = client.get(path)
        assert response.status_code == 200
        assert f"max-age={page_assets._CACHE_FOREVER}" in response.headers.get("cache-control", "")
