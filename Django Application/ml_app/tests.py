"""
tests.py – Basic smoke tests for the DeepGuard deepfake detection application.

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
        response = self.client.get(reverse('ml_app:home'))
        self.assertEqual(response.status_code, 200)

    def test_image_upload_page_returns_200(self):
        """The photo upload page should load successfully."""
        response = self.client.get(reverse('ml_app:predict_image'))
        self.assertEqual(response.status_code, 200)

    def test_about_page_returns_200(self):
        """The About page should load and return HTTP 200."""
        response = self.client.get(reverse('ml_app:about'))
        self.assertEqual(response.status_code, 200)

    def test_image_calibration_status_endpoint_returns_200(self):
        """Calibration status endpoint should return HTTP 200."""
        response = self.client.get(reverse('ml_app:api_image_calibration_status'))
        self.assertEqual(response.status_code, 200)

    def test_calibration_endpoint_rejects_missing_validation_dir(self):
        """Calibration API must reject payloads without validation_dir."""
        response = self.client.post(
            reverse('ml_app:api_calibrate_image_threshold'),
            data='{}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_video_form_rejects_empty_submission(self):
        """
        Submitting the video upload form without a file should trigger
        a form validation error and re-render the home page (status 200),
        not redirect or raise a 500.
        """
        response = self.client.post(reverse('ml_app:home'), data={
            'sequence_length': 10,
            # No 'upload_video_file' provided
        })
        # Page re-renders with form errors; must not redirect (302) or crash (500)
        self.assertEqual(response.status_code, 200)
        # The form should report that the file field is required
        self.assertFormError(response, 'form', 'upload_video_file', 'This field is required.')

    def test_video_form_rejects_zero_sequence_length(self):
        """
        Submitting a sequence_length of 0 should trigger a min_value
        validation error from the form itself.
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        dummy_video = SimpleUploadedFile("test.mp4", b"fake_video_data", content_type="video/mp4")
        response = self.client.post(reverse('ml_app:home'), data={
            'upload_video_file': dummy_video,
            'sequence_length': 0,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response, 'form', 'sequence_length',
            'Ensure this value is greater than or equal to 1.'
        )
