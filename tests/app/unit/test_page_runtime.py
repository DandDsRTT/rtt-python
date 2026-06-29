from types import SimpleNamespace

from rtt.app import settings as show_settings
from rtt.app.page_runtime import PageRuntime, clamp_chapter


class TestPageRuntime:
    def test_building_guard_sets_true_inside_and_restores_false_outside(self):
        rt = PageRuntime()
        assert rt.building is False
        with rt.building_guard():
            assert rt.building is True
        assert rt.building is False

    def test_building_guard_is_reentrant_and_restores_the_prior_true_value(self):
        rt = PageRuntime()
        with rt.building_guard():
            with rt.building_guard():
                assert rt.building is True
            assert rt.building is True, "a nested guard must not clear building out from under the outer one"
        assert rt.building is False

    def test_building_guard_restores_even_when_the_body_raises(self):
        rt = PageRuntime()
        try:
            with rt.building_guard():
                raise ValueError("boom")
        except ValueError:
            pass
        assert rt.building is False

    def test_set_chapter_clamps_into_range_and_defaults_garbage(self):
        rt = PageRuntime()
        assert rt.set_chapter(10**9) == show_settings.CHAPTER_STAR
        assert rt.chapter == show_settings.CHAPTER_STAR
        assert rt.set_chapter(-50) == show_settings.CHAPTER_MIN
        assert rt.set_chapter("not-a-number") == show_settings.CHAPTER_DEFAULT
        assert clamp_chapter(None) == show_settings.CHAPTER_DEFAULT

    def test_col_tokens_reads_the_identities_of_the_named_axis(self):
        rt = PageRuntime()
        assert rt.col_tokens("gens") == []
        rt.set_last_lay(SimpleNamespace(identities={"gens": [("a", 0), ("b", 0)], "commas": []}))
        assert rt.col_tokens("gens") == ["a", "b"]
        assert rt.col_tokens("commas") == []
        assert rt.col_tokens("absent_axis") == []

    def test_token_index_locates_a_cells_token_within_its_axis(self):
        rt = PageRuntime()
        rt.set_last_lay(SimpleNamespace(identities={"gens": [(3, 0), (7, 0)]}))
        assert rt.token_index("etpick:7", "gens") == 1
        assert rt.token_index("etpick:3", "gens") == 0
        assert rt.token_index("etpick:99", "gens") is None

    def test_available_keys_filters_implemented_by_current_chapter(self):
        rt = PageRuntime()
        rt.set_chapter(show_settings.CHAPTER_MIN)
        expected = [
            k
            for k in show_settings.IMPLEMENTED
            if show_settings.reveal_chapter(k) <= show_settings.CHAPTER_MIN
        ]
        assert rt.available_keys() == expected

    def test_chapter_reading_drops_the_prefix_past_the_guide_and_numbers_the_rest(self):
        rt = PageRuntime()
        rt.set_chapter(show_settings.CHAPTER_STAR)
        assert rt.chapter_reading() == show_settings.CHAPTER_TITLES[show_settings.CHAPTER_STAR]
        rt.set_chapter(show_settings.CHAPTER_MIN)
        assert rt.chapter_reading().startswith(f"{show_settings.CHAPTER_MIN}: ")

    def test_dark_icon_reflects_dark_mode(self):
        rt = PageRuntime()
        assert rt.dark_icon() == "dark_mode"
        rt.dark_mode = True
        assert rt.dark_icon() == "light_mode"

    def test_bind_client_records_the_captured_page_client(self):
        rt = PageRuntime()
        assert rt.page_client is None
        sentinel = object()
        rt.bind_client(sentinel)
        assert rt.page_client is sentinel
