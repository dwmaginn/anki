from __future__ import annotations

from typing import List, TYPE_CHECKING

# During runtime, the Qt bindings are available; during static analysis they may not be.
if TYPE_CHECKING:  # pragma: no cover
    from .qt import QDialog, QVBoxLayout, QTextEdit, QLineEdit, QPushButton
else:
    try:
        from .qt import QDialog, QVBoxLayout, QTextEdit, QLineEdit, QPushButton  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover
        QDialog = QVBoxLayout = QTextEdit = QLineEdit = QPushButton = object  # type: ignore
from . import mw  # type: ignore
# Standard library
import os


class TutorDialog(QDialog):
    """Interactive ChatGPT-powered tutor dialog for a single card."""

    def __init__(self, parent, question: str, answer: str):
        super().__init__(parent)
        self.setWindowTitle("Tutor – ChatGPT")
        self.resize(500, 600)

        self._messages: List[dict[str, str]] = [
            {"role": "system", "content": "You are a helpful tutor for flashcards."},
            {"role": "user", "content": f"Q: {question}\nA: {answer}\nPlease explain this answer in detail."},
        ]

        self.layout = QVBoxLayout(self)
        self.chat_view = QTextEdit(self)
        self.chat_view.setReadOnly(True)
        self.layout.addWidget(self.chat_view)

        self.input_line = QLineEdit(self)
        self.layout.addWidget(self.input_line)

        send_btn = QPushButton("Send", self)
        send_btn.clicked.connect(self._on_send_clicked)
        self.layout.addWidget(send_btn)

        # immediately fetch first explanation
        self._append_chat("You", "Explain")
        self._ask_openai()

    # Utility
    def _append_chat(self, speaker: str, text: str) -> None:
        self.chat_view.append(f"<b>{speaker}:</b> {text}")

    # Slot
    def _on_send_clicked(self):
        user_text = self.input_line.text().strip()
        if not user_text:
            return
        self.input_line.clear()
        self._append_chat("You", user_text)
        self._messages.append({"role": "user", "content": user_text})
        self._ask_openai()

    def _ask_openai(self):
        # run in background to avoid blocking UI
        def worker() -> str:
            try:
                import openai  # type: ignore[import-error]

                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    return "OpenAI API key not set. Set OPENAI_API_KEY env var."
                openai.api_key = api_key
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=self._messages,
                    max_tokens=300,
                )
                return response["choices"][0]["message"]["content"].strip()
            except Exception as e:
                return f"Error contacting OpenAI: {e}"

        def done(fut):  # type: ignore
            text = fut.result()
            self._append_chat("Tutor", text)
            self._messages.append({"role": "assistant", "content": text})

        mw.taskman.run_in_background(worker, done, uses_collection=False)