"""A single reusable AI sidebar docked to Anki's main window.

Original implementation. A persistent QWebEngineProfile keeps cookies/logins
under the add-on's ``user_files/web_profile/`` folder so AI sessions survive
Anki restarts. Kept deliberately small: a slim text-only header (no icons,
no logos, no provider images) over a single web view.
"""

import os

from aqt import mw
from aqt.qt import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    Qt,
    QUrl,
    QVBoxLayout,
    QWidget,
)
from aqt.utils import openLink

try:
    from aqt.qt import QWebEngineView, QWebEngineProfile, QWebEnginePage
except ImportError:  # pragma: no cover - Qt build without WebEngine
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage


# Module-level singletons so the profile and dock are created only once. The
# profile MUST be kept alive here (and constructed without a parent) so Qt does
# not destroy it before the pages that reference it.
_dock = None
_view = None
_profile = None
_header_label = None
_current_url = ""


def _profile_dir():
    """Absolute path to the persistent web-profile storage under user_files/."""
    base = os.path.join(os.path.dirname(__file__), "user_files", "web_profile")
    os.makedirs(base, exist_ok=True)
    return base


def _get_profile():
    global _profile
    if _profile is None:
        # No parent: the module-level ``_profile`` ref owns its lifetime, so it
        # cannot be torn down ahead of the pages built on it.
        _profile = QWebEngineProfile("bury_explain")
        storage = _profile_dir()
        _profile.setPersistentStoragePath(storage)
        _profile.setCachePath(os.path.join(storage, "cache"))
        try:
            _profile.setPersistentCookiesPolicy(
                QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
            )
        except Exception:
            pass
    return _profile


def _open_current_in_browser():
    if _current_url:
        openLink(_current_url)


def _hide():
    if _dock is not None:
        _dock.hide()


def _flat_button(text, tip, on_click):
    btn = QPushButton(text)
    btn.setFlat(True)
    btn.setToolTip(tip)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        "QPushButton { border: none; color: #888; font-size: 12px; "
        "padding: 2px 6px; background: transparent; }"
        "QPushButton:hover { color: #ddd; }"
    )
    btn.clicked.connect(on_click)
    return btn


def _build_header():
    """Slim flat text-only header: 'AI · <Provider>' left, two buttons right."""
    global _header_label
    header = QWidget()
    header.setObjectName("buryExplainHeader")
    header.setStyleSheet("#buryExplainHeader { border-bottom: 1px solid #444; }")
    row = QHBoxLayout(header)
    row.setContentsMargins(10, 4, 6, 4)
    row.setSpacing(4)

    _header_label = QLabel("AI")
    _header_label.setStyleSheet("color: #888; font-size: 12px;")
    row.addWidget(_header_label)
    row.addStretch(1)
    row.addWidget(_flat_button("↗ browser", "Open the current page in your browser", _open_current_in_browser))
    row.addWidget(_flat_button("✕", "Hide the AI sidebar", _hide))
    return header


def _build_dock():
    global _dock, _view
    _view = QWebEngineView(mw)
    _view.setPage(QWebEnginePage(_get_profile(), _view))

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(_build_header())
    layout.addWidget(_view, 1)

    _dock = QDockWidget("AI", mw)
    _dock.setObjectName("buryExplainDock")
    _dock.setAllowedAreas(
        Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
    )
    _dock.setWidget(container)
    # Closing the dock just hides it; the profile/view are reused next time.
    _dock.setFeatures(
        QDockWidget.DockWidgetFeature.DockWidgetClosable
        | QDockWidget.DockWidgetFeature.DockWidgetMovable
        | QDockWidget.DockWidgetFeature.DockWidgetFloatable
    )
    mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, _dock)
    if mw.width() > 900:
        mw.resizeDocks([_dock], [max(420, mw.width() // 3)], Qt.Orientation.Horizontal)


def open_url(url, provider_label=""):
    """Create-or-raise the sidebar dock and load ``url`` into it."""
    global _current_url
    if _dock is None:
        _build_dock()
    _current_url = url
    if _header_label is not None:
        _header_label.setText(f"AI · {provider_label}" if provider_label else "AI")
    _view.setUrl(QUrl(url))
    _dock.show()
    _dock.raise_()


def is_visible():
    """True only if the dock has been built and is currently shown."""
    return _dock is not None and _dock.isVisible()


def hide_dock():
    """Hide the dock if it exists (no-op otherwise)."""
    _hide()
