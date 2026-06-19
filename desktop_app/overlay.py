"""Career Copilot Premium - World Class Overlay v2"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

QT_IMPORT_ERROR: str | None = None

try:
    from PySide6.QtCore import Qt, QPoint, QTimer, QSize, QObject, Signal
    from PySide6.QtGui import QColor, QFont, QCursor, QFontMetrics
    from PySide6.QtWidgets import (
        QApplication, QLabel, QPushButton, QVBoxLayout,
        QHBoxLayout, QWidget, QScrollArea, QFrame,
        QLineEdit, QSlider, QSizeGrip, QTextBrowser,
        QSplitter, QComboBox,
    )
    QT_AVAILABLE = True
except ImportError as e:
    QApplication = None
    QWidget = object
    QT_AVAILABLE = False
    QT_IMPORT_ERROR = str(e)


@dataclass
class OverlayState:
    status: str
    transcript: str = ""
    suggested_answer: str = ""
    alternatives: list[str] = field(default_factory=list)
    confidence_score: int = 0
    provider_status: str = ""
    opacity: float = 0.92
    visible: bool = True


class OverlayWindow(Protocol):
    def apply_state(self, state: OverlayState) -> None: ...
    def show(self) -> None: ...
    def hide(self) -> None: ...
    def close(self) -> None: ...


@dataclass
class OverlayRuntime:
    app: object | None
    controller: "LiveOverlayController"

    @property
    def owns_event_loop(self) -> bool:
        return self.app is not None

    def run(self) -> int:
        if self.app is None:
            return 0
        return self.app.exec()


def build_listening_overlay(opacity: float = 0.92) -> OverlayState:
    return OverlayState(status="listening", provider_status="Listening", opacity=opacity)


def build_answer_overlay(transcript, suggested_answer, alternatives, confidence_score, provider_status="", opacity=0.92):
    return OverlayState(
        status="answer_ready",
        transcript=transcript,
        suggested_answer=suggested_answer,
        alternatives=alternatives,
        confidence_score=confidence_score,
        provider_status=provider_status,
        opacity=opacity,
        visible=True,
    )


def build_preview_overlay_state() -> OverlayState:
    return build_answer_overlay(
        transcript="Why should we hire you for this backend engineering role?",
        suggested_answer="My strongest skill is Python backend delivery. At Northstar Labs, I improved API response times by 38% and turned that into measurable release stability. I bring ownership, speed, and backend depth that maps directly to your requirements.",
        alternatives=[
            "Short: I bring Python depth, measurable impact, and calm execution.",
            "Impact: I combine backend ownership with clear business results.",
            "Formal: With 4.5 years of Python backend experience, I deliver measurable outcomes.",
        ],
        confidence_score=91,
        provider_status="Ollama(llama3.2:3b)",
        opacity=0.92,
    )


def qt_runtime_available() -> bool:
    return QT_AVAILABLE


def qt_runtime_error_message() -> str:
    if QT_IMPORT_ERROR:
        return f"PySide6 could not be imported: {QT_IMPORT_ERROR}"
    return "PySide6 is not installed."


class LiveOverlayController:
    def __init__(self, window=None, initial_state=None):
        self.window = window
        self.state = initial_state or OverlayState(status="idle", visible=False)

    @property
    def active(self):
        return self.window is not None

    def update(self, state):
        self.state = state
        if self.window is None:
            return self.state
        self.window.apply_state(state)
        if state.visible:
            self.window.show()
        else:
            self.window.hide()
        return self.state

    def hide(self):
        hidden = OverlayState(
            status=self.state.status,
            transcript=self.state.transcript,
            suggested_answer=self.state.suggested_answer,
            alternatives=list(self.state.alternatives),
            confidence_score=self.state.confidence_score,
            provider_status=self.state.provider_status,
            opacity=self.state.opacity,
            visible=False,
        )
        return self.update(hidden)

    def shutdown(self):
        if self.window is not None:
            self.window.close()


def create_overlay_controller(theme="dark", initial_state=None):
    state = initial_state or build_preview_overlay_state()
    return LiveOverlayController(initial_state=state)


def create_overlay_runtime(theme="dark", initial_state=None, qt_app=None):
    state = initial_state or build_preview_overlay_state()
    if not QT_AVAILABLE or QApplication is None:
        return OverlayRuntime(app=None, controller=LiveOverlayController(initial_state=state))
    app = qt_app or QApplication.instance()
    owned_app = None
    if app is None:
        app = QApplication([])
        owned_app = app
    controller = LiveOverlayController(TransparentOverlayWindow(state), initial_state=state)
    return OverlayRuntime(app=owned_app, controller=controller)


def build_overlay_stylesheet(theme="dark"):
    return ""


if QT_AVAILABLE:

    STYLE = {
        "bg":       "#0D1117",
        "bg2":      "#161B22",
        "bg3":      "#1C2128",
        "border":   "#30363D",
        "accent":   "#58A6FF",
        "green":    "#3FB950",
        "yellow":   "#D29922",
        "red":      "#F85149",
        "text":     "#E6EDF3",
        "text2":    "#8B949E",
        "btn":      "#21262D",
        "btnhov":   "#30363D",
    }

    def _btn(label, color, hover_bg=None):
        hbg = hover_bg or STYLE["btnhov"]
        return f"""
            QPushButton {{
                background: {STYLE['btn']};
                color: {color};
                border: 1px solid {STYLE['border']};
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 12px;
                font-weight: 600;
                font-family: 'Segoe UI';
                min-height: 32px;
            }}
            QPushButton:hover {{
                background: {hbg};
                border-color: {color};
                color: #fff;
            }}
            QPushButton:pressed {{
                background: {color};
                color: #000;
            }}
        """

    class ManualAnswerSignals(QObject):
        """Thread-safe bridge: emit from worker threads, handle on the Qt main thread."""

        answer_ready = Signal(str, str, str, object, int)
        answer_failed = Signal(str, str)
        listen_ready = Signal(str, str, str, object, int)
        listen_failed = Signal(str)

    class StatusBarSignals(QObject):
        status_ready = Signal(bool, str, bool, str, str, str)

    class TransparentOverlayWindow(QWidget):

        def __init__(self, state: OverlayState, theme="dark"):
            super().__init__()
            self.state = state
            self._drag_pos = QPoint()
            self._minimized = False
            self._stealth = False
            self._history: list[dict] = []
            self._show_hist = False
            self._manual_signals = ManualAnswerSignals()
            self._manual_signals.answer_ready.connect(self._apply_manual_answer)
            self._manual_signals.answer_failed.connect(self._apply_manual_error)
            self._manual_signals.listen_ready.connect(self._apply_manual_answer)
            self._manual_signals.listen_failed.connect(self._apply_listen_error)
            self._status_signals = StatusBarSignals()
            self._status_signals.status_ready.connect(self._on_status_bar_ready)
            self.dashboard_url = "http://127.0.0.1:5000"
            self.current_session_id = ""

            self.setWindowTitle("Career Copilot")
            self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setMinimumSize(380, 300)
            self.resize(460, 600)
            self.setWindowOpacity(state.opacity)

            self._build_ui()
            self.apply_state(state)
            self._status_timer = QTimer(self)
            self._status_timer.timeout.connect(self._refresh_status_bar)
            self._status_timer.start(30000)
            self._refresh_status_bar_sync()
            try:
                from .mistral_setup import refresh_mistral_validation_async

                refresh_mistral_validation_async(force=True)
            except Exception:
                pass
            self._status_refresh_inflight = False

            self._last_api_status = ""
            self._last_audio_status = ""
            self._restore_overlay_position()

        def _build_ui(self):
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)

            self._card = QFrame(self)
            self._card.setObjectName("card")
            self._card.setStyleSheet(f"""
                #card {{
                    background: {STYLE['bg']};
                    border: 1px solid {STYLE['border']};
                    border-radius: 14px;
                }}
            """)
            root.addWidget(self._card)

            vbox = QVBoxLayout(self._card)
            vbox.setContentsMargins(0, 0, 0, 0)
            vbox.setSpacing(0)

            # Title bar
            tbar = QWidget()
            tbar.setFixedHeight(44)
            tbar.setCursor(QCursor(Qt.SizeAllCursor))
            tbar.setStyleSheet(f"""
                background: {STYLE['bg2']};
                border-radius: 14px 14px 0 0;
                border-bottom: 1px solid {STYLE['border']};
            """)
            tbar.mousePressEvent = self._tbar_press
            tbar.mouseMoveEvent = self._tbar_move
            tbar.mouseReleaseEvent = self._tbar_release

            tl = QHBoxLayout(tbar)
            tl.setContentsMargins(14, 0, 10, 0)
            tl.setSpacing(6)

            ico = QLabel("*")
            ico.setStyleSheet("font-size:16px;")
            tl.addWidget(ico)

            title = QLabel("Career Copilot Premium")
            title.setStyleSheet(f"color:{STYLE['accent']};font-size:12px;font-weight:700;font-family:'Segoe UI';")
            tl.addWidget(title)
            tl.addStretch()

            self._pill = QLabel("READY")
            self._pill.setStyleSheet(self._pill_style(STYLE['green'], "rgba(63,185,80,0.12)"))
            tl.addWidget(self._pill)

            for sym, cb, col in [
                ("S", self._toggle_stealth, STYLE['yellow']),
                ("H", self._toggle_history, STYLE['accent']),
                ("-", self._toggle_min,     STYLE['text2']),
                ("X", self.hide,            STYLE['red']),
            ]:
                b = QPushButton(sym)
                b.setFixedSize(28, 28)
                b.setCursor(QCursor(Qt.PointingHandCursor))
                b.setStyleSheet(f"""
                    QPushButton{{background:transparent;color:{col};border:none;font-size:13px;border-radius:6px;}}
                    QPushButton:hover{{background:{STYLE['btnhov']};}}
                """)
                b.clicked.connect(cb)
                tl.addWidget(b)

            vbox.addWidget(tbar)

            # Scrollable body
            self._body_scroll = QScrollArea()
            self._body_scroll.setWidgetResizable(True)
            self._body_scroll.setFrameShape(QFrame.NoFrame)
            self._body_scroll.setStyleSheet(f"""
                QScrollArea{{background:transparent;border:none;}}
                QScrollBar:vertical{{background:{STYLE['bg']};width:6px;border-radius:3px;}}
                QScrollBar::handle:vertical{{background:{STYLE['border']};border-radius:3px;min-height:20px;}}
                QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}
            """)

            body = QWidget()
            body.setStyleSheet(f"background:{STYLE['bg']};")
            bl = QVBoxLayout(body)
            bl.setContentsMargins(14, 12, 14, 8)
            bl.setSpacing(10)

            bl.addWidget(self._section_label("INTERVIEWER SAID"))
            self._q_box = QTextBrowser()
            self._q_box.setMinimumHeight(52)
            self._q_box.setMaximumHeight(90)
            self._q_box.setStyleSheet(self._box_style(STYLE['border']))
            self._q_box.setText("Listening for interviewer question...")
            bl.addWidget(self._q_box)

            bl.addWidget(self._section_label("SUGGESTED ANSWER", STYLE['accent']))
            self._a_box = QTextBrowser()
            self._a_box.setMinimumHeight(90)
            self._a_box.setStyleSheet(self._box_style(STYLE['accent'], bg=STYLE['bg3']))
            self._a_box.setText("Processing answer...")
            bl.addWidget(self._a_box)

            cr = QHBoxLayout()
            self._conf_lbl = QLabel("CONFIDENCE")
            self._conf_lbl.setStyleSheet(f"color:{STYLE['text2']};font-size:10px;font-family:'Segoe UI';")
            self._conf_val = QLabel("0%")
            self._conf_val.setStyleSheet(f"color:{STYLE['green']};font-size:11px;font-weight:700;font-family:'Segoe UI';")
            self._prov_lbl = QLabel("AI ---")
            self._prov_lbl.setStyleSheet(f"color:{STYLE['text2']};font-size:10px;font-family:'Segoe UI';")
            cr.addWidget(self._conf_lbl)
            cr.addWidget(self._conf_val)
            cr.addStretch()
            cr.addWidget(self._prov_lbl)
            bl.addLayout(cr)

            bl.addWidget(self._section_label("ALTERNATIVES"))
            self._alt_box = QTextBrowser()
            self._alt_box.setMinimumHeight(70)
            self._alt_box.setMaximumHeight(110)
            self._alt_box.setStyleSheet(self._box_style(STYLE['border']))
            bl.addWidget(self._alt_box)

            self._hist_frame = QFrame()
            self._hist_frame.setVisible(False)
            hfl = QVBoxLayout(self._hist_frame)
            hfl.setContentsMargins(0, 0, 0, 0)
            hfl.setSpacing(4)
            hfl.addWidget(self._section_label("SESSION HISTORY"))
            self._hist_box = QTextBrowser()
            self._hist_box.setFixedHeight(110)
            self._hist_box.setStyleSheet(self._box_style(STYLE['border']))
            hfl.addWidget(self._hist_box)
            bl.addWidget(self._hist_frame)

            bl.addWidget(self._section_label("LANGUAGE SETTINGS"))
            lang_row = QHBoxLayout()
            lang_row.setSpacing(8)
            listen_lbl = QLabel("Listen:")
            listen_lbl.setStyleSheet(f"color:{STYLE['text2']};font-size:10px;font-family:'Segoe UI';")
            self._listen_lang = QComboBox()
            self._reply_lang = QComboBox()
            for label, code in self._language_options():
                self._listen_lang.addItem(label, code)
                self._reply_lang.addItem(label, code)
            self._load_language_controls()
            self._listen_lang.currentIndexChanged.connect(self._on_language_changed)
            self._reply_lang.currentIndexChanged.connect(self._on_language_changed)
            reply_lbl = QLabel("Reply:")
            reply_lbl.setStyleSheet(f"color:{STYLE['text2']};font-size:10px;font-family:'Segoe UI';")
            combo_style = f"""
                QComboBox {{
                    color: #E6EDF3;
                    background: #161B22;
                    border: 1px solid #30363D;
                    border-radius: 6px;
                    padding: 4px 8px;
                    min-height: 24px;
                }}
                QComboBox::drop-down {{
                    border: none;
                    width: 18px;
                }}
                QComboBox QAbstractItemView {{
                    color: #E6EDF3;
                    background: #161B22;
                    border: 1px solid #30363D;
                    selection-background-color: #58A6FF;
                    selection-color: #0D1117;
                    outline: none;
                }}
            """
            for combo in (self._listen_lang, self._reply_lang):
                combo.setStyleSheet(combo_style)
            lang_row.addWidget(listen_lbl)
            lang_row.addWidget(self._listen_lang, 1)
            lang_row.addWidget(reply_lbl)
            lang_row.addWidget(self._reply_lang, 1)
            bl.addLayout(lang_row)

            bl.addWidget(self._section_label("MANUAL INPUT - Type question and press Enter for live AI reply"))
            self._inp = QLineEdit()
            self._inp.setPlaceholderText("Type interviewer question and press Enter...")
            self._inp.setStyleSheet(f"""
                QLineEdit{{
                    background:{STYLE['bg2']};color:{STYLE['text']};
                    border:1px solid {STYLE['border']};border-radius:8px;
                    padding:8px 12px;font-size:12px;font-family:'Segoe UI';
                    min-height:34px;
                }}
                QLineEdit:focus{{border-color:{STYLE['accent']};}}
            """)
            self._inp.returnPressed.connect(self._on_manual_send)
            bl.addWidget(self._inp)

            self._body_scroll.setWidget(body)
            vbox.addWidget(self._body_scroll)

            # Action buttons
            btn_frame = QFrame()
            btn_frame.setStyleSheet(f"background:{STYLE['bg2']};border-top:1px solid {STYLE['border']};")
            bfl = QVBoxLayout(btn_frame)
            bfl.setContentsMargins(12, 8, 12, 8)
            bfl.setSpacing(6)

            row1 = QHBoxLayout()
            row1.setSpacing(6)
            self._btn_listen = self._make_btn("Listen F2", STYLE['yellow'])
            self._btn_copy  = self._make_btn("Copy Answer", STYLE['green'])
            self._btn_regen = self._make_btn("Regenerate",  STYLE['yellow'])
            self._btn_simple = self._make_btn("Simple",     STYLE['accent'])
            self._btn_send  = self._make_btn("Send Input",  STYLE['accent'])
            for b in [self._btn_listen, self._btn_copy, self._btn_regen, self._btn_simple, self._btn_send]:
                row1.addWidget(b)
            bfl.addLayout(row1)

            op_row = QHBoxLayout()
            op_lbl = QLabel("Opacity:")
            op_lbl.setStyleSheet(f"color:{STYLE['text2']};font-size:10px;font-family:'Segoe UI';")
            self._op_slider = QSlider(Qt.Horizontal)
            self._op_slider.setRange(20, 100)
            self._op_slider.setValue(int(self.state.opacity * 100))
            self._op_slider.setFixedHeight(18)
            self._op_slider.setStyleSheet(f"""
                QSlider::groove:horizontal{{background:{STYLE['border']};height:4px;border-radius:2px;}}
                QSlider::handle:horizontal{{background:{STYLE['accent']};width:14px;height:14px;border-radius:7px;margin:-5px 0;}}
                QSlider::sub-page:horizontal{{background:{STYLE['accent']};border-radius:2px;}}
            """)
            self._op_slider.valueChanged.connect(lambda v: self.setWindowOpacity(v / 100) if not self._stealth else None)
            op_row.addWidget(op_lbl)
            op_row.addWidget(self._op_slider)
            bfl.addLayout(op_row)

            vbox.addWidget(btn_frame)

            status_frame = QFrame()
            status_frame.setStyleSheet(
                f"background:{STYLE['bg3']};border-top:1px solid {STYLE['border']};border-radius:0 0 14px 14px;"
            )
            status_layout = QVBoxLayout(status_frame)
            status_layout.setContentsMargins(12, 6, 12, 8)
            status_layout.setSpacing(2)
            self._api_status_lbl = QLabel("API: Loading...")
            self._audio_status_lbl = QLabel("Audio: Loading...")
            self._stt_status_lbl = QLabel("STT: Loading...")
            self._lang_status_lbl = QLabel("Languages: English -> English")
            for lbl in (self._api_status_lbl, self._audio_status_lbl, self._stt_status_lbl, self._lang_status_lbl):
                lbl.setStyleSheet(f"color:{STYLE['text2']};font-size:10px;font-family:'Segoe UI';")
                status_layout.addWidget(lbl)
            vbox.addWidget(status_frame)

            try:
                import webbrowser

                from .premium_footer import BRAND_TAGLINE, PREMIUM_FOOTER_LINKS

                footer_frame = QFrame()
                footer_frame.setStyleSheet(
                    f"background:{STYLE['bg2']};border-top:1px solid {STYLE['border']};"
                )
                footer_layout = QVBoxLayout(footer_frame)
                footer_layout.setContentsMargins(10, 4, 10, 6)
                footer_layout.setSpacing(4)
                brand_lbl = QLabel(BRAND_TAGLINE)
                brand_lbl.setStyleSheet(
                    f"color:{STYLE['text2']};font-size:9px;font-weight:600;font-family:'Segoe UI';"
                )
                footer_layout.addWidget(brand_lbl)
                links_row = QHBoxLayout()
                links_row.setSpacing(4)
                for link in PREMIUM_FOOTER_LINKS:
                    link_btn = QPushButton(link.icon)
                    link_btn.setToolTip(f"{link.label}: {link.url}")
                    link_btn.setFixedSize(28, 22)
                    link_btn.setCursor(QCursor(Qt.PointingHandCursor))
                    link_btn.setStyleSheet(
                        f"QPushButton{{background:transparent;color:{link.color};"
                        f"border:1px solid {STYLE['border']};border-radius:5px;"
                        f"font-size:10px;font-weight:700;font-family:'Segoe UI';}}"
                        f"QPushButton:hover{{background:{STYLE['btnhov']};}}"
                    )
                    link_btn.clicked.connect(
                        lambda _checked=False, url=link.url: webbrowser.open(url)
                    )
                    links_row.addWidget(link_btn)
                links_row.addStretch()
                footer_layout.addLayout(links_row)
                vbox.addWidget(footer_frame)
            except Exception:
                pass

            grip_row = QHBoxLayout()
            grip_row.setContentsMargins(0, 0, 4, 2)
            grip_row.addStretch()
            sg = QSizeGrip(self)
            sg.setStyleSheet(f"color:{STYLE['text2']};background:transparent;")
            grip_row.addWidget(sg)
            vbox.addLayout(grip_row)

            self._btn_copy.clicked.connect(self._copy_answer)
            self._btn_listen.clicked.connect(self._on_live_listen)
            self._btn_send.clicked.connect(self._on_manual_send)
            self._btn_simple.clicked.connect(self._show_simple)
            self._btn_regen.clicked.connect(self._on_regen)

        def _language_options(self):
            try:
                from .language_config import LANGUAGE_OPTIONS

                return LANGUAGE_OPTIONS
            except Exception:
                return [("English", "en-US")]

        def _load_language_controls(self) -> None:
            try:
                from .language_config import language_label_for_code, load_language_prefs

                prefs = load_language_prefs()
                self._listen_lang.blockSignals(True)
                self._reply_lang.blockSignals(True)
                try:
                    listen_index = self._listen_lang.findData(prefs["listen_language"])
                    reply_index = self._reply_lang.findData(prefs["reply_language"])
                    if listen_index >= 0:
                        self._listen_lang.setCurrentIndex(listen_index)
                    if reply_index >= 0:
                        self._reply_lang.setCurrentIndex(reply_index)
                finally:
                    self._listen_lang.blockSignals(False)
                    self._reply_lang.blockSignals(False)
                self._lang_status_lbl.setText(
                    f"Languages: {language_label_for_code(prefs['listen_language'])} "
                    f"-> {language_label_for_code(prefs['reply_language'])} (saved)"
                )
            except Exception:
                pass

        def _on_language_changed(self) -> None:
            try:
                from .language_config import language_label_for_code, save_language_prefs

                listen_code = str(self._listen_lang.currentData() or "en-US")
                reply_code = str(self._reply_lang.currentData() or "en-US")
                save_language_prefs(listen_code, reply_code)
                self._lang_status_lbl.setText(
                    f"Languages: {language_label_for_code(listen_code)} "
                    f"-> {language_label_for_code(reply_code)} (saved)"
                )
                self._lang_status_lbl.setStyleSheet(
                    f"color:{STYLE['green']};font-size:10px;font-family:'Segoe UI';"
                )
                QTimer.singleShot(2500, self._refresh_status_bar_sync)
            except Exception:
                pass

        def _on_status_bar_ready(
            self,
            api_ok: bool,
            api_text: str,
            audio_ok: bool,
            audio_text: str,
            listen_code: str,
            reply_code: str,
        ) -> None:
            self._status_refresh_inflight = False
            self._apply_status_bar(
                api_ok=api_ok,
                api_text=api_text,
                audio_ok=audio_ok,
                audio_text=audio_text,
                listen_code=listen_code,
                reply_code=reply_code,
            )

        def _build_status_labels(self) -> tuple[bool, str, bool, str]:
            from .mistral_setup import mistral_connection_status
            from .audio_handler import microphone_capture_status

            ok, message = mistral_connection_status()
            api_text = (
                "API: Mistral Connected"
                if ok
                else f"API: Key missing — {message}"
            )
            mic_status = microphone_capture_status()
            call_source = str(mic_status.get("call_audio_source") or "")
            device_name = call_source.split(":", 1)[1] if ":" in call_source else ""
            if mic_status.get("can_capture"):
                if "stereo_mix" in call_source:
                    audio_text = "Audio: Speaker Capture (Stereo Mix)"
                elif "virtual_cable" in call_source:
                    label = "VB-Cable" if "vb" in call_source.casefold() else "BlackHole"
                    audio_text = f"Audio: Speaker Capture ({label})"
                else:
                    short_name = device_name[:28] if device_name else "default mic"
                    audio_text = f"Audio: Mic Ready ({short_name})"
                audio_ok = True
            else:
                audio_text = "Audio: Not available"
                audio_ok = False
            return ok, api_text, audio_ok, audio_text

        def _apply_stt_status(self) -> None:
            try:
                from .stt_engine import stt_runtime_status

                status = stt_runtime_status()
                ready = bool(status.get("ready"))
                label = str(status.get("label", "STT: Unknown"))
                self._stt_status_lbl.setText(label)
                self._stt_status_lbl.setStyleSheet(
                    f"color:{STYLE['green'] if ready else STYLE['red']};font-size:10px;font-family:'Segoe UI';"
                )
            except Exception:
                self._stt_status_lbl.setText("STT: Status unavailable")
                self._stt_status_lbl.setStyleSheet(
                    f"color:{STYLE['red']};font-size:10px;font-family:'Segoe UI';"
                )

        def _refresh_status_bar_sync(self) -> None:
            try:
                listen_code = str(self._listen_lang.currentData() or "en-US")
                reply_code = str(self._reply_lang.currentData() or "en-US")
                ok, api_text, audio_ok, audio_text = self._build_status_labels()
                self._apply_status_bar(
                    api_ok=ok,
                    api_text=api_text,
                    audio_ok=audio_ok,
                    audio_text=audio_text,
                    listen_code=listen_code,
                    reply_code=reply_code,
                )
                self._apply_stt_status()
            except Exception:
                self._api_status_lbl.setText("API: Ready")
                self._audio_status_lbl.setText("Audio: Ready")
                self._apply_stt_status()

        def _apply_status_bar(
            self,
            *,
            api_ok: bool,
            api_text: str,
            audio_ok: bool,
            audio_text: str,
            listen_code: str,
            reply_code: str,
        ) -> None:
            self._animate_status_change(self._api_status_lbl, api_text, self._last_api_status, api_ok)
            self._last_api_status = api_text
            self._api_status_lbl.setStyleSheet(
                f"color:{STYLE['green'] if api_ok else STYLE['red']};font-size:10px;font-family:'Segoe UI';"
            )
            self._animate_status_change(self._audio_status_lbl, audio_text, self._last_audio_status, audio_ok)
            self._last_audio_status = audio_text
            self._audio_status_lbl.setStyleSheet(
                f"color:{STYLE['green'] if audio_ok else STYLE['red']};font-size:10px;font-family:'Segoe UI';"
            )
            from .language_config import language_label_for_code

            self._lang_status_lbl.setText(
                f"🌐 Listen: {language_label_for_code(listen_code)} → Reply: {language_label_for_code(reply_code)}"
            )
            self._apply_stt_status()

        def _refresh_status_bar(self) -> None:
            if self._status_refresh_inflight:
                return
            self._status_refresh_inflight = True
            listen_code = str(self._listen_lang.currentData() or "en-US")
            reply_code = str(self._reply_lang.currentData() or "en-US")

            import threading

            def _worker() -> None:
                try:
                    ok, api_text, audio_ok, audio_text = self._build_status_labels()
                    self._status_signals.status_ready.emit(
                        ok,
                        api_text,
                        audio_ok,
                        audio_text,
                        listen_code,
                        reply_code,
                    )
                except Exception:
                    self._status_signals.status_ready.emit(
                        False,
                        "API: Status unavailable",
                        False,
                        "Audio: Status unavailable",
                        listen_code,
                        reply_code,
                    )

            threading.Thread(target=_worker, name="overlay-status-refresh", daemon=True).start()

        def _animate_status_change(self, label, new_text: str, previous_text: str, is_ok: bool) -> None:
            label.setText(new_text)
            if new_text != previous_text:
                flash_color = STYLE["green"] if is_ok else STYLE["yellow"]
                normal_color = STYLE["green"] if is_ok else STYLE["red"]
                label.setStyleSheet(
                    f"color:{flash_color};font-size:10px;font-weight:700;font-family:'Segoe UI';"
                )
                QTimer.singleShot(
                    450,
                    lambda: label.setStyleSheet(
                        f"color:{normal_color};font-size:10px;font-family:'Segoe UI';"
                    ),
                )

        def _overlay_position_path(self):
            try:
                from runtime_paths import cache_root

                return cache_root() / "overlay_position.json"
            except Exception:
                return None

        def _restore_overlay_position(self) -> None:
            try:
                path = self._overlay_position_path()
                if path is None or not path.is_file():
                    raise FileNotFoundError
                import json

                payload = json.loads(path.read_text(encoding="utf-8"))
                x = int(payload.get("x", 0))
                y = int(payload.get("y", 0))
                if x or y:
                    self.move(x, y)
                    return
            except Exception:
                pass
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(screen.width() - self.width() - 24, screen.height() - self.height() - 60)

        def _save_overlay_position(self) -> None:
            try:
                path = self._overlay_position_path()
                if path is None:
                    return
                import json

                path.parent.mkdir(parents=True, exist_ok=True)
                pos = self.pos()
                path.write_text(
                    json.dumps({"x": pos.x(), "y": pos.y()}, indent=2),
                    encoding="utf-8",
                )
            except Exception:
                pass

        def _section_label(self, text, color=None):
            lbl = QLabel(text)
            c = color or STYLE['text2']
            lbl.setStyleSheet(f"color:{c};font-size:9px;font-weight:700;font-family:'Segoe UI';letter-spacing:1px;")
            return lbl

        def _box_style(self, border_color, bg=None):
            bg_c = bg or STYLE['bg2']
            return f"""
                QTextBrowser{{
                    background:{bg_c};
                    color:{STYLE['text']};
                    border:1px solid {border_color};
                    border-radius:8px;
                    padding:8px;
                    font-size:12px;
                    font-family:'Segoe UI';
                    line-height:1.6;
                    selection-background-color:{STYLE['accent']};
                }}
                QScrollBar:vertical{{background:{STYLE['bg']};width:5px;border-radius:2px;}}
                QScrollBar::handle:vertical{{background:{STYLE['border']};border-radius:2px;}}
                QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}
            """

        def _make_btn(self, label, color):
            b = QPushButton(label)
            b.setCursor(QCursor(Qt.PointingHandCursor))
            b.setStyleSheet(_btn(label, color))
            return b

        def _pill_style(self, color, bg):
            return f"""
                color:{color};font-size:9px;font-weight:700;font-family:'Segoe UI';
                padding:3px 10px;background:{bg};
                border:1px solid {color};border-radius:10px;
            """

        def apply_state(self, state: OverlayState) -> None:
            self.state = state
            if state.status == "listening":
                self._q_box.setText("Listening for interviewer question...")
                self._a_box.setText("Waiting for question...")
                self._pill.setText("LISTENING")
                self._pill.setStyleSheet(self._pill_style(STYLE['yellow'], "rgba(210,153,34,0.12)"))
            else:
                self._q_box.setText(state.transcript or "No transcript yet.")
                self._a_box.setText(state.suggested_answer or "No answer yet.")
                self._pill.setText("READY")
                self._pill.setStyleSheet(self._pill_style(STYLE['green'], "rgba(63,185,80,0.12)"))
                if state.transcript and state.suggested_answer:
                    self._history.insert(0, {"q": state.transcript, "a": state.suggested_answer})
                    self._history = self._history[:10]
                    self._refresh_history()

            alts = state.alternatives or []
            self._alt_box.setText("\n\n".join(f"- {a}" for a in alts) if alts else "No alternatives yet.")
            score = state.confidence_score or 0
            col = STYLE['green'] if score >= 70 else STYLE['yellow'] if score >= 40 else STYLE['red']
            self._conf_val.setText(f"{score}%")
            self._conf_val.setStyleSheet(f"color:{col};font-size:11px;font-weight:700;font-family:'Segoe UI';")
            self._prov_lbl.setText(f"AI {state.provider_status or 'Not connected'}")
            self.setWindowOpacity(max(0.15, min(state.opacity, 1.0)))

        def _refresh_history(self):
            lines = []
            for i, item in enumerate(self._history[:6], 1):
                lines.append(f"[{i}] Q: {item['q'][:70]}")
                lines.append(f"    A: {item['a'][:100]}")
                lines.append("-" * 40)
            self._hist_box.setText("\n".join(lines) if lines else "No history yet.")

        def _copy_answer(self):
            txt = self._a_box.toPlainText()
            if txt and txt not in ("Processing answer...", "No answer yet."):
                QApplication.clipboard().setText(txt)
                self._btn_copy.setText("Copied!")
                QTimer.singleShot(2000, lambda: self._btn_copy.setText("Copy Answer"))

        def _show_simple(self):
            alts = self.state.alternatives
            if alts:
                self._a_box.setText(alts[0])

        def _on_regen(self):
            txt = self._q_box.toPlainText().strip()
            if txt and txt not in ("Listening for interviewer question...", "No transcript yet."):
                self._inp.setText(txt)
                self._on_manual_send()

        def _resolve_active_session_id(self) -> str:
            existing = str(self.current_session_id or "").strip()
            if existing:
                return existing
            try:
                from runtime_paths import session_registry_path

                from .runtime_controller import load_session_registry

                registry = load_session_registry(session_registry_path())
                if not registry:
                    return ""
                latest = max(
                    registry.items(),
                    key=lambda item: str(item[1].get("updated_at", "") or ""),
                )
                return str(latest[0]).strip()
            except Exception:
                return ""

        def _on_live_listen(self) -> None:
            session_id = self._resolve_active_session_id()
            if not session_id:
                self._a_box.setText("No active session. Open the dashboard and click Create Session first.")
                self._pill.setText("ERROR")
                self._pill.setStyleSheet(self._pill_style(STYLE['red'], "rgba(248,81,73,0.12)"))
                self.show()
                return

            self.current_session_id = session_id

            from .audio_handler import microphone_capture_status

            mic_status = microphone_capture_status(force_refresh=True)
            if not bool(mic_status.get("can_capture", False)):
                self._apply_listen_error(str(mic_status.get("message", "Live microphone capture is unavailable.")))
                return

            from .stt_engine import stt_runtime_status

            stt_status = stt_runtime_status()
            if not bool(stt_status.get("ready", False)):
                self._apply_listen_error(str(stt_status.get("message", "Speech-to-text is not available.")))
                return

            self._q_box.setText("Listening to interviewer...")
            self._a_box.setText("Capturing call audio and generating your script...")
            self._pill.setText("LISTENING")
            self._pill.setStyleSheet(self._pill_style(STYLE['yellow'], "rgba(210,153,34,0.12)"))
            self.show()
            self.raise_()

            import threading

            threading.Thread(target=self._run_live_listen_request, daemon=True).start()

        def _run_live_listen_request(self) -> None:
            session_id = self._resolve_active_session_id()
            if not session_id:
                self._manual_signals.listen_failed.emit(
                    "No active session. Open the dashboard and click Create Session first."
                )
                return

            listen_code = str(self._listen_lang.currentData() or "en-US")
            reply_code = str(self._reply_lang.currentData() or "en-US")
            try:
                from runtime_paths import session_registry_path

                from .language_config import save_language_prefs
                from .live_listen import build_listening_state_for_session, run_live_listen_cycle

                save_language_prefs(listen_code, reply_code)
                registry_path = session_registry_path()
                build_listening_state_for_session(session_id, registry_path)
                result = run_live_listen_cycle(
                    session_id,
                    registry_path=registry_path,
                    listen_language=listen_code,
                    reply_language=reply_code,
                )
                self._manual_signals.listen_ready.emit(
                    result.transcript,
                    result.suggested_answer,
                    result.provider_status,
                    list(result.alternatives),
                    result.confidence_score,
                )
            except Exception as error:
                self._manual_signals.listen_failed.emit(str(error))

        def _apply_listen_error(self, message: str) -> None:
            hint = message.strip() or "Live listen failed."
            if "403" in hint or "activation" in hint.casefold():
                hint = f"{hint}\n\nActivate this computer from the dashboard first."
            elif "10061" in hint or "connection refused" in hint.casefold() or "urlopen error" in hint.casefold():
                hint = (
                    "Listen could not reach the desktop session service. "
                    "Restart Career Copilot Premium, create a session, then press Listen (F2) again."
                )
            elif "microphone" in hint.casefold() or "recording" in hint.casefold() or "sounddevice" in hint.casefold():
                hint = (
                    f"{hint}\n\nEnable microphone permission in Windows Settings > Privacy > Microphone. "
                    "For Zoom/WhatsApp calls, enable Stereo Mix (Recording devices) or install VB-Cable."
                )
            elif "no speech" in hint.casefold():
                hint = (
                    f"{hint}\n\nSpeak clearly near the PC microphone, or type the question in Manual Input."
                )
            self._q_box.setText("Listen failed")
            self._a_box.setText(f"Error: {hint}")
            self._pill.setText("ERROR")
            self._pill.setStyleSheet(self._pill_style(STYLE['red'], "rgba(248,81,73,0.12)"))
            self.show()

        def _on_manual_send(self):
            txt = self._inp.text().strip()
            if not txt:
                return
            self._q_box.setText(f"Q: {txt}")
            self._a_box.setText("Generating answer...")
            self._pill.setText("THINKING")
            self._pill.setStyleSheet(self._pill_style(STYLE['accent'], "rgba(88,166,255,0.12)"))
            self._inp.clear()

            import threading

            threading.Thread(target=self._generate_manual_answer, args=(txt,), daemon=True).start()

        def _generate_manual_answer(self, question: str) -> None:
            try:
                import threading

                from .answer_builder import generate_manual_answer

                listen_language = str(self._listen_lang.currentData() or "en-US")
                reply_language = str(self._reply_lang.currentData() or "en-US")
                result_holder: list[object] = []
                error_holder: list[Exception] = []

                def _worker() -> None:
                    try:
                        result_holder.append(
                            generate_manual_answer(
                                question,
                                listen_language=listen_language,
                                reply_language=reply_language,
                            )
                        )
                    except Exception as exc:
                        error_holder.append(exc)

                worker = threading.Thread(target=_worker, name="overlay-manual-answer", daemon=True)
                worker.start()
                worker.join(timeout=25.0)
                if worker.is_alive():
                    raise TimeoutError(
                        "AI answer took too long. Start Ollama or verify your Mistral API key."
                    )
                if error_holder:
                    raise error_holder[0]
                if not result_holder:
                    raise RuntimeError("No answer was generated.")
                result = result_holder[0]
                answer = result.suggested_answer.strip() or "No answer generated. Please try again."
                confidence = 88 if "Deterministic" not in result.provider_name else 72
                self._manual_signals.answer_ready.emit(
                    question,
                    answer,
                    result.provider_name,
                    list(result.alternatives),
                    confidence,
                )
            except Exception as error:
                self._manual_signals.answer_failed.emit(question, str(error))

        def _apply_manual_answer(
            self,
            question: str,
            answer: str,
            provider_name: str,
            alternatives: list,
            confidence: int,
        ) -> None:
            display_question = question.strip() or "No transcript yet."
            if not display_question.startswith("Q:"):
                display_question = f"Q: {display_question}"
            self._q_box.setText(display_question)
            self._history.insert(0, {"q": question, "a": answer})
            self._history = self._history[:10]
            self._a_box.setText(answer)
            alt_lines = [f"- {item}" for item in alternatives if str(item).strip()]
            if not alt_lines:
                alt_lines = [f"- Short: {answer[:80]}", "- Confident: I have direct experience with this."]
            self._alt_box.setText("\n\n".join(alt_lines))
            self._conf_val.setText(f"{confidence}%")
            self._conf_val.setStyleSheet(
                f"color:{STYLE['green']};font-size:11px;font-weight:700;font-family:'Segoe UI';"
            )
            display_provider = (
                provider_name.replace("OpenAICompatible", "Mistral")
                .replace("Ollama(", "Ollama ")
                .replace(")", "")
            )
            self._prov_lbl.setText(f"AI {display_provider}")
            self._pill.setText("READY")
            self._pill.setStyleSheet(self._pill_style(STYLE['green'], "rgba(63,185,80,0.12)"))
            self._refresh_history()
            self.show()
            self.raise_()

        def _apply_manual_error(self, question: str, message: str) -> None:
            hint = message.strip() or "Unknown error"
            if "MISTRAL_API_KEY" in hint or "Missing API key" in hint:
                hint = (
                    f"{hint}\n\nInstall Ollama (see docs/requirements/DOWNLOAD-OLLAMA.txt) "
                    "or add MISTRAL_API_KEY to .env (see docs/requirements/DOWNLOAD-MISTRAL.txt)."
                )
            elif "Ollama" in hint or "11434" in hint:
                hint = (
                    f"{hint}\n\nStart Ollama (ollama serve) or set MISTRAL_API_KEY in .env as fallback."
                )
            self._a_box.setText(f"Error: {hint}")
            self._q_box.setText(f"Q: {question}")
            self._pill.setText("ERROR")
            self._pill.setStyleSheet(self._pill_style(STYLE['red'], "rgba(248,81,73,0.12)"))
            self.show()

        def _toggle_stealth(self):
            self._stealth = not self._stealth
            self.setWindowOpacity(0.06 if self._stealth else self._op_slider.value() / 100)

        def _toggle_history(self):
            self._show_hist = not self._show_hist
            self._hist_frame.setVisible(self._show_hist)

        def _toggle_min(self):
            self._minimized = not self._minimized
            self._body_scroll.setVisible(not self._minimized)
            if self._minimized:
                self.setFixedHeight(44)
            else:
                self.setMinimumSize(380, 300)
                self.setMaximumSize(16777215, 16777215)
                self.resize(460, 600)

        def _tbar_press(self, e):
            if e.button() == Qt.LeftButton:
                self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

        def _tbar_move(self, e):
            if e.buttons() == Qt.LeftButton and self._drag_pos:
                self.move(e.globalPosition().toPoint() - self._drag_pos)

        def _tbar_release(self, e):
            self._drag_pos = QPoint()
            self._save_overlay_position()


    class SettingsWindow(QWidget):
        def __init__(self, theme, hotkey, stt_model, llm_model):
            super().__init__()
            self.setWindowTitle("Career Copilot Settings")
            self.resize(380, 260)
            self.setStyleSheet(
                f"background:{STYLE['bg']};color:{STYLE['text']};font-family:'Segoe UI';"
            )
            l = QVBoxLayout(self)
            l.setContentsMargins(20, 20, 20, 20)
            t = QLabel("Career Copilot Settings")
            t.setStyleSheet(f"font-size:14px;font-weight:700;color:{STYLE['accent']};")
            l.addWidget(t)
            for k, v in [("Theme", theme), ("Hotkey", hotkey), ("STT", stt_model), ("LLM", llm_model)]:
                row = QHBoxLayout()
                kl = QLabel(k)
                kl.setStyleSheet(f"color:{STYLE['text2']};font-size:11px;")
                vl = QLabel(v)
                vl.setStyleSheet(f"color:{STYLE['text']};font-size:11px;")
                row.addWidget(kl)
                row.addStretch()
                row.addWidget(vl)
                l.addLayout(row)
            l.addStretch()


    def launch_overlay_preview(theme, hotkey, stt_model, llm_model):
        runtime = create_overlay_runtime(theme=theme, initial_state=build_preview_overlay_state())
        w = runtime.controller.window
        s = SettingsWindow(theme, hotkey, stt_model, llm_model)
        if w is None:
            raise RuntimeError("PySide6 required.")
        w.show()
        s.show()
        return runtime.run()

else:
    class TransparentOverlayWindow:
        def __init__(self, *a, **k):
            raise RuntimeError("PySide6 required.")

    def create_overlay_runtime(theme="dark", initial_state=None):
        state = initial_state or build_preview_overlay_state()
        return OverlayRuntime(app=None, controller=LiveOverlayController(initial_state=state))

    class SettingsWindow:
        def __init__(self, *a, **k):
            raise RuntimeError("PySide6 required.")

    def launch_overlay_preview(*a, **k):
        raise RuntimeError(qt_runtime_error_message())
