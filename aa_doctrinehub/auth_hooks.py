"""Alliance Auth hooks for aa_doctrinehub."""

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls
from .app_settings import DOCTRINEHUB_APP_NAME


class DoctrineHubMenuItem(MenuItemHook):
    """Menu item for Doctrine Hub."""

    def __init__(self):
        super().__init__(
            DOCTRINEHUB_APP_NAME,
            "fas fa-shield-alt fa-fw",
            "aa_doctrinehub:index",
            navactive=["aa_doctrinehub:"],
        )

    def render(self, request):
        if request.user.has_perm("aa_doctrinehub.basic_access"):
            return super().render(request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    """Register the menu item."""
    return DoctrineHubMenuItem()


@hooks.register("url_hook")
def register_urls():
    """Register the URLs."""
    return UrlHook(urls, "aa_doctrinehub", r"^doctrines/")
