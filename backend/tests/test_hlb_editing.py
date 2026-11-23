import uuid as _uuid

import pytest

from app.gis.spatial import (
    validate_and_convert_geojson_polygon,
    validate_and_convert_point,
)
from app.models.administrative_area import AdministrativeArea, AreaType
from app.models.audit_log import AuditLog
from app.models.hlb import HlbHouse, HlbStatus, HouselistingBlock
from app.models.house import BuildingSourceType, House
from app.models.layout import Layout, LayoutStatus, LayoutVersion, LayoutVersionStatus

SAMPLE_VILLAGE_BOUNDARY = {
    "type": "Polygon",
    "coordinates": [
        [
            [77.1100, 11.0700],
            [77.1400, 11.0700],
            [77.1400, 11.1000],
            [77.1100, 11.1000],
            [77.1100, 11.0700],
        ]
    ],
}


def get_auth_headers(client, username="deputy", password="password123"):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clean_tables(db):
    db.query(AuditLog).delete()
    db.query(HlbHouse).delete()
    db.query(HouselistingBlock).delete()
    db.query(LayoutVersion).delete()
    db.query(Layout).delete()
    db.query(House).delete()
    db.query(AdministrativeArea).delete()
    db.commit()


@pytest.fixture
def sample_layout_with_hlbs(db):
    # Create area
    area = AdministrativeArea(
        id=_uuid.uuid4(),
        name="Arasur Village",
        type=AreaType.VILLAGE,
        code="VILL-638401",
        boundary=validate_and_convert_geojson_polygon(SAMPLE_VILLAGE_BOUNDARY),
    )
    db.add(area)
    db.flush()

    # Create 30 buildings
    houses = []
    for i in range(30):
        lng = 77.115 + (i % 6) * 0.003
        lat = 11.075 + (i // 6) * 0.004
        pt_wkb = validate_and_convert_point(lat, lng)
        h = House(
            id=_uuid.uuid4(),
            area_id=area.id,
            building_reference=f"BLD-{i:03d}",
            latitude=lat,
            longitude=lng,
            location=pt_wkb,
            source_type=BuildingSourceType.SATELLITE_DETECTED,
        )
        db.add(h)
        houses.append(h)
    db.flush()

    # Create layout
    layout = Layout(
        id=_uuid.uuid4(),
        area_id=area.id,
        name="Arasur Master Layout",
        target_hlb_building_count=15,
        actual_building_count=30,
        expected_hlb_count=2,
        boundary=area.boundary,
        status=LayoutStatus.GENERATED,
    )
    db.add(layout)
    db.flush()

    # Create candidate version
    version = LayoutVersion(
        id=_uuid.uuid4(),
        layout_id=layout.id,
        version_number=1,
        status=LayoutVersionStatus.CANDIDATE,
        target_buildings_per_hlb=15,
        total_buildings=30,
        hlb_count=2,
    )
    db.add(version)
    db.flush()
    layout.active_version_id = version.id

    # Create 2 HLBs (15 buildings each)
    hlb1_geom = {
        "type": "Polygon",
        "coordinates": [
            [
                [77.1100, 11.0700],
                [77.1250, 11.0700],
                [77.1250, 11.1000],
                [77.1100, 11.1000],
                [77.1100, 11.0700],
            ]
        ],
    }
    hlb2_geom = {
        "type": "Polygon",
        "coordinates": [
            [
                [77.1250, 11.0700],
                [77.1400, 11.0700],
                [77.1400, 11.1000],
                [77.1250, 11.1000],
                [77.1250, 11.0700],
            ]
        ],
    }

    hlb1 = HouselistingBlock(
        id=_uuid.uuid4(),
        layout_id=layout.id,
        version_id=version.id,
        block_code="HLB-001",
        name="Block 1",
        target_building_count=15,
        actual_building_count=15,
        boundary=validate_and_convert_geojson_polygon(hlb1_geom),
        status=HlbStatus.GENERATED,
    )
    hlb2 = HouselistingBlock(
        id=_uuid.uuid4(),
        layout_id=layout.id,
        version_id=version.id,
        block_code="HLB-002",
        name="Block 2",
        target_building_count=15,
        actual_building_count=15,
        boundary=validate_and_convert_geojson_polygon(hlb2_geom),
        status=HlbStatus.GENERATED,
    )
    db.add(hlb1)
    db.add(hlb2)
    db.flush()

    for h in houses[:15]:
        db.add(HlbHouse(hlb_id=hlb1.id, house_id=h.id, status="ASSIGNED"))
    for h in houses[15:]:
        db.add(HlbHouse(hlb_id=hlb2.id, house_id=h.id, status="ASSIGNED"))

    db.commit()

    return {
        "area": area,
        "layout": layout,
        "version": version,
        "hlb1": hlb1,
        "hlb2": hlb2,
        "houses": houses,
    }


# ----------------------------------------------------------------------
# Tests — Boundary Editing
# ----------------------------------------------------------------------


def test_edit_hlb_boundary_success(client, sample_layout_with_hlbs, db):
    headers = get_auth_headers(client, "deputy")
    hlb1 = sample_layout_with_hlbs["hlb1"]

    new_boundary = {
        "type": "Polygon",
        "coordinates": [
            [
                [77.1100, 11.0700],
                [77.1300, 11.0700],
                [77.1300, 11.1000],
                [77.1100, 11.1000],
                [77.1100, 11.0700],
            ]
        ],
    }

    response = client.patch(
        f"/api/v1/hlbs/{hlb1.id}/boundary",
        headers=headers,
        json={"boundary": new_boundary},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(hlb1.id)
    assert data["block_code"] == "HLB-001"
    assert "boundary" in data
    assert data["actual_building_count"] > 0

    # Verify AuditLog created
    audit = db.query(AuditLog).filter(AuditLog.action == "HLB_EDITED").first()
    assert audit is not None
    assert str(audit.entity_id) == str(hlb1.id)


def test_edit_hlb_boundary_invalid_geometry(client, sample_layout_with_hlbs):
    headers = get_auth_headers(client, "deputy")
    hlb1 = sample_layout_with_hlbs["hlb1"]

    # Invalid geometry (not enough coordinates)
    bad_geom = {
        "type": "Polygon",
        "coordinates": [[[77.11, 11.07], [77.12, 11.08]]],
    }

    response = client.patch(
        f"/api/v1/hlbs/{hlb1.id}/boundary",
        headers=headers,
        json={"boundary": bad_geom},
    )
    assert response.status_code == 422


def test_edit_hlb_boundary_outside_area_rejected(client, sample_layout_with_hlbs):
    headers = get_auth_headers(client, "deputy")
    hlb1 = sample_layout_with_hlbs["hlb1"]

    # Polygon far outside layout boundary
    outside_geom = {
        "type": "Polygon",
        "coordinates": [
            [
                [78.0000, 12.0000],
                [78.0500, 12.0000],
                [78.0500, 12.0500],
                [78.0000, 12.0500],
                [78.0000, 12.0000],
            ]
        ],
    }

    response = client.patch(
        f"/api/v1/hlbs/{hlb1.id}/boundary",
        headers=headers,
        json={"boundary": outside_geom},
    )
    assert response.status_code == 400
    assert "outside" in response.json()["detail"].lower()


# ----------------------------------------------------------------------
# Tests — Split HLB
# ----------------------------------------------------------------------


def test_split_hlb_success(client, sample_layout_with_hlbs, db):
    headers = get_auth_headers(client, "deputy")
    hlb1 = sample_layout_with_hlbs["hlb1"]

    response = client.post(
        f"/api/v1/hlbs/{hlb1.id}/split",
        headers=headers,
        json={"split_ratio": 0.5},
    )
    assert response.status_code == 200
    data = response.json()
    assert "split_hlb_a" in data
    assert "split_hlb_b" in data
    assert data["split_hlb_a"]["actual_building_count"] > 0
    assert data["split_hlb_b"]["actual_building_count"] > 0
    assert (
        data["split_hlb_a"]["actual_building_count"]
        + data["split_hlb_b"]["actual_building_count"]
        == 15
    )

    # Check AuditLog
    audit = db.query(AuditLog).filter(AuditLog.action == "HLB_SPLIT").first()
    assert audit is not None


# ----------------------------------------------------------------------
# Tests — Merge HLBs
# ----------------------------------------------------------------------


def test_merge_hlbs_success(client, sample_layout_with_hlbs, db):
    headers = get_auth_headers(client, "deputy")
    hlb1 = sample_layout_with_hlbs["hlb1"]
    hlb2 = sample_layout_with_hlbs["hlb2"]

    response = client.post(
        "/api/v1/hlbs/merge",
        headers=headers,
        json={"hlb_id_1": str(hlb1.id), "hlb_id_2": str(hlb2.id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert "merged_hlb" in data
    assert data["merged_hlb"]["actual_building_count"] == 30

    # Ensure hlb2 was removed from database
    deleted_hlb = (
        db.query(HouselistingBlock).filter(HouselistingBlock.id == hlb2.id).first()
    )
    assert deleted_hlb is None

    # Check AuditLog
    audit = db.query(AuditLog).filter(AuditLog.action == "HLB_MERGED").first()
    assert audit is not None


def test_merge_same_hlb_rejected(client, sample_layout_with_hlbs):
    headers = get_auth_headers(client, "deputy")
    hlb1 = sample_layout_with_hlbs["hlb1"]

    response = client.post(
        "/api/v1/hlbs/merge",
        headers=headers,
        json={"hlb_id_1": str(hlb1.id), "hlb_id_2": str(hlb1.id)},
    )
    assert response.status_code == 400


# ----------------------------------------------------------------------
# Tests — Layout Validation & Approval
# ----------------------------------------------------------------------


def test_validate_layout_success(client, sample_layout_with_hlbs):
    headers = get_auth_headers(client, "deputy")
    layout = sample_layout_with_hlbs["layout"]

    response = client.post(
        f"/api/v1/layouts/{layout.id}/validate",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is True
    assert data["can_approve"] is True
    assert data["status"] == "READY_FOR_APPROVAL"
    assert data["total_buildings"] == 30
    assert data["assigned_buildings"] == 30
    assert data["unassigned_buildings"] == 0
    assert data["duplicate_assignments"] == 0
    assert len(data["checklist"]) >= 4


def test_approve_layout_success(client, sample_layout_with_hlbs, db):
    headers = get_auth_headers(client, "deputy")
    layout = sample_layout_with_hlbs["layout"]

    response = client.post(
        f"/api/v1/layouts/{layout.id}/approve",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == LayoutStatus.APPROVED.value
    assert data["version_status"] == LayoutVersionStatus.APPROVED.value

    # Verify database state
    db_layout = db.query(Layout).filter(Layout.id == layout.id).first()
    assert db_layout.status == LayoutStatus.APPROVED
    assert db_layout.approved_at is not None

    db_version = (
        db.query(LayoutVersion)
        .filter(LayoutVersion.id == layout.active_version_id)
        .first()
    )
    assert db_version.status == LayoutVersionStatus.APPROVED

    # Check AuditLog
    audit = db.query(AuditLog).filter(AuditLog.action == "LAYOUT_APPROVED").first()
    assert audit is not None


def test_approve_layout_unauthorized_role(client, sample_layout_with_hlbs):
    # Supervisor should get 403 Forbidden
    headers = get_auth_headers(client, "supervisor")
    layout = sample_layout_with_hlbs["layout"]

    response = client.post(
        f"/api/v1/layouts/{layout.id}/approve",
        headers=headers,
    )
    assert response.status_code == 403


def test_modify_approved_layout_rejected(client, sample_layout_with_hlbs):
    headers = get_auth_headers(client, "deputy")
    layout = sample_layout_with_hlbs["layout"]
    hlb1 = sample_layout_with_hlbs["hlb1"]

    # Approve layout first
    app_res = client.post(
        f"/api/v1/layouts/{layout.id}/approve",
        headers=headers,
    )
    assert app_res.status_code == 200

    # Attempt to edit boundary on approved layout
    new_boundary = {
        "type": "Polygon",
        "coordinates": [
            [
                [77.1100, 11.0700],
                [77.1300, 11.0700],
                [77.1300, 11.1000],
                [77.1100, 11.1000],
                [77.1100, 11.0700],
            ]
        ],
    }
    edit_res = client.patch(
        f"/api/v1/hlbs/{hlb1.id}/boundary",
        headers=headers,
        json={"boundary": new_boundary},
    )
    assert edit_res.status_code == 400
    assert "approved" in edit_res.json()["detail"].lower()


def test_split_hlb_preview_options(client, sample_layout_with_hlbs):
    headers = get_auth_headers(client, "deputy")
    hlb1 = sample_layout_with_hlbs["hlb1"]

    # 1. Auto Balanced Preview
    prev_auto = client.post(
        f"/api/v1/hlbs/{hlb1.id}/split/preview",
        headers=headers,
        json={"split_method": "AUTO_BALANCED", "split_ratio": 0.5},
    )
    assert prev_auto.status_code == 200
    d_auto = prev_auto.json()
    assert d_auto["is_valid"] is True
    assert d_auto["total_buildings"] == 15
    assert d_auto["part_a_buildings"] + d_auto["part_b_buildings"] == 15
    assert d_auto["part_a_code"] == "HLB-001A"
    assert d_auto["part_b_code"] == "HLB-001B"

    # 2. Target-Based Preview
    prev_target = client.post(
        f"/api/v1/hlbs/{hlb1.id}/split/preview",
        headers=headers,
        json={"split_method": "TARGET_BASED", "target_building_count": 8},
    )
    assert prev_target.status_code == 200
    d_target = prev_target.json()
    assert d_target["is_valid"] is True
    assert d_target["part_a_buildings"] == 8
    assert d_target["part_b_buildings"] == 7

    # 3. Draw Split Line Preview
    prev_line = client.post(
        f"/api/v1/hlbs/{hlb1.id}/split/preview",
        headers=headers,
        json={
            "split_method": "DRAW_SPLIT_LINE",
            "split_line_coordinates": [
                [77.110, 11.080],
                [77.130, 11.080],
            ],
        },
    )
    assert prev_line.status_code == 200
    d_line = prev_line.json()
    assert d_line["is_valid"] is True
    assert d_line["part_a_buildings"] + d_line["part_b_buildings"] == 15


def test_merge_hlb_preview_and_adjacency(client, sample_layout_with_hlbs):
    headers = get_auth_headers(client, "deputy")
    hlb1 = sample_layout_with_hlbs["hlb1"]
    hlb2 = sample_layout_with_hlbs["hlb2"]

    # Preview merge between adjacent HLB 1 and 2
    prev_res = client.post(
        "/api/v1/hlbs/merge/preview",
        headers=headers,
        json={"hlb_id_1": str(hlb1.id), "hlb_id_2": str(hlb2.id)},
    )
    assert prev_res.status_code == 200
    p_data = prev_res.json()
    assert p_data["is_adjacent"] is True
    assert p_data["is_valid"] is True
    assert p_data["combined_buildings"] == 30
    assert "HLB-001" in p_data["suggested_name"]
