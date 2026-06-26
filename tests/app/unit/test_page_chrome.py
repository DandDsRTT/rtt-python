from rtt.app.page_chrome import PageChrome


def test_page_chrome_starts_with_empty_registries_and_unset_elements():
    chrome = PageChrome()
    for registry in (
        chrome.refs,
        chrome.boxes,
        chrome.examples,
        chrome.tile_parts,
        chrome.show_rows,
        chrome.cell_parents,
    ):
        assert registry == {}
    for element in (chrome.grid_pane, chrome.board, chrome.chapter_slider, chrome.select_all_box):
        assert element is None


def test_page_chrome_registries_are_independent_instances_per_page():
    a, b = PageChrome(), PageChrome()
    a.refs["x"] = 1
    assert b.refs == {}
