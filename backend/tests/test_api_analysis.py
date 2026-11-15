def test_get_epochs_clustering(client, monkeypatch):
    """Verifica épocas apiladas y restas entre épocas consecutivas (contrato del frontend)."""
    import numpy as np
    from app import cache, spherex

    rows = [
        {"access_url": f"https://irsa.ipac.caltech.edu/image_{i}.fits", "mjd": mjd, "detector": "D2"}
        for i, mjd in enumerate((60800.0, 60805.0, 60900.0, 60905.0))
    ]
    monkeypatch.setattr(cache, "get_cached_metadata", lambda *args, **kwargs: None)
    monkeypatch.setattr(spherex, "search_images", lambda ra, dec: rows)
    monkeypatch.setattr(spherex, "fetch_cutout", lambda **kwargs: b"fits")
    monkeypatch.setattr(spherex, "aligned_array", lambda *args, **kwargs: np.ones((2, 2)))
    monkeypatch.setattr(spherex, "array_to_png", lambda *args, **kwargs: b"png")
    monkeypatch.setattr(spherex, "diff_to_png", lambda *args, **kwargs: b"png")
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


def test_get_spectrum_photometry(client, monkeypatch):
    """Verifica el cálculo de fotometría de apertura y espectro astronómico."""
    from app import cache, spherex

    rows = [
        {
            "access_url": f"https://irsa.ipac.caltech.edu/image_{i}.fits",
            "mjd": 60800.0 + i,
            "detector": "D2",
        }
        for i in range(6)
    ]
    monkeypatch.setattr(cache, "get_cached_metadata", lambda *args, **kwargs: None)
    monkeypatch.setattr(spherex, "search_images", lambda ra, dec: rows)
    monkeypatch.setattr(
        spherex,
        "spectrum_points",
        lambda *args, **kwargs: [
            {
                "wavelength_um": 1.2,
                "flux": 10.0,
                "flux_err": 1.0,
                "mjd": 60800.0,
                "date": "2025-05-01",
                "detector": "D2",
            }
        ],
    )
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