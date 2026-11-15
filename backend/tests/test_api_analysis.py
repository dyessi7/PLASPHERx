def test_get_epochs_clustering(client):
    """Verifica épocas apiladas y restas entre épocas consecutivas (contrato del frontend)."""
    resp = client.get("/api/epochs?target=rw_aur&detector=D2&n=16&threshold_days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert data["detector"] == "D2"
    assert len(data["epochs"]) >= 1
    assert len(data["diffs"]) == len(data["epochs"]) - 1

    for i, ep in enumerate(data["epochs"], start=1):
        assert ep["id"] == f"e{i}"
        assert ep["url"].startswith("data:image/png;base64,")
        assert ep["date_start"] <= ep["date_end"]
        assert ep["n_frames"] > 0
        assert isinstance(ep["mjd_mid"], float)

    ids = [ep["id"] for ep in data["epochs"]]
    for d in data["diffs"]:
        assert d["url"].startswith("data:image/png;base64,")
        assert ids.index(d["b"]) == ids.index(d["a"]) + 1


def test_get_spectrum_photometry(client):
    """Verifica el cálculo de fotometría de apertura y espectro astronómico."""
    resp = client.get("/api/spectrum?target=rw_aur&detector=D2&n=6")
    assert resp.status_code == 200
    data = resp.json()
    assert data["target"]["name"] == "RW Aurigae"
    assert data["total_points"] >= 1
    assert data["flux_unit"] == "mJy"
    assert data["aperture_arcsec"] > 0

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