"""URL configuration for aa_doctrinehub."""

from django.urls import path

from . import views, views_spa_api

app_name = "aa_doctrinehub"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/v1/doctrines/", views_spa_api.doctrines, name="api_doctrines"),
    path("api/v1/fittings/", views_spa_api.fittings, name="api_fittings"),
    path("api/v1/fittings/import/", views_spa_api.import_fitting, name="api_import_fitting"),
    path("api/v1/fittings/<int:fitting_id>/", views_spa_api.fitting_detail, name="api_fitting_detail"),
    path("api/v1/settings/sync/", views_spa_api.sync_settings, name="api_sync_settings"),
    path("api/v1/settings/sync/run/", views_spa_api.run_fittings_sync, name="api_run_fittings_sync"),
    path("api/v1/settings/remote-scrape/", views_spa_api.remote_scrape, name="api_remote_scrape"),
    # The SPA handles its own routes below the index.
    path("<path:spa_path>", views.index, name="spa"),
]
