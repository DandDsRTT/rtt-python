import pkgutil

import rtt.library
from rtt.bot.library_reference import library_reference


class TestLibraryReference:
    def test_lists_every_public_function_of_every_library_module_with_its_signature(self):
        reference = library_reference()
        assert "## rtt.library.parsing" in reference
        assert "parse_temperament_data(data: str | Temperament) -> Temperament" in reference
        assert "optimize_generator_tuning_map(" in reference
        assert "## rtt.library.tuning_scheme_names" in reference
        assert "_reject_junk" not in reference

    def test_describes_the_temperament_value_object_and_its_variance(self):
        reference = library_reference()
        assert "class Temperament" in reference
        assert "matrix: tuple[tuple[int, ...], ...]" in reference
        assert "class Variance" in reference
        assert "ROW" in reference and "COL" in reference

    def test_every_module_has_a_heading_in_sorted_order_so_the_prompt_is_cache_stable(self):
        headings = [line[3:] for line in library_reference().splitlines() if line.startswith("## ")]
        assert headings == sorted(headings)
        assert headings == sorted(f"rtt.library.{info.name}" for info in pkgutil.iter_modules(rtt.library.__path__))

    def test_cached_functions_are_listed_like_plain_ones(self):
        assert "get_primes(count: int) -> tuple" in library_reference()
