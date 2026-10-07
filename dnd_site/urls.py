from django.contrib import admin
from django.urls import include, path
from django.contrib.auth.views import LoginView, LogoutView
from django.conf import settings
from django.conf.urls.static import static

from spells.views.pages import (
    character_list_page,
    character_create_page,
    character_edit_page,
    character_delete_page,
    register_page,
    spell_list_page,
    spell_detail_page,
    spell_create_page,
    my_spell_list_page,
    spell_import_page,
    spell_edit_page,

)

urlpatterns = [
    path("", character_list_page, name="character_list_page"),
    path("spells/", spell_list_page, name="spell_list_page"),
    path(
        "spells/new/",
        spell_create_page,
        name="spell_create_page",
    ),
    path(
        "my-spells/",
        my_spell_list_page,
        name="my_spell_list_page",
    ),
    path(
        "spells/<int:pk>/",
        spell_detail_page,
        name="spell_detail_page",
    ),
        path(
        "spells/import/",
        spell_import_page,
        name="spell_import_page",
    ),
        path(
        "spells/<int:pk>/edit/",
        spell_edit_page,
        name="spell_edit_page",
    ),
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
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )