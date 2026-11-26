"""DisasterScope - Interactive Geospatial Analysis & Disaster Simulation Platform."""

import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from PySide6.QtCore import QObject, Qt, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.prepare_map_data import prepare_map_data
from simulation import run_drought_simulation, run_flood_simulation
from simulation.common import RISK_LABELS, SimulationResult
from ui.widgets import (
    ACCENT,
    BACKGROUND,
    MUTED,
    PANEL,
    PANEL_LIGHT,
    TEXT,
    SliderRow,
    TaskWorker,
    create_action_button,
    create_card,
    create_label,
    create_nav_button,
)
from visualization import RAW_RASTER_LAYERS, export_raw_raster_overlay, export_simulation_overlay

BASE_DIR = Path(__file__).resolve().parent
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
MAP_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/maps/diy_map.html"

REGIONS = [
    ("Semua Wilayah (DIY)", ""),
    ("Kabupaten Sleman", "Sleman"),
    ("Kabupaten Bantul", "Bantul"),
    ("Kabupaten Gunungkidul", "Gunungkidul"),
    ("Kabupaten Kulon Progo", "Kulon Progo"),
    ("Kota Yogyakarta", "Kota Yogyakarta"),
]


class DebugWebEnginePage(QWebEnginePage):
    """QWebEnginePage forwarding JS console errors/logs to stdout."""

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        print(f"[JS:{lineNumber}] {message} ({sourceID})")


class MapBridge(QObject):
    """Bridge object exposed to JavaScript via QWebChannel."""

    region_clicked = Signal(str)

    @Slot(str)
    def onRegionSelected(self, region_name: str):
        self.region_clicked.emit(region_name)


class ReusableHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class QuietHTTPHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002
        pass


class LocalServer:
    """Embedded HTTP server serving local maps, assets, and overlays."""

    def __init__(self, directory: Path, port: int = SERVER_PORT):
        self.server = ReusableHTTPServer(
            (SERVER_HOST, port),
            lambda *args, **kwargs: QuietHTTPHandler(
                *args, directory=str(directory), **kwargs
            ),
        )
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


