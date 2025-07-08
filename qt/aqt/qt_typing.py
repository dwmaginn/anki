from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Re-export frequently used Qt classes for static type checking.
    from aqt.qt import (  # type: ignore[attr-defined,import-error]
        QDialog,
        QVBoxLayout,
        QTextEdit,
        QLineEdit,
        QPushButton,
        QMessageBox,
        QWidget,
        QAction,
    )

__all__: list[str] = []