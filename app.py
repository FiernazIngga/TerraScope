
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Thread

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
)

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEnginePage


# ==========================================
# KONFIGURASI DIREKTORI
# ==========================================

BASE_DIR = Path(__file__).resolve().parent


# ==========================================
# KONFIGURASI SERVER LOKAL
# ==========================================

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000

MAP_URL = (
    f"http://{SERVER_HOST}:{SERVER_PORT}/maps/diy_map.html"
)


# ==========================================
# KONFIGURASI WARNA
# ==========================================

BACKGROUND = "#0f172a"
PANEL = "#1e293b"
PANEL_LIGHT = "#334155"
TEXT = "#f8fafc"
MUTED = "#94a3b8"
ACCENT = "#22c55e"


# ==========================================
# FUNGSI MEMBUAT LABEL
# ==========================================

def create_label(text, size=12, color=TEXT, bold=False):

    label = QLabel(text)

    weight = "bold" if bold else "normal"

    label.setStyleSheet(f"""
        QLabel {{
            color: {color};
            font-size: {size}px;
            font-weight: {weight};
        }}
    """)

    return label


# ==========================================
# FUNGSI MEMBUAT CARD
# ==========================================

def create_card():

    card = QFrame()

    card.setStyleSheet(f"""
        QFrame {{
            background-color: {PANEL};
            border: 1px solid {PANEL_LIGHT};
            border-radius: 8px;
        }}
    """)

    return card


# ==========================================
# DEBUG JAVASCRIPT
# ==========================================

class DebugWebEnginePage(QWebEnginePage):

    def javaScriptConsoleMessage(
        self, level, message, lineNumber, sourceID
    ):

        print("\n===== JAVASCRIPT CONSOLE =====")
        print("Pesan:", message)
        print("Baris:", lineNumber)
        print("Sumber:", sourceID)
        print("==============================\n")


# ==========================================
# SERVER HTTP LOKAL
# ==========================================

class LocalServer:

    def __init__(self, directory, port=8000):

        self.server = ThreadingHTTPServer(
            (SERVER_HOST, port),

            lambda *args, **kwargs: SimpleHTTPRequestHandler(
                *args,
                directory=str(directory),
                **kwargs
            )
        )

        self.thread = Thread(
            target=self.server.serve_forever,
            daemon=True
        )

    def start(self):

        self.thread.start()

    def stop(self):

        self.server.shutdown()
        self.server.server_close()


# ==========================================
# CLASS UTAMA DISASTERSCOPE
# ==========================================

