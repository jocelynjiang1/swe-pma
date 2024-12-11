import os
import re
from io import BytesIO

# for file detection
import magic
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.files.base import ContentFile
from django.db import models
from django.utils import timezone

# for thumbnails
from PIL import Image, UnidentifiedImageError
from taggit.managers import TaggableManager


class CustomUserManager(UserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        extra_fields.setdefault("user_type", "common user")
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    # updating effect of createsuperuser script - note that this will create a Django admin instead of a user with all privileges
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("user_type", "django_admin")
        user = self.create_user(email, password, **extra_fields)
        return user


class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ("common", "Common User"),
        ("site_admin", "Site Admin"),
        ("django_admin", "Django Admin"),
    )
    user_type = models.CharField(
        max_length=12, choices=USER_TYPE_CHOICES, default="common"
    )

    THEME_CHOICES = (
        ("light", "Light Mode"),
        ("dark", "Dark Mode"),
    )
    theme = models.CharField(
        max_length=10,
        choices=THEME_CHOICES,
        default="light",
        help_text="Select your preferred theme.",
    )
    date_joined = models.DateTimeField(default=timezone.now)

    objects = CustomUserManager()

    def __str__(self):
        return self.username


class AdminRequest(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="admin_requests",
        null=True,
        blank=True,
    )
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"AdminRequest by {self.user.username}"


class Keyword(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class UploadedFile(models.Model):
    TYPE_CHOICES = [
        ("image", "Image"),
        ("text", "Text"),
        ("pdf", "PDF"),
        ("other", "Other"),
    ]
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="files",
        blank=True,
        null=True,
    )
    file = models.FileField(upload_to="uploads/")
    timestamp = models.DateTimeField(default=timezone.now)
    keywords = models.ManyToManyField(Keyword, related_name="files", blank=True)
    title = models.CharField(max_length=255, blank=True)
    description = models.CharField(max_length=255, blank=True)
    file_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        blank=True,
    )
    vision_board = models.ForeignKey(
        "VisionBoard",
        on_delete=models.CASCADE,
        related_name="files",
        blank=True,
        null=True,
    )

    def __str__(self):
        return self.description or self.file.name

    def set_file_type(self):
        self.file_type = detect_file_type(self.file)

    def save(self, *args, **kwargs):
        if not self.file_type:
            self.set_file_type()
        super().save(*args, **kwargs)


def detect_file_type(file):
    mime = magic.Magic(mime=True)
    mime_type = mime.from_buffer(file.read(2048))
    file.seek(0)

    if mime_type.startswith("image/"):
        return "image"
    elif mime_type == "application/pdf":
        return "pdf"
    elif mime_type.startswith("text/"):
        return "text"
    else:
        return "other"


class UploadedImageFile(UploadedFile):
    thumbnail = models.ImageField(
        upload_to="uploads/thumbnails/", blank=True, null=True
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        print("creating thumbnail")
        if self.file and not self.thumbnail:
            try:
                self.create_thumbnail()
            except UnidentifiedImageError:
                print("File is not a recognizable image format.")
            except Exception as e:
                print(f"Error creating thumbnail: {e}")
                raise e

    def create_thumbnail(self):
        max_size = (500, 500)

        # Open the file as a stream
        self.file.open()
        try:
            with Image.open(self.file) as img:
                img.thumbnail(max_size, Image.LANCZOS)
                thumb_io = BytesIO()

                # Use the original file format for the thumbnail
                original_format = img.format
                if not original_format:
                    original_format = (
                        "JPEG"  # Default to JPEG if format is not detected
                    )

                img.save(thumb_io, format=original_format)

                # Generate the thumbnail filename
                thumbnail_extension = original_format.lower()
                thumbnail_filename = f"thumb_{os.path.splitext(os.path.basename(self.file.name))[0]}.{thumbnail_extension}"

                self.thumbnail.save(
                    thumbnail_filename, ContentFile(thumb_io.getvalue()), save=False
                )
                print("Thumbnail created")
        finally:
            self.file.close()

        super().save()

    def delete(self, *args, **kwargs):
        print(f"deleting file {self} and thumbnail {self.thumbnail}")
        # Delete the thumbnail file if it exists
        if self.thumbnail:
            self.thumbnail.delete(save=False)
        # Call the superclass delete method to delete the instance
        super().delete(*args, **kwargs)


class VisionBoard(models.Model):
    name = models.CharField(max_length=400)
    owner = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="owned_vision_boards"
    )
    members = models.ManyToManyField(CustomUser, related_name="vision_boards")
    created_at = models.DateTimeField(default=timezone.now)
    thumbnail = models.ManyToManyField(UploadedImageFile)
    websocket_name = models.CharField(max_length=255, editable=False, blank=True)
    description = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        self.websocket_name = re.sub(r"[^a-zA-Z0-9_-]", "-", self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Post(models.Model):
    name = models.CharField(max_length=255)  # title
    file = models.ForeignKey(
        UploadedFile,
        on_delete=models.CASCADE,
        related_name="posts",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(  # post creator
        CustomUser,
        on_delete=models.CASCADE,
        related_name="posts",
        null=True,
        blank=True,
    )
    caption = models.CharField(max_length=255)   # description
    tags = TaggableManager()  # keywords
    created_at = models.DateTimeField(default=timezone.now)  # timestamp
    vision_board = models.ForeignKey(
        VisionBoard,
        on_delete=models.CASCADE,
        related_name="vision_board",
        blank=True,
        null=True,
    )

    def __str__(self):
        return self.name


class Message(models.Model):
    vision_board = models.ForeignKey(
        VisionBoard,
        on_delete=models.CASCADE,
        related_name="messages",
        db_index=True,
        default=None,
    )
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="messages", db_index=True
    )
    content = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.user.username} - {self.vision_board.name}"


class Inbox(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="inbox",
        null=True,
        blank=True,
    )

    def __str__(self):
        return "inbox of: "


class Notification(models.Model):
    inbox = models.ForeignKey(
        Inbox,
        on_delete=models.CASCADE,
        related_name="notifications",
        blank=True,
        null=True,
    )
    creation_date = models.DateTimeField(default=timezone.now)
    subject = models.CharField(max_length=255)
    message = models.CharField(max_length=1000)
    sender = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="sent_notifications",
        null=True,
        blank=True,
    )
    recipient = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="received_notifications",
        null=True,
        blank=True,
    )

    def __str__(self):
        if self.subject != None:
            return self.subject
        else:
            return "Notification"


class JoinRequest(Notification):
    STATUS_CHOICES = [
        {"pending": "Pending"},
        {"accepted": "Accepted"},
        {"rejected": "Rejected"},
    ]
    status = models.CharField(max_length=8, default="pending")
    vision_board = models.ForeignKey(
        "VisionBoard",
        on_delete=models.CASCADE,
        related_name="join_requests",
        blank=True,
        null=True,
    )
