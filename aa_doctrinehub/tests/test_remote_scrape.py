"""Tests for scraping doctrines, fittings, and categories from an external Auth."""

from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from aa_doctrinehub.models import Category, Doctrine, Fitting, Source
from aa_doctrinehub.services.fittings import ReadOnlyFittingError, update_from_eft
from aa_doctrinehub.services.remote_scrape import (
    RemoteScrapeError,
    import_remote_scrape,
    preview_remote_scrape,
    scrape_remote_fittings_site,
)

pytestmark = pytest.mark.django_db

INDEX_HTML = """
<html><body>
  <a href="/fittings/doctrine/11/">Shield HAC</a>
</body></html>
"""

DOCTRINE_HTML = """
<html><body>
  <h1>Shield HAC</h1>
  <div class="card">
    <div class="card-header"><h5 class="card-title">Description</h5></div>
    <div class="card-body"><p>Mainline HAC fleet</p></div>
  </div>
  <img src="https://images.evetech.net/types/12015/icon?size=64" />
  <a href="/fittings/fit/101/">Muninn DPS</a>
</body></html>
"""

FITS_LIST_HTML = """
<html><body>
  <a href="/fittings/fit/101/">Muninn DPS</a>
  <a href="/fittings/fit/102/">Sabre Tackle</a>
</body></html>
"""

FIT_101_HTML = """
<html><body>
  <img src="https://images.evetech.net/types/12015/icon?size=64" />
  <textarea id="eft-fitting">[Muninn, Muninn DPS]

Gyrostabilizer II
Gyrostabilizer II
</textarea>
  <div class="card">
    <div class="card-header"><h5 class="card-title">Fitting Notes</h5></div>
    <div class="card-body"><p>Keep at 40km</p></div>
  </div>
</body></html>
"""

FIT_102_HTML = """
<html><body>
  <img src="https://images.evetech.net/types/22456/icon?size=64" />
  <textarea id="eft-fitting">[Sabre, Sabre Tackle]

Gyrostabilizer II
</textarea>
</body></html>
"""

CATS_LIST_HTML = """
<html><body>
  <a href="/fittings/cat/7/">Alliance</a>
</body></html>
"""

CAT_7_HTML = """
<html><body>
  <span class="badge" style="background-color: rgb(255, 0, 0);">Alliance</span>
  <div id="tab-fittings"><a href="/fittings/fit/102/">Sabre Tackle</a></div>
  <div id="tab-doctrines"><a href="/fittings/doctrine/11/">Shield HAC</a></div>
</body></html>
"""


class _FakeResp:
    def __init__(self, text: str, url: str = "https://other.example/fittings/", status_code: int = 200):
        self.text = text
        self.url = url
        self.status_code = status_code


def _fake_get_factory(responses: dict[str, _FakeResp]):
    def _fake_get(self, url, **kwargs):
        return responses[url]

    return _fake_get


