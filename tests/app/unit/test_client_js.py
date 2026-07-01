"""The client-JS consistency contract (WP9).

These pin the shape the seven asset modules under ``rtt/app/assets`` share after the
consistency pass: the fraction/decimal twins delegate to one factory, every module
guards against double-injection the same way, the boot-retry lives in one place, and
the repeated magic literals are named. They fail if a later edit reintroduces the
drift the pass removed (a re-typed selector, a scattered gain floor, a duplicated
retry loop) so the suite stays the executable spec for the JS the render tests can't
run in-process.
"""

import inspect

from rtt.app import _page_parts, page_assets, render_html


_GUARDED_MODULES = {
    "_AUDIO_JS": "__rttAudio",
    "_FREEZE_JS": "__rttFreeze",
    "_FRACTION_JS": "__rttFraction",
    "_DECIMAL_JS": "__rttDecimal",
    "_ACTIVECELL_JS": "__rttActiveCell",
    "_TOUR_JS": "__rttTour",
    "_MAPPING_DEMO_JS": "__rttMapDemo",
}


class TestSharedStackedEditFactory:
    def test_fraction_and_decimal_delegate_to_one_factory(self):
        factory = page_assets._STACKED_EDIT_JS
        assert "window.rttStackedEditMode = function" in factory
        for js in (page_assets._FRACTION_JS, page_assets._DECIMAL_JS):
            assert "window.rttStackedEditMode({" in js
            assert "addEventListener" not in js, "the listener wiring lives once in the factory, not per twin"

    def test_each_twin_configures_only_its_differing_literals(self):
        frac = page_assets._FRACTION_JS
        assert "rtt-fraction-edit" in frac and "fracmode" in frac
        assert "modeOn: 'ratio'" in frac and "openKey: '/'" in frac
        dec = page_assets._DECIMAL_JS
        assert "rtt-decimal-edit" in dec and "decmode" in dec
        assert "modeOn: 'decimal'" in dec and "openKey: '.'" in dec

    def test_ratio_font_is_injected_from_the_python_source_of_truth(self):
        frac = page_assets._FRACTION_JS
        assert "13px" not in frac, "the ratio font is the injected _RATIO_MAX_FONT, not a re-typed literal"
        assert "window.rttFraction" in frac and "ratioFont" in frac
        src = inspect.getsource(_page_parts.setup_page_head)
        assert "window.rttFraction" in src and "ratioFont" in src and "_RATIO_MAX_FONT" in src

    def test_decimal_twin_keeps_no_font_hack(self):
        assert "fontSize" not in page_assets._DECIMAL_JS, (
            "the intended asymmetry: the decimal view has no bar to seat, so it does the ratio "
            "twin's font pre-shrink"
        )


class TestIdempotencyGuards:
    def test_every_module_installs_only_once_with_the_uniform_scheme(self):
        for attr, token in _GUARDED_MODULES.items():
            js = getattr(page_assets, attr)
            assert f"if (window.{token}) return;" in js, f"{attr} lacks the uniform guard"
            assert f"window.{token} = true;" in js, f"{attr} lacks the uniform guard"

    def test_shared_utilities_guard_on_their_own_namespace(self):
        assert "if (window.rttBoot) return;" in page_assets._BOOT_JS
        assert "if (window.rttStackedEditMode) return;" in page_assets._STACKED_EDIT_JS


class TestSharedBootRetry:
    def test_boot_retry_lives_in_one_place(self):
        boot = page_assets._BOOT_JS
        assert "window.rttBoot = function" in boot
        assert "RETRIES = 12" in boot and "INTERVAL = 100" in boot

    def test_freeze_and_activecell_call_the_shared_boot(self):
        for attr in ("_FREEZE_JS", "_ACTIVECELL_JS"):
            js = getattr(page_assets, attr)
            assert "window.rttBoot(" in js
            assert "setTimeout(boot" not in js, "the retry loop is no longer hand-inlined"


class TestNamedLiterals:
    def test_audio_gain_floor_is_named_once(self):
        js = page_assets._AUDIO_JS
        assert "GAIN_FLOOR = 0.0001" in js
        assert js.count("0.0001") == 1, "the acoustic floor is the named constant, not scattered literals"

    def test_audio_speaker_selector_has_one_builder(self):
        js = page_assets._AUDIO_JS
        assert "function seg(tile, index)" in js and "function tiles(tile)" in js
        assert "function segCells" not in js

    def test_tour_viewport_inset_is_named(self):
        js = page_assets._TOUR_JS
        assert "EDGE = 12" in js
        assert "Math.max(EDGE" in js


class TestStyleNits:
    def test_mapping_demo_glyphs_reuse_the_serif_token(self):
        js = page_assets._MAPPING_DEMO_JS
        assert "var(--rtt-serif)" in js
        assert "STIX Two Text', Georgia" not in js, "no hand-restated (and diverged) serif stack"

    def test_activecell_uses_the_el_naming_convention(self):
        assert "e2" not in page_assets._ACTIVECELL_JS

    def test_overlay_scroll_listeners_are_passive(self):
        for attr in ("_AUDIO_JS", "_TOUR_JS", "_MAPPING_DEMO_JS"):
            assert "passive: true" in getattr(page_assets, attr)


class TestInjectionSource:
    def test_ratio_max_font_is_a_plain_number_the_stamp_can_serialize(self):
        assert isinstance(render_html._RATIO_MAX_FONT, (int, float))
