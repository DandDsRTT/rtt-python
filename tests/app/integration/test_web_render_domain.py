from fractions import Fraction

from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction

from _render_support import _live_page, _wrap_classes
from rtt.app import editor_codec, page_assets, service
from rtt.app.editor import Editor

NONSTANDARD = "2.5/3.7/5 [⟨1 0 -1] ⟨0 1 2]⧽"


def _token(**flags) -> str:
    editor = Editor()
    editor.settings["nonstandard_domain"] = True
    for key, value in flags.items():
        editor.settings[key] = value
    editor.state = service.from_temperament_data(NONSTANDARD)
    return page_assets._encode_state(editor_codec.serialize(editor))


class TestCanonicalizeButton:
    async def test_the_button_only_rides_a_nonstandard_domain(self, user: User) -> None:
        await user.open("/")
        await user.should_not_see(marker="canonicalize_domain")
        await user.open("/?state=" + _token())
        await user.should_see(marker="canonicalize_domain")

    async def test_clicking_canonicalizes_the_whole_page(self, user: User) -> None:
        await user.open("/?state=" + _token())
        _, page = _live_page()
        assert page.editor.state.domain_basis == (2, Fraction(5, 3), Fraction(7, 5))
        user.find(kind=ui.button, content="canonicalize").click()
        assert page.editor.state.domain_basis == (2, Fraction(5, 3), Fraction(7, 3))
        assert page.editor.can_undo is True

    async def test_the_button_arms_the_busy_scrim(self, user: User) -> None:
        await user.open("/?state=" + _token())
        button = next(iter(user.find(kind=ui.button, content="canonicalize").elements))
        assert "rtt-acts" in button._classes, "the busy-scrim arm hook (rtt-acts) rides the button"

    async def test_hovering_the_button_previews_the_change_then_clears(self, user: User) -> None:
        await user.open("/?state=" + _token())
        button = next(iter(user.find(kind=ui.button, content="canonicalize").elements))
        UserInteraction(user, {button}, None).trigger("mouseenter")
        assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:1:2"), \
            "hovering previews the mapping entry that canonicalizing rewrites"
        UserInteraction(user, {button}, None).trigger("mouseleave")
        assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:1:2")

    async def test_the_button_is_disabled_when_already_canonical(self, user: User) -> None:
        editor = Editor()
        editor.settings["nonstandard_domain"] = True
        editor.state = service.from_temperament_data("2.5/3.7/3 [⟨1 0 -1] ⟨0 1 3]⧽")
        await user.open("/?state=" + page_assets._encode_state(editor_codec.serialize(editor)))
        button = next(iter(user.find(kind=ui.button, content="canonicalize").elements))
        assert button.enabled is False, "an already-canonical basis leaves nothing to canonicalize"

    async def test_the_button_disables_itself_after_canonicalizing(self, user: User) -> None:
        await user.open("/?state=" + _token())
        _, page = _live_page()
        assert next(iter(user.find(kind=ui.button, content="canonicalize").elements)).enabled is True
        page.editor.canonicalize_domain_basis()
        page.renderer.render()
        assert next(iter(user.find(kind=ui.button, content="canonicalize").elements)).enabled is False


class TestDomainElementHandles:
    async def test_reorder_grips_ride_each_element_and_obey_the_setting(self, user: User) -> None:
        await user.open("/?state=" + _token())
        await user.should_see(marker="element_reorder:0")
        await user.should_see(marker="element_reorder:2")
        await user.open("/?state=" + _token(reorder_grips=False))
        await user.should_not_see(marker="element_reorder:0")

    async def test_combine_handles_only_ride_the_drag_to_combine_setting(self, user: User) -> None:
        await user.open("/?state=" + _token())
        await user.should_not_see(marker="element_combine:0")
        await user.open("/?state=" + _token(drag_to_combine=True))
        await user.should_see(marker="element_combine:0")
        await user.should_see(marker="element_combine:2")

    async def test_a_single_element_domain_shows_no_handles(self, user: User) -> None:
        editor = Editor()
        editor.settings["nonstandard_domain"] = True
        editor.settings["drag_to_combine"] = True
        editor.state = service.from_mapping(((1,),), (Fraction(5, 3),))
        await user.open("/?state=" + page_assets._encode_state(editor_codec.serialize(editor)))
        await user.should_not_see(marker="element_reorder:0")
        await user.should_not_see(marker="element_combine:0")
