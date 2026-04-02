import uuid

def get_token(client, username: str, password: str = "test1234") -> str:
    client.post("/auth/signup", json={
        "username": username,
        "password": password
    })
    response = client.post("/auth/login", json={
        "username": username,
        "password": password
    })
    return response.json()["access_token"]

def test_post_score(client):
    token = get_token(client, f"test_{uuid.uuid4().hex[:6]}")
    response = client.post(
        "/scores",
        json={"score": 1000},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["ok"] == True

def test_post_score_unauthenticated(client):
    response = client.post("/scores", json={"score": 1000})
    assert response.status_code == 401

def test_score_only_updates_if_higher(client):
    token = get_token(client, f"test_{uuid.uuid4().hex[:6]}")
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/scores", json={"score": 500}, headers=headers)
    client.post("/scores", json={"score": 200}, headers=headers)
    response = client.post("/scores", json={"score": 200}, headers=headers)
    assert response.json()["best"] == 500

def test_get_leaderboard(client):
    response = client.get("/leaderboard")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data

def test_get_leaderboard_pagination(client):
    response = client.get("/leaderboard?page=1&size=5")
    assert response.status_code == 200
    assert response.json()["size"] == 5