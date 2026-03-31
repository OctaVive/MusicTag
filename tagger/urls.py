from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/tree", views.api_tree, name="api_tree"),
    path("api/file", views.api_file, name="api_file"),
    path("api/save", views.api_save, name="api_save"),
    path("api/save-bulk", views.api_save_bulk, name="api_save_bulk"),
    path("api/parser-preview", views.api_parser_preview, name="api_parser_preview"),
    path("api/apply-map", views.api_apply_map, name="api_apply_map"),
    path("api/presets", views.api_presets, name="api_presets"),
    path("api/auto-number", views.api_auto_number, name="api_auto_number"),
    path("api/preview-bulk", views.api_preview_bulk, name="api_preview_bulk"),
    path("api/undo-last", views.api_undo_last, name="api_undo_last"),
    path("api/quality-check", views.api_quality_check, name="api_quality_check"),
    path("api/cover-bulk", views.api_cover_bulk, name="api_cover_bulk"),
    path("api/audio", views.api_audio, name="api_audio"),
    path("api/lookup", views.api_lookup, name="api_lookup"),
    path("api/lock", views.api_lock, name="api_lock"),
]
