from spells.account_forms import EmailAuthenticationForm
from spells.views.accounts import account_email_page, resend_confirmation, confirm_email, EmailPasswordResetView
from django.contrib.auth import views as password_views
from spells.views.bulk_import import bulk_spell_import_page
from spells.views.user_classes import user_class_create_page
from spells.views.play_tools import catalog_link_search, catalog_preview
from spells.views.plans import plan_create_page, plan_edit_page, plan_toggle_page, plan_delete_page
from spells.views.play_tools import character_detail_page, character_resource_change, spell_link_search, spell_preview
from spells.views.progression_pages import class_table_edit_page
from django.contrib import admin
from django.urls import include, path
from django.contrib.auth.views import LoginView, LogoutView
from django.conf import settings
from django.conf.urls.static import static
from spells.views.class_pages import (
    class_detail_page,
    subclass_create_page,
    subclass_edit_page,
    subclass_delete_page,
    class_feature_create_page,
    class_feature_edit_page,
    class_feature_delete_page,
    class_section_create_page,
    class_section_edit_page,
    class_section_delete_page,
)

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
    home_page,
    spell_save_page,
    spell_unsave_page,
    official_spell_import_page,
    official_spell_create_page,
    spell_delete_page,
    spellbook_list_page,
    spellbook_create_page,
    spellbook_detail_page,
    spellbook_slot_change_page,
    spellbook_edit_page,
    spellbook_delete_page,
)
from spells.views.catalog import (
    catalog_list_page,
    catalog_detail_page,
    catalog_create_page,
    catalog_edit_page,
    catalog_delete_page,
)

urlpatterns = [
    path('account/email/',account_email_page,name='account_email_page'),
    path('account/email/resend/',resend_confirmation,name='resend_confirmation'),
    path('account/email/confirm/<str:token>/',confirm_email,name='confirm_email'),
    path('password-reset/',EmailPasswordResetView.as_view(),name='password_reset'),
    path('password-reset/sent/',password_views.PasswordResetDoneView.as_view(template_name='spells/password_reset_done.html'),name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/',password_views.PasswordResetConfirmView.as_view(template_name='spells/password_reset_confirm.html'),name='password_reset_confirm'),
    path('password-reset/complete/',password_views.PasswordResetCompleteView.as_view(template_name='spells/password_reset_complete.html'),name='password_reset_complete'),
    path("spells/import/bulk/", bulk_spell_import_page, name="bulk_spell_import_page"),
    path("my-classes/new/", user_class_create_page, name="user_class_create_page"),
    path("catalog-links/<slug:slug>/", catalog_link_search, name="catalog_link_search"),
    path("catalog/<slug:slug>/<int:pk>/preview/", catalog_preview, name="catalog_preview"),
    path("plans/new/", plan_create_page, name="plan_create_page"),
    path("plans/<int:pk>/edit/", plan_edit_page, name="plan_edit_page"),
    path("plans/<int:pk>/toggle/", plan_toggle_page, name="plan_toggle_page"),
    path("plans/<int:pk>/delete/", plan_delete_page, name="plan_delete_page"),
    path("characters/<int:pk>/", character_detail_page, name="character_detail_page"),
    path("characters/<int:pk>/resources/", character_resource_change, name="character_resource_change"),
    path("spell-links/", spell_link_search, name="spell_link_search"),
    path("spells/<int:pk>/preview/", spell_preview, name="spell_preview"),
    path("catalog/<slug:slug>/<int:pk>/delete/", catalog_delete_page, name="catalog_delete_page"),
    path("classes/<int:pk>/table/edit/", class_table_edit_page, name="class_table_edit_page"),
    path("classes/<int:pk>/subclasses/<int:entry_pk>/table/edit/", class_table_edit_page, name="subclass_table_edit_page"),
    path(
        "classes/<int:pk>/subclasses/<int:entry_pk>/delete/",
        subclass_delete_page,
        name="subclass_delete_page",
    ),
    path("", home_page, name="home_page"),
    path("characters/", character_list_page, name="character_list_page"),
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
            authentication_form=EmailAuthenticationForm,
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
    path(
        "spells/<int:pk>/save/",
        spell_save_page,
        name="spell_save_page",
    ),
        path(
        "spells/<int:pk>/unsave/",
        spell_unsave_page,
        name="spell_unsave_page",
    ),
        path(
        "spells/official/import/",
        official_spell_import_page,
        name="official_spell_import_page",
    ),
    path(
        "spells/official/create/",
        official_spell_create_page,
        name="official_spell_create_page",
    ),
        path(
        "spells/<int:pk>/delete/",
        spell_delete_page,
        name="spell_delete_page",
    ),
        path(
        "spellbooks/",
        spellbook_list_page,
        name="spellbook_list_page",
    ),
    path(
        "spellbooks/new/",
        spellbook_create_page,
        name="spellbook_create_page",
    ),
        path(
        "spellbooks/<int:pk>/",
        spellbook_detail_page,
        name="spellbook_detail_page",
    ),
        path(
        "spellbooks/<int:pk>/slots/change/",
        spellbook_slot_change_page,
        name="spellbook_slot_change_page",
    ),
        path(
        "spellbooks/<int:pk>/edit/",
        spellbook_edit_page,
        name="spellbook_edit_page",
    ),
    path(
        "spellbooks/<int:pk>/delete/",
        spellbook_delete_page,
        name="spellbook_delete_page",
    ),
        path(
        "catalog/<slug:slug>/",
        catalog_list_page,
        name="catalog_list_page",
    ),
    path(
        "catalog/<slug:slug>/<int:pk>/",
        catalog_detail_page,
        name="catalog_detail_page",
    ),
        path(
        "catalog/<slug:slug>/new/",
        catalog_create_page,
        name="catalog_create_page",
    ),
    path(
        "catalog/<slug:slug>/<int:pk>/edit/",
        catalog_edit_page,
        name="catalog_edit_page",
    ),
        path(
        "classes/<int:pk>/",
        class_detail_page,
        name="class_detail_page",
    ),
        path(
        "classes/<int:pk>/subclasses/new/",
        subclass_create_page,
        name="subclass_create_page",
    ),
    path(
        "classes/<int:pk>/subclasses/<int:entry_pk>/edit/",
        subclass_edit_page,
        name="subclass_edit_page",
    ),
    path(
        "classes/<int:pk>/features/new/",
        class_feature_create_page,
        name="class_feature_create_page",
    ),
    path(
        "classes/<int:pk>/features/<int:entry_pk>/edit/",
        class_feature_edit_page,
        name="class_feature_edit_page",
    ),
    path(
        "classes/<int:pk>/features/<int:entry_pk>/delete/",
        class_feature_delete_page,
        name="class_feature_delete_page",
    ),
    path(
        "classes/<int:pk>/sections/new/",
        class_section_create_page,
        name="class_section_create_page",
    ),
    path(
        "classes/<int:pk>/sections/<int:entry_pk>/edit/",
        class_section_edit_page,
        name="class_section_edit_page",
    ),
    path(
        "classes/<int:pk>/sections/<int:entry_pk>/delete/",
        class_section_delete_page,
        name="class_section_delete_page",
    ),
]
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )