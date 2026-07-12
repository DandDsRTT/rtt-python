from __future__ import annotations

from dataclasses import replace

from rtt.app import settings as show_settings
from rtt.app.grid_tables import NATURAL_COLUMN_KEYS, NATURAL_ROW_KEYS


def reordered_before(order, natural_keys, src_key: str, before_key: str | None):
    keys = list(order or natural_keys)
    if src_key == before_key or src_key not in keys:
        return None
    if before_key is not None and before_key not in keys:
        return None
    rest = [key for key in keys if key != src_key]
    rest.insert(len(rest) if before_key is None else rest.index(before_key), src_key)
    return tuple(rest) if rest != keys else None


class _ShowCommands:
    @property
    def collapsed(self) -> frozenset[str]:
        return self.grid_view.collapsed

    @property
    def row_order(self) -> tuple[str, ...]:
        return self.grid_view.row_order

    @property
    def column_order(self) -> tuple[str, ...]:
        return self.grid_view.column_order

    def move_row(self, src_key: str, before_key: str | None) -> bool:
        keys = reordered_before(self.row_order, NATURAL_ROW_KEYS, src_key, before_key)
        if keys is None:
            return False
        self.snapshot()
        self.grid_view = replace(self.grid_view, row_order=keys)
        return True

    def move_column(self, src_key: str, before_key: str | None) -> bool:
        keys = reordered_before(self.column_order, NATURAL_COLUMN_KEYS, src_key, before_key)
        if keys is None:
            return False
        self.snapshot()
        self.grid_view = replace(self.grid_view, column_order=keys)
        return True

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
        folded = set(self.collapsed)
        folded.discard(item) if item in folded else folded.add(item)
        self.set_collapsed(folded)

    def set_collapsed(self, items) -> None:
        self.snapshot()
        self.grid_view = replace(self.grid_view, collapsed=frozenset(items))
