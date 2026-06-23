from __future__ import annotations

from rtt.app import settings as show_settings
from rtt.app.editor_document import Document
from rtt.app.editor_structure import StructureOps


class ShowSettingsOps:
    def __init__(self, doc: Document, structure: StructureOps) -> None:
        self.doc = doc
        self.structure = structure

    def set_show(self, key: str, value: bool) -> None:
        self.doc.snapshot()
        had_alt_complexity = self.doc.settings["alt_complexity"]
        had_all_interval = self.doc.settings["all_interval"]
        self.doc.settings[key] = value
        if value:
            for parent in show_settings.ancestors_of(key):
                self.doc.settings[parent] = True
        else:
            for child in show_settings.subcontrols_of(key):
                self.doc.settings[child] = False
        if had_alt_complexity and not self.doc.settings["alt_complexity"]:
            self.doc.reset_to_basic_tuning()
        self.doc.exit_all_interval_if_hidden(had_all_interval)
        self.doc.reconcile_custom_weights()

    def set_all_show(self, value: bool, keys=None) -> None:
        keys = show_settings.IMPLEMENTED if keys is None else keys
        self.doc.snapshot()
        had_alt_complexity = self.doc.settings["alt_complexity"]
        had_all_interval = self.doc.settings["all_interval"]
        for key in keys:
            self.doc.settings[key] = value
        if not value and "nonstandard_domain" in keys and self.structure.basis_is_nonstandard:
            self.structure.standardize_domain_in_place()
        if had_alt_complexity and not self.doc.settings["alt_complexity"]:
            self.doc.reset_to_basic_tuning()
        self.doc.exit_all_interval_if_hidden(had_all_interval)
        self.doc.reconcile_custom_weights()

    def disable_hidden_settings(self, chapter: int) -> None:
        had_alt_complexity = self.doc.settings["alt_complexity"]
        had_all_interval = self.doc.settings["all_interval"]
        for key in self.doc.settings:
            if self.doc.settings[key] and show_settings.reveal_chapter(key) > chapter:
                self.doc.settings[key] = False
        if had_alt_complexity and not self.doc.settings["alt_complexity"]:
            self.doc.reset_to_basic_tuning()
        self.doc.exit_all_interval_if_hidden(had_all_interval)
        self.doc.reconcile_custom_weights()

    def toggle_collapsed(self, item: str) -> None:
        self.doc.snapshot()
        self.doc.collapsed.discard(item) if item in self.doc.collapsed else self.doc.collapsed.add(
            item
        )

    def set_collapsed(self, items) -> None:
        self.doc.snapshot()
        self.doc.collapsed = set(items)
