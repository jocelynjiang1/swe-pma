import json
import logging
from contextvars import Context
from io import BytesIO
from itertools import chain

import boto3
import requests
from allauth.account import app_settings
from allauth.account import app_settings as allauth_settings
from allauth.account.forms import AddEmailForm, SignupForm
from allauth.account.models import EmailAddress
from allauth.account.utils import complete_signup
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.files.base import ContentFile
from django.http import HttpResponseForbidden, HttpResponseNotFound, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from PIL import Image

from .forms.base import (  # CreateGroupForm,
    MessageForm,
    PostForm,
    UploadedFile,
    UploadedImageFile,
    UploadFileForm,
    UploadImageFileForm,
    VisionBoardForm,
)
from .models.base import (
    AdminRequest,
    Inbox,
    JoinRequest,
    Keyword,
    Message,
    Post,
    UploadedImageFile,
    VisionBoard,
)

logger = logging.getLogger(__name__)


boto3.set_stream_logger("boto3.resources")


def is_site_admin(user):
    return user.is_authenticated and user.user_type == "site_admin"


def login_view(request):
    if request.method == "POST":
        username = request.POST["login"]
        password = request.POST["password"]
        request.session["username"] = username
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if user.is_superuser:
                # print("user is superuser")
                return redirect("admin:index")
            elif user.is_staff:
                # print("is staff")
                return redirect("admin_home")
            else:
                # print("is not staff")
                return redirect("home")
        else:
            messages.error(request, "Invalid username or password")
            return redirect("login")  # Redirect to login page with error message

    # For non-POST requests, return the login page
    return render(request, "account/login.html")


