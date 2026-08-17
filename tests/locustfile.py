"""Locust load test targeting the test engine.

Run with:  locust -f tests/locustfile.py --host http://localhost:5000

Simulates students logging in, starting a test, and hammering the timer +
answer-save endpoints — the hot path under real usage.
"""
from locust import HttpUser, task, between
import re


class StudentLoad(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        r = self.client.get("/auth/login")
        m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
        self.token = m.group(1) if m else ""
        self.client.post("/auth/login", data={
            "csrf_token": self.token,
            "email": "student@example.com",
            "password": "password",
        })

    @task(3)
    def timer_poll(self):
        # Simulates the HTMX 15s timer sync
        self.client.get("/api/attempt/1/timer?module_num=1")

    @task(1)
    def save_answer(self):
        self.client.post("/api/attempt/1/answer", data={
            "question_id": 1, "choice_id": 2, "time_delta_seconds": 5,
        }, headers={"X-CSRFToken": self.token})
