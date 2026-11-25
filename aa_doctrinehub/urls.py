"""URL configuration for aa_doctrinehub."""

from django.urls import path

from . import views, views_spa_api

app_name = "aa_doctrinehub"

urlpatterns = [
    path("", views.index, name="index"),
    path("link-character/", views.link_character, name="link_character"),
    path("api/v1/doctrines/", views_spa_api.doctrines, name="api_doctrines"),
    path("api/v1/fittings/", views_spa_api.fittings, name="api_fittings"),
    path("api/v1/fittings/import/", views_spa_api.import_fitting, name="api_import_fitting"),
    path("api/v1/fittings/<int:fitting_id>/", views_spa_api.fitting_detail, name="api_fitting_detail"),
    path(
        "api/v1/fittings/<int:fitting_id>/eligibility/",
        views_spa_api.fitting_eligibility,
        name="api_fitting_eligibility",
    ),
    path(
        "api/v1/fittings/<int:fitting_id>/skills/",
        views_spa_api.fitting_skills,
        name="api_fitting_skills",
    ),
    path(
        "api/v1/fittings/<int:fitting_id>/skill-plan/",
        views_spa_api.fitting_skill_plan,
        name="api_fitting_skill_plan",
    ),
    path("api/v1/eligibility/status/", views_spa_api.eligibility_status, name="api_eligibility_status"),
    path("api/v1/eligibility/sync/", views_spa_api.eligibility_sync, name="api_eligibility_sync"),
    path("api/v1/compliance/overview/", views_spa_api.compliance_overview_view, name="api_compliance_overview"),
    path("api/v1/rules/", views_spa_api.rules_collection, name="api_rules"),
    path("api/v1/rules/<int:rule_id>/", views_spa_api.rule_detail, name="api_rule_detail"),
    path("api/v1/rules/evaluate/", views_spa_api.rules_evaluate, name="api_rules_evaluate"),
    path("api/v1/rules/approvals/", views_spa_api.rules_approvals, name="api_rules_approvals"),
    path(
        "api/v1/rules/approvals/<int:approval_id>/decide/",
        views_spa_api.rule_approval_decide,
        name="api_rule_approval_decide",
    ),
    path("api/v1/rules/audit/", views_spa_api.rules_audit, name="api_rules_audit"),
    path("api/v1/settings/sync/", views_spa_api.sync_settings, name="api_sync_settings"),
    path("api/v1/settings/sync/run/", views_spa_api.run_fittings_sync, name="api_run_fittings_sync"),
    path("api/v1/settings/remote-scrape/", views_spa_api.remote_scrape, name="api_remote_scrape"),
    path("api/v1/settings/remote-scrape/purge/", views_spa_api.remote_scrape_purge, name="api_remote_scrape_purge"),
    path(
        "api/v1/settings/notifications/",
        views_spa_api.notification_settings,
        name="api_notification_settings",
    ),
    path("api/v1/integrations/hangar-check/", views_spa_api.hangar_check_view, name="api_hangar_check"),
    path(
        "api/v1/integrations/industry-order/",
        views_spa_api.industry_order_view,
        name="api_industry_order",
    ),
    path("api/v1/integrations/srp-compare/", views_spa_api.srp_compare_view, name="api_srp_compare"),
    # The SPA handles its own routes below the index.
    path("<path:spa_path>", views.index, name="spa"),
]
