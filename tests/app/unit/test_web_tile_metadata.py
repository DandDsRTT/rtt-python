from _spreadsheet_support import _maximized_superspace_builder

from rtt.app import grid_tables
from rtt.app.grid_tables import SUBSCRIPT_C, SUBSCRIPT_L
from rtt.app.spreadsheet import build_context
from rtt.app.spreadsheet_decorations import _matrix_label_group_count, _tile_groups, _tile_tint

SPINE = frozenset({"quantities", "units", "counts"})
UNSYMBOLED_COLUMNS = frozenset({"interest"})
UNSYMBOLED_ROWS = frozenset({"complexity"})
UNITLESS_TILES = frozenset({("scaling_factors", "commas")})
UNINDEXED_COLUMNS = frozenset({"interest"})
FORM_MATRIX_TILES = frozenset({("canonical", "generators"), ("canonical", "canonical_generators")})


def _built():
    b = _maximized_superspace_builder()
    b.layout()
    return b


def _value_tiles(b):
    return sorted(t for t in b.geometry.declared_tiles if t[0] not in SPINE and t[1] not in SPINE)


def _carries_symbol(b, tile):
    return tile in grid_tables.SYMBOLS or tile in b.resolved.labels.prescaling_symbols


def _has_index_slot(b, tile):
    return tile[1] in _matrix_label_group_count(b.resolved) and b.geometry.rows[tile[0]].matrix_label_top is not None


class TestEveryValueTileIsLabeled:
    def test_every_value_tile_has_a_name(self):
        b = _built()
        missing = [t for t in _value_tiles(b) if t not in b.resolved.labels.names]
        assert missing == [], f"a declared tile with no name renders as a blank caption: {missing}"

    def test_every_value_tile_has_a_unit(self):
        b = _built()
        missing = [t for t in _value_tiles(b) if t not in grid_tables.UNITS]
        assert missing == sorted(UNITLESS_TILES), "the scaling factors are pure ratios; every other tile carries units"

    def test_every_value_tile_in_a_symbol_row_has_a_symbol(self):
        b = _built()
        rows = grid_tables.BANDS["symbol"].rows
        missing = [t for t in _value_tiles(b) if t[0] in rows and not _carries_symbol(b, t)]
        exempt = sorted(t for t in _value_tiles(b) if t[0] in rows
                        and (t[1] in UNSYMBOLED_COLUMNS or (t[0] in UNSYMBOLED_ROWS and t[1] != "targets")))
        assert missing == exempt, "only the ad-hoc intervals column and the complexity row (bar 𝒄) go without a symbol"

    def test_every_matrix_tile_indexes_its_columns_or_its_rows(self):
        b = _built()
        labels, rows = b.resolved.labels.column_labels, grid_tables.ROW_LABEL_LETTERS
        missing = [t for t in _value_tiles(b) if _has_index_slot(b, t)
                   and t[1] not in UNINDEXED_COLUMNS and t not in labels and t not in rows]
        assert missing == sorted(FORM_MATRIX_TILES), "the form matrices index generators on both axes; every other matrix labels one"

    def test_every_mnemonic_is_a_substring_of_the_name_it_underlines(self):
        names = _built().resolved.labels.names
        stray = {t: kw for t, kw in grid_tables.MNEMONICS.items() if t in names and kw not in names[t]}
        assert stray == {}, f"a mnemonic that is not in its name underlines nothing: {stray}"

    def test_a_symbol_is_shared_only_by_tiles_showing_the_same_quantity(self):
        b = _built()
        names, seen = b.resolved.labels.names, {}
        for tile in _value_tiles(b):
            symbol = b.resolved.labels.prescaling_symbols.get(tile, grid_tables.SYMBOLS.get(tile))
            if symbol:
                seen.setdefault(symbol, []).append(tile)
        clashes = {s: t for s, t in seen.items() if len({names[x] for x in t}) > 1}
        assert clashes == {}, f"these tiles share a symbol but name different quantities: {clashes}"


class TestGeneratorFamilyTileMetadata:
    def test_the_embedding_columns_one_size_row_is_the_generator_tuning_map(self):
        b = _built()
        assert b.resolved.labels.names[("tuning", "generator_embedding")] == "(just) generator embedding interval size list"
        assert grid_tables.SYMBOLS[("tuning", "generator_embedding")] == "𝒋G"
        assert grid_tables.EQUIVALENCES[("tuning", "generator_embedding")] == " = 𝒈"
        assert grid_tables.UNITS[("tuning", "generator_embedding")] == "¢/g"
        assert b.resolved.labels.column_labels[("tuning", "generator_embedding")] == "𝒋𝐠"

    def test_the_size_rows_declare_nothing_over_a_generator_family_column(self):
        b = _built()
        pairs = [(row, column) for row in ("just", "retune", "prescaling", "complexity")
                 for column in ("generators", "generator_embedding", "canonical_generators")]
        tables = {"declared": b.geometry.declared_tiles, "names": b.resolved.labels.names,
                  "symbols": grid_tables.SYMBOLS, "units": grid_tables.UNITS,
                  "factors": grid_tables.CELL_FACTORS, "labels": b.resolved.labels.column_labels,
                  "prescaling_symbols": b.resolved.labels.prescaling_symbols}
        stray = {name: [t for t in pairs if t in table] for name, table in tables.items()}
        assert {k: v for k, v in stray.items() if v} == {}, \
            "the generator family columns carry matrices and the generator tuning map, never a size list"

    def test_the_superspace_generator_symbols_carry_their_subscript(self):
        assert grid_tables.SYMBOLS[("just", "superspace_generators")] == f"𝒋{SUBSCRIPT_L}D{SUBSCRIPT_L}"
        assert grid_tables.SYMBOLS[("retune", "superspace_generators")] == f"𝒓{SUBSCRIPT_L}D{SUBSCRIPT_L}"
        assert grid_tables.SYMBOLS[("prescaling", "superspace_generators")] == f"LD{SUBSCRIPT_L}"
        assert grid_tables.SYMBOLS[("tuning", "canonical_generators")] == f"𝒈{SUBSCRIPT_C}"

    def test_the_prescaling_symbols_track_the_live_prescaler_letter(self):
        symbols = _built().resolved.labels.prescaling_symbols
        assert symbols[("prescaling", "superspace_generators")] == f"𝐿D{SUBSCRIPT_L}"
        assert symbols[("prescaling", "commas")] == "𝐿C"

    def test_the_superspace_rows_spell_out_the_lift_of_the_domain_embedding(self):
        assert grid_tables.SYMBOLS[("superspace_vectors", "generator_embedding")] == f"B{SUBSCRIPT_L}G"
        assert grid_tables.SYMBOLS[("superspace_mapping", "generator_embedding")] == f"𝑀ₛ→{SUBSCRIPT_L}G"
        assert grid_tables.SYMBOLS[("superspace_projection", "generator_embedding")] == f"𝑃{SUBSCRIPT_L}G"
        assert grid_tables.SYMBOLS[("superspace_vectors", "canonical_generators")] == f"B{SUBSCRIPT_L}D{SUBSCRIPT_C}"
        assert grid_tables.SYMBOLS[("superspace_mapping", "canonical_generators")] == f"𝑀ₛ→{SUBSCRIPT_L}D{SUBSCRIPT_C}"
        assert grid_tables.SYMBOLS[("superspace_projection", "canonical_generators")] == f"𝑃{SUBSCRIPT_L}D{SUBSCRIPT_C}"

    def test_the_superspace_generators_column_mirrors_the_generators_column(self):
        assert grid_tables.SYMBOLS[("superspace_vectors", "superspace_generators")] == f"D{SUBSCRIPT_L}"
        assert grid_tables.SYMBOLS[("superspace_projection", "superspace_generators")] == f"𝑃{SUBSCRIPT_L}D{SUBSCRIPT_L}"
        names = _built().resolved.labels.names
        assert names[("superspace_vectors", "superspace_generators")] == "superspace generator detempering"
        assert names[("superspace_projection", "superspace_generators")] == "projected superspace generator detempering"
        assert names[("superspace_vectors", "superspace_generators")] != names[("superspace_projection", "superspace_generators")]

    def test_the_units_cancel_along_each_generator_family_product(self):
        u = grid_tables.UNITS
        assert u[("superspace_vectors", "generator_embedding")] == "p/g", "B_L is p/b and G is b/g"
        assert u[("superspace_mapping", "generator_embedding")] == f"g{SUBSCRIPT_L}/g"
        assert u[("superspace_projection", "generator_embedding")] == "p/g"
        assert u[("superspace_vectors", "superspace_generators")] == "p", "D_L is a list of intervals, like the domain detempering"
        assert u[("superspace_vectors", "canonical_generators")] == "p"
        assert u[("superspace_mapping", "canonical_generators")] == f"g{SUBSCRIPT_L}"
        assert u[("superspace_projection", "canonical_generators")] == "p"

    def test_a_size_row_keeps_the_denominator_its_column_supplies(self):
        u = grid_tables.UNITS
        assert u[("just", "superspace_generators")] == "¢" and u[("retune", "superspace_generators")] == "¢"
        assert u[("prescaling", "superspace_generators")] == "oct" and u[("complexity", "superspace_generators")] == "(C)"
        assert u[("tuning", "generator_embedding")] == "¢/g" and u[("tuning", "generators")] == "¢/g"
        assert u[("tuning", "canonical_generators")] == f"¢/g{SUBSCRIPT_C}"

    def test_every_generator_family_column_indexes_its_columns(self):
        labels = _built().resolved.labels.column_labels
        assert labels[("mapping", "generator_embedding")] == "𝑀𝐠"
        assert labels[("canonical", "generator_embedding")] == f"𝑀{SUBSCRIPT_C}𝐠"
        assert labels[("superspace_vectors", "generator_embedding")] == f"B{SUBSCRIPT_L}𝐠"
        assert labels[("superspace_mapping", "generator_embedding")] == f"𝑀ₛ→{SUBSCRIPT_L}𝐠", "the index label spells the same map its symbol does"
        assert labels[("superspace_projection", "generator_embedding")] == f"𝑃{SUBSCRIPT_L}𝐠"
        assert labels[("tuning", "generator_embedding")] == "𝒋𝐠"
        assert labels[("retune", "superspace_generators")] == f"𝒓{SUBSCRIPT_L}𝐝{SUBSCRIPT_L}"
        assert labels[("prescaling", "superspace_generators")] == f"𝐿𝐝{SUBSCRIPT_L}"
        assert labels[("complexity", "superspace_generators")](0) == f"‖𝐿𝐝{SUBSCRIPT_L}₁‖{grid_tables.NORM_SUB_OPEN}q{grid_tables.NORM_SUB_CLOSE}", "the column it indexes is D_L, not G_L"


