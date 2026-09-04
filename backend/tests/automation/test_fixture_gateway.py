from app.automation.fixture_gateway import FixtureBrowserGateway
from app.automation.jd_union import OfficialFirstJdGateway
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


def test_fixture_gateway_preserves_exact_color_from_price_sheet_query(monkeypatch) -> None:
    monkeypatch.setenv("PRICE_COMPARE_AUTOMATION_FIXTURE_DELAY_MS", "0")
    gateway = FixtureBrowserGateway()

    candidates = gateway.discover("Apple iPhone 17 256GB 黑色", 30)

    assert len(candidates) == 20
    assert candidates[0].title == "Apple iPhone 17 256GB 黑色 全新国行"
    assert candidates[0].initial_price_cents == 519900


def test_fixture_checkout_preview_has_verified_conditional_and_address_required_cases(monkeypatch) -> None:
    monkeypatch.setenv("PRICE_COMPARE_AUTOMATION_FIXTURE_DELAY_MS", "0")
    gateway = FixtureBrowserGateway()
    black = gateway.discover("Apple iPhone 17 256GB 黑色", 50)
    white = gateway.discover("Apple iPhone 17 256GB 白色", 50)

    verified = gateway.checkout_preview(black[0], get_region_target("110100"))
    conditional = gateway.checkout_preview(black[1], get_region_target("110100"))
    address_required = gateway.checkout_preview(white[0], get_region_target("110100"))

    assert verified.price_status == "verified"
    assert verified.payable_price_cents == 519900
    assert conditional.price_status == "conditional"
    assert conditional.payable_price_cents < verified.payable_price_cents
    assert address_required.price_status == "unavailable"
    assert address_required.unavailable_code == "checkout_address_required"


def test_fixture_gateway_requires_exact_test_environment_value(monkeypatch) -> None:
    monkeypatch.delenv("JD_UNION_APP_KEY", raising=False)
    monkeypatch.delenv("JD_UNION_APP_SECRET", raising=False)
    monkeypatch.setenv("PRICE_COMPARE_AUTOMATION_FIXTURE", "true")
    assert isinstance(_default_browser_gateway_factory(), OpenCliGateway)

    monkeypatch.setenv("PRICE_COMPARE_AUTOMATION_FIXTURE", "1")
    monkeypatch.setenv("PRICE_COMPARE_AUTOMATION_FIXTURE_DELAY_MS", "0")
    assert isinstance(_default_browser_gateway_factory(), FixtureBrowserGateway)


def test_default_gateway_enables_official_first_only_with_both_credentials(monkeypatch) -> None:
    monkeypatch.delenv("PRICE_COMPARE_AUTOMATION_FIXTURE", raising=False)
    monkeypatch.setenv("JD_UNION_APP_KEY", "test-app")
    monkeypatch.delenv("JD_UNION_APP_SECRET", raising=False)
    assert isinstance(_default_browser_gateway_factory(), OpenCliGateway)

    monkeypatch.setenv("JD_UNION_APP_SECRET", "test-secret")
    assert isinstance(_default_browser_gateway_factory(), OfficialFirstJdGateway)
