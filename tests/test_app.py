import pytest
from app import app, jm
from journal.db import init_db, get_connection
import os

@pytest.fixture
def client():
    # Use testing mode
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False  # Disable CSRF for easier testing

    # The existing test suite (test_manager.py) already tests JournalManager DB logic thoroughly.
    # For test_app.py, we will just use the test client against the real DB for quick integration checks
    # since it creates its own users and verifies endpoints.
    # To keep the real db clean, we would typically mock it, but here we'll just test using unique usernames.

    with app.test_client() as client:
        yield client

def test_home_redirects_when_not_logged_in(client):
    response = client.get("/")
    # The home route returns base.html if not logged in (status 200)
    assert response.status_code == 200
    assert b"Login" in response.data

def test_register_and_login(client):
    unique_user = "test_web_user_1"
    
    # Register
    res = client.post("/register", data={
        "username": unique_user,
        "password": "password123",
        "email": "test_web1@example.com"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Account created" in res.data or b"already taken" in res.data
    
    # Login
    res = client.post("/login", data={
        "username": unique_user,
        "password": "password123"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Welcome back" in res.data or b"Today&#39;s Checklist" in res.data

def test_protected_routes(client):
    client.get("/logout") # ensure logged out
    
    res = client.get("/habits", follow_redirects=True)
    # login_required should redirect to login page
    assert b"Please log in" in res.data or b"Login" in res.data

def test_multi_user_isolation(client):
    u1 = "iso_user_1"
    u2 = "iso_user_2"
    
    client.post("/register", data={"username": u1, "password": "pw", "email": "iso1@ex.com"})
    client.post("/register", data={"username": u2, "password": "pw", "email": "iso2@ex.com"})
    
    # Login user 1
    client.post("/login", data={"username": u1, "password": "pw"})
    # Add habit
    client.post("/habits/add", data={"name": "U1_Habit"})
    
    res = client.get("/habits")
    assert b"U1_Habit" in res.data
    
    # Logout
    client.get("/logout")
    
    # Login user 2
    client.post("/login", data={"username": u2, "password": "pw"})
    res = client.get("/habits")
    assert b"U1_Habit" not in res.data # Should not see U1's habit


def test_stats_route(client):
    u = "stats_user"
    client.post("/register", data={"username": u, "password": "pw"})
    client.post("/login", data={"username": u, "password": "pw"})
    client.post("/habits/add", data={"name": "Running"})

    res = client.get("/stats")
    assert res.status_code == 200
    assert b"Habit Performance" in res.data
    assert b"Running" in res.data


def test_goals_route(client):
    u = "goals_user"
    client.post("/register", data={"username": u, "password": "pw"})
    client.post("/login", data={"username": u, "password": "pw"})

    # Get habit id or name
    client.post("/habits/add", data={"name": "Reading"})
    habits = jm.list_active_habits(jm.get_user_by_username(u).id)
    h_id = habits[0].id

    # Add goal
    res = client.post("/goals/add", data={"habit_id": h_id, "description": "Read 12 books"}, follow_redirects=True)
    assert res.status_code == 200
    assert b"Read 12 books" in res.data