class TestGeneratorFamilyColorization:
    def test_the_generators_column_greens_every_tuning_row_over_it(self):
        b = _built()
        ctx = build_context(b)
        for row in ("tuning", "projection", "superspace_projection"):
            assert _tile_tint(b.resolved, ctx, row, "generators") == "temperament-tuning", \
                f"{row} over the yellow generator basis is green"

    def test_the_generators_column_stays_yellow_under_the_temperament_rows(self):
        b = _built()
        ctx = build_context(b)
        for row in ("vectors", "mapping", "superspace_vectors", "superspace_mapping"):
            assert _tile_tint(b.resolved, ctx, row, "generators") == "temperament"

    def test_the_embedding_column_greens_only_where_a_temperament_object_multiplies_in(self):
        b = _built()
        ctx = build_context(b)
        tint = lambda row: _tile_tint(b.resolved, ctx, row, "generator_embedding")
        for row in ("mapping", "superspace_vectors", "superspace_mapping"):
            assert tint(row) == "temperament-tuning", f"{row} multiplies the cyan embedding G by a yellow matrix"
        for row in ("vectors", "projection", "superspace_projection", "tuning"):
            assert tint(row) == "tuning", f"{row} over the embedding column carries no temperament object"

    def test_the_canonical_row_over_the_embedding_column_blends_all_three(self):
        b = _built()
        assert _tile_groups(b.resolved, "canonical", "generator_embedding") == {"temperament", "tuning", "form"}, \
            "𝑀꜀G is the mapping, the form, and the embedding at once"

    def test_the_canonical_generators_column_whitens_every_tuning_row_over_it(self):
        b = _built()
        ctx = build_context(b)
        for row in ("tuning", "projection", "superspace_projection"):
            assert _tile_tint(b.resolved, ctx, row, "canonical_generators") == "triple"

    def test_the_canonical_generators_column_reddens_the_temperament_rows(self):
        b = _built()
        ctx = build_context(b)
        for row in ("vectors", "mapping", "canonical", "superspace_vectors", "superspace_mapping"):
            assert _tile_tint(b.resolved, ctx, row, "canonical_generators") == "form-temperament"


