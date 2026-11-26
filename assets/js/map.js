// Memastikan data GeoJSON tersedia
if (!window.DIY_GEOJSON) {
    throw new Error("Data GeoJSON DIY tidak ditemukan.");
}

const DIY_BOUNDS = [
    [110.00359125, -8.205601],
    [110.83882785, -7.54116156]
];

let pyBridge = null;
if (typeof qt !== "undefined" && qt.webChannelTransport && typeof QWebChannel !== "undefined") {
    new QWebChannel(qt.webChannelTransport, function (channel) {
        pyBridge = channel.objects.bridge || null;
    });
}

// Membuat peta menggunakan MapLibre
const map = new maplibregl.Map({
    container: "map",
    style: "https://tiles.openfreemap.org/styles/liberty",
    center: [110.3695, -7.7956],
    zoom: 9
});

map.on("error", function (event) {
    console.error("MAPLIBRE ERROR:", event.error);
});

map.addControl(new maplibregl.NavigationControl(), "top-right");

let mapReady = false;
let activePopup = null;

function collectCoords(coords, out) {
    if (typeof coords[0] === "number") {
        out.push(coords);
    } else {
        for (const item of coords) {
            collectCoords(item, out);
        }
    }
}

function getFeatureBounds(feature) {
    const pts = [];
    collectCoords(feature.geometry.coordinates, pts);
    let minLng = Infinity;
    let minLat = Infinity;
    let maxLng = -Infinity;
    let maxLat = -Infinity;

    for (const [lng, lat] of pts) {
        if (lng < minLng) minLng = lng;
        if (lat < minLat) minLat = lat;
        if (lng > maxLng) maxLng = lng;
        if (lat > maxLat) maxLat = lat;
    }
    return [
        [minLng, minLat],
        [maxLng, maxLat]
    ];
}

function renderLegend(legend) {
    const el = document.getElementById("map-legend");
    if (!el) return;
    if (!legend || !legend.items || legend.items.length === 0) {
        el.classList.add("hidden");
        el.innerHTML = "";
        return;
    }

    const itemsHtml = legend.items
        .map(
            (item) =>
                `<div class="map-legend-item">` +
                `<span class="map-legend-swatch" style="background:${item.color}"></span>` +
                `<span>${item.label}</span>` +
                `</div>`
        )
        .join("");

    el.innerHTML = `<div class="map-legend-title">${legend.title}</div>${itemsHtml}`;
    el.classList.remove("hidden");
}

function selectFeature(regionName) {
    if (!mapReady) return;
    if (regionName) {
        map.setFilter("diy-selected-outline", ["==", ["get", "WADMKK"], regionName]);
    } else {
        map.setFilter("diy-selected-outline", ["==", ["get", "WADMKK"], ""]);
    }
}

window.terraMap = {
    setBoundaryVisible: function (visible) {
        if (!mapReady) return;
        const vis = visible ? "visible" : "none";
        ["diy-fill", "diy-outline", "diy-selected-outline"].forEach((layerId) => {
            if (map.getLayer(layerId)) {
                map.setLayoutProperty(layerId, "visibility", vis);
            }
        });
    },

    setRasterOverlay: function (imageUrl, coordinates, legend) {
        if (!mapReady) return;
        if (map.getLayer("raster-overlay-layer")) {
            map.removeLayer("raster-overlay-layer");
        }
        if (map.getSource("raster-overlay")) {
            map.removeSource("raster-overlay");
        }

        map.addSource("raster-overlay", {
            type: "image",
            url: imageUrl,
            coordinates: coordinates
        });

        const beforeLayer = map.getLayer("diy-outline") ? "diy-outline" : undefined;
        map.addLayer(
            {
                id: "raster-overlay-layer",
                type: "raster",
                source: "raster-overlay",
                paint: {
                    "raster-opacity": 0.82,
                    "raster-fade-duration": 0
                }
            },
            beforeLayer
        );

        renderLegend(legend);
    },

    clearRasterOverlay: function () {
        if (!mapReady) return;
        if (map.getLayer("raster-overlay-layer")) {
            map.removeLayer("raster-overlay-layer");
        }
        if (map.getSource("raster-overlay")) {
            map.removeSource("raster-overlay");
        }
        renderLegend(null);
    },

    focusRegion: function (regionName) {
        if (!mapReady) return;
        const feature = window.DIY_GEOJSON.features.find(
            (f) => f.properties && f.properties.WADMKK === regionName
        );
        if (!feature) return;

        selectFeature(regionName);
        map.fitBounds(getFeatureBounds(feature), { padding: 45, duration: 600 });
    },

    resetView: function () {
        if (!mapReady) return;
        selectFeature("");
        if (activePopup) {
            activePopup.remove();
            activePopup = null;
        }
        map.fitBounds(DIY_BOUNDS, { padding: 30, duration: 600 });
    }
};

map.on("load", function () {
    mapReady = true;

    map.addSource("diy-boundaries", {
        type: "geojson",
        data: window.DIY_GEOJSON
    });

    map.addLayer({
        id: "diy-fill",
        type: "fill",
        source: "diy-boundaries",
        paint: {
            "fill-color": "#3388ff",
            "fill-opacity": 0.1
        }
    });

    map.addLayer({
        id: "diy-outline",
        type: "line",
        source: "diy-boundaries",
        paint: {
            "line-color": "#163a5c",
            "line-width": 2
        }
    });

    map.addLayer({
        id: "diy-selected-outline",
        type: "line",
        source: "diy-boundaries",
        filter: ["==", ["get", "WADMKK"], ""],
        paint: {
            "line-color": "#22c55e",
            "line-width": 3.5
        }
    });

    map.fitBounds(DIY_BOUNDS, { padding: 30 });

    map.on("click", "diy-fill", function (event) {
        const feature = event.features[0];
        const region = feature.properties.WADMKK;

        selectFeature(region);
        if (activePopup) activePopup.remove();

        activePopup = new maplibregl.Popup()
            .setLngLat(event.lngLat)
            .setHTML("<strong>Wilayah:</strong> " + region)
            .addTo(map);

        if (pyBridge && typeof pyBridge.onRegionSelected === "function") {
            pyBridge.onRegionSelected(region);
        }
    });

    map.on("mouseenter", "diy-fill", function () {
        map.getCanvas().style.cursor = "pointer";
    });

    map.on("mouseleave", "diy-fill", function () {
        map.getCanvas().style.cursor = "";
    });

    console.log("Peta DisasterScope berhasil dimuat.");
});
