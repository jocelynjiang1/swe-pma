from django.apps import AppConfig


class ProjectA10Config(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "projecta10"

    def ready(self):
        import projecta10.signals
