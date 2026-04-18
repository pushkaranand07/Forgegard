"""
forms.py – Django form definitions for image and video detection.

Provides:
  ImageUploadForm – accepts an image file for manipulation detection.
  VideoUploadForm – accepts a video file for deepfake detection.
"""

from django import forms


class ImageUploadForm(forms.Form):
    """Form for uploading an image file to be analysed for manipulation."""

    upload_image_file = forms.FileField(
        label="Select image",
        required=True,
        widget=forms.FileInput(attrs={"accept": "image/*"}),
    )
    sequence_length = forms.IntegerField(
        label="Sequence length",
        required=False,
        initial=100,
        widget=forms.HiddenInput(),
    )


class VideoUploadForm(forms.Form):
    """Form for uploading a video file to be analysed for deepfakes."""

    upload_video_file = forms.FileField(
        label="Select video",
        required=True,
        widget=forms.FileInput(attrs={"accept": "video/*"}),
    )
    num_frames = forms.IntegerField(
        label="Number of frames to extract",
        required=False,
        initial=32,
        widget=forms.HiddenInput(),
    )