def test_scrape_remote_site_collects_doctrines_fittings_and_categories():
    base = "https://other.example"
    pages = {
        f"{base}/fittings/fit/all/": _FakeResp(FITS_LIST_HTML, f"{base}/fittings/fit/all/"),
        f"{base}/fittings/": _FakeResp(INDEX_HTML, f"{base}/fittings/"),
        f"{base}/fittings/doctrine/11/": _FakeResp(DOCTRINE_HTML, f"{base}/fittings/doctrine/11/"),
        f"{base}/fittings/fit/101/": _FakeResp(FIT_101_HTML, f"{base}/fittings/fit/101/"),
        f"{base}/fittings/fit/102/": _FakeResp(FIT_102_HTML, f"{base}/fittings/fit/102/"),
        f"{base}/fittings/cat/all/": _FakeResp(CATS_LIST_HTML, f"{base}/fittings/cat/all/"),
        f"{base}/fittings/cat/7/": _FakeResp(CAT_7_HTML, f"{base}/fittings/cat/7/"),
    }

    with patch("requests.Session.get", new=_fake_get_factory(pages)):
        snap = scrape_remote_fittings_site(base, "secret-cookie", request_delay=0)

    assert len(snap.doctrines) == 1
    assert snap.doctrines[0].name == "Shield HAC"
    assert snap.doctrines[0].fitting_ids == [101]
    assert len(snap.fittings) == 2
    assert len(snap.categories) == 1
    assert snap.categories[0].color == "#ff0000"

    preview = preview_remote_scrape(snap)
    assert preview["doctrines_new"] == 1
    assert preview["fittings_new"] == 2
    assert preview["categories_new"] == 1

    result = import_remote_scrape(snap)
    assert result.doctrines_created == 1
    assert result.fittings_created == 2
    assert result.categories_synced == 1

    doc = Doctrine.objects.get(source=Source.REMOTE_AUTH, external_id=11)
    assert doc.is_editable is False
    fit = Fitting.objects.get(source=Source.REMOTE_AUTH, external_id=101)
    assert fit.is_editable is False
    with pytest.raises(ReadOnlyFittingError):
        update_from_eft(fit, "[Muninn, Muninn DPS]\n\nGyrostabilizer II\n")

    cat = Category.objects.get(source=Source.REMOTE_AUTH, external_id=7)
    assert cat.color == "#ff0000"
    # Local group restrictions added afterwards are preserved on re-import
    grp = Group.objects.create(name="Line Members")
    cat.visible_to_groups.add(grp)
    import_remote_scrape(snap)
    assert list(cat.visible_to_groups.all()) == [grp]


def test_scrape_rejects_expired_session_redirect():
    base = "https://other.example"
    pages = {
        f"{base}/fittings/fit/all/": _FakeResp(
            "login", url=f"{base}/account/login/?next=/fittings/fit/all/"
        )
    }
    with patch("requests.Session.get", new=_fake_get_factory(pages)):
        with pytest.raises(RemoteScrapeError, match="expired"):
            scrape_remote_fittings_site(base, "expired", request_delay=0)


def test_remote_scrape_api_endpoint_requires_permission_and_imports(client):
    from allianceauth.tests.auth_utils import AuthUtils

    user = AuthUtils.create_user("mgr_scrape")
    AuthUtils.add_main_character(user, "Mgr Scrape", character_id=92099)
    AuthUtils.add_permission_to_user_by_name("aa_doctrinehub.basic_access", user)
    client.force_login(user)

    url = reverse("aa_doctrinehub:api_remote_scrape")
    resp_denied = client.post(
        url,
        data={"base_url": "https://other.example", "sessionid": "abc", "mode": "preview"},
        content_type="application/json",
    )
    assert resp_denied.status_code == 302

    AuthUtils.add_permission_to_user_by_name("aa_doctrinehub.manage_doctrines", user)
    user.refresh_from_db()
    client.force_login(user)

    base = "https://other.example"
    pages = {
        f"{base}/fittings/fit/all/": _FakeResp(FITS_LIST_HTML, f"{base}/fittings/fit/all/"),
        f"{base}/fittings/": _FakeResp(INDEX_HTML, f"{base}/fittings/"),
        f"{base}/fittings/doctrine/11/": _FakeResp(DOCTRINE_HTML, f"{base}/fittings/doctrine/11/"),
        f"{base}/fittings/fit/101/": _FakeResp(FIT_101_HTML, f"{base}/fittings/fit/101/"),
        f"{base}/fittings/fit/102/": _FakeResp(FIT_102_HTML, f"{base}/fittings/fit/102/"),
        f"{base}/fittings/cat/all/": _FakeResp(CATS_LIST_HTML, f"{base}/fittings/cat/all/"),
        f"{base}/fittings/cat/7/": _FakeResp(CAT_7_HTML, f"{base}/fittings/cat/7/"),
    }
    with patch("requests.Session.get", new=_fake_get_factory(pages)):
        resp_prev = client.post(
            url,
            data={"base_url": base, "sessionid": "abc", "mode": "preview"},
            content_type="application/json",
        )
        assert resp_prev.status_code == 200
        assert resp_prev.json()["doctrines_count"] == 1

        resp_imp = client.post(
            url,
            data={"base_url": base, "sessionid": "abc", "mode": "import"},
            content_type="application/json",
        )
        assert resp_imp.status_code == 200
        assert resp_imp.json()["doctrines_created"] == 1
