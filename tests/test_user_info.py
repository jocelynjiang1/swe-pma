from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from projecta10.models import AdminRequest

User = get_user_model()


class LoginTest(TestCase):
    def test_user_login(self):
        user = User.objects.create_user(
            username="regular", password="samplepwd", email="filler@gmail.com"
        )
        login = self.client.login(username="regular", password="samplepwd")
        self.assertTrue(login)


class AdminRequestTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            username="regular", password="samplepwd", email="filler@gmail.com"
        )
        mock_request = AdminRequest.objects.create(user=user)

    def test_create_admin_request(self):  # AdminRequest instance created
        # print(AdminRequest.objects.first().username)
        self.assertEqual(AdminRequest.objects.count(), 1)
        self.assertEqual(AdminRequest.objects.first().user.username, "regular")

    def test_user_request_shown(self):
        response = self.client.get(reverse("admin_requests"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("regular", data.get("usernames", []))