def signup_view(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save(request)
            if request.POST.get("user_type_request") == "site_admin":
                print("user requested to be site admin")
                AdminRequest.objects.create(user=user)

            email_verification = allauth_settings.EMAIL_VERIFICATION
            return complete_signup(
                request,
                user,
                email_verification=email_verification,
                success_url=reverse("home"),
            )
        else:
            # Form is not valid; re-render the form with errors
            messages.error(request, "Please correct the errors below.")
            return render(request, "account/signup.html", {"form": form})
    else:
        form = SignupForm()
    return render(request, "account/signup.html", {"form": form})


def home_view(request):
    user = request.user
    username = user.username
    inbox_pk = 0
    if user.is_authenticated:
        inbox_pk = user.inbox.pk
        if user.user_type == "django_admin":
            return redirect("/admin/")
    else:
        username == "Guest"
    boards = VisionBoard.objects.all()
    vb_data = []
    for board in boards:
        latest_image = board.thumbnail.order_by("-timestamp").first()
        vb_data.append(
            {"vision_board": board, "latest_image": latest_image}
        )  # create dictionary for each vb's data
        # print(board.members.all())
    pending_count = 0
    if user.is_authenticated:
        user_vision_boards = VisionBoard.objects.filter(members=user)
        pending_count = JoinRequest.objects.filter(
            status='pending',
            vision_board__in=user_vision_boards
        ).count()
    context = {"username": username, "vision_board_data": vb_data, "inbox_pk": inbox_pk, "pending_join_requests": pending_count}
    return render(request, "home.html", context)


@login_required
def mock_home_view(request):
    user = request.user
    latest_files = sorted(
        (obj for obj in UploadedFile.objects.all() if type(obj) is UploadedFile),
        key=lambda x: x.timestamp,
        reverse=True,
    )[:10]
    latest_images = UploadedImageFile.objects.order_by("-timestamp")[:10]
    username = user.username
    context = {
        "username": username,
        "latest_images": latest_images,
        "latest_files": latest_files,
    }
    if (
        user.user_type == "site_admin"
    ):  # in case admin user tries to visit common user's page, redirect to correct page
        return redirect("admin_home")
    else:
        return render(request, "mock_home.html", context)


def admin_home_view(request):
    user = request.user
    username = request.user.username

    if user.user_type == "site_admin":
        boards = VisionBoard.objects.all()
        vb_data = []
        for board in boards:
            latest_image = board.thumbnail.order_by("-timestamp").first()
            vb_data.append(
                {"vision_board": board, "latest_image": latest_image}
            )  # create dictionary for each vb's data
            # print(board.members.all())
        context = {"username": username, "vision_board_data": vb_data}
        return render(request, "home.html", context)
    else:  # in case common user tries to access this view, redirect to correct page
        return redirect("home")


def admin_requests_view(request):
    return JsonResponse(
        {
            "usernames": list(
                map(
                    lambda admin_request: admin_request.user.username,
                    AdminRequest.objects.all(),
                )
            )
        }
    )


@login_required
def create_vb_view(request):
    if request.method == "POST":
        form = VisionBoardForm(request.POST)
        if form.is_valid():
            vb = form.save(commit=False)
            user = request.user
            vb.owner = user
            vb.save()

            response = requests.get(
                "https://project-a10.s3.us-east-2.amazonaws.com/content/thumbnail.jpg"
            )
            image_content = ContentFile(response.content, name="generic")
            generic_vb_img = UploadedImageFile(file=image_content)
            generic_vb_img.owner = user
            generic_vb_img.save()
            vb.thumbnail.add(generic_vb_img)

            vb.members.add(request.user)
            vb.save()
            messages.success(request, f"Vision Board '{vb.name}' created successfully!")
            return redirect("home")
        else:
            messages.error(
                request,
                "There was an error creating the group. Please correct the errors below.",
            )
    else:
        form = VisionBoardForm()

    return render(request, "groups/create_group.html", {"form": form})


from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect


@login_required
def join_vision_board(request, pk):
    group = get_object_or_404(VisionBoard, pk=pk)
    user = request.user

    # Check if a pending join request already exists
    existing_request = JoinRequest.objects.filter(
        sender=user, vision_board=group, status="pending"
    ).exists()
    if existing_request:
        messages.error(
            request, "You already have a pending join request for this Vision Board."
        )
        return redirect("home")  # Or another appropriate redirect

    # If no duplicate, create the join request
    join_request_data = {
        "inbox": group.owner.inbox,
        "sender": user,
        "recipient": group.owner,
        "subject": f"Join Request from {user.username}",
        "message": f"{user.username} would like to join your Vision Board, \"{group}\".",
        "vision_board": group,
    }
    join_request = JoinRequest.objects.create(**join_request_data)

    if join_request:
        messages.success(request, "Join request sent.")
    else:
        messages.error(request, "Something went wrong. Please try again later.")

    # Redirect back to home or referrer
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
def vision_board_view(request, pk):
    vision_board = get_object_or_404(VisionBoard, pk=pk)
    posts = Post.objects.filter(vision_board=vision_board)

    image_posts = Post.objects.filter(
        vision_board=vision_board, file__file_type="image"
    )
    # keyword filtering
    if request.method == "GET":
        query = request.GET.get("query", "").strip()
        print("query:", query)
        if query:  # "truthy" if query is a nonempty string
            matches = Post.objects.filter(
                vision_board=vision_board, file__file_type="image", tags__name=query
            )
            image_posts = matches

    non_image_posts = Post.objects.filter(
        vision_board=vision_board, file__file_type="other"
    )
    context = {
        "posts": posts,
        "vision_board": vision_board,
        "image_posts": image_posts,
        "non_image_posts": non_image_posts,
    }
    print(f"context:  {context}")
    return render(request, "vision_board.html", context)


@login_required
def delete_vision_board(request, pk):
    try:
        vision_board = VisionBoard.objects.get(pk=pk)
        vision_board_name = str(vision_board)
        vision_board.delete()
        messages.success(request, f"{vision_board_name} deleted.")
        return redirect("home")
    except VisionBoard.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Vision Board not found"}, status=404
        )


def anonymous_login(request):
    # vision_boards = VisionBoard.objects.all()
    # thumbnails = []
    # for vision_board in vision_boards:
    #     thumbnails.append(vision_board.thumbnail.all())
    # return render(request, "home.html")
    return redirect("home")


