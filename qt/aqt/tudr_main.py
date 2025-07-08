from __future__ import annotations
"""Tudr main initialisation.

This module is imported once by `aqt.__init__`, and registers a callback on
`profile_did_open`.  When the user profile is opened (ie. a collection is
loaded), we lazily import Tudr sub-modules.  Importing them earlier leads to
circular-import issues, because they expect `aqt.mw` to be available.
"""

from typing import TYPE_CHECKING
from importlib import import_module

from _aqt.hooks import profile_did_open  # type: ignore[misc]

if TYPE_CHECKING:  # pragma: no cover
    import aqt


def _load_submodules(_: "aqt.AnkiQt") -> None:  # noqa: D401 – simple callback
    """Import Tudr feature modules after the profile is open."""

    # Import only once
    if getattr(_load_submodules, "_done", False):  # type: ignore[attr-defined]
        return

    import_module("aqt.tudr_features")
    import_module("aqt.tudr_analytics")
    import_module("aqt.tudr_tutor")
    # Future: settings, classification, etc.

    _load_submodules._done = True  # type: ignore[attr-defined]


# Register the hook (type ignored, as hooks are dynamically generated)
profile_did_open.append(_load_submodules)  # type: ignore[misc]