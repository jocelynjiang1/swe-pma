from django.apps import apps
from django.contrib import admin

from .forms.accounts import CustomUserChangeForm, CustomUserCreationForm
from .models.base import (
    AdminRequest,
    CustomUser,
    Message,
    Post,
    UploadedFile,
    UploadedImageFile,
    VisionBoard,
)


@admin.register(AdminRequest)
class AdminRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "is_approved")
    search_fields = ("user__username",)
    list_filter = ("is_approved",)


@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ("description", "file", "timestamp")
    search_fields = ("description",)


@admin.register(UploadedImageFile)
class UploadedImageFileAdmin(admin.ModelAdmin):
    list_display = (
        "description",
        "file",
        "thumbnail",
        "timestamp",
    )
    search_fields = ("description",)


@admin.register(VisionBoard)
class VisionBoardAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "created_at")
    search_fields = (
        "name",
        "owner__username",
    )


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("name", "file", "user", "created_at")
    search_fields = ("name", "user__username")
    list_filter = ("tags",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "timestamp",
    )
    search_fields = ("user__username",)
    list_filter = ("timestamp",)


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = ["email", "username", "user_type"]


app_models = apps.get_models()
registered_models = {
    AdminRequest,
    CustomUser,
    Message,
    Post,
    UploadedFile,
    UploadedImageFile,
    VisionBoard,
}

for model in app_models:
    if model not in registered_models:
        try:
            admin.site.register(model)
        except admin.sites.AlreadyRegistered:
            pass