@login_required
def add_post(request, vision_board_id):
    user = request.user
    vision_board = get_object_or_404(VisionBoard, id=vision_board_id)
    if request.method == "POST":
        post_form = PostForm(request.POST)
        upload_image_form = UploadImageFileForm(request.POST, request.FILES)
        if post_form.is_valid() and upload_image_form.is_valid():
            user = request.user
            validate_and_upload_image(upload_image_form, vision_board, user)
            uploaded_image = upload_image_form.save()
            print("image uploaded")
            if post_form.is_valid():
                print("post form validated")
                post: Post = post_form.save(commit=False)
                post.file = uploaded_image
                post.user = user
                post.vision_board = vision_board
                post.save()

                tag_string = request.POST.get("tags", "")
                tag_list = tag_string.split(",")
                for tag in tag_list:
                    tag = tag.strip()
                    print(tag)
                    post.tags.add(tag)
                post.save()

                print("test")
                url = reverse("vision_board_view", kwargs={"pk": vision_board_id})
                return redirect(url)
        else:
            messages.error(
                request,
                "There was an error creating the post. Please correct the errors below.",
            )
            context = {
                "vision_board": vision_board,
                "vision_board_id": vision_board_id,
                "user": request.user,
                "form": upload_image_form,
                "post_form": post_form,
            }
        return render(request, "add-image-post.html", context)

    else:
        post_form = PostForm()
        upload_image_form = UploadImageFileForm()
        context = {
            "vision_board": vision_board,
            "vision_board_id": vision_board_id,
            "user": request.user,
            "form": upload_image_form,
            "post_form": post_form,
        }
        return render(request, "add-image-post.html", context)


@login_required
def create_uploaded_file(request, vision_board_id=None):
    user = request.user
    vision_board = None
    if vision_board_id:
        vision_board = get_object_or_404(VisionBoard, id=vision_board_id)

    if request.method == "POST":
        upload_form = UploadFileForm(request.POST, request.FILES)
        if upload_form.is_valid():
            # Save the uploaded file
            uploaded_file = upload_form.save(commit=False)
            uploaded_file.owner = user
            if vision_board:
                uploaded_file.vision_board = vision_board

            uploaded_file.set_file_type()  # Automatically detect the file type
            uploaded_file.save()

            # Process new and existing keywords
            new_keyword = request.POST.get("new_keyword", "").strip()
            if new_keyword:
                print(f"New keyword: {new_keyword}")
                uploaded_file.keywords.create(name=new_keyword)

            existing_keywords = upload_form.cleaned_data.get("keywords", [])
            for keyword in existing_keywords:
                uploaded_file.keywords.add(keyword)

            uploaded_file.save()
            messages.success(request, "File uploaded successfully!")

            # Redirect to the vision board view or another appropriate page
            if vision_board:
                return redirect(
                    reverse("vision_board_view", kwargs={"pk": vision_board_id})
                )
            return redirect(reverse("uploaded_file_list"))  # Update this as needed
        else:
            messages.error(
                request,
                "There was an error uploading the file. Please correct the errors below.",
            )
    else:
        upload_form = UploadFileForm()

    context = {
        "form": upload_form,
        "vision_board": vision_board,
    }
    return render(request, "upload.html", context)


@login_required
def delete_post(request, pk, post_id):
    try:
        board = VisionBoard.objects.get(pk=pk)
        post = Post.objects.get(id=post_id)
        post.delete()
        return redirect("vision_board_view", pk)
    except VisionBoard.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Vision Board not found"}, status=404
        )


@login_required
def view_vision_board_files(request, vision_board_id):
    if request.method == "GET":
        vision_board = VisionBoard.objects.get(id=vision_board_id)
        print(f"all files: {UploadedFile.objects.all()}")
        files = UploadedFile.objects.filter(
            vision_board=vision_board, file_type__in=["text", "pdf"]
        )
        context = {
            "vision_board": vision_board,
            "files": files,
        }
        print(context)
        return render(request, "vision_board_files.html", context)


@login_required
def group_list(request):
    vision_boards = VisionBoard.objects.all()
    thumbnails = []
    for vision_board in vision_boards:
        thumbnails.append(vision_board.thumbnail.all())
    return render(request, "groups/group_list.html", {"thumbnails": thumbnails})


def chat_room(request, room_name):
    vision_board = get_object_or_404(VisionBoard, name=room_name)

    if request.user not in vision_board.members.all():
        return HttpResponseForbidden("You are not a member of this vision board.")

    if request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            Message.objects.create(
                vision_board=vision_board,
                user=request.user,
                content=form.cleaned_data["content"],
                timestamp=timezone.now(),
            )
        return redirect("chat_room", room_name=room_name)

    messages = vision_board.messages.order_by("timestamp")
    form = MessageForm()

    return render(
        request,
        "chat.html",
        {
            "visionboard": vision_board,
            "messages": messages,
            "form": form,
            "room_name": room_name,
        },
    )


