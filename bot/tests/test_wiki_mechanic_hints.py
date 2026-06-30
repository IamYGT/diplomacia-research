"""Wiki mekanik → API çıkarımı."""

from diplomacy_bot.wiki_mechanic_hints import infer_api_paths


def test_pazar_suggests_market():
    paths = infer_api_paths("Pazar", excerpt="kaynak alışverişi market")
    assert "/market/list" in paths


def test_fabrika_suggests_factories_world():
    paths = infer_api_paths("Fabrika Türleri", excerpt="elmas fabrikası dünya")
    assert "/factories/world" in paths


def test_seyahat_suggests_provinces():
    paths = infer_api_paths("Harita & Eyaletler", excerpt="Seyahat gerçek mesafe")
    assert "/provinces/travel/start" in paths