PRESCALER_SCHEMES = ("minimax-S", "minimax-ES", "minimax-sopfr-S", "minimax-E-copfr-S",
                     "minimax-lils-S", "minimax-E-lils-S")


def _prescaler_labels(scheme):
    from _spreadsheet_support import _all_on
    from rtt.app import service, spreadsheet
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]⧽")
    b = spreadsheet._GridBuilder(state, _all_on(), tuning_scheme=scheme,
                                 held_vectors=((1, 0, 0),), interest=((-1, 1, 0),))
    b.layout()
    return b.resolved.labels


class TestThePretransformerIsOneLetterEverywhere:
    def _head(self, labels):
        return "superspace_primes" if ("prescaling", "superspace_primes") in labels.names else "primes"

    def test_every_prescaled_tile_and_index_label_scales_by_the_rows_own_letter(self):
        for scheme in PRESCALER_SCHEMES:
            labels = _prescaler_labels(scheme)
            letter, head = labels.prescaler_symbol, self._head(labels)
            for (row, column), symbol in labels.prescaling_symbols.items():
                if (row, column) == ("prescaling", head):
                    continue
                assert symbol.startswith(letter), f"{scheme}: {row}/{column} scales by {symbol!r}, not {letter}"
            for (row, column), label in labels.column_labels.items():
                if row not in ("prescaling", "complexity") or column == "targets":
                    continue
                text = label(0) if callable(label) else label
                assert letter in text, f"{scheme}: the {row}/{column} index label {text!r} drops {letter}"

    def test_a_size_factor_pretransformer_is_X_because_it_is_no_longer_the_log_prime_matrix(self):
        sized = _prescaler_labels("minimax-lils-S")
        assert sized.prescaler_symbol == "𝑋", "𝑍𝐿 is not 𝐿, so its prescaled tiles cannot read 𝐿C, 𝐿D, 𝐿G"
        assert sized.prescaler_equivalence == " = 𝑍𝐿"
        assert sized.prescaling_symbols[("prescaling", "commas")] == "𝑋C"
        bare = _prescaler_labels("minimax-S")
        assert bare.prescaler_symbol == "𝐿" and bare.prescaler_equivalence == " = 𝐿"
        assert bare.prescaling_symbols[("prescaling", "commas")] == "𝐿C"

    def test_the_head_tile_names_what_the_pretransformer_equals(self):
        for scheme, equivalence in (("minimax-S", " = 𝐿"), ("minimax-sopfr-S", " = diag(𝒑)"),
                                    ("minimax-E-copfr-S", " = 𝐼"), ("minimax-lils-S", " = 𝑍𝐿")):
            labels = _prescaler_labels(scheme)
            assert labels.prescaler_equivalence == equivalence, scheme
            assert grid_tables.SYMBOLS[("prescaling", "superspace_primes")] == "𝑋", \
                "the head tile always carries the general 𝑋; the equivalence says which matrix it is"
