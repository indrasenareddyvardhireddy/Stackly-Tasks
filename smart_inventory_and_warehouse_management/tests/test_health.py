def test_health(client):
    r=client.get("/health");assert r.status_code==200;assert r.json()["status"]=="ok"
def test_docs(client):
    assert client.get("/docs").status_code==200
