"""Smoke tests for the Espresso web UI."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from web_app import app


def test_homepage_loads():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"Espresso" in response.data


def test_dataset_profile_api_loads():
    client = app.test_client()
    response = client.get("/api/datasets/test_panel.csv")
    assert response.status_code == 200
    data = response.get_json()
    assert data["rows"] > 0
    assert "unemployment" in data["column_names"]
