import threading
from pathlib import Path

import subprocess
import sys

from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QIcon, QPixmap, QColor
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow,
                                QPushButton, QScrollArea, QSystemTrayIcon,
                                QVBoxLayout, QWidget)

from config import presets as preset_store
from config import settings as cfg_store
from core import extractor, processor, updater
from core.cloud_scorer import CloudScorer
from ui import theme
from ui.controls import DestinationControls, OutputControls
from ui.drop_zone import DropZone
from ui.file_list import FileListWidget
from ui.presets_bar import PresetsBar
from ui.progress_panel import ProgressPanel
from ui.scoring_panel import ScoringPanel
from ui.settings_panel import SettingsPanel
from version import __version__


class _WorkerSignals(QObject):
    video_progress = Signal(str, float, int)   # name, 0-1, frames
    video_done = Signal(str, int)              # name, frames
    video_error = Signal(str, str)             # name, msg
    all_done = Signal(int)                     # total frames
    status = Signal(str)


class _BatchWorker(QThread):
    signals: _WorkerSignals

    def __init__(self, videos, output_dir, output_mode, exact_count,
                 secs_per_frame, blur_pct, cloud_scorer, subfolder):
        super().__init__()
        self.signals = _WorkerSignals()
        self._videos = videos
        self._output_dir = output_dir
        self._output_mode = output_mode
        self._exact_count = exact_count
        self._secs_per_frame = secs_per_frame
        self._blur_pct = blur_pct
        self._cloud = cloud_scorer
        self._subfolder = subfolder
        self._stop = threading.Event()

    def run(self):
        def progress_cb(name: str, prog: float, frames: int):
            self.signals.video_progress.emit(name, prog, frames)

        results = processor.process_batch(
            videos=self._videos,
            output_dir=self._output_dir,
            output_mode=self._output_mode,
            exact_count=self._exact_count,
            secs_per_frame=self._secs_per_frame,
            blur_pct=self._blur_pct,
            cloud_scorer=self._cloud,
            subfolder=self._subfolder,
            progress_cb=progress_cb,
            stop_event=self._stop,
        )
        total = 0
        for r in results:
            if r.error:
                self.signals.video_error.emit(r.video_path.name, r.error)
            else:
                self.signals.video_done.emit(r.video_path.name, r.frame_count)
                total += r.frame_count
        self.signals.all_done.emit(total)

    def stop(self):
        self._stop.set()


class _UpdateWorker(QThread):
    update_found = Signal(str, str)  # version, url

    def __init__(self, current_version: str):
        super().__init__()
        self._version = current_version

    def run(self):
        v, url = updater.check_for_update(self._version)
        if v:
            self.update_found.emit(v, url or "")


class _DownloadWorker(QThread):
    progress = Signal(int)    # 0-100
    finished = Signal()
    failed = Signal(str)

    def __init__(self, url: str):
        super().__init__()
        self._url = url

    def run(self):
        try:
            updater.download_and_install(
                self._url,
                progress_callback=lambda p: self.progress.emit(p),
            )
            self.finished.emit()
        except Exception as e:
            self.failed.emit(str(e))


def _rule() -> QWidget:
    w = QWidget()
    w.setFixedHeight(1)
    w.setStyleSheet(f"background: {theme.BORDER};")
    return w


