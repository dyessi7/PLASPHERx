from app import targets


def test_get_targets_catalog_counts_and_types(client):
    """Verifies that catalog returns the 5 official targets with types and base coordinates."""
    resp = client.get("/api/targets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5

    tmap = {t["id"]: t for t in data["targets"]}
    assert set(tmap.keys()) == {"r_dra", "rw_aur", "barnard", "wise0855", "eps_ind"}

    # Expected types: 'variable' or 'mover'
    assert tmap["r_dra"]["target_type"] == "variable"
    assert tmap["rw_aur"]["target_type"] == "variable"
    assert tmap["barnard"]["target_type"] == "mover"
    assert tmap["wise0855"]["target_type"] == "mover"
    assert tmap["eps_ind"]["target_type"] == "mover"

    # J2000 base coordinates
    assert tmap["r_dra"]["ra"] == 248.1675
    assert tmap["r_dra"]["dec"] == 66.7550
    assert tmap["barnard"]["ra"] == 269.45208
    assert tmap["barnard"]["dec"] == 4.69339


def test_target_proper_motion_kinematics():
    """Verifies that proper motion kinematics project coordinates to 2026 correctly."""
    # Barnard moves northward (+10362 mas/yr in Dec)
    ra_2026, dec_2026 = targets.calculate_target_position("barnard", "2026-01-01")
    assert dec_2026 > 4.75  # ~4.768° in 2026 vs 4.693° in 2000

    # R Dra has negligible proper motion
    ra_rdra, dec_rdra = targets.calculate_target_position("r_dra", "2026-01-01")
    assert ra_rdra == 248.1675
    assert dec_rdra == 66.7550


def test_find_target_by_coordinates():
    """Verifies automatic coordinate matching for celestial positions."""
    matched = targets.find_target_by_coords(248.1675, 66.7550, tolerance_deg=0.05)
    assert matched is not None
    assert matched.id == "r_dra"

    unmatched = targets.find_target_by_coords(12.3456, 78.9012, tolerance_deg=0.05)
    assert unmatched is None
