"""Page views for aa_doctrinehub: one page that mounts the SPA plus ESI character linking."""

from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from esi.decorators import token_required

from . import __version__
from .app_settings import DOCTRINEHUB_APP_NAME
from .services.esi_sync import REQUIRED_SCOPES


@login_required
@permission_required("aa_doctrinehub.basic_access")
def index(request: HttpRequest, spa_path: str = "") -> HttpResponse:
    """Serve the single-page app."""
    context = {
        "app_name": DOCTRINEHUB_APP_NAME,
        "version": __version__,
        "can_manage": request.user.has_perm("aa_doctrinehub.manage_doctrines"),
        "can_view_compliance": request.user.has_perm("aa_doctrinehub.view_compliance"),
        "can_manage_rules": request.user.has_perm("aa_doctrinehub.manage_rules"),
    }
    return render(request, "aa_doctrinehub/spa.html", context)


@login_required
@permission_required("aa_doctrinehub.basic_access")
@token_required(scopes=REQUIRED_SCOPES, new=True)
def link_character(request: HttpRequest, token) -> HttpResponse:
    """Complete the mandatory ESI character linking flow and return to the SPA."""
    return redirect("aa_doctrinehub:index")
