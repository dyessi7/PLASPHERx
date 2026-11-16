def _mock_frame_search(monkeypatch, rows):
    from app import cache, spherex

    monkeypatch.setattr(spherex, "search_images", lambda ra, dec: rows)
    monkeypatch.setattr(cache, "get_cached_metadata", lambda *args, **kwargs: None)
    monkeypatch.setattr(cache, "save_cached_metadata", lambda *args, **kwargs: None)


def _rows():
    return [
        {
            "obs_id": f"obs_{i}",
            "access_url": f"https://irsa.ipac.caltech.edu/image_{i}.fits",
            "mjd": 60800.0 + i * 60,
            "detector": "D2",
        }
        for i in range(4)
    ]


def test_get_frames_by_target(client, monkeypatch):
    """Verifies retrieval of temporal frame sequence for a known target."""
    _mock_frame_search(monkeypatch, _rows())
    resp = client.get("/api/frames?target=rw_aur&detector=D2&n=8")
    assert resp.status_code == 200
    data = resp.json()
    assert data["target"]["name"] == "RW Aurigae"
    assert data["total_frames"] > 0
    assert len(data["frames"]) <= 8

    first = data["frames"][0]
    assert "url" in first
    assert first["detector"] == "D2"
    assert "mjd" in first
    assert "date" in first


def test_get_frames_by_coordinates(client, monkeypatch):
    """Verifies retrieval of frames using direct RA/Dec sky coordinates."""
    _mock_frame_search(monkeypatch, _rows())
    resp = client.get("/api/frames?ra=76.95642&dec=30.40142&fov=0.1&detector=D2&n=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["frames"]) > 0


def test_get_frames_validation_errors(client):
    """Verifies rejection with 400 when invalid query parameters are supplied."""
    # Without target or coordinates
    resp_empty = client.get("/api/frames")
    assert resp_empty.status_code == 400

    # Coordinates out of range
    resp_bad_ra = client.get("/api/frames?ra=999&dec=0")
    assert resp_bad_ra.status_code == 400
    assert set(resp_bad_ra.json()) == {"error"}

    # Invalid detector
    resp_bad_det = client.get("/api/frames?target=rw_aur&detector=D99")
    assert resp_bad_det.status_code == 400

    # Non-existent target
    resp_bad_target = client.get("/api/frames?target=non_existent_star_xyz")
    assert resp_bad_target.status_code == 400


def test_frames_timeout_uses_gateway_timeout_response(client, monkeypatch):
    from app import cache, spherex

    def timeout(ra, dec):
        raise TimeoutError("IRSA timed out")

    monkeypatch.setattr(cache, "get_cached_metadata", lambda *args, **kwargs: None)
    monkeypatch.setattr(spherex, "search_images", timeout)
    resp = client.get("/api/frames?ra=10&dec=20")

    assert resp.status_code == 504
    assert set(resp.json()) == {"error"}


def test_get_frame_png_rendering_and_cache(client, sample_fits_file):
    """Verifies in-memory cutout download/processing to PNG and subsequent cached retrieval."""
    mock_url = f"https://irsa.ipac.caltech.edu/ibe/data/spherex/{sample_fits_file.name}"

    # First call: downloads, processes, and caches
    resp1 = client.get(
        f"/api/frame?src={mock_url}&ra=76.95642&dec=30.40142&fov=0.1"
    )
    assert resp1.status_code == 200
    assert resp1.headers["content-type"] == "image/png"
    assert len(resp1.content) > 500
    assert resp1.content.startswith(b"\x89PNG\r\n\x1a\n")

    # Second call: must return identical output directly from cache
    resp2 = client.get(
        f"/api/frame?src={mock_url}&ra=76.95642&dec=30.40142&fov=0.1"
    )
    assert resp2.status_code == 200
    assert resp2.content == resp1.content


def test_get_frame_ssrf_protection(client):
    """Verifies that /api/frame rejects unauthorized URLs not hosted by IRSA."""
    bad_url = "https://malicious-domain.com/evil.fits"
    resp = client.get(f"/api/frame?src={bad_url}&ra=10.0&dec=20.0")
    assert resp.status_code == 400
    assert "invalid" in resp.json()["error"].lower()


def test_frame_cors_exposes_wavelength_header(client):
    """Allows the local frontend to read the optional metadata response headers."""
    resp = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"
    exposed = resp.headers["access-control-expose-headers"]
    assert "X-Wavelength-Um" in exposed
    assert "X-Saturated" in exposed
    assert "X-Contamination-Flags" in exposed
