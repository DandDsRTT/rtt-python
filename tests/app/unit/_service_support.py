from rtt.app import service, spreadsheet
from rtt.app import settings as app_settings


def _grid_with_plain_text(state, scheme, custom_prescaler=None, **extra):
    se = app_settings.defaults()
    se.update({"plain_text_values": True, "weighting": True, "alt_complexity": True})
    se.update(extra)
    return spreadsheet._GridBuilder(state, se, None, service.resolve_tuning_scheme(scheme), "TILT",
                                    custom_prescaler=custom_prescaler)


def _barbados_state():
    return service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
