"""
tests.py – Basic smoke tests for the ForgeGuard deepfake detection application.

These tests verify that the API routes return the correct HTTP status codes.
(The legacy template pages they used to cover were removed; see tests/test_legacy_removed.py.)  They run without
a GPU or a trained model file, making them suitable for CI environments.
"""

from django.test import Client, TestCase
from django.urls import reverse


class SmokeTests(TestCase):
    """
    Lightweight tests that confirm the application's views are wired up
    correctly and respond to requests without crashing.
    """

    def setUp(self):
        self.client = Client()

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
