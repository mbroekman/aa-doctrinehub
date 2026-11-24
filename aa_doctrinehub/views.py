"""Page views for aa_doctrinehub: one page that mounts the SPA."""

from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from . import __version__
from .app_settings import DOCTRINEHUB_APP_NAME


@login_required
@permission_required("aa_doctrinehub.basic_access")
def index(request: HttpRequest, spa_path: str = "") -> HttpResponse:
    """Serve the single-page app."""
    context = {
        "app_name": DOCTRINEHUB_APP_NAME,
        "version": __version__,
        "can_manage": request.user.has_perm("aa_doctrinehub.manage_doctrines"),
    }
    return render(request, "aa_doctrinehub/spa.html", context)
