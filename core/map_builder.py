
import folium
import geopandas as gpd

from pathlib import Path
from folium.plugins import Fullscreen


# Lokasi file GeoJSON
BASE_DIR = Path(__file__).resolve().parent.parent

BOUNDARY_FILE = (
    BASE_DIR
    / "data"
    / "boundaries"
    / "diy_kabupaten_kota.geojson"
)


def create_diy_map():

    # Membuat peta dasar DIY
    map_object = folium.Map(
        location=[-7.7956, 110.3695],
        zoom_start=9,
        tiles="OpenStreetMap",
        control_scale=True,
        zoom_control=True
    )

    # Membaca data batas wilayah
    gdf = gpd.read_file(BOUNDARY_FILE)

    # Memastikan koordinat menggunakan WGS84
    if gdf.crs is None:
        raise ValueError("Data batas wilayah tidak memiliki CRS.")

    gdf = gdf.to_crs(epsg=4326)

    # Menambahkan batas administratif ke peta
    folium.GeoJson(
        data=gdf.to_json(),
        name="Batas Kabupaten/Kota",

        style_function=lambda feature: {
            "fillColor": "#3388ff",
            "color": "#163a5c",
            "weight": 2,
            "fillOpacity": 0.12
        },

        highlight_function=lambda feature: {
            "weight": 4,
            "color": "#ff7800",
            "fillOpacity": 0.3
        },

        tooltip=folium.GeoJsonTooltip(
            fields=["WADMKK"],
            aliases=["Wilayah:"],
            sticky=True
        )
    ).add_to(map_object)

    # Menyesuaikan tampilan agar seluruh DIY terlihat
    min_x, min_y, max_x, max_y = gdf.total_bounds

    map_object.fit_bounds([
        [min_y, min_x],
        [max_y, max_x]
    ])

    # Tombol fullscreen
    Fullscreen().add_to(map_object)

    # Kontrol layer
    folium.LayerControl().add_to(map_object)

    return map_object
