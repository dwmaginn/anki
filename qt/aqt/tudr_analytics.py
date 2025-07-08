# Tudr analytics and daily report generation

"""This module runs once per application session (after the profile is opened)
    to generate a daily performance report and build/update the Tudr practice deck.

    The logic is intentionally simple:
    1. When the profile is opened, check last report date stored in collection
       config (key: "tudr_last_report_date"). If it differs from today,
       generate a report covering the previous 24 h (failures and totals).
    2. Create/update a filtered deck named "Tudr Practice" that contains cards
       tagged with the `_WEAK_TAG` tag (added in `tudr_features.py`). The deck is
       configured *not* to reschedule cards – it’s purely extra practice.

    The implementation avoids heavy dependence on Anki internals and should be
    robust across versions.
"""

from __future__ import annotations

import datetime as _dt
import time
from collections import Counter
from typing import List

from . import gui_hooks, mw  # type: ignore
from .qt import QMessageBox  # type: ignore[attr-defined,import-error]
from anki.decks import DeckId  # type: ignore
from anki.scheduler import FilteredDeckForUpdate  # type: ignore
from anki.decks import FilteredDeckConfig  # type: ignore

from .tudr_features import _WEAK_TAG  # reuse tag constant


_REPORT_DATE_KEY = "tudr_last_report_date"
_TUDR_DECK_NAME = "Tudr Practice"


def _human_date(d: _dt.date) -> str:
    return d.strftime("%b %d, %Y")


def _generate_report(col) -> None:
    """Generate yesterday’s performance summary and show the user."""

    now_ts = int(time.time())
    ts_start = now_ts - 86400  # last 24h

    # Query revlog for reviews in last 24h
    rows = col.db.all("SELECT cid, ease FROM revlog WHERE id >= ?", ts_start * 1000)

    total_reviews = len(rows)
    if total_reviews == 0:
        return  # nothing to report

    wrong_cards: List[int] = [cid for cid, ease in rows if ease == 1]

    # Build topic counters based on deck names (simple heuristic)
    topic_counts: Counter[str] = Counter()
    for cid in wrong_cards:
        try:
            card = col.get_card(cid)
        except Exception:
            continue
        deck_name = col.decks.name(card.did)
        topic_counts[deck_name] += 1

    # Compose report text
    date_str = _human_date(_dt.date.today() - _dt.timedelta(days=1))
    accuracy = 100.0 * (total_reviews - len(wrong_cards)) / total_reviews
    lines = [
        f"Tudr Daily Report – {date_str}",
        "",
        f"You reviewed {total_reviews} cards yesterday and answered {accuracy:.1f}% correctly.",
    ]

    if topic_counts:
        lines.append("\nWeakest topics:")
        for topic, count in topic_counts.most_common(3):
            lines.append(f" • {topic}: {count} incorrect")
    else:
        lines.append("\nGreat job – no incorrect answers!")

    # Build summarised message
    msg = "\n".join(lines)

    # Display to user (modal but non-blocking at startup)
    QMessageBox.information(mw, "Tudr Daily Report", msg)


def _create_or_update_tudr_deck(col) -> None:
    """Create or update the Tudr filtered deck based on the weak-tag."""
    # Find existing deck by name
    did: DeckId | None = col.decks.id_for_name(_TUDR_DECK_NAME)
    if did is None:
        did = DeckId(0)  # create new
    fd: FilteredDeckForUpdate = col.sched.get_or_create_filtered_deck(deck_id=did)

    fd.name = _TUDR_DECK_NAME
    cfg: FilteredDeckConfig = fd.config
    cfg.reschedule = False  # practice only, don’t change intervals

    # Define a single search term: cards tagged with TudrWeak
    cfg.search_terms.clear()
    cfg.search_terms.append(
        FilteredDeckConfig.SearchTerm(search=f"tag:{_WEAK_TAG}", limit=100, order=0)
    )

    # Save deck (synchronously OK at startup)
    col.sched.add_or_update_filtered_deck(fd)


def _on_profile_open() -> None:
    """Entry point after profile is opened."""
    if mw is None or mw.col is None:
        return

    col = mw.col
    today_str = _dt.date.today().isoformat()
    last_date = col.get_config(_REPORT_DATE_KEY, "")

    if last_date == today_str:
        return  # already generated today

    # Generate before updating key so we don’t skip on errors
    try:
        _generate_report(col)
        _create_or_update_tudr_deck(col)
    finally:
        col.set_config(_REPORT_DATE_KEY, today_str)


# Register hook once at import time
if _on_profile_open not in gui_hooks.profile_did_open:  # type: ignore[attr-defined]
    gui_hooks.profile_did_open.append(_on_profile_open)  # type: ignore[attr-defined]