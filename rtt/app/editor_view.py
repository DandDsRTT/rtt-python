from __future__ import annotations

from rtt.app import editor_solve, presets, service


class _TuningQueries:
    def _solve(self) -> editor_solve.Solve:
        return editor_solve.solve_model(self)

    @property
    def tuning_scheme_options(self) -> dict[str, str]:
        return presets.tuning_scheme_options(
            service.is_all_interval(self.tuning_scheme),
            self.settings["alt_complexity"],
            self.settings["weighting"],
            self.settings["dd_terminology"],
        )

    def optimum_tuning(self) -> service.Tuning:
        return editor_solve.optimum_tuning(self._solve())

    def optimum_generator_tuning(self) -> tuple[float, ...]:
        return editor_solve.optimum_generator_tuning(self._solve())

    def optimum_superspace_generator_tuning(self) -> tuple[float, ...]:
        return editor_solve.optimum_superspace_generator_tuning(self._solve())

    def effective_generator_tuning(self) -> tuple[float, ...] | None:
        return editor_solve.effective_generator_tuning(self._solve())

    @property
    def displayed_tuning_scheme_name(self) -> str | None:
        return editor_solve.displayed_tuning_scheme_name(self._solve())

    @property
    def tuning_is_optimized(self) -> bool:
        return editor_solve.tuning_is_optimized(self._solve())

    @property
    def displayed_prescaler_name(self) -> str | None:
        return editor_solve.displayed_prescaler_name(self._solve())

    def displayed_retuning_map(self) -> tuple[float, ...] | None:
        return editor_solve.displayed_retuning_map(self._solve())

    @property
    def unchanged_ratios(self) -> tuple[str, ...]:
        return editor_solve.unchanged_ratios(self._solve())

    @property
    def targets_in_use(self) -> bool:
        return editor_solve.targets_in_use(self._solve())

    @property
    def displayed_projection_scheme_name(self) -> str | None:
        return editor_solve.displayed_projection_scheme_name(self._solve())
