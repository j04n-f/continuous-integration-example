import requests


def test_health() -> None:
    response = requests.get("http://ci-example.local/health")
    assert response.status_code == 200
    assert response.json() == {"status": "Ok"}
