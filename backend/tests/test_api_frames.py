def test_get_frames_by_target(client):
    """Verifica la obtención de la secuencia temporal para un objetivo conocido."""
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


def test_get_frames_by_coordinates(client):
    """Verifica la obtención de cuadros mediante coordenadas directas RA/Dec."""
    resp = client.get("/api/frames?ra=76.95642&dec=30.40142&fov=0.1&detector=D2&n=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["frames"]) > 0


def test_get_frames_validation_errors(client):
    """Verifica el rechazo con 400 o 422 ante parámetros inválidos."""
    # Sin target ni coordenadas
    resp_empty = client.get("/api/frames")
    assert resp_empty.status_code == 400

    # Coordenadas fuera de rango
    resp_bad_ra = client.get("/api/frames?ra=999&dec=0")
    assert resp_bad_ra.status_code in (400, 422)

    # Detector inválido
    resp_bad_det = client.get("/api/frames?target=rw_aur&detector=D99")
    assert resp_bad_det.status_code == 400

    # Objetivo inexistente
    resp_bad_target = client.get("/api/frames?target=non_existent_star_xyz")
    assert resp_bad_target.status_code == 404


def test_get_frame_png_rendering_and_cache(client, sample_fits_file):
    """Verifica la descarga/procesamiento en memoria a PNG y la respuesta desde caché."""
    mock_url = f"https://irsa.ipac.caltech.edu/ibe/data/spherex/{sample_fits_file.name}"

    # Primera llamada: descarga/procesa y guarda en caché
    resp1 = client.get(
        f"/api/frame?src={mock_url}&ra=76.95642&dec=30.40142&fov=0.1"
    )
    assert resp1.status_code == 200
    assert resp1.headers["content-type"] == "image/png"
    assert len(resp1.content) > 500
    assert resp1.content.startswith(b"\x89PNG\r\n\x1a\n")

    # Segunda llamada: debe responder idéntico desde caché
    resp2 = client.get(
        f"/api/frame?src={mock_url}&ra=76.95642&dec=30.40142&fov=0.1"
    )
    assert resp2.status_code == 200
    assert resp2.content == resp1.content


def test_get_frame_ssrf_protection(client):
    """Verifica que /api/frame rechace URLs no autorizadas que no provengan de IRSA."""
    bad_url = "https://malicious-domain.com/evil.fits"
    resp = client.get(f"/api/frame?src={bad_url}&ra=10.0&dec=20.0")
    assert resp.status_code == 400
    assert "inválida" in resp.json()["error"].lower()
