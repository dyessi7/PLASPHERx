def test_get_epochs_clustering(client):
    """Verifica la agrupación temporal de cuadros en épocas de observación."""
    resp = client.get("/api/epochs?target=rw_aur&detector=D2&threshold_days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_epochs"] >= 1
    assert len(data["epochs"]) == data["total_epochs"]

    for ep in data["epochs"]:
        assert ep["epoch_index"] >= 1
        assert "Época" in ep["label"]
        assert ep["frame_count"] > 0
        assert ep["mjd_start"] <= ep["mjd_end"]
        assert len(ep["frames"]) == ep["frame_count"]


def test_get_spectrum_photometry(client):
    """Verifica el cálculo de fotometría de apertura y espectro astronómico."""
    resp = client.get("/api/spectrum?target=rw_aur&detector=D2&n=6")
    assert resp.status_code == 200
    data = resp.json()
    assert data["target"]["name"] == "RW Aurigae"
    assert data["total_points"] >= 1

    points = data["points"]
    # Verificar orden ascendente por longitud de onda
    wavelengths = [p["wavelength_um"] for p in points]
    assert wavelengths == sorted(wavelengths)

    first = points[0]
    assert 0.75 <= first["wavelength_um"] <= 5.0
    assert isinstance(first["flux"], float)


def test_get_health_system_status(client):
    """Verifica que /api/health reporte estado ok, permisos de escritura y conteo de caché."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["cache_writable"] is True
    assert "cache_stats" in data
    stats = data["cache_stats"]
    assert "cached_png_frames" in stats
    assert "cached_metadata_queries" in stats
    assert "cached_raw_fits" in stats