class DisasterScope(QMainWindow):
    """Main desktop window coordinating sidebar controls, MapLibre view, and results."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DisasterScope - Disaster Scenario Simulator")
        self.resize(1460, 860)
        self.setMinimumSize(1140, 680)

        self.local_server: LocalServer | None = None
        self.map_ready = False
        self.active_worker: TaskWorker | None = None
        self.last_result: SimulationResult | None = None
        self.selected_region = ""

        central = QWidget()
        central.setStyleSheet(f"background-color: {BACKGROUND};")
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = self.create_sidebar()
        self.center_panel = self.create_center_panel()
        self.right_panel = self.create_right_panel()

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.center_panel, 1)
        main_layout.addWidget(self.right_panel)

        self.load_map()

    # ======================================
    # SIDEBAR KIRI
    # ======================================

    def create_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(265)
        sidebar.setStyleSheet(
            f"""
            QFrame {{
                background-color: {BACKGROUND};
                border-right: 1px solid {PANEL_LIGHT};
            }}
            """
        )

        outer = QVBoxLayout(sidebar)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 22, 18, 18)
        layout.setSpacing(10)

        layout.addWidget(create_label("DISASTERSCOPE", 19, ACCENT, True))
        layout.addWidget(create_label("Disaster Scenario Simulator", 10, MUTED))
        layout.addSpacing(10)

        # Navigasi
        layout.addWidget(create_label("NAVIGASI", 10, MUTED, True))
        self.btn_interactive = create_nav_button("▣   Peta Interaktif")
        self.btn_interactive.setChecked(True)
        layout.addWidget(self.btn_interactive)
        layout.addSpacing(10)

        # Simulasi Bencana
        layout.addWidget(create_label("SIMULASI BENCANA", 10, MUTED, True))
        self.btn_drought = create_nav_button("◈   Kekeringan")
        self.btn_flood = create_nav_button("◈   Banjir")
        layout.addWidget(self.btn_drought)
        layout.addWidget(self.btn_flood)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_group.addButton(self.btn_interactive, 0)
        self.mode_group.addButton(self.btn_drought, 1)
        self.mode_group.addButton(self.btn_flood, 2)
        self.mode_group.idClicked.connect(self.on_mode_changed)

        # Panel Parameter Simulasi
        self.sim_param_card = create_card()
        sim_layout = QVBoxLayout(self.sim_param_card)
        sim_layout.setContentsMargins(12, 12, 12, 12)
        sim_layout.setSpacing(10)

        self.sim_param_stack = QStackedWidget()
        self.sim_param_stack.setStyleSheet("background: transparent;")

        # Page 0: Kekeringan
        drought_page = QWidget()
        drought_page.setStyleSheet("background: transparent;")
        d_layout = QVBoxLayout(drought_page)
        d_layout.setContentsMargins(0, 0, 0, 0)
        d_layout.setSpacing(10)
        self.sld_rain_cut = SliderRow("Pengurangan Hujan", 0, 60, 20, step=5, unit="%")
        self.sld_temp_up = SliderRow("Kenaikan Suhu", 0.0, 5.0, 1.5, step=0.5, unit=" °C")
        d_layout.addWidget(self.sld_rain_cut)
        d_layout.addWidget(self.sld_temp_up)

        # Page 1: Banjir
        flood_page = QWidget()
        flood_page.setStyleSheet("background: transparent;")
        f_layout = QVBoxLayout(flood_page)
        f_layout.setContentsMargins(0, 0, 0, 0)
        f_layout.setSpacing(10)
        self.sld_rain_surge = SliderRow("Kenaikan Hujan", 0, 100, 30, step=5, unit="%")
        self.sld_runoff = SliderRow("Sensitivitas Limpasan", 0.5, 1.5, 1.0, step=0.1, unit="x")
        f_layout.addWidget(self.sld_rain_surge)
        f_layout.addWidget(self.sld_runoff)

        self.sim_param_stack.addWidget(drought_page)
        self.sim_param_stack.addWidget(flood_page)
        sim_layout.addWidget(self.sim_param_stack)

        self.btn_run_sim = create_action_button("Jalankan Simulasi", primary=True)
        self.btn_clear_overlay = create_action_button("Bersihkan Layer", primary=False)
        self.btn_run_sim.clicked.connect(self.on_run_simulation)
        self.btn_clear_overlay.clicked.connect(self.on_clear_overlay)
        sim_layout.addWidget(self.btn_run_sim)
        sim_layout.addWidget(self.btn_clear_overlay)

        self.sim_param_card.setVisible(False)
        layout.addWidget(self.sim_param_card)
        layout.addSpacing(10)

        # Data Spasial
        layout.addWidget(create_label("DATA SPASIAL", 10, MUTED, True))

        checkbox_style = f"""
            QCheckBox {{
                color: {TEXT};
                font-size: 12px;
                spacing: 8px;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 15px;
                height: 15px;
                border-radius: 3px;
                border: 1px solid {PANEL_LIGHT};
                background: {PANEL};
            }}
            QCheckBox::indicator:checked {{
                background: {ACCENT};
                border-color: {ACCENT};
            }}
        """

        self.chk_boundaries = QCheckBox("Batas Administrasi")
        self.chk_boundaries.setChecked(True)
        self.chk_boundaries.setStyleSheet(checkbox_style)
        self.chk_boundaries.toggled.connect(self.on_toggle_boundaries)
        layout.addWidget(self.chk_boundaries)

        self.chk_raster = QCheckBox("Data Raster")
        self.chk_raster.setChecked(False)
        self.chk_raster.setStyleSheet(checkbox_style)
        self.chk_raster.toggled.connect(self.on_toggle_raster_layer)
        layout.addWidget(self.chk_raster)

        self.cmb_raster = QComboBox()
        self.cmb_raster.setStyleSheet(
            f"""
            QComboBox {{
                background-color: {PANEL};
                color: {TEXT};
                border: 1px solid {PANEL_LIGHT};
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 11px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {PANEL};
                color: {TEXT};
                selection-background-color: #14532d;
            }}
            """
        )
        for key, cfg in RAW_RASTER_LAYERS.items():
            self.cmb_raster.addItem(cfg["label"], key)
        self.cmb_raster.currentIndexChanged.connect(self.on_raster_combo_changed)
        layout.addWidget(self.cmb_raster)

        layout.addStretch()
        layout.addWidget(create_label("DisasterScope v0.2", 10, MUTED))
        layout.addWidget(create_label("DIY, Indonesia", 10, MUTED))

        scroll.setWidget(content)
        outer.addWidget(scroll)
        return sidebar

    # ======================================
    # PANEL TENGAH
    # ======================================

    def create_center_panel(self) -> QWidget:
        center = QWidget()
        layout = QVBoxLayout(center)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(75)
        header.setStyleSheet(
            f"""
            QFrame {{
                background-color: {PANEL};
                border-bottom: 1px solid {PANEL_LIGHT};
            }}
            """
        )
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 10, 20, 10)
        header_layout.setSpacing(4)
        self.header_title = create_label("Peta Interaktif DIY", 17, TEXT, True)
        self.header_subtitle = create_label(
            "Daerah Istimewa Yogyakarta, Indonesia", 10, MUTED
        )
        header_layout.addWidget(self.header_title)
        header_layout.addWidget(self.header_subtitle)
        layout.addWidget(header)

        self.map_view = QWebEngineView()
        debug_page = DebugWebEnginePage(self.map_view)
        self.web_channel = QWebChannel(debug_page)
        self.bridge = MapBridge()
        self.bridge.region_clicked.connect(self.on_map_region_clicked)
        self.web_channel.registerObject("bridge", self.bridge)
        debug_page.setWebChannel(self.web_channel)

        self.map_view.setPage(debug_page)
        self.map_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self.map_view)

        return center

    # ======================================
    # PANEL KANAN
    # ======================================

    def create_right_panel(self) -> QFrame:
        panel = QFrame()
        panel.setFixedWidth(290)
        panel.setStyleSheet(
            f"""
            QFrame {{
                background-color: {BACKGROUND};
                border-left: 1px solid {PANEL_LIGHT};
            }}
            """
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 22, 18, 18)
        layout.setSpacing(12)

        layout.addWidget(create_label("INFORMASI PETA", 14, TEXT, True))
        layout.addWidget(create_label("Cakupan Wilayah", 11, MUTED))

        region_card = create_card()
        region_layout = QVBoxLayout(region_card)
        region_layout.setContentsMargins(12, 12, 12, 12)
        region_layout.addWidget(create_label("5 Kabupaten/Kota", 17, ACCENT, True))
        region_layout.addWidget(create_label("Daerah Istimewa Yogyakarta", 10, MUTED))
        layout.addWidget(region_card)

        layout.addWidget(create_label("DAFTAR WILAYAH", 10, MUTED, True))

        self.region_group = QButtonGroup(self)
        self.region_group.setExclusive(True)
        self.region_buttons: dict[str, object] = {}

        for idx, (label, wadmkk) in enumerate(REGIONS):
            btn = create_nav_button(f"●   {label}")
            if wadmkk == "":
                btn.setChecked(True)
            self.region_group.addButton(btn, idx)
            self.region_buttons[wadmkk] = btn
            layout.addWidget(btn)

        self.region_group.idClicked.connect(self.on_region_button_clicked)

        layout.addSpacing(8)
        layout.addWidget(create_label("STATUS SIMULASI", 10, MUTED, True))

        status_card = create_card()
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(12, 12, 12, 12)
        status_layout.setSpacing(6)

        self.status_title = create_label("Siap digunakan", 12, TEXT, True)
        self.status_desc = create_label(
            "Pilih simulasi Kekeringan / Banjir atau aktifkan Data Raster di sidebar kiri.",
            10,
            MUTED,
        )
        self.status_desc.setWordWrap(True)
        self.status_metrics = create_label("", 11, TEXT)
        self.status_metrics.setWordWrap(True)

        status_layout.addWidget(self.status_title)
        status_layout.addWidget(self.status_desc)
        status_layout.addWidget(self.status_metrics)
        layout.addWidget(status_card)

        layout.addStretch()
        layout.addWidget(create_label("DATA SPASIAL", 10, MUTED, True))
        layout.addWidget(create_label("Batas: BIG (GeoJSON)", 11, TEXT))
        layout.addWidget(create_label("Raster: Landsat 8/9, SRTM, ESA, CHIRPS", 10, MUTED))

        return panel

    # ======================================
    # PEMUATAN PETA & JS HELPERS
    # ======================================

    def load_map(self):
        geojson_js = BASE_DIR / "maps" / "diy_geojson.js"
        if not geojson_js.exists():
            prepare_map_data()

        map_file = BASE_DIR / "maps" / "diy_map.html"
        if not map_file.exists():
            raise FileNotFoundError(f"File peta tidak ditemukan: {map_file}")

        self.local_server = LocalServer(directory=BASE_DIR, port=SERVER_PORT)
        self.local_server.start()

        self.map_view.loadFinished.connect(self.on_map_loaded)
        self.map_view.setUrl(QUrl(MAP_URL))

    def on_map_loaded(self, success: bool):
        self.map_ready = success
        if success:
            print("Peta DisasterScope berhasil dibuka.")
        else:
            print("Peta gagal dimuat.")

    def _run_js(self, code: str):
        if self.map_ready:
            self.map_view.page().runJavaScript(code)

    # ======================================
    # HANDLER INTERAKSI
    # ======================================

    def on_mode_changed(self, mode_id: int):
        if mode_id == 0:
            self.sim_param_card.setVisible(False)
            self.header_title.setText("Peta Interaktif DIY")
            self.header_subtitle.setText("Daerah Istimewa Yogyakarta, Indonesia")
        elif mode_id == 1:
            self.sim_param_stack.setCurrentIndex(0)
            self.sim_param_card.setVisible(True)
            self.header_title.setText("Simulasi Bencana Kekeringan")
            self.header_subtitle.setText("Indeks Vegetasi (NDVI), Kelembapan (NDMI), Suhu (LST) & Hujan")
        elif mode_id == 2:
            self.sim_param_stack.setCurrentIndex(1)
            self.sim_param_card.setVisible(True)
            self.header_title.setText("Simulasi Bencana Banjir")
            self.header_subtitle.setText("Elevasi SRTM, Kemiringan Lereng, Tutupan Lahan & Curah Hujan")

    def on_toggle_boundaries(self, checked: bool):
        self._run_js(f"window.terraMap?.setBoundaryVisible({json.dumps(checked)});")

    def on_toggle_raster_layer(self, checked: bool):
        if checked:
            self._load_selected_raw_raster()
        else:
            self._run_js("window.terraMap?.clearRasterOverlay();")
            if self.last_result is None:
                self.status_title.setText("Layer raster dimatikan")
                self.status_desc.setText("Peta kembali menampilkan batas wilayah DIY.")
                self.status_metrics.setText("")

    def on_raster_combo_changed(self):
        if self.chk_raster.isChecked():
            self._load_selected_raw_raster()

    def _load_selected_raw_raster(self):
        layer_key = self.cmb_raster.currentData()
        layer_label = self.cmb_raster.currentText()
        self._set_busy(True, "Memuat layer raster...", layer_label)

        def job():
            return export_raw_raster_overlay(layer_key)

        self._start_worker(job, self._on_raw_raster_ready)

    def _on_raw_raster_ready(self, overlay_cfg: dict):
        self._set_busy(False)
        self.last_result = None
        self._apply_overlay_to_map(overlay_cfg)
        self.status_title.setText("Pratinjau Data Raster")
        self.status_desc.setText(overlay_cfg["legend"]["title"])
        self.status_metrics.setText("Sumber: data/raster/ (30 m, EPSG:32749)")

    def on_run_simulation(self):
        mode_id = self.mode_group.checkedId()
        if mode_id not in (1, 2):
            return

        if self.chk_raster.isChecked():
            self.chk_raster.blockSignals(True)
            self.chk_raster.setChecked(False)
            self.chk_raster.blockSignals(False)

        if mode_id == 1:
            rain_cut = self.sld_rain_cut.value()
            temp_up = self.sld_temp_up.value()
            self._set_busy(
                True,
                "Menghitung Simulasi Kekeringan...",
                f"Pengurangan hujan {rain_cut:.0f}%, kenaikan suhu +{temp_up:.1f} °C",
            )

            def job():
                res = run_drought_simulation(
                    rainfall_reduction_pct=rain_cut,
                    temp_increase_c=temp_up,
                )
                overlay = export_simulation_overlay(res)
                return res, overlay

        else:
            rain_surge = self.sld_rain_surge.value()
            runoff = self.sld_runoff.value()
            self._set_busy(
                True,
                "Menghitung Simulasi Banjir...",
                f"Kenaikan hujan +{rain_surge:.0f}%, sensitivitas limpasan {runoff:.1f}x",
            )

            def job():
                res = run_flood_simulation(
                    rainfall_increase_pct=rain_surge,
                    runoff_sensitivity=runoff,
                )
                overlay = export_simulation_overlay(res)
                return res, overlay

        self._start_worker(job, self._on_simulation_ready)

    def _on_simulation_ready(self, payload):
        result, overlay_cfg = payload
        self._set_busy(False)
        self.last_result = result
        self._apply_overlay_to_map(overlay_cfg)
        self._refresh_simulation_card()

    def on_clear_overlay(self):
        self.last_result = None
        if self.chk_raster.isChecked():
            self.chk_raster.blockSignals(True)
            self.chk_raster.setChecked(False)
            self.chk_raster.blockSignals(False)
        self._run_js("window.terraMap?.clearRasterOverlay();")
        self.status_title.setText("Overlay dibersihkan")
        self.status_desc.setText("Pilih simulasi atau aktifkan Data Raster untuk menampilkan hasil.")
        self.status_metrics.setText("")

    def on_region_button_clicked(self, btn_id: int):
        _, wadmkk = REGIONS[btn_id]
        self.selected_region = wadmkk
        if wadmkk:
            self._run_js(f"window.terraMap?.focusRegion({json.dumps(wadmkk)});")
        else:
            self._run_js("window.terraMap?.resetView();")
        self._refresh_simulation_card()

    def on_map_region_clicked(self, region_name: str):
        self.selected_region = region_name
        btn = self.region_buttons.get(region_name)
        if btn is not None:
            btn.setChecked(True)
        self._refresh_simulation_card()

    def _apply_overlay_to_map(self, cfg: dict):
        url = json.dumps(cfg["imageUrl"])
        coords = json.dumps(cfg["coordinates"])
        legend = json.dumps(cfg["legend"])
        self._run_js(f"window.terraMap?.setRasterOverlay({url}, {coords}, {legend});")

    def _refresh_simulation_card(self):
        if self.last_result is None:
            if self.selected_region:
                self.status_title.setText(self.selected_region)
                self.status_desc.setText(
                    "Wilayah dipilih. Jalankan simulasi Kekeringan atau Banjir untuk melihat statistik wilayah ini."
                )
                self.status_metrics.setText("")
            return

        res = self.last_result
        if self.selected_region and self.selected_region in res.stats["by_region"]:
            scope_name = self.selected_region
            summary = res.stats["by_region"][self.selected_region]
        else:
            scope_name = "Seluruh DIY"
            summary = res.stats["overall"]

        self.status_title.setText(f"{res.title} — {scope_name}")
        if res.scenario == "drought":
            self.status_desc.setText(
                f"Hujan -{res.params['rainfall_reduction_pct']:.0f}%, "
                f"Suhu +{res.params['temp_increase_c']:.1f} °C | Total: {summary['total_km2']} km²"
            )
        else:
            self.status_desc.setText(
                f"Hujan +{res.params['rainfall_increase_pct']:.0f}%, "
                f"Limpasan {res.params['runoff_sensitivity']:.1f}x | Total: {summary['total_km2']} km²"
            )

        lines = [
            f"• {RISK_LABELS[cid]}: {summary['classes'][cid]['area_km2']} km² "
            f"({summary['classes'][cid]['pct']}%)"
            for cid in (4, 3, 2, 1)
        ]
        self.status_metrics.setText("\n".join(lines))

    def _set_busy(self, busy: bool, title: str = "", desc: str = ""):
        self.btn_run_sim.setEnabled(not busy)
        self.chk_raster.setEnabled(not busy)
        self.cmb_raster.setEnabled(not busy)
        if busy:
            self.status_title.setText(title)
            self.status_desc.setText(desc)
            self.status_metrics.setText("")

    def _start_worker(self, job_fn, on_success):
        if self.active_worker is not None and self.active_worker.isRunning():
            return
        self.active_worker = TaskWorker(job_fn)
        self.active_worker.finished_ok.connect(on_success)
        self.active_worker.failed.connect(self._on_worker_error)
        self.active_worker.start()

    def _on_worker_error(self, message: str):
        self._set_busy(False)
        self.status_title.setText("Terjadi Kesalahan")
        self.status_desc.setText(message)
        self.status_metrics.setText("")

    def closeEvent(self, event):
        if self.active_worker is not None and self.active_worker.isRunning():
            self.active_worker.quit()
            self.active_worker.wait(1000)
        if self.local_server:
            self.local_server.stop()
            print("Server lokal berhasil dihentikan.")
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DisasterScope()
    window.show()
    sys.exit(app.exec())
