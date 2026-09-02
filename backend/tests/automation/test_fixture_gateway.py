from app.automation.fixture_gateway import FixtureBrowserGateway
from app.automation.opencli import OpenCliGateway
from app.automation.regions import get_region_target
from app.main import _default_browser_gateway_factory


def test_fixture_gateway_is_deterministic_across_representative_regions(monkeypatch) -> None:
    monkeypatch.setenv("PRICE_COMPARE_AUTOMATION_FIXTURE_DELAY_MS", "0")
    gateway = FixtureBrowserGateway()

    candidates = gateway.discover("Apple iPhone 17 256GB", 10)
    beijing = gateway.verify(candidates[0], get_region_target("110100"))
    shanghai = gateway.verify(candidates[0], get_region_target("310100"))

    assert len(candidates) == 10
    assert beijing.sale_price_cents == 499900
    assert shanghai.sale_price_cents == 500300
    assert gateway.diagnose().plugin_ready is True


def test_fixture_gateway_requires_exact_test_environment_value(monkeypatch) -> None:
    monkeypatch.setenv("PRICE_COMPARE_AUTOMATION_FIXTURE", "true")
    assert isinstance(_default_browser_gateway_factory(), OpenCliGateway)

    monkeypatch.setenv("PRICE_COMPARE_AUTOMATION_FIXTURE", "1")
    monkeypatch.setenv("PRICE_COMPARE_AUTOMATION_FIXTURE_DELAY_MS", "0")
    assert isinstance(_default_browser_gateway_factory(), FixtureBrowserGateway)
