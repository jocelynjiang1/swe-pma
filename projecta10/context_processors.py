from projecta10.models.base import Inbox


def inbox_context(request):
    if request.user.is_authenticated and hasattr(request.user, "inbox"):
        return {"inbox_pk": request.user.inbox.pk}
    return {"inbox_pk": None}
