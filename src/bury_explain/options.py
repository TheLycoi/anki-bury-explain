"""Minimalist options dialog for Bury Explain.

A single flat column: small gray uppercase section headers over plain rows.
No tabs, no icons. Reads/writes config via the add-on manager.
"""

from aqt import mw
from aqt.qt import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    Qt,
    QVBoxLayout,
)

from . import logic

# (label shown to user, value stored in config) for the provider combo.
_PROVIDERS = [
    ("ChatGPT", "chatgpt"),
    ("Claude", "claude"),
    ("Perplexity", "perplexity"),
    ("DuckDuckGo", "duckduckgo"),
    ("Gemini", "gemini"),
    ("Custom", "custom"),
]

_OPEN_IN = [
    ("Sidebar", "sidebar"),
    ("System browser", "browser"),
]


def _section(text):
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "color: #888; font-size: 11px; font-weight: bold; "
        "letter-spacing: 1px; margin-top: 14px;"
    )
    return lbl


def _row(label_text, widget):
    row = QHBoxLayout()
    lbl = QLabel(label_text)
    lbl.setMinimumWidth(150)
    row.addWidget(lbl)
    row.addWidget(widget, 1)
    return row


class OptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle("Bury Explain Options")
        self.setMinimumWidth(450)
        self._cfg = {**logic.DEFAULT_CONFIG, **(mw.addonManager.getConfig(__name__.rsplit(".", 1)[0]) or {})}
        self._build()
        self._load(self._cfg)

    # ---- widget construction ----
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(8)

        # GENERAL
        outer.addWidget(_section("GENERAL"))
        self.enabled = QCheckBox("Enabled")
        outer.addWidget(self.enabled)

        self.threshold = QSpinBox()
        self.threshold.setRange(1, 10)
        outer.addLayout(_row("Again threshold", self.threshold))

        self.window_hours = QSpinBox()
        self.window_hours.setRange(1, 168)
        outer.addLayout(_row("Time window (hours)", self.window_hours))

        self.ignore_new = QCheckBox("Ignore new / learning cards")
        outer.addWidget(self.ignore_new)
        self.skip_image = QCheckBox("Skip image / occlusion cards")
        outer.addWidget(self.skip_image)
        self.notifications = QCheckBox("Show notifications")
        outer.addWidget(self.notifications)

        # BURY
        outer.addWidget(_section("BURY"))
        self.bury = QCheckBox("Bury the card when triggered")
        outer.addWidget(self.bury)
        self.add_tag = QCheckBox("Tag the card")
        self.add_tag.toggled.connect(self._sync_tag_enabled)
        outer.addWidget(self.add_tag)
        self.tag = QLineEdit()
        outer.addLayout(_row("Tag to add", self.tag))

        # AI
        outer.addWidget(_section("AI"))
        self.provider = QComboBox()
        for label, _ in _PROVIDERS:
            self.provider.addItem(label)
        self.provider.currentIndexChanged.connect(self._sync_custom_enabled)
        outer.addLayout(_row("Provider", self.provider))

        self.custom_url = QLineEdit()
        self.custom_url.setPlaceholderText("https://example.com/?q={q}")
        outer.addLayout(_row("Custom URL", self.custom_url))

        self.open_in = QComboBox()
        for label, _ in _OPEN_IN:
            self.open_in.addItem(label)
        outer.addLayout(_row("Open in", self.open_in))

        outer.addWidget(QLabel("Prompt template ({agains}, {card})"))
        self.prompt = QPlainTextEdit()
        self.prompt.setMinimumHeight(110)
        outer.addWidget(self.prompt)

        # Buttons
        outer.addSpacing(10)
        btns = QHBoxLayout()
        restore = QPushButton("Restore Defaults")
        restore.clicked.connect(self._restore)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setDefault(True)
        save.clicked.connect(self._save)
        btns.addWidget(restore)
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(save)
        outer.addLayout(btns)

    # ---- helpers ----
    def _sync_custom_enabled(self):
        is_custom = _PROVIDERS[self.provider.currentIndex()][1] == "custom"
        self.custom_url.setEnabled(is_custom)

    def _sync_tag_enabled(self):
        self.tag.setEnabled(self.add_tag.isChecked())

    def _load(self, cfg):
        self.enabled.setChecked(bool(cfg.get("enabled", True)))
        self.threshold.setValue(int(cfg.get("again_threshold", 3)))
        self.window_hours.setValue(int(cfg.get("timeframe_hours", 24)))
        self.ignore_new.setChecked(bool(cfg.get("ignore_new_cards", False)))
        self.skip_image.setChecked(bool(cfg.get("skip_image_cards", True)))
        self.notifications.setChecked(bool(cfg.get("show_notification", True)))
        self.bury.setChecked(bool(cfg.get("bury", True)))
        self.add_tag.setChecked(bool(cfg.get("add_tag", True)))
        self.tag.setText(str(cfg.get("tag", "")))
        self._sync_tag_enabled()
        self._select(self.provider, _PROVIDERS, cfg.get("provider", "chatgpt"))
        self.custom_url.setText(str(cfg.get("custom_url", "")))
        self._select(self.open_in, _OPEN_IN, cfg.get("open_in", "sidebar"))
        self.prompt.setPlainText(str(cfg.get("prompt_template", "")))
        self._sync_custom_enabled()

    @staticmethod
    def _select(combo, pairs, value):
        for i, (_, v) in enumerate(pairs):
            if v == value:
                combo.setCurrentIndex(i)
                return
        combo.setCurrentIndex(0)

    def _restore(self):
        self._load(logic.DEFAULT_CONFIG)

    def _save(self):
        cfg = {
            "enabled": self.enabled.isChecked(),
            "again_threshold": self.threshold.value(),
            "timeframe_hours": self.window_hours.value(),
            "ignore_new_cards": self.ignore_new.isChecked(),
            "skip_image_cards": self.skip_image.isChecked(),
            "show_notification": self.notifications.isChecked(),
            "bury": self.bury.isChecked(),
            "add_tag": self.add_tag.isChecked(),
            "tag": self.tag.text().strip(),
            "provider": _PROVIDERS[self.provider.currentIndex()][1],
            "custom_url": self.custom_url.text().strip(),
            "open_in": _OPEN_IN[self.open_in.currentIndex()][1],
            "prompt_template": self.prompt.toPlainText(),
        }
        mw.addonManager.writeConfig(__name__.rsplit(".", 1)[0], cfg)
        self.accept()


def open_options():
    dlg = OptionsDialog(mw)
    dlg.setModal(True)
    dlg.exec()
