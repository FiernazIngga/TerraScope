"""Shared theme colors and reusable Qt widgets for DisasterScope."""

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

BACKGROUND = "#0f172a"
PANEL = "#1e293b"
PANEL_LIGHT = "#334155"
TEXT = "#f8fafc"
MUTED = "#94a3b8"
ACCENT = "#22c55e"
ACCENT_HOVER = "#16a34a"
DANGER = "#ef4444"


def create_label(text: str, size: int = 12, color: str = TEXT, bold: bool = False) -> QLabel:
    """Create a styled QLabel with word wrap disabled by default."""
    label = QLabel(text)
    weight = "bold" if bold else "normal"
    label.setStyleSheet(
        f"color: {color}; font-size: {size}px; font-weight: {weight}; background: transparent;"
    )
    return label


def create_card() -> QFrame:
    """Create a dark rounded card container."""
    card = QFrame()
    card.setStyleSheet(
        f"""
        QFrame {{
            background-color: {PANEL};
            border: 1px solid {PANEL_LIGHT};
            border-radius: 8px;
        }}
        """
    )
    return card


def create_nav_button(text: str, checkable: bool = True) -> QPushButton:
    """Create a sidebar/region navigation button with active state styling."""
    btn = QPushButton(text)
    btn.setCheckable(checkable)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"""
        QPushButton {{
            text-align: left;
            padding: 8px 10px;
            border-radius: 6px;
            border: 1px solid transparent;
            background-color: transparent;
            color: {TEXT};
            font-size: 12px;
        }}
        QPushButton:hover {{
            background-color: {PANEL};
            border-color: {PANEL_LIGHT};
        }}
        QPushButton:checked {{
            background-color: #14532d;
            border-color: {ACCENT};
            color: {TEXT};
            font-weight: bold;
        }}
        """
    )
    return btn


def create_action_button(text: str, primary: bool = True) -> QPushButton:
    """Create a primary or secondary action button."""
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {ACCENT};
                color: #052e16;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {ACCENT_HOVER}; color: {TEXT}; }}
            QPushButton:disabled {{ background-color: {PANEL_LIGHT}; color: {MUTED}; }}
            """
        )
    else:
        btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {PANEL_LIGHT};
                color: {TEXT};
                border: none;
                border-radius: 6px;
                padding: 7px 12px;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: #475569; }}
            """
        )
    return btn


class SliderRow(QWidget):
    """Labeled horizontal slider that scales integer steps to float values."""

    def __init__(
        self,
        title: str,
        min_val: float,
        max_val: float,
        default_val: float,
        step: float = 1.0,
        unit: str = "",
    ):
        super().__init__()
        self._step = step
        self._unit = unit

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        self.title_lbl = create_label(title, 11, MUTED)
        self.val_lbl = create_label("", 11, TEXT, bold=True)
        top.addWidget(self.title_lbl)
        top.addStretch()
        top.addWidget(self.val_lbl)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(int(round(min_val / step)))
        self.slider.setMaximum(int(round(max_val / step)))
        self.slider.setValue(int(round(default_val / step)))
        self.slider.setStyleSheet(
            f"""
            QSlider::groove:horizontal {{
                height: 5px;
                background: {PANEL_LIGHT};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {ACCENT};
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
            """
        )
        self.slider.valueChanged.connect(self._update_label)
        self._update_label()

        layout.addLayout(top)
        layout.addWidget(self.slider)

    def _update_label(self):
        val = self.value()
        fmt = f"{val:.1f}" if self._step < 1.0 else f"{int(round(val))}"
        self.val_lbl.setText(f"{fmt}{self._unit}")

    def value(self) -> float:
        return self.slider.value() * self._step


class TaskWorker(QThread):
    """Run CPU-heavy raster simulations or overlay exports off the UI thread."""

    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
