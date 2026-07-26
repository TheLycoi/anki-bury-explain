"""A single reusable AI sidebar docked to Anki's main window.

Original implementation. A persistent QWebEngineProfile keeps cookies/logins
under the add-on's ``user_files/web_profile/`` folder so AI sessions survive
Anki restarts. Kept deliberately small: no toolbars, no navigation chrome.
"""

import os

from aqt import mw
from aqt.qt import (
    QDockWidget,
    Qt,
    QUrl,
    QWidget,
    QVBoxLayout,
)

try:
    from aqt.qt import QWebEngineView, QWebEngineProfile, QWebEnginePage
except ImportError:  # pragma: no cover - Qt build without WebEngine
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage


# Module-level singletons so the profile and dock are created only once.
_dock = None
_view = None
_profile = None


def _profile_dir():
    """Absolute path to the persistent web-profile storage under user_files/."""
    base = os.path.join(os.path.dirname(__file__), "user_files", "web_profile")
    os.makedirs(base, exist_ok=True)
    return base


def _get_profile():
    global _profile
    if _profile is None:
        _profile = QWebEngineProfile("bury_explain", mw)
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


def _build_dock():
    global _dock, _view
    _view = QWebEngineView(mw)
    _view.setPage(QWebEnginePage(_get_profile(), _view))

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(_view)

    _dock = QDockWidget("Bury & Explain", mw)
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


def open_url(url):
    """Create-or-raise the sidebar dock and load ``url`` into it."""
    if _dock is None:
        _build_dock()
    _view.setUrl(QUrl(url))
    _dock.show()
    _dock.raise_()
