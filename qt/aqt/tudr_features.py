# Tudr features module
# This lightweight module hooks into Anki's reviewer to mark cards that were
# answered incorrectly, paving the way for daily analytics and practice decks.

from __future__ import annotations

import time
from typing import Any, List, Tuple

from . import gui_hooks  # type: ignore
from anki.cards import Card  # type: ignore
from anki.notes import Note  # type: ignore

# Tag applied to notes that were answered incorrectly today
_WEAK_TAG = "TudrWeak"

# In-memory log of (card_id, ease, timestamp)
_review_log: List[Tuple[int, int, int]] = []


def _tag_note(note: Note) -> None:
    """Add the Tudr weak tag to the given note if not already present."""
    if not note.has_tag(_WEAK_TAG):
        note.add_tag(_WEAK_TAG)
        note.flush()


def _on_card_answered(reviewer: Any, card: Card, ease: int) -> None:  # noqa: ANN401
    """Hook invoked each time a card is answered during review."""
    global _review_log

    # Log every answer
    _review_log.append((card.id, ease, int(time.time())))

    # If answered "Again" (ease==1), consider it a weakness
    if ease == 1:
        _tag_note(card.note())


# Register the hook when module is imported
if gui_hooks.reviewer_did_answer_card.count() == 0 or _on_card_answered not in gui_hooks.reviewer_did_answer_card:  # type: ignore[attr-defined]
    gui_hooks.reviewer_did_answer_card.append(_on_card_answered)  # type: ignore[attr-defined]


# Placeholder for future daily report/deck creation logic
# -------------------------------------------------------
# The current implementation focuses on tagging weak cards on-the-fly. Future
# iterations will generate daily analytics and build a filtered "Tudr" deck
# based on these tags. This stub ensures the hooks are in place without adding
# complexity that might disrupt normal Anki usage.