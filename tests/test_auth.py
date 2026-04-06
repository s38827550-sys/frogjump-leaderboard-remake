import uuid

def make_user():
    username = f"test_{uuid.uuid4().hex[:6]}"
    nickname = f"nick_{uuid.uuid4().hex[:6]}"
    return username, nickname


def test_signup(client):
    username, nickname = make_user()

    response = client.post("/auth/signup", json={
        "username": username,
        "password": "test1234",
        "nickname": nickname
    })

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_signup_duplicate(client):
    username, nickname = make_user()

    client.post("/auth/signup", json={
        "username": username,
        "password": "test1234",
        "nickname": nickname
    })

    response = client.post("/auth/signup", json={
        "username": username,
        "password": "test1234",
        "nickname": nickname
    })

    assert response.status_code == 409


def test_login_success(client):
    username, nickname = make_user()

    client.post("/auth/signup", json={
        "username": username,
        "password": "test1234",
        "nickname": nickname
    })

    response = client.post("/auth/login", json={
        "username": username,
        "password": "test1234"
    })

    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password(client):
    username, nickname = make_user()

    client.post("/auth/signup", json={
        "username": username,
        "password": "test1234",
        "nickname": nickname
    })

    response = client.post("/auth/login", json={
        "username": username,
        "password": "wrongpass"
    })

    assert response.status_code == 401