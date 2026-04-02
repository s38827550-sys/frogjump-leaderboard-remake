import uuid

def test_signup(client):
    username = f"pu_{uuid.uuid4().hex[:6]}"
    response = client.post("/auth/signup", json={
        "username": username,
        "password": "test1234"
    })
    assert response.status_code == 200
    assert response.json()["ok"] == True

def test_signup_duplicate(client):
    username = f"pd_{uuid.uuid4().hex[:6]}"
    client.post("/auth/signup", json={
        "username": username,
        "password": "test1234"
    })
    response = client.post("/auth/signup", json={
        "username": username,
        "password": "test1234"
    })
    assert response.status_code == 409

def test_login_success(client):
    username = f"pl_{uuid.uuid4().hex[:6]}"
    client.post("/auth/signup", json={
        "username": username,
        "password": "test1234"
    })
    response = client.post("/auth/login", json={
        "username": username,
        "password": "test1234"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_login_wrong_password(client):
    username = f"pw_{uuid.uuid4().hex[:6]}"
    client.post("/auth/signup", json={
        "username": username,
        "password": "test1234"
    })
    response = client.post("/auth/login", json={
        "username": username,
        "password": "wrongpass"
    })
    assert response.status_code == 401