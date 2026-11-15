from app import spherex


def test_select_frames_linspace_distribution():
    """Verifies that select_frames uses uniform sampling across time."""
    rows = [
        {"obs_id": f"obs_{i:02d}", "mjd": 60800.0 + i * 2, "detector": "D2", "access_url": f"http://test/{i}.fits"}
        for i in range(40)
    ]
    sampled = spherex.select_frames(rows, detector="D2", n=10)
    assert len(sampled) == 10
    # First and last element must be the temporal extremes
    assert sampled[0]["obs_id"] == "obs_00"
    assert sampled[-1]["obs_id"] == "obs_39"


def test_build_epochs_clustering_logic():
    """Verifies the pure logic of epoch clustering by day separation."""
    frames = [
        {"mjd": 60800.0, "detector": "D2", "date": "2025-05-01"},
        {"mjd": 60805.0, "detector": "D2", "date": "2025-05-06"},
        # Gap of 65 days (> 45 days)
        {"mjd": 60870.0, "detector": "D2", "date": "2025-07-10"},
        {"mjd": 60875.0, "detector": "D2", "date": "2025-07-15"},
    ]
    epochs = spherex.build_epochs(frames, threshold_days=45.0)
    assert len(epochs) == 2
    assert epochs[0]["frame_count"] == 2
    assert epochs[1]["frame_count"] == 2
    assert epochs[0]["mjd_start"] == 60800.0
    assert epochs[1]["mjd_start"] == 60870.0


def test_cutout_to_png_pure_function(sample_fits_file):
    """Verifies the pure function cutout_to_png receiving in-memory bytes."""
    raw_fits_bytes = sample_fits_file.read_bytes()
    png_bytes = spherex.cutout_to_png(
        fits_bytes=raw_fits_bytes,
        ra=76.95642,
        dec=30.40142,
        fov=0.1,
        zoom=4,
    )
    assert isinstance(png_bytes, bytes)
    assert len(png_bytes) > 500
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def test_cutout_wavelength_pure_function(sample_fits_file):
    """Verifies pure wavelength extraction from FITS bytes."""
    raw_fits_bytes = sample_fits_file.read_bytes()
    lam = spherex.cutout_wavelength(raw_fits_bytes, ra=76.95642, dec=30.40142)
    assert lam is not None
    assert 0.75 <= lam <= 5.0


def _png_pixels(png_bytes):
    import io

    import imageio.v2 as imageio

    return imageio.imread(io.BytesIO(png_bytes))


def test_saturated_pixels_render_white_and_no_data_black():
    """Saturados (+inf) en blanco: negro se leería como cielo vacío. Sin datos (NaN) en negro."""
    import numpy as np

    arr = np.linspace(0.0, 1.0, 16).reshape(4, 4)
    arr[1, 1] = np.inf
    arr[2, 2] = np.nan
    img = _png_pixels(spherex.array_to_png(arr, zoom=1))
    # _encode_png voltea las filas (norte arriba)
    assert img[2, 1] == 255
    assert img[1, 2] == 0


def test_diff_ignores_saturated_pixels():
    """En la diferencia, un píxel saturado no tiene cambio medible: gris."""
    import numpy as np

    diff = np.array([[np.inf, 1.0], [np.nan, -1.0]])
    img = _png_pixels(spherex.diff_to_png(diff, zoom=1))
    assert img.tolist() == [[127, 0], [127, 255]]
