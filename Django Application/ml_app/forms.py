"""
forms.py – Django form definitions for the DeepGuard deepfake detection app.

Provides two forms:
  VideoUploadForm – accepts a video file and a frame sequence length.
  ImageUploadForm – accepts an image file for manipulation detection.
"""

from django import forms


class VideoUploadForm(forms.Form):
    """Form for uploading a video file to be analysed for deepfake content."""

    upload_video_file = forms.FileField(
        label="Select video",
        required=True,
        widget=forms.FileInput(attrs={"accept": "video/*"}),
    )
    sequence_length = forms.IntegerField(
        label="Sequence length",
        required=True,
        min_value=1,
        help_text=(
            "Number of frames the model will analyse. "
            "Higher values are more accurate but take longer. "
            "Must match the frame count your trained model supports."
        ),
    )


class ImageUploadForm(forms.Form):
    """Form for uploading an image file to be analysed for manipulation (deepfake)."""

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
