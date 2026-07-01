from __future__ import annotations

from rtt.app import settings as show_settings


class _ShowCommands:
    def set_show(self, key: str, value: bool) -> None:
        self.snapshot()
        had_alt_complexity = self.settings["alt_complexity"]
        had_all_interval = self.settings["all_interval"]
        self.settings[key] = value
        if value:
            for parent in show_settings.ancestors_of(key):
                self.settings[parent] = True
        else:
            for child in show_settings.subcontrols_of(key):
                self.settings[child] = False
        if had_alt_complexity and not self.settings["alt_complexity"]:
            self.reset_to_basic_tuning()
        self.exit_all_interval_if_hidden(had_all_interval)
        self.reconcile_custom_weights()

    def set_all_show(self, value: bool, keys=None) -> None:
        keys = show_settings.IMPLEMENTED if keys is None else keys
        self.snapshot()
        had_alt_complexity = self.settings["alt_complexity"]
        had_all_interval = self.settings["all_interval"]
        for key in keys:
            self.settings[key] = value
        if not value and "nonstandard_domain" in keys and self.basis_is_nonstandard:
            self.standardize_domain_in_place()
        if had_alt_complexity and not self.settings["alt_complexity"]:
            self.reset_to_basic_tuning()
        self.exit_all_interval_if_hidden(had_all_interval)
        self.reconcile_custom_weights()

    def disable_hidden_settings(self, chapter: int) -> None:
        had_alt_complexity = self.settings["alt_complexity"]
        had_all_interval = self.settings["all_interval"]
        for key in self.settings:
            if self.settings[key] and show_settings.reveal_chapter(key) > chapter:
                self.settings[key] = False
        if had_alt_complexity and not self.settings["alt_complexity"]:
            self.reset_to_basic_tuning()
        self.exit_all_interval_if_hidden(had_all_interval)
        self.reconcile_custom_weights()

    def reveal_default_settings(self, chapter: int) -> None:
        for key, default in show_settings.DEFAULTS.items():
            if default is True and show_settings.reveal_chapter(key) <= chapter:
                self.settings[key] = True

    def toggle_collapsed(self, item: str) -> None:
        self.snapshot()
        self.collapsed.discard(item) if item in self.collapsed else self.collapsed.add(item)

    def set_collapsed(self, items) -> None:
        self.snapshot()
        self.collapsed = set(items)
