"""A single reusable AI sidebar docked to Anki's main window.

Original implementation. A persistent QWebEngineProfile keeps cookies/logins
under the add-on's ``user_files/web_profile/`` folder so AI sessions survive
Anki restarts. Kept deliberately small: a slim text-only header (no icons,
no logos, no provider images) over a single web view.
"""

import json
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
# Prompt to auto-type into the page once the next load finishes. Used to keep
# ChatGPT in a real Temporary Chat: we load ?temporary-chat=true with no `q`
# (a q= auto-submit would create a saved conversation and drop temp mode), then
# type + send the prompt ourselves after the composer appears.
_pending_prompt = None


def _inject_prompt_js(prompt):
    """JS that polls for the composer, types ``prompt``, then clicks send.

    Kept defensive: it retries while ChatGPT's React app mounts, tries a few
    known selectors, and never throws if the page shape is unexpected (e.g. a
    login wall). Selectors track ChatGPT's current DOM and may need updating if
    they change their UI.
    """
    payload = json.dumps(prompt)
    return (
        "(function(){"
        "var PROMPT=" + payload + ";"
        "var tries=0;"
        "var t=setInterval(function(){"
        "  tries++;"
        "  var box=document.querySelector('#prompt-textarea')"
        "    ||document.querySelector('div[contenteditable=\"true\"]')"
        "    ||document.querySelector('textarea');"
        "  if(!box){ if(tries>120){clearInterval(t);} return; }"
        "  clearInterval(t);"
        "  box.focus();"
        "  try{"
        "    if(box.tagName==='TEXTAREA'){"
        "      var d=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value');"
        "      d.set.call(box,PROMPT);"
        "      box.dispatchEvent(new Event('input',{bubbles:true}));"
        "    } else {"
        "      document.execCommand('insertText',false,PROMPT);"
        "    }"
        "  }catch(e){}"
        "  var st=0;"
        "  var s=setInterval(function(){"
        "    st++;"
        "    var btn=document.querySelector('[data-testid=\"send-button\"]')"
        "      ||document.querySelector('button[aria-label*=\"Send\"]');"
        "    if(btn&&!btn.disabled){ clearInterval(s); btn.click(); }"
        "    else if(st>40){ clearInterval(s); }"
        "  },200);"
        "},200);"
        "})();"
    )


def _on_load_finished(ok):
    """After a navigation completes, run any queued prompt injection once."""
    global _pending_prompt
    if not ok or not _pending_prompt or _view is None:
        return
    prompt = _pending_prompt
    _pending_prompt = None
    _view.page().runJavaScript(_inject_prompt_js(prompt))


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
    _view.loadFinished.connect(_on_load_finished)

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


def open_url(url, provider_label="", inject_prompt=None):
    """Create-or-raise the sidebar dock and load ``url`` into it.

    If ``inject_prompt`` is given, it is typed into the page and sent once the
    load finishes (used to fill a Temporary Chat without a q= auto-submit).
    """
    global _current_url, _pending_prompt
    if _dock is None:
        _build_dock()
    _current_url = url
    _pending_prompt = inject_prompt or None
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