class DisasterScope(QMainWindow):

    def __init__(self):

        super().__init__()

        # Konfigurasi jendela aplikasi
        self.setWindowTitle(
            "DisasterScope - Disaster Scenario Simulator"
        )

        self.resize(1440, 850)
        self.setMinimumSize(1100, 650)

        # Menyiapkan server lokal
        self.local_server = None

        # Widget utama
        central = QWidget()
        self.setCentralWidget(central)

        # Layout utama horizontal
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Membuat tiga panel utama
        self.sidebar = self.create_sidebar()
        self.center_panel = self.create_center_panel()
        self.right_panel = self.create_right_panel()

        # Memasukkan panel ke layout utama
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.center_panel, 1)
        main_layout.addWidget(self.right_panel)

        central.setStyleSheet(
            f"background-color: {BACKGROUND};"
        )

        # Memuat peta
        self.load_map()

    # ======================================
    # SIDEBAR KIRI
    # ======================================

    def create_sidebar(self):

        sidebar = QFrame()
        sidebar.setFixedWidth(230)

        sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {BACKGROUND};
                border-right: 1px solid {PANEL_LIGHT};
            }}
        """)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 22, 18, 18)
        layout.setSpacing(18)

        layout.addWidget(
            create_label("DISASTERSCOPE", 19, ACCENT, True)
        )

        layout.addWidget(
            create_label(
                "Disaster Scenario Simulator",
                10,
                MUTED
            )
        )

        layout.addSpacing(15)

        layout.addWidget(
            create_label("NAVIGASI", 10, MUTED, True)
        )

        layout.addWidget(
            create_label("▣   Peta Interaktif", 13, TEXT, True)
        )

        layout.addSpacing(20)

        layout.addWidget(
            create_label("SIMULASI BENCANA", 10, MUTED, True)
        )

        layout.addWidget(
            create_label("◈   Kekeringan", 13, TEXT)
        )

        layout.addWidget(
            create_label("◈   Banjir", 13, TEXT)
        )

        layout.addSpacing(20)

        layout.addWidget(
            create_label("DATA SPASIAL", 10, MUTED, True)
        )

        layout.addWidget(
            create_label("▤   Batas Administrasi", 12, TEXT)
        )

        layout.addWidget(
            create_label("▤   Data Raster", 12, MUTED)
        )

        layout.addStretch()

        layout.addWidget(
            create_label("DisasterScope v0.1", 10, MUTED)
        )

        layout.addWidget(
            create_label("DIY, Indonesia", 10, MUTED)
        )

        return sidebar

    # ======================================
    # PANEL TENGAH
    # ======================================

    def create_center_panel(self):

        center = QWidget()

        layout = QVBoxLayout(center)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header peta
        header = QFrame()
        header.setFixedHeight(75)

        header.setStyleSheet(f"""
            QFrame {{
                background-color: {PANEL};
                border-bottom: 1px solid {PANEL_LIGHT};
            }}
        """)

        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 10, 20, 10)
        header_layout.setSpacing(4)

        header_layout.addWidget(
            create_label("Peta Interaktif DIY", 17, TEXT, True)
        )

        header_layout.addWidget(
            create_label(
                "Daerah Istimewa Yogyakarta, Indonesia",
                10,
                MUTED
            )
        )

        layout.addWidget(header)

        # Web view untuk menampilkan MapLibre
        self.map_view = QWebEngineView()

        # Mengaktifkan pemantauan error JavaScript
        debug_page = DebugWebEnginePage(self.map_view)
        self.map_view.setPage(debug_page)

        self.map_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        layout.addWidget(self.map_view)

        return center

    # ======================================
    # PANEL KANAN
    # ======================================

    def create_right_panel(self):

        panel = QFrame()
        panel.setFixedWidth(260)

        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {BACKGROUND};
                border-left: 1px solid {PANEL_LIGHT};
            }}
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 22, 18, 18)
        layout.setSpacing(15)

        layout.addWidget(
            create_label("INFORMASI PETA", 14, TEXT, True)
        )

        layout.addWidget(
            create_label("Cakupan Wilayah", 11, MUTED)
        )

        # Card cakupan wilayah
        region_card = create_card()

        region_layout = QVBoxLayout(region_card)
        region_layout.setContentsMargins(12, 12, 12, 12)

        region_layout.addWidget(
            create_label("5 Kabupaten/Kota", 17, ACCENT, True)
        )

        region_layout.addWidget(
            create_label(
                "Daerah Istimewa Yogyakarta",
                10,
                MUTED
            )
        )

        layout.addWidget(region_card)

        # Daftar wilayah
        layout.addWidget(
            create_label("DAFTAR WILAYAH", 10, MUTED, True)
        )

        regions = [
            "Kabupaten Sleman",
            "Kabupaten Bantul",
            "Kabupaten Gunungkidul",
            "Kabupaten Kulon Progo",
            "Kota Yogyakarta",
        ]

        for region in regions:

            layout.addWidget(
                create_label("●   " + region, 11, TEXT)
            )

        layout.addSpacing(20)

        # Status simulasi
        layout.addWidget(
            create_label("STATUS SIMULASI", 10, MUTED, True)
        )

        status_card = create_card()

        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(12, 12, 12, 12)

        status_layout.addWidget(
            create_label(
                "Belum ada simulasi",
                12,
                TEXT,
                True
            )
        )

        status_layout.addWidget(
            create_label(
                "Pilih skenario kekeringan atau banjir "
                "setelah modul simulasi tersedia.",
                10,
                MUTED
            )
        )

        layout.addWidget(status_card)

        layout.addStretch()

        # Informasi sumber data
        layout.addWidget(
            create_label("DATA BATAS WILAYAH", 10, MUTED, True)
        )

        layout.addWidget(
            create_label("Sumber: BIG", 11, TEXT)
        )

        layout.addWidget(
            create_label("Format: GeoJSON", 11, MUTED)
        )

        return panel

    # ======================================
    # MEMUAT PETA
    # ======================================

    def load_map(self):

        map_file = BASE_DIR / "maps" / "diy_map.html"

        if not map_file.exists():

            raise FileNotFoundError(
                f"File peta tidak ditemukan: {map_file}"
            )

        # Menjalankan server HTTP lokal
        self.local_server = LocalServer(
            directory=BASE_DIR,
            port=SERVER_PORT
        )

        self.local_server.start()

        # Memantau status pemuatan peta
        self.map_view.loadFinished.connect(
            self.on_map_loaded
        )

        # Membuka peta melalui HTTP lokal
        self.map_view.setUrl(QUrl(MAP_URL))

        print("File peta:", map_file)
        print("File tersedia:", map_file.exists())
        print("Server lokal: Aktif")
        print("Alamat peta:", MAP_URL)

    # ======================================
    # STATUS PEMUATAN PETA
    # ======================================

    def on_map_loaded(self, success):

        print("Status pemuatan peta:", success)

        if success:

            print("Peta DisasterScope berhasil dibuka.")

        else:

            print("Peta gagal dimuat.")

    # ======================================
    # MENUTUP APLIKASI
    # ======================================

    def closeEvent(self, event):

        # Mematikan server ketika aplikasi ditutup
        if self.local_server:

            self.local_server.stop()

            print("Server lokal berhasil dihentikan.")

        event.accept()


# ==========================================
# MENJALANKAN APLIKASI
# ==========================================

if __name__ == "__main__":

    app = QApplication(sys.argv)

    window = DisasterScope()
    window.show()

    sys.exit(app.exec())
