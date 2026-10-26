"""Actual registered REST routes with synthetic signed identities and real DB."""

import json


def headers(identity, **claims):
    return {"Authorization": "Bearer " + identity.token(**claims)}


def test_layer_response_preserves_json_shape_and_counts(client, db, identity):
    response = client.get("/api/redactionlayers/910", headers=headers(identity))
    assert response.status_code == 200
    layers = json.loads(response.get_data(as_text=True))
    assert isinstance(layers, list) and len(layers) > 0
    assert {"redactionlayerid", "name", "description", "sortorder", "count"} <= layers[
        0
    ].keys()
    assert all(layer["count"] == 0 for layer in layers)


def test_annotation_empty_request_preserves_json_shape(client, db, identity):
    response = client.get("/api/annotation/910/redline", headers=headers(identity))
    assert response.status_code == 200
    assert json.loads(response.get_data(as_text=True)) == {}


def test_registered_routes_reject_denied_group(client, identity):
    response = client.get(
        "/api/redactionlayers/910", headers=headers(identity, groups=[])
    )
    assert response.status_code == 401
