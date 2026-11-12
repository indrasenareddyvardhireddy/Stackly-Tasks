from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()

REGISTER = {
    "first_name": "Ada",
    "last_name": "Lovelace",
    "email": "ada@example.com",
    "password": "StrongPass123",
    "confirm_password": "StrongPass123",
}


class AuthTests(APITestCase):
    def test_register_hashes_password_and_hides_it(self):
        res = self.client.post(reverse("register"), REGISTER)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("password", res.data)
        user = User.objects.get(email="ada@example.com")
        self.assertNotEqual(user.password, "StrongPass123")
        self.assertTrue(user.check_password("StrongPass123"))

    def test_register_password_mismatch(self):
        res = self.client.post(reverse("register"), {**REGISTER, "confirm_password": "nope12345"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("confirm_password", res.data)

    def test_register_short_password_and_duplicate_email(self):
        res = self.client.post(reverse("register"), {**REGISTER, "password": "short", "confirm_password": "short"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("password", res.data)
        self.client.post(reverse("register"), REGISTER)
        res = self.client.post(reverse("register"), REGISTER)
        self.assertEqual(res.status_code, 400)
        self.assertIn("email", res.data)

    def test_login_me_and_refresh(self):
        self.client.post(reverse("register"), REGISTER)
        res = self.client.post(reverse("login"), {"email": "ADA@example.com", "password": "StrongPass123"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)
        me = self.client.get(reverse("me"), HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["email"], "ada@example.com")
        self.assertNotIn("password", me.data)
        ref = self.client.post(reverse("token-refresh"), {"refresh": res.data["refresh"]})
        self.assertEqual(ref.status_code, 200)
        self.assertIn("access", ref.data)

    def test_me_requires_token(self):
        self.assertEqual(self.client.get(reverse("me")).status_code, 401)

    def test_change_password(self):
        self.client.post(reverse("register"), REGISTER)
        user = User.objects.get(email="ada@example.com")
        self.client.force_authenticate(user)
        bad = self.client.put(reverse("change-password"), {
            "old_password": "wrong", "new_password": "NewStrong456", "confirm_password": "NewStrong456"})
        self.assertEqual(bad.status_code, 400)
        self.assertIn("old_password", bad.data)
        ok = self.client.put(reverse("change-password"), {
            "old_password": "StrongPass123", "new_password": "NewStrong456", "confirm_password": "NewStrong456"})
        self.assertEqual(ok.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewStrong456"))

    def test_logout_blacklists_refresh_token(self):
        self.client.post(reverse("register"), REGISTER)
        tokens = self.client.post(reverse("login"), {"email": "ada@example.com", "password": "StrongPass123"}).data
        out = self.client.post(reverse("logout"), {"refresh": tokens["refresh"]})
        self.assertEqual(out.status_code, 204)
        again = self.client.post(reverse("token-refresh"), {"refresh": tokens["refresh"]})
        self.assertEqual(again.status_code, 401)
