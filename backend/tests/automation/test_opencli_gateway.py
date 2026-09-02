import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from app.automation.contracts import GatewayFailure
from app.automation.opencli import (
    CommandResult,
    OpenCliGateway,
    SubprocessCommandRunner,
)
from app.automation.regions import get_region_target


FIXTURES = Path(__file__).parent / "fixtures"
SEARCH_JSON = (FIXTURES / "opencli-search.json").read_text(encoding="utf-8")
VERIFY_JSON = (FIXTURES / "opencli-verify.json").read_text(encoding="utf-8")


class FakeRunner:
    def __init__(
        self,
        *,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
        results: Sequence[CommandResult] | None = None,
    ) -> None:
        self.default = CommandResult(returncode=returncode, stdout=stdout, stderr=stderr)
        self.results = list(results or [])
        self.calls: list[list[str]] = []

    def run(self, args: list[str], timeout_seconds: int) -> CommandResult:
        self.calls.append(args)
        return self.results.pop(0) if self.results else self.default


def test_discover_uses_argument_array_and_parses_json() -> None:
    runner = FakeRunner(stdout=SEARCH_JSON)
    gateway = OpenCliGateway(runner)

    items = gateway.discover("Apple iPhone 17 256GB", limit=30)

    assert runner.calls == [[
        "opencli",
        "price-compare-jd",
        "search",
        "Apple iPhone 17 256GB",
        "--limit",
        "30",
        "-f",
        "json",
    ]]
    assert items[0].platform_sku_id == "100000000001"
    assert items[0].initial_price_cents == 519900


def test_verify_passes_region_names_and_parses_offer() -> None:
    runner = FakeRunner(results=[
        CommandResult(returncode=0, stdout=SEARCH_JSON, stderr=""),
        CommandResult(returncode=0, stdout=VERIFY_JSON, stderr=""),
    ])
    gateway = OpenCliGateway(runner)

    offer = gateway.verify(
        gateway.discover("Apple iPhone 17 256GB", 30)[0],
        get_region_target("110100"),
    )

    assert runner.calls[-1] == [
        "opencli",
        "price-compare-jd",
        "verify",
        "100000000001",
        "--province",
        "北京市",
        "--city",
        "北京市",
        "--district",
        "朝阳区",
        "-f",
        "json",
    ]
    assert offer.sale_price_cents == 519900
    assert offer.stock_status == "in_stock"


@pytest.mark.parametrize(
    ("returncode", "stderr", "code"),
    [
        (66, "", "empty_result"),
        (69, "", "tool_unavailable"),
        (75, "", "network_error"),
        (77, "", "login_required"),
        (78, "", "tool_unavailable"),
        (1, '{"error":{"code":"CAPTCHA","message":"需要验证"}}', "captcha"),
        (1, '{"error":{"code":"PAGE_CHANGED","message":"结构变化"}}', "page_changed"),
        (1, '{"error":{"code":"UNSUPPORTED_REGION","message":"地区不可选"}}', "unsupported_region"),
    ],
)
def test_gateway_maps_structured_failures(returncode: int, stderr: str, code: str) -> None:
    gateway = OpenCliGateway(FakeRunner(returncode=returncode, stderr=stderr))

    with pytest.raises(GatewayFailure) as failure:
        gateway.discover("iPhone 17", 30)

    assert failure.value.code == code
    assert len(failure.value.safe_message) <= 300


def test_gateway_rejects_unknown_output_fields() -> None:
    rows = json.loads(SEARCH_JSON)
    rows[0]["cookie"] = "must-not-pass"
    gateway = OpenCliGateway(FakeRunner(stdout=json.dumps(rows, ensure_ascii=False)))

    with pytest.raises(GatewayFailure) as failure:
        gateway.discover("iPhone 17", 30)

    assert failure.value.code == "invalid_output"
    assert "must-not-pass" not in failure.value.safe_message


def test_gateway_rejects_overlong_query_before_starting_process() -> None:
    runner = FakeRunner(stdout=SEARCH_JSON)
    gateway = OpenCliGateway(runner)

    with pytest.raises(ValueError, match="200"):
        gateway.discover("x" * 201, 30)

    assert runner.calls == []


def test_subprocess_runner_never_uses_a_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        captured.update(kwargs)
        return subprocess.CompletedProcess(args, 0, "[]", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = SubprocessCommandRunner().run(["opencli", "list", "-f", "json"], 10)

    assert result.returncode == 0
    assert captured["args"] == ["opencli", "list", "-f", "json"]
    assert captured["shell"] is False
