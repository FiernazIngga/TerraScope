
import requests
import json

from pathlib import Path


# ==========================================
# KONFIGURASI
# ==========================================

API_URL = (
    "https://geoservices.big.go.id/rbi/rest/services/"
    "BATASWILAYAH/BATAS_KABKOTA_AR/MapServer/0/query"
)

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "boundaries"

OUTPUT_FILE = OUTPUT_DIR / "diy_kabupaten_kota.geojson"


# ==========================================
# MENGAMBIL DATA DARI BIG
# ==========================================

def download_boundaries():

    print("Menghubungi layanan BIG...")

    params = {
        "where": "WADMPR = 'Daerah Istimewa Yogyakarta'",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson"
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise RuntimeError(data["error"])

    features = data.get("features", [])

    print("Jumlah wilayah ditemukan:", len(features))

    # Memastikan tepat lima wilayah
    if len(features) != 5:
        raise ValueError(
            f"Seharusnya ada 5 wilayah, tetapi ditemukan {len(features)}"
        )

    # Membuat folder jika belum tersedia
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Menyimpan GeoJSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False)

    print("\nData berhasil disimpan!")
    print("Lokasi:", OUTPUT_FILE)

    print("\nDaftar wilayah:")

    for feature in features:
        properties = feature.get("properties", {})
        print("-", properties.get("WADMKK"))


if __name__ == "__main__":
    download_boundaries()
