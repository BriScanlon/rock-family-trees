from app.content import LINEUP_CAPS, build_content, links_for
from app.fitting import fit_content
from app.pipeline import Options, harvester_for


def _content():
    return build_content("demo:yardbirds", Options(depth=4, max_bands=24))


def test_all_the_content_is_built_before_any_placement():
    content = _content()
    s = content.summary()
    assert set(content.trees) == set(LINEUP_CAPS)  # every level of detail, ready
    assert s["bands"] == len(content.full.bands) >= 10 and s["lineups"] > s["bands"]
    assert s["links"] > 0 and content.lettering in ("classic", "heavy")
    for tree in content.trees.values():  # the same candidates at each level of detail
        assert set(tree.bands) == set(content.full.bands)


def test_links_trace_every_musicians_moves():
    links = links_for(_content().full)
    page = [l for l in links if l["person"].endswith("jimmy-page")]
    assert any(l["from_band"] == "demo:yardbirds" and l["to_band"].endswith("led-zeppelin") for l in page)
    for l in links:  # never from a line-up to itself
        assert (l["from_band"], l["from_lineup"]) != (l["to_band"], l["to_lineup"])


def test_the_placement_only_reads_the_content(monkeypatch):
    content = _content()
    import app.harvester as H

    def no_fetching(*a, **k):
        raise AssertionError("the placement fetched data")

    monkeypatch.setattr(H.Harvester, "fetch", no_fetching)
    monkeypatch.setattr(H.Harvester, "harvest", no_fetching)
    tree, layout, fit = fit_content(content, paper="A2")
    assert tree.bands and layout["boxes"] and fit["bands_shown"] <= content.summary()["bands"]
