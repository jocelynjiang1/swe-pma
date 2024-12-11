from django import forms
from django.core.exceptions import ValidationError

from ..models.base import Message, Post, UploadedFile, UploadedImageFile, VisionBoard


class UploadImageFileForm(forms.ModelForm):
    class Meta:
        model = UploadedImageFile
        fields = ["file", "description"]
        widgets = {
            "file": forms.ClearableFileInput(attrs={"class": "form-control-file"}),
            "description": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Optional description",
                }
            ),
        }
        labels = {
            "file": "Upload File",
            "description": "Description",
        }
        help_texts = {
            "file": "Allowed file types: .jpg, .png. Max size: 5MB.",
        }

    def clean_file(self):
        uploaded_file = self.cleaned_data.get("file")
        if uploaded_file:
            if uploaded_file.size > 5 * 1024 * 1024:
                raise ValidationError("File size must be under 5MB.")

            valid_mime_types = ["image/jpeg", "image/png",]
            file_mime_type = uploaded_file.content_type
            if file_mime_type not in valid_mime_types:
                raise ValidationError(
                    "Unsupported file type. Allowed types: .jpg, .png, .pdf."
                )

        return uploaded_file


class UploadFileForm(forms.ModelForm):
    class Meta:
        model = UploadedFile
        # fields = ["file"]
        fields = ["file", "title", "description", "keywords"]
        widgets = {
            "file": forms.ClearableFileInput(
                attrs={
                    "accept": "text/plain, application/pdf"  # Allowed file extensions
                }
            ),
        }

        def clean_file(self):
            file = self.cleaned_data.get("file")

            # List of allowed MIME types
            allowed_types = ["text/plain", "application/pdf"]

            if file:
                # Check MIME type
                if file.content_type not in allowed_types:
                    raise ValidationError(
                        "Unsupported file type. Allowed types are: plain text or PDF."
                    )

            return file


class VisionBoardForm(forms.ModelForm):
    class Meta:
        model = VisionBoard
        fields = ["name", "description"]
        labels = {
            "name": "Vision board name",
            "description": "Description"
        }
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter a unique vision board name",
                }
            ),
            "description": forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Provide a description for the vision board (optional)",
            }
        ),
        }
        help_texts = {
            "name": "Choose a unique name for your vision board.",
            "description": "Optional: Describe the purpose or focus of the vision board."
        }

    def clean_name(self):
        name = self.cleaned_data.get("name")
        if VisionBoard.objects.filter(name__iexact=name).exists():
            raise ValidationError(
                "A vision board with this name already exists. Please choose a different name."
            )
        return name


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Type your message here...",
                    "class": "form-control",
                }
            ),
        }
        labels = {
            "content": "",
        }
        help_texts = {
            "content": "Enter your message to the group.",
        }

    def clean_content(self):
        content = self.cleaned_data.get("content")
        if len(content) > 1000:
            raise ValidationError("Message content cannot exceed 1000 characters.")
        return content


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["name", "caption", "tags"]

    name = forms.CharField(label="Title")
