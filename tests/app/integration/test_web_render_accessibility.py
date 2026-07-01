"""WP3 accessibility at the served-page layer: the document advertises its language.

NiceGUI's page ``language`` argument only loads Quasar's i18n bundle; it never writes
``<html lang>``, which is the attribute a screen reader reads for pronunciation. The app
injects a head script that sets it, so it is present in the served HTML before the body
mounts — this drives the real GET to confirm it."""

from nicegui.testing import User


class TestDocumentLanguage:
    async def test_served_html_sets_the_document_language(self, user: User) -> None:
        response = await user.http_client.get("/")
        assert response.status_code == 200
        assert "document.documentElement.lang='en'" in response.text