@login_required
def upload_file(request, vision_board_id):
    form = UploadFileForm()
    context = {"form": form, "vision_board_id": vision_board_id}
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                print(f"DEFAULT_FILE_STORAGE: {settings.DEFAULT_FILE_STORAGE}")
                print(f"MEDIA_URL: {settings.MEDIA_URL}")
                user = request.user
                uploaded_file = form.save(commit=False)
                uploaded_file.owner = user
                uploaded_file.vision_board = get_object_or_404(
                    VisionBoard, id=vision_board_id
                )
                print("saving file")
                uploaded_file.save()
                uploaded_file.timestamp = timezone.now()
                new_key = request.POST.get("new_keyword")
                keyword = Keyword.objects.create(name=new_key)
                uploaded_file.keywords.add(keyword)
                print(f"File timestamp: ", uploaded_file.timestamp)
                print(f"File '{uploaded_file.file.name}' uploaded successfully.")
                return redirect("upload_success", vision_board_id)
            except Exception as e:
                print(f"Error uploading file: {e}")
                form.add_error(None, "An error occurred while uploading the file.")
        else:
            print(f"Form is not valid: {form.errors}")

    return render(request, "upload.html", context)


@login_required
def upload_image(request, vision_board_id):
    vision_board = get_object_or_404(VisionBoard, id=vision_board_id)

    if request.method == "POST":
        form = UploadImageFileForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                user = request.user
                uploaded_file = form.save(commit=False)
                uploaded_file.owner = user
                uploaded_file.save()
                # post = Post.objects.create(
                #     name=uploaded_file.title,
                #     file=uploaded_file,
                #     caption=uploaded_file.description,
                #     user=request.user  # Assuming the user is logged in
                # )
                # Associate the post with the vision board
                vision_board.thumbnail.add(uploaded_file)

                return redirect("vision_board_view", pk=vision_board.pk)
            except Exception as e:
                print(f"Error occurred while saving the image: {e}")
                logger.error(f"Error during image upload: {e}", exc_info=True)
                form.add_error(None, f"An error occurred while uploading the file: {e}")
        else:
            print(f"Form is not valid: {form.errors}")
            logger.error(f"Form errors: {form.errors}")

    else:
        form = UploadImageFileForm()

    return render(
        request, "upload_image.html", {"form": form, "vision_board": vision_board}
    )


def validate_and_upload_image(
    form: UploadImageFileForm, vision_board: VisionBoard, owner
):
    if form.is_valid():
        try:
            uploaded_file = form.save(commit=False)
            uploaded_file.owner = owner
            uploaded_file.save()
            vision_board.thumbnail.add(uploaded_file)
        except Exception as e:
            print(f"Error occurred while saving the image: {e}")
            logger.error(f"Error during image upload: {e}", exc_info=True)
            form.add_error(None, f"An error occurred while uploading the file: {e}")
    else:
        print(f"Form is not valid: {form.errors}")
        logger.error(f"Form errors: {form.errors}")


def upload_success(request, vision_board_id):
    return render(request, "upload_success.html", {"vision_board_id": vision_board_id})


