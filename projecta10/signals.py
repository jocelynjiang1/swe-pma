from allauth.account.signals import user_signed_up
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

User = get_user_model()

# for thumbnails
from django.db.models.signals import post_delete

from .models.base import Inbox, Post, UploadedFile, UploadedImageFile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def set_default_preferences(sender, instance, created, **kwargs):
    if created:
        # Set default theme preference
        if not instance.theme:
            instance.theme = "light"
            instance.save()


@receiver(user_signed_up)
def populate_user_preferences(request, user, **kwargs):
    # Ensure preferences are set upon OAuth signup
    if not user.theme:
        user.theme = "light"  # Default theme
        user.save()


@receiver(post_delete, sender=UploadedImageFile)
def delete_thumbnail_on_model_delete(sender, instance, **kwargs):
    # Ensure the thumbnail file is deleted
    if instance.thumbnail:
        instance.thumbnail.delete(save=False)


@receiver(post_delete, sender=Post)
def delete_uploaded_file(sender, instance, **kwargs):
    if instance.file:
        print(f"Deleting UploadedFile: {instance.file}")
        instance.file.delete()


# Create the inbox when a new user is created
@receiver(post_save, sender=User)
def create_inbox_for_user(sender, instance, created, **kwargs):
    if created:
        Inbox.objects.create(user=instance)
