"""
URL configuration for projecta10 project.


The `urlpatterns` list routes URLs to views. For more information please see:
   https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
   1. Add an import:  from my_app import views
   2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
   1. Add an import:  from other_app.views import Home
   2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
   1. Import the include() function: from django.urls import include, path
   2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

from .views import about_view, admin_home_view, admin_request, leave_board  # group_chat,; join_group,
from .views import (  # signup_view,; file_detail_view; add_image_post,
    account_view,
    add_post,
    admin_requests_view,
    anonymous_login,
    answer_request,
    chat_room,
    create_vb_view,
    delete_file,
    delete_post,
    delete_vision_board,
    home_view,
    inbox_view,
    join_vision_board,
    login_view,
    upload_file,
    upload_image,
    upload_success,
    view_vision_board_files,
    vision_board_view,
    create_uploaded_file
)

urlpatterns = [
    # Custom URL to bypass the intermediate /accounts/google/login/ page
    path('accounts/', include('allauth.urls')),

    path("", login_view, name="index"),
    path("login/", login_view, name="login"),
    #  path("signup/", signup_view, name="signup"),
    path("home/", home_view, name="home"),
    path("staff-dashboard/", admin_home_view, name="admin_home"),
    path("admin/", admin.site.urls),
    path("admin-requests/", admin_requests_view, name="admin_requests"),
    path("accounts/", include("allauth.urls")),
    path("create-vb/", create_vb_view, name="create_vb"),
    path("anonymous-login/", anonymous_login, name="anonymous_login"),
    path("account/", account_view, name="account"),
    path("boards/join/<int:pk>/", join_vision_board, name="join_vision_board"),
    path("boards/<int:vision_board_id>/upload/", upload_file, name="upload_file"),
    path("upload_image/<int:vision_board_id>", upload_image, name="upload_image"),
    path(
        "boards/<int:vision_board_id>/upload/upload_success/",
        upload_success,
        name="upload_success",
    ),
    path("boards/<int:pk>/", vision_board_view, name="vision_board_view"),
    path("chat/<str:room_name>/", chat_room, name="chat_room"),
    path(
        "boards/<int:pk>/delete-post/<int:post_id>/",
        delete_post,
        name="delete_vision_board_post",
    ),
    path("add-post/<int:vision_board_id>/", add_post, name="add-post"),
    path(
        "delete-vision-board/<int:pk>", delete_vision_board, name="delete_vision_board"
    ),
    path(
        "boards/<int:vision_board_id>/files",
        view_vision_board_files,
        name="view_vision_board_files",
    ),
    path("inbox/<int:inbox_pk>/", inbox_view, name="inbox"),
    path("answer_request/<int:request_id>/", answer_request, name="answer_request"),
    path("delete_file/<int:pk>/", delete_file, name="delete_file"),
    path("boards/<int:pk>/leave/", leave_board, name="leave_board"),
    path("boards/<int:pk>/about/", about_view, name="about_view"),
    path('boards/<int:vision_board_id>/upload-blog/', create_uploaded_file, name='upload_blog_post'),
    path('admin-request/', admin_request, name="admin_request")
]