@login_required
def account_view(request):
    user = request.user

    if request.method == "POST":
        # Check if the request is an AJAX request for theme toggling
        is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"

        if is_ajax:
            # Handle theme toggling
            if user.theme == "light":
                user.theme = "dark"
                message = "Dark mode activated."
                theme = "dark"
            else:
                user.theme = "light"
                message = "Light mode activated."
                theme = "light"
            user.save()

            return JsonResponse(
                {"status": "success", "message": message, "theme": theme}
            )

        else:
            # Handle email management actions
            print("handling email management")
            action = request.POST.get("email_action")
            email = request.POST.get("email")

            print(f"POST data: {request.POST}")
            print(f"{action=}, {email=}")

            if action == "action_add":
                print(f"Trying to action_add with allauth.account.forms.AddEmailForm")
                print(f"{request.POST=}, {request.user}")
                form = AddEmailForm(request.user, request.POST)
                if form.is_valid():
                    try:
                        form.save(request)
                    except:
                        print(f"ignoring django-allauth trying to send confirmation email")
                    messages.success(request, "Email added successfully.")
                else:
                    messages.error(
                        request, "Failed to add email. Please check the form."
                    )
            elif action == "action_send":
                try:
                    email_address = EmailAddress.objects.get(
                        user=user, email__iexact=email
                    )
                    email_address.send_confirmation(request)
                    messages.success(request, "Verification email sent.")
                except EmailAddress.DoesNotExist:
                    messages.error(request, "Email not found.")
            elif action == "action_remove":
                try:
                    email_address = EmailAddress.objects.get(
                        user=user, email__iexact=email
                    )
                    if email_address.primary:
                        messages.error(
                            request,
                            "You cannot remove your primary email address. Please set another email as primary before removing this one.",
                        )
                    else:
                        email_address.delete()
                        messages.success(request, "Email removed successfully.")
                except EmailAddress.DoesNotExist:
                    messages.error(request, "Email not found.")
                    messages.error(request, "Email not found.")
            elif action == "action_primary":
                try:
                    email_address = EmailAddress.objects.get(
                        user=user, email__iexact=email
                    )
                    email_address.set_as_primary()
                    messages.success(request, "Primary email set.")
                except EmailAddress.DoesNotExist:
                    messages.error(request, "Email not found.")
            else:
                return HttpResponseNotFound()

            return redirect("account")

    else:
        form = AddEmailForm(user=request.user)
        emailaddresses = EmailAddress.objects.filter(user=user)
        can_add_email = (
            app_settings.MAX_EMAIL_ADDRESSES is None
            or emailaddresses.count() < app_settings.MAX_EMAIL_ADDRESSES
        )

    context = {
        "user": user,
        "emailaddresses": emailaddresses,
        "can_add_email": can_add_email,
        "form": form,
    }
    return render(request, "account/account.html", context)


@login_required
def inbox_view(request, inbox_pk):
    inbox = get_object_or_404(Inbox, pk=inbox_pk)
    recipient = request.user
    if inbox.user != recipient and not is_site_admin(recipient):
        return HttpResponseForbidden("You are not authorized to view this inbox.")
    pending_join_requests = JoinRequest.objects.filter(
        recipient=recipient, status="pending"
    )
    context = {"recipient": recipient, "pending_join_requests": pending_join_requests}
    return render(request, "inbox.html", context)


def answer_request(request, request_id):
    if request.method == "POST":

        join_request = get_object_or_404(JoinRequest, pk=request_id)

        if join_request.recipient != request.user:
            return HttpResponseForbidden(
                "You are not authorized to act on this request."
            )

        data = json.loads(request.body)
        new_status = data.get("new_status")
        # new_status = request.POST.get("new_status")

        if new_status not in ["accepted", "rejected"]:
            return JsonResponse(
                {"error": f"Invalid status '{new_status}' "}, status=400
            )
        print(join_request)
        print(new_status)
        join_request.status = new_status
        join_request.save()
        sender = join_request.sender
        vision_board = join_request.vision_board
        if new_status == "accepted":
            sender.vision_boards.add(vision_board)
        return JsonResponse({"success": True, "message": f"Request {new_status}."})

    return JsonResponse({"error": "Invalid request."}, status=400)


@login_required
def delete_file(request, pk):
    try:
        file = UploadedFile.objects.get(pk=pk)
        print(file)
        if request.user == file.owner:
            file.delete()
            messages.success(request, "File deleted.")
        else:
            messages.error(
                request,
                f'You cannot delete "{file.title}." Files can only be deleted by their owner.',
            )
        return redirect("view_vision_board_files", file.vision_board.id)
    except UploadedFile.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "File not found"}, status=404
        )

@login_required
def leave_board(request, pk):
    try:
        user = request.user
        board = get_object_or_404(VisionBoard, pk=pk)
        user.vision_boards.remove(board)
        if user == board.owner:
            delete_vision_board(request, pk)
        return redirect('home')
    except VisionBoard.DoesNotExist:
        print("VisionBoard not found.")
    except user.DoesNotExist:
        print("Member not found.")
        
@login_required
def about_view(request, pk):
    if request.method == 'GET':
        board = get_object_or_404(VisionBoard, pk=pk)
        members = board.members.all()
        context = {
            'vision_board':board,
            'members': members
        }
        return render(request, 'about.html', context)
    else:
        redirect('boards', pk)
    

@login_required
def admin_request(request):
    user = request.user
    if not user.admin_requests.exists():
        admin_request = AdminRequest.objects.create(user=user)
        admin_request.save()
        return render(request, 'home.html')
    else:
        messages.error(request, "You already have an admin request pending.")
        print(AdminRequest.objects.all())
        return redirect('home')
    
