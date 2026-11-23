import pytest

from app.models.administrative_area import AdministrativeArea
from app.models.house import House

SAMPLE_POLYGON_GEOJSON = {
    "type": "Polygon",
    "coordinates": [
        [
            [77.1100, 11.0700],
            [77.1350, 11.0700],
            [77.1350, 11.0950],
            [77.1100, 11.0950],
            [77.1100, 11.0700],
        ]
    ],
}

INVALID_COORDS_GEOJSON = {
    "type": "Polygon",
    "coordinates": [
        [
            [277.1100, 11.0700],  # Longitude > 180
            [77.1350, 11.0700],
            [77.1350, 11.0950],
            [77.1100, 11.0950],
            [277.1100, 11.0700],
        ]
    ],
}


def get_auth_headers(client, username, password="password123"):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clean_areas_and_houses(db):
    db.query(House).delete()
    db.query(AdministrativeArea).delete()
    db.commit()


def test_create_administrative_area_success(client):
    headers = get_auth_headers(client, "deputy")
    payload = {
        "name": "Kaniyur Village",
        "type": "VILLAGE",
        "code": "VILL-638402",
        "boundary": SAMPLE_POLYGON_GEOJSON,
    }
    response = client.post("/api/v1/areas", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Kaniyur Village"
    assert data["code"] == "VILL-638402"
    assert data["type"] == "VILLAGE"
    assert "id" in data


def test_create_administrative_area_invalid_coordinates(client):
    headers = get_auth_headers(client, "deputy")
    payload = {
        "name": "Invalid Village",
        "type": "VILLAGE",
        "code": "VILL-INVALID",
        "boundary": INVALID_COORDS_GEOJSON,
    }
    response = client.post("/api/v1/areas", json=payload, headers=headers)
    assert response.status_code == 400
    assert "detail" in response.json()


def test_create_administrative_area_rbac_supervisor_forbidden(client):
    headers = get_auth_headers(client, "supervisor")
    payload = {
        "name": "Unauthorized Area",
        "type": "VILLAGE",
        "code": "VILL-UNAUTH",
        "boundary": SAMPLE_POLYGON_GEOJSON,
    }
    response = client.post("/api/v1/areas", json=payload, headers=headers)
    assert response.status_code == 403


def test_get_areas_list(client):
    deputy_headers = get_auth_headers(client, "deputy")
    payload = {
        "name": "Area One",
        "type": "VILLAGE",
        "code": "VILL-001",
        "boundary": SAMPLE_POLYGON_GEOJSON,
    }
    client.post("/api/v1/areas", json=payload, headers=deputy_headers)

    # Supervisor can read areas list
    sup_headers = get_auth_headers(client, "supervisor")
    response = client.get("/api/v1/areas", headers=sup_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) >= 1
    assert data["items"][0]["code"] == "VILL-001"
    assert "house_count" in data["items"][0]


def test_get_area_boundary_geojson(client):
    headers = get_auth_headers(client, "deputy")
    create_res = client.post(
        "/api/v1/areas",
        json={
            "name": "Boundary Test Village",
            "type": "VILLAGE",
            "code": "VILL-BOUND",
            "boundary": SAMPLE_POLYGON_GEOJSON,
        },
        headers=headers,
    )
    area_id = create_res.json()["id"]

    # Retrieve boundary GeoJSON
    response = client.get(f"/api/v1/areas/{area_id}/boundary", headers=headers)
    assert response.status_code == 200
    boundary_data = response.json()
    assert "boundary" in boundary_data
    assert boundary_data["boundary"]["type"] in ("Polygon", "MultiPolygon")
    assert boundary_data["code"] == "VILL-BOUND"


def test_create_and_get_houses_for_area(client):
    headers = get_auth_headers(client, "deputy")
    create_res = client.post(
        "/api/v1/areas",
        json={
            "name": "House Test Village",
            "type": "VILLAGE",
            "code": "VILL-HOUSE",
            "boundary": SAMPLE_POLYGON_GEOJSON,
        },
        headers=headers,
    )
    area_id = create_res.json()["id"]

    # Add a house to the area
    house_payload = {
        "building_reference": "BLD-101",
        "house_number": "1/101",
        "latitude": 11.0850,
        "longitude": 77.1250,
    }
    create_house_res = client.post(
        f"/api/v1/areas/{area_id}/houses",
        json=house_payload,
        headers=headers,
    )
    assert create_house_res.status_code == 201
    house_data = create_house_res.json()
    assert house_data["building_reference"] == "BLD-101"
    assert house_data["house_number"] == "1/101"
    assert house_data["latitude"] == 11.0850
    assert house_data["longitude"] == 77.1250

    # Get houses list
    list_houses_res = client.get(f"/api/v1/areas/{area_id}/houses", headers=headers)
    assert list_houses_res.status_code == 200
    houses_data = list_houses_res.json()
    assert "items" in houses_data
    assert len(houses_data["items"]) == 1
    assert houses_data["items"][0]["house_number"] == "1/101"


def test_create_house_invalid_coordinates(client):
    headers = get_auth_headers(client, "deputy")
    create_res = client.post(
        "/api/v1/areas",
        json={
            "name": "House Invalid Village",
            "type": "VILLAGE",
            "code": "VILL-HOUSE-INV",
            "boundary": SAMPLE_POLYGON_GEOJSON,
        },
        headers=headers,
    )
    area_id = create_res.json()["id"]

    house_payload = {
        "building_reference": "BLD-INV",
        "house_number": "999",
        "latitude": 95.0,  # Invalid latitude > 90
        "longitude": 77.1250,
    }
    res = client.post(
        f"/api/v1/areas/{area_id}/houses",
        json=house_payload,
        headers=headers,
    )
    assert res.status_code in (400, 422)


def test_get_building_estimation(client):
    headers = get_auth_headers(client, "deputy")
    create_res = client.post(
        "/api/v1/areas",
        json={
            "name": "Estimation Village",
            "type": "VILLAGE",
            "code": "VILL-EST-01",
            "boundary": SAMPLE_POLYGON_GEOJSON,
        },
        headers=headers,
    )
    area_id = create_res.json()["id"]

    # Initial estimation with 0 buildings
    est_res = client.get(f"/api/v1/areas/{area_id}/estimation", headers=headers)
    assert est_res.status_code == 200
    est_data = est_res.json()
    assert est_data["total_buildings"] == 0
    assert est_data["area_code"] == "VILL-EST-01"

    # Add a satellite detected building
    client.post(
        f"/api/v1/areas/{area_id}/houses",
        json={
            "building_reference": "BLD-S1",
            "house_number": "1/1",
            "latitude": 11.0800,
            "longitude": 77.1200,
            "source_type": "SATELLITE_DETECTED",
            "detection_confidence": 0.89,
            "imagery_source": "esri_world_imagery",
        },
        headers=headers,
    )

    # Re-check estimation
    est_res2 = client.get(f"/api/v1/areas/{area_id}/estimation", headers=headers)
    assert est_res2.status_code == 200
    est_data2 = est_res2.json()
    assert est_data2["total_buildings"] == 1
    assert est_data2["source_type"] == "SATELLITE_DETECTED"
    assert est_data2["quality_label"] == "Satellite-derived estimate"
    assert est_data2["average_confidence"] == 0.89
    assert len(est_data2["density_clusters"]) == 1


def test_detect_buildings_deputy_success(client):
    headers = get_auth_headers(client, "deputy")
    create_res = client.post(
        "/api/v1/areas",
        json={
            "name": "Detection Run Village",
            "type": "VILLAGE",
            "code": "VILL-DETECT-01",
            "boundary": SAMPLE_POLYGON_GEOJSON,
        },
        headers=headers,
    )
    area_id = create_res.json()["id"]

    # Trigger detection with fallback allowed for test environment
    detect_res = client.post(
        f"/api/v1/areas/{area_id}/detect-buildings?allow_development_fallback=true",
        headers=headers,
    )
    assert detect_res.status_code == 200
    detect_data = detect_res.json()
    assert detect_data["total_buildings"] > 0
    assert detect_data["source_type"] in ("SATELLITE_DETECTED", "DEVELOPMENT_DATA")
    assert len(detect_data["density_clusters"]) > 0

    # Verify houses list has detected records
    houses_res = client.get(f"/api/v1/areas/{area_id}/houses", headers=headers)
    assert houses_res.status_code == 200
    houses_data = houses_res.json()
    assert houses_data["total"] == detect_data["total_buildings"]
    first_house = houses_data["items"][0]
    assert first_house["footprint"] is not None


def test_detect_buildings_rbac_supervisor_forbidden(client):
    deputy_headers = get_auth_headers(client, "deputy")
    create_res = client.post(
        "/api/v1/areas",
        json={
            "name": "RBAC Village",
            "type": "VILLAGE",
            "code": "VILL-RBAC-01",
            "boundary": SAMPLE_POLYGON_GEOJSON,
        },
        headers=deputy_headers,
    )
    area_id = create_res.json()["id"]

    # Supervisor is forbidden from triggering building detection
    sup_headers = get_auth_headers(client, "supervisor")
    detect_res = client.post(
        f"/api/v1/areas/{area_id}/detect-buildings",
        headers=sup_headers,
    )
    assert detect_res.status_code == 403


def test_get_houses_source_type_filter(client):
    headers = get_auth_headers(client, "deputy")
    create_res = client.post(
        "/api/v1/areas",
        json={
            "name": "Filter Village",
            "type": "VILLAGE",
            "code": "VILL-FILTER-01",
            "boundary": SAMPLE_POLYGON_GEOJSON,
        },
        headers=headers,
    )
    area_id = create_res.json()["id"]

    # Add 1 satellite detected and 1 development house
    client.post(
        f"/api/v1/areas/{area_id}/houses",
        json={
            "building_reference": "BLD-SAT-1",
            "house_number": "1/1",
            "latitude": 11.0800,
            "longitude": 77.1200,
            "source_type": "SATELLITE_DETECTED",
        },
        headers=headers,
    )
    client.post(
        f"/api/v1/areas/{area_id}/houses",
        json={
            "building_reference": "BLD-DEV-1",
            "house_number": "1/2",
            "latitude": 11.0810,
            "longitude": 77.1210,
            "source_type": "DEVELOPMENT_DATA",
        },
        headers=headers,
    )

    # Query with filter SATELLITE_DETECTED
    sat_res = client.get(
        f"/api/v1/areas/{area_id}/houses?source_type=SATELLITE_DETECTED",
        headers=headers,
    )
    assert sat_res.status_code == 200
    assert sat_res.json()["total"] == 1
    assert sat_res.json()["items"][0]["source_type"] == "SATELLITE_DETECTED"

    # Query with filter DEVELOPMENT_DATA
    dev_res = client.get(
        f"/api/v1/areas/{area_id}/houses?source_type=DEVELOPMENT_DATA",
        headers=headers,
    )
    assert dev_res.status_code == 200
    assert dev_res.json()["total"] == 1
    assert dev_res.json()["items"][0]["source_type"] == "DEVELOPMENT_DATA"
