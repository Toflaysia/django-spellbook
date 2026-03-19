from django.urls import path

from spells.views.material_component import (
    MaterialComponentDetailView,
    MaterialConponentListView,
)

app_name = "spells"
urlpatterns = [
    path(
        "material_component/",
        MaterialConponentListView.as_view(),
        name="material_component_list",
    ),
    path(
        "material_component/<int:id>/",
        MaterialComponentDetailView.as_view(),
        name="material_component_detail",
    ),
]
