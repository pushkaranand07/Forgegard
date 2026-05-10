"""
tests.py – Basic smoke tests for the ForgeGuard deepfake detection application.

These tests verify that all primary routes return the correct HTTP status
codes and that basic form validation works as expected.  They run without
a GPU or a trained model file, making them suitable for CI environments.
"""

from django.test import TestCase, Client
from django.urls import reverse


class SmokeTests(TestCase):
    """
    Lightweight tests that confirm the application's views are wired up
    correctly and respond to requests without crashing.
    """

    def setUp(self):
        self.client = Client()

    def test_home_page_returns_200(self):
        """The video upload home page should load successfully."""
        response = self.client.get(reverse('api:home'))
        self.assertEqual(response.status_code, 200)

    def test_image_upload_page_returns_200(self):
        """The photo upload page should load successfully."""
        response = self.client.get(reverse('api:predict_image'))
        self.assertEqual(response.status_code, 200)

    def test_about_page_returns_200(self):
        """The About page should load and return HTTP 200."""
        response = self.client.get(reverse('api:about'))
        self.assertEqual(response.status_code, 200)

    def test_api_detect_rejects_get_request(self):
        """The unified detect API endpoint must reject GET requests (POST only)."""
        response = self.client.get(reverse('api:api_detect'))
        self.assertEqual(response.status_code, 405)  # Method Not Allowed

    def test_api_detect_rejects_empty_post(self):
        """The unified detect endpoint must return 400 when no file is provided."""
        response = self.client.post(reverse('api:api_detect'), data={})
        self.assertEqual(response.status_code, 400)

    def test_api_detect_image_rejects_get_request(self):
        """The image detect endpoint must reject GET requests."""
        response = self.client.get(reverse('api:api_detect_image'))
        self.assertEqual(response.status_code, 405)

    def test_api_detect_video_rejects_get_request(self):
        """The video detect endpoint must reject GET requests."""
        response = self.client.get(reverse('api:api_detect_video'))
        self.assertEqual(response.status_code, 405)
