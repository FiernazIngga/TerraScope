
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "boundaries"
    / "diy_kabupaten_kota.geojson"
)

OUTPUT_FILE = (
    BASE_DIR
    / "maps"
    / "diy_geojson.js"
)


def prepare_map_data():
    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        geojson_data = json.load(file)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        file.write("window.DIY_GEOJSON = ")
        json.dump(
            geojson_data,
            file,
            ensure_ascii=False
        )
        file.write(";")

    print("Data peta berhasil disiapkan.")
    print("Jumlah wilayah:", len(geojson_data["features"]))
    print("Lokasi:", OUTPUT_FILE)


if __name__ == "__main__":
    prepare_map_data()
