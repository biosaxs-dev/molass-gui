"""User-facing names for internal elution-model keys."""

_MODEL_DISPLAY_NAMES = {}


def model_display_name(model_key):
    return _MODEL_DISPLAY_NAMES.get(model_key.lower(), model_key.upper())
