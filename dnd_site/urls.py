from django.contrib import admin
from django.urls import include, path
from django.contrib.auth.views import LoginView, LogoutView

from spells.views.pages import (
    character_list_page,
    character_create_page,
    character_edit_page,
    character_delete_page,
    register_page
)
from spells.views.pages import (
    character_create_page,
    character_list_page,
    character_edit_page,
    character_delete_page,
    register_page
)

urlpatterns = [
    path("", character_list_page, name="character_list_page"),
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("api/spells/", include("spells.urls")),
    path(
        "characters/new/",
        character_create_page,
        name="character_create_page",
    ),
        path(
        "characters/<int:pk>/edit/",
        character_edit_page,
        name="character_edit_page",
    ),
        path(
        "characters/<int:pk>/delete/",
        character_delete_page,
        name="character_delete_page",
    ),
        path(
        "login/",
        LoginView.as_view(
            template_name="spells/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
        path(
        "logout/",
        LogoutView.as_view(),
        name="logout",
    ),
        path(
        "register/",
        register_page,
        name="register",
    ),
]