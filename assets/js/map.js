// Memastikan data GeoJSON tersedia
if (!window.DIY_GEOJSON) {
    throw new Error("Data GeoJSON DIY tidak ditemukan.");
}

// Membuat peta menggunakan MapLibre
const map = new maplibregl.Map({
    container: "map",

    // Peta dasar OpenFreeMap
    style: "https://tiles.openfreemap.org/styles/liberty",

    // Titik tengah DIY
    center: [110.3695, -7.7956],

    // Tingkat pembesaran awal
    zoom: 9
});

// Memantau error dari MapLibre
map.on("error", function (event) {
    console.error("MAPLIBRE ERROR:", event.error);
});

// Menambahkan kontrol zoom dan rotasi
map.addControl(
    new maplibregl.NavigationControl(),
    "top-right"
);

// Menunggu peta selesai dimuat
map.on("load", function () {

    // Memasukkan data batas wilayah DIY
    map.addSource("diy-boundaries", {
        type: "geojson",
        data: window.DIY_GEOJSON
    });

    // Membuat lapisan warna wilayah
    map.addLayer({
        id: "diy-fill",
        type: "fill",
        source: "diy-boundaries",
        paint: {
            "fill-color": "#3388ff",
            "fill-opacity": 0.12
        }
    });

    // Membuat garis batas wilayah
    map.addLayer({
        id: "diy-outline",
        type: "line",
        source: "diy-boundaries",
        paint: {
            "line-color": "#163a5c",
            "line-width": 2
        }
    });

    // Menyesuaikan tampilan dengan batas DIY
    map.fitBounds(
        [
            [110.00359125, -8.205601],
            [110.83882785, -7.54116156]
        ],
        {
            padding: 30
        }
    );

    // Menampilkan nama wilayah ketika diklik
    map.on("click", "diy-fill", function (event) {

        const feature = event.features[0];
        const region = feature.properties.WADMKK;

        new maplibregl.Popup()
            .setLngLat(event.lngLat)
            .setHTML("<strong>Wilayah:</strong> " + region)
            .addTo(map);
    });

    // Mengubah kursor ketika diarahkan ke wilayah
    map.on("mouseenter", "diy-fill", function () {
        map.getCanvas().style.cursor = "pointer";
    });

    // Mengembalikan kursor ketika keluar dari wilayah
    map.on("mouseleave", "diy-fill", function () {
        map.getCanvas().style.cursor = "";
    });

    console.log("Peta DisasterScope berhasil dimuat.");
});
