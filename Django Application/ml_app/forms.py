"""
forms.py – Django form definitions for the DeepGuard deepfake detection app.

Provides two forms:
  VideoUploadForm – accepts a video file and a frame sequence length.
  ImageUploadForm – accepts a photo and a frame sequence length for the
                    replicated-frame inference pipeline.
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
    """Form for uploading a single photo to be analysed for deepfake content."""

    upload_image_file = forms.FileField(
        label="Select photo",
        required=True,
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/jpg,image/png,image/webp"}),
    )
    sequence_length = forms.IntegerField(
        label="Sequence length",
        required=True,
        initial=100,
        min_value=1,
        help_text=(
            "The uploaded photo is replicated this many times to form a "
            "pseudo-video sequence that the model can process. "
            "Set this to match your trained model (typically 100)."
        ),
    )