class TitleBar(QWidget):
    settings_clicked = Signal()
    update_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setStyleSheet(f"background: {theme.SURFACE2};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 16, 0)
        layout.setSpacing(12)

        title = QLabel("FRAMEABLE")
        title.setStyleSheet(
            f"color: {theme.TEXT}; font-size: 14px; letter-spacing: 0.22em;"
        )
        layout.addWidget(title)

        self._ver_lbl = QLabel(f"v{__version__}")
        self._ver_lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 10px; letter-spacing: 0.06em;"
        )
        layout.addWidget(self._ver_lbl)

        layout.addStretch()

        self._update_btn = QPushButton("")
        self._update_btn.hide()
        self._update_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {theme.WARN};
                border: 1px solid {theme.WARN};
                font-size: 9px;
                letter-spacing: 0.12em;
                padding: 3px 10px;
            }}
            QPushButton:hover {{
                background: {theme.WARN};
                color: {theme.BG};
            }}
        """)
        self._update_btn.clicked.connect(self.update_clicked)
        layout.addWidget(self._update_btn)

        settings_btn = QPushButton("S")
        settings_btn.setFixedSize(28, 28)
        settings_btn.setToolTip("Settings")
        settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {theme.TEXT_DIM};
                border: 1px solid {theme.BORDER};
                font-size: 11px;
                padding: 0;
            }}
            QPushButton:hover {{
                color: {theme.TEXT};
                border-color: {theme.TEXT_DIM};
            }}
        """)
        settings_btn.clicked.connect(self.settings_clicked)
        layout.addWidget(settings_btn)

    def show_update(self, version: str):
        self._update_btn.setText(f"UPDATE v{version}")
        self._update_btn.show()

    def hide_update(self):
        self._update_btn.hide()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        theme.load_fonts()
        self._cfg = cfg_store.load()
        self._cloud_scorer: CloudScorer | None = self._build_cloud_scorer()
        self._worker: _BatchWorker | None = None
        self._pending_update_url: str = ""

        self.setWindowTitle("Frameable")
        self.setMinimumSize(720, 640)
        self.resize(820, 740)
        self.setStyleSheet(theme.QSS)

        # Root widget
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Title bar
        self._title_bar = TitleBar()
        self._title_bar.settings_clicked.connect(self._open_settings)
        self._title_bar.update_clicked.connect(self._do_update)
        root_layout.addWidget(self._title_bar)

        root_layout.addWidget(_rule())

        # Scroll area for main content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root_layout.addWidget(scroll, 1)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 20)
        content_layout.setSpacing(12)
        scroll.setWidget(content)

        # Drop zone
        self._drop_zone = DropZone()
        self._drop_zone.files_dropped.connect(self._on_files_dropped)
        content_layout.addWidget(self._drop_zone)

        content_layout.addSpacing(8)

        # File list
        self._file_list = FileListWidget()
        self._file_list.list_changed.connect(self._on_list_changed)
        content_layout.addWidget(self._file_list)

        # Presets bar
        self._presets_bar = PresetsBar()
        self._presets_bar.preset_loaded.connect(self._apply_preset)
        content_layout.addWidget(self._presets_bar)

        # Output controls
        self._output_ctrl = OutputControls(self._cfg)
        self._output_ctrl.settings_changed.connect(self._persist_cfg)
        self._output_ctrl.settings_changed.connect(self._sync_preset_bar)
        content_layout.addWidget(self._output_ctrl)

        content_layout.addSpacing(8)

        # Destination controls
        self._dest_ctrl = DestinationControls(self._cfg)
        self._dest_ctrl.settings_changed.connect(self._persist_cfg)
        self._dest_ctrl.settings_changed.connect(self._sync_preset_bar)
        content_layout.addWidget(self._dest_ctrl)

        content_layout.addSpacing(8)

        # Scoring panel
        self._scoring = ScoringPanel(self._cloud_scorer)
        content_layout.addWidget(self._scoring)

        # Progress panel (hidden until running)
        self._progress = ProgressPanel()
        self._progress.hide()
        content_layout.addWidget(self._progress)

        content_layout.addStretch()

        # Bottom action bar
        action_bar = QWidget()
        action_bar.setFixedHeight(60)
        action_bar.setStyleSheet(f"background: {theme.SURFACE2};")
        root_layout.addWidget(_rule())
        root_layout.addWidget(action_bar)

        ab_layout = QHBoxLayout(action_bar)
        ab_layout.setContentsMargins(24, 0, 24, 0)
        ab_layout.setSpacing(12)

        self._status_lbl = QLabel("READY")
        self._status_lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 9px; letter-spacing: 0.10em;"
        )
        ab_layout.addWidget(self._status_lbl)
        ab_layout.addStretch()

        self._open_folder_btn = QPushButton("OPEN FOLDER")
        self._open_folder_btn.hide()
        self._open_folder_btn.clicked.connect(self._open_output_folder)
        ab_layout.addWidget(self._open_folder_btn)

        self._cancel_btn = QPushButton("CANCEL")
        self._cancel_btn.setObjectName("cancel_btn")
        self._cancel_btn.hide()
        self._cancel_btn.clicked.connect(self._cancel)
        ab_layout.addWidget(self._cancel_btn)

        self._run_btn = QPushButton("RUN")
        self._run_btn.setObjectName("run_btn")
        self._run_btn.setEnabled(False)
        self._run_btn.setFixedWidth(130)
        self._run_btn.clicked.connect(self._run)
        ab_layout.addWidget(self._run_btn)

        # System tray (for completion notifications)
        self._tray = self._build_tray()

        # Sync preset bar with current control values
        self._sync_preset_bar()

        # Check for updates silently
        self._check_updates()

    def _build_cloud_scorer(self) -> CloudScorer:
        g = cfg_store.get_api_key("google_vision")
        r = cfg_store.get_api_key("replicate_token")
        return CloudScorer(cfg_store.CONFIG_DIR, google_key=g, replicate_token=r)

    def _on_files_dropped(self, paths: list[Path]):
        durations = {}
        codecs = {}
        for p in paths:
            try:
                info = extractor.get_video_info(p)
                durations[p] = info.duration
                codecs[p] = info.codec
            except Exception:
                pass
        self._file_list.add_files(paths, durations=durations, codecs=codecs)

    def _on_list_changed(self, count: int):
        self._run_btn.setEnabled(count > 0)
        if count == 0:
            self._set_status("READY")
        else:
            self._set_status(f"{count} FILE{'S' if count != 1 else ''} LOADED")

    def _run(self):
        paths = self._file_list.paths()
        if not paths:
            return

        output_dir = self._dest_ctrl.output_dir()
        if self._dest_ctrl.subfolder_per_video():
            # processor handles sub-dir creation per video
            pass

        self._run_btn.setEnabled(False)
        self._open_folder_btn.hide()
        self._cancel_btn.show()
        self._drop_zone.setEnabled(False)
        self._file_list.lock(True)
        self._progress.show()
        self._progress.start_batch([p.name for p in paths])

        for p in paths:
            self._file_list.set_status(p, "queue", "QUEUE")

        self._worker = _BatchWorker(
            videos=paths,
            output_dir=output_dir,
            output_mode=self._output_ctrl.output_mode(),
            exact_count=self._output_ctrl.exact_count(),
            secs_per_frame=self._output_ctrl.secs_per_frame(),
            blur_pct=self._output_ctrl.blur_pct(),
            cloud_scorer=self._cloud_scorer,
            subfolder=self._dest_ctrl.subfolder_per_video(),
        )
        w = self._worker
        w.signals.video_progress.connect(self._on_video_progress)
        w.signals.video_done.connect(self._on_video_done)
        w.signals.video_error.connect(self._on_video_error)
        w.signals.all_done.connect(self._on_all_done)
        w.start()
        self._set_status("PROCESSING")

    def _cancel(self):
        if self._worker:
            self._worker.stop()
            self._set_status("CANCELLING")

    def _on_video_progress(self, name: str, prog: float, frames: int):
        self._progress.update_video(name, prog, frames)
        p = self._file_list.paths()
        # Mark as processing
        for path in p:
            if path.name == name:
                self._file_list.set_status(path, "processing",
                                           f"{int(prog * 100)}%")
                break

    def _on_video_done(self, name: str, frames: int):
        self._progress.video_done(name, frames)
        for path in self._file_list.paths():
            if path.name == name:
                self._file_list.set_status(path, "done", f"{frames} STILLS")
                break

    def _on_video_error(self, name: str, msg: str):
        self._progress.video_error(name, msg)
        for path in self._file_list.paths():
            if path.name == name:
                self._file_list.set_status(path, "error", "ERROR")
                break

    def _on_all_done(self, total: int):
        self._run_btn.setEnabled(True)
        self._cancel_btn.hide()
        self._open_folder_btn.show()
        self._drop_zone.setEnabled(True)
        self._file_list.lock(False)
        self._scoring.refresh()
        self._set_status(f"DONE  —  {total} FRAMES SAVED")
        self._persist_cfg()

        # Tray notification if window is not in focus
        if not self.isActiveWindow() and self._tray and self._tray.isVisible():
            self._tray.showMessage(
                "Frameable",
                f"{total} frames extracted and saved.",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )

    def _build_tray(self) -> QSystemTrayIcon | None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        icon = self._app_icon()
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("Frameable")
        tray.show()
        return tray

    def _app_icon(self) -> QIcon:
        from pathlib import Path
        icon_path = Path(__file__).parent.parent / "assets" / "icon.png"
        if icon_path.exists():
            return QIcon(str(icon_path))
        # Fallback: paint a tiny icon with Qt
        px = QPixmap(32, 32)
        px.fill(QColor(theme.BG))
        return QIcon(px)

    def _open_output_folder(self):
        path = self._dest_ctrl.output_dir()
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)])
        elif sys.platform == "win32":
            subprocess.run(["explorer", str(path)])
        else:
            subprocess.run(["xdg-open", str(path)])

    def _apply_preset(self, data: dict):
        self._output_ctrl.apply_preset(data)
        self._dest_ctrl.apply_preset(data)
        self._persist_cfg()

    def _sync_preset_bar(self):
        self._presets_bar.inject_settings(self._current_settings())

    def _current_settings(self) -> dict:
        return {
            "output_mode":        self._output_ctrl.output_mode(),
            "exact_count":        self._output_ctrl.exact_count(),
            "blur_mix_pct":       self._output_ctrl.blur_pct(),
            "auto_frames_per_sec":self._output_ctrl.secs_per_frame(),
            "subfolder_per_video":self._dest_ctrl.subfolder_per_video(),
        }

    def _open_settings(self):
        panel = SettingsPanel(self)
        panel.keys_updated.connect(self._on_keys_updated)
        panel.exec()

    def _on_keys_updated(self):
        self._cloud_scorer = self._build_cloud_scorer()
        self._scoring.set_cloud_scorer(self._cloud_scorer)

    def _persist_cfg(self):
        self._cfg["last_output_dir"] = str(self._dest_ctrl.output_dir())
        self._cfg["output_mode"] = self._output_ctrl.output_mode()
        self._cfg["exact_count"] = self._output_ctrl.exact_count()
        self._cfg["blur_mix_pct"] = self._output_ctrl.blur_pct()
        self._cfg["auto_frames_per_sec"] = self._output_ctrl.secs_per_frame()
        self._cfg["subfolder_per_video"] = self._dest_ctrl.subfolder_per_video()
        cfg_store.save(self._cfg)

    def _set_status(self, text: str):
        self._status_lbl.setText(text)

    def _check_updates(self):
        self._update_worker = _UpdateWorker(__version__)
        self._update_worker.update_found.connect(self._on_update_found)
        self._update_worker.start()

    def _on_update_found(self, version: str, url: str):
        self._pending_update_url = url
        self._title_bar.show_update(version)
        self._set_status(f"UPDATE AVAILABLE  v{version}")

    def _do_update(self):
        if not self._pending_update_url:
            self._set_status("NO DOWNLOAD URL — CHECK GITHUB RELEASES")
            return
        self._set_status("DOWNLOADING UPDATE")
        self._run_btn.setEnabled(False)
        self._title_bar.hide_update()

        self._dl_worker = _DownloadWorker(self._pending_update_url)
        self._dl_worker.progress.connect(
            lambda p: self._set_status(f"DOWNLOADING  {p}%")
        )
        self._dl_worker.failed.connect(self._on_update_failed)
        self._dl_worker.start()

    def _on_update_failed(self, msg: str):
        self._set_status(f"UPDATE FAILED  —  {msg}")
        self._run_btn.setEnabled(len(self._file_list.paths()) > 0)
        self._title_bar.show_update(self._pending_update_url.split("v")[-1].split("/")[0])
