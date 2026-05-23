from django.urls import path

from . import views

app_name = "contacts"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("contacts/", views.contact_list, name="list"),
    path("contacts/favorites/", views.contact_list, {"mode": "favorites"}, name="favorites"),
    path("contacts/archive/", views.contact_list, {"mode": "archive"}, name="archive"),
    path("contacts/new/", views.contact_create, name="create"),
    path("contacts/<int:pk>/", views.contact_detail, name="detail"),
    path("contacts/<int:pk>/photo/", views.contact_photo, name="photo"),
    path("contacts/<int:pk>/edit/", views.contact_update, name="edit"),
    path("contacts/<int:pk>/delete/", views.contact_delete, name="delete"),
    path("contacts/<int:pk>/restore/", views.contact_restore, name="restore"),
    path("contacts/<int:pk>/favorite/", views.contact_toggle_favorite, name="favorite"),
    path("contacts/<int:pk>/vcard/", views.vcard_export_one, name="vcard_one"),
    path("organization/", views.organization, name="organization"),
    path("organization/groups/<int:pk>/delete/", views.group_delete, name="group_delete"),
    path("organization/tags/<int:pk>/delete/", views.tag_delete, name="tag_delete"),
    path("selection/toggle/", views.selection_toggle, name="selection_toggle"),
    path("selection/clear/", views.selection_clear, name="selection_clear"),
    path("selection/page/", views.selection_page, name="selection_page"),
    path("bulk/", views.bulk_action, name="bulk_action"),
    path("import/", views.csv_import, name="csv_import"),
    path("import/errors.csv", views.csv_error_report, name="csv_error_report"),
    path("export/csv/", views.csv_export, name="csv_export"),
    path("export/vcard/", views.vcard_export_bulk, name="vcard_bulk"),
]
