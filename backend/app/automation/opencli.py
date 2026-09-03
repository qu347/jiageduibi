from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.automation.contracts import (
    AutomationEnvironment,
    DiscoveredCandidate,
    GatewayFailure,
    VerifiedOffer,
)
from app.automation.regions import RegionTarget


MAX_OUTPUT_BYTES = 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 90
OPENCLI_EXECUTABLE = "opencli.cmd" if sys.platform == "win32" else "opencli"


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(self, args: list[str], timeout_seconds: int) -> CommandResult: ...


class SubprocessCommandRunner:
    def run(self, args: list[str], timeout_seconds: int) -> CommandResult:
        try:
            completed = subprocess.run(
                args,
                shell=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return CommandResult(returncode=75, stdout="", stderr="command timeout")
        except OSError:
            return CommandResult(returncode=78, stdout="", stderr="command unavailable")
        return CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


class CandidateOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform_sku_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=500)
    product_url: str = Field(min_length=1, max_length=2000)
    shop_name: str = Field(min_length=1, max_length=200)
    platform_shop_id: str | None = Field(default=None, max_length=160)
    shop_type: Literal["self_operated", "official_flagship", "authorized", "third_party"]
    initial_price_cents: int = Field(gt=0)


class VerifiedOfferOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform_sku_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=500)
    product_url: str = Field(min_length=1, max_length=2000)
    shop_name: str = Field(min_length=1, max_length=200)
    platform_shop_id: str | None = Field(default=None, max_length=160)
    shop_type: Literal["self_operated", "official_flagship", "authorized", "third_party"]
    listed_price_cents: int | None = Field(default=None, ge=0)
    sale_price_cents: int = Field(gt=0)
    merchant_discount_cents: int = Field(default=0, ge=0)
    platform_coupon_cents: int = Field(default=0, ge=0)
    member_discount_cents: int = Field(default=0, ge=0)
    payment_discount_cents: int = Field(default=0, ge=0)
    subsidy_amount_cents: int = Field(default=0, ge=0)
    subsidy_status: Literal["confirmed", "estimated", "unknown", "ineligible"] = "unknown"
    shipping_fee_cents: int = Field(default=0, ge=0)
    installation_fee_cents: int = Field(default=0, ge=0)
    conditional_price_cents: int | None = Field(default=None, ge=0)
    stock_status: str = Field(min_length=1, max_length=40)
    captured_at: datetime


_EXIT_FAILURES = {
    66: ("empty_result", "平台没有返回可用结果"),
    69: ("tool_unavailable", "浏览器桥接当前不可用"),
    75: ("network_error", "浏览器命令超时或网络异常"),
    77: ("login_required", "需要先在浏览器登录平台"),
    78: ("tool_unavailable", "OpenCLI 配置或命令不可用"),
}

_TOKEN_FAILURES = {
    "CAPTCHA": ("captcha", "需要在浏览器完成验证码"),
    "AUTH_REQUIRED": ("login_required", "需要先在浏览器登录平台"),
    "PAGE_CHANGED": ("page_changed", "平台页面结构已经变化"),
    "UNSUPPORTED_REGION": ("unsupported_region", "页面无法选择该代表地区"),
    "NETWORK_ERROR": ("network_error", "浏览器命令超时或网络异常"),
}


class OpenCliGateway:
    adapter_version = "price-compare-jd/0.1.0"

    def __init__(self, command_runner: CommandRunner) -> None:
        self._runner = command_runner

    def discover(self, query: str, limit: int) -> list[DiscoveredCandidate]:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            raise ValueError("查询内容不能为空")
        if len(normalized_query) > 200:
            raise ValueError("查询内容不能超过 200 个字符")
        if not 1 <= limit <= 50:
            raise ValueError("候选数量必须在 1 到 50 之间")

        rows = self._execute_rows(
            [
                OPENCLI_EXECUTABLE,
                "price-compare-jd",
                "search",
                normalized_query,
                "--limit",
                str(limit),
                "-f",
                "json",
            ],
            CandidateOutput,
        )
        return [DiscoveredCandidate(**row.model_dump()) for row in rows]

    def verify(
        self,
        candidate: DiscoveredCandidate,
        region: RegionTarget,
    ) -> VerifiedOffer:
        rows = self._execute_rows(
            [
                OPENCLI_EXECUTABLE,
                "price-compare-jd",
                "verify",
                candidate.platform_sku_id,
                "--province",
                region.province,
                "--city",
                region.city,
                "--district",
                region.district,
                "-f",
                "json",
            ],
            VerifiedOfferOutput,
        )
        if len(rows) != 1:
            raise GatewayFailure("invalid_output", "地区核验没有返回唯一商品结果")
        return VerifiedOffer(**rows[0].model_dump())

    def diagnose(self) -> AutomationEnvironment:
        agent_reach = self._runner.run(["agent-reach", "doctor", "--json"], 20)
        doctor = self._runner.run([OPENCLI_EXECUTABLE, "doctor"], 20)
        commands = self._runner.run(
            [OPENCLI_EXECUTABLE, "price-compare-jd", "--help", "-f", "json"],
            20,
        )

        agent_reach_available = agent_reach.returncode != 78
        opencli_available = doctor.returncode != 78
        browser_bridge_ready = doctor.returncode == 0
        plugin_ready = commands.returncode == 0 and self._plugin_commands_present(commands.stdout)

        if not agent_reach_available:
            message = "请先安装 Agent-Reach"
        elif not opencli_available:
            message = "请通过 Agent-Reach 安装 OpenCLI"
        elif not browser_bridge_ready:
            message = "请安装并连接 OpenCLI 浏览器扩展"
        elif not plugin_ready:
            message = "请运行自动采集安装脚本注册京东插件"
        else:
            message = "自动采集环境可用"
        return AutomationEnvironment(
            agent_reach_available=agent_reach_available,
            opencli_available=opencli_available,
            browser_bridge_ready=browser_bridge_ready,
            plugin_ready=plugin_ready,
            safe_message=message,
        )

    def _execute_rows[
        OutputModel: BaseModel
    ](self, args: list[str], model: type[OutputModel]) -> list[OutputModel]:
        result = self._runner.run(args, DEFAULT_TIMEOUT_SECONDS)
        if result.returncode != 0:
            self._raise_command_failure(result)
        if len(result.stdout.encode("utf-8")) > MAX_OUTPUT_BYTES:
            raise GatewayFailure("invalid_output", "OpenCLI 输出超过安全大小限制")
        try:
            payload = json.loads(result.stdout)
            if not isinstance(payload, list):
                raise TypeError("expected list")
            return [model.model_validate(item) for item in payload]
        except (json.JSONDecodeError, TypeError, ValidationError) as exc:
            raise GatewayFailure("invalid_output", "OpenCLI 返回的数据格式不符合报价契约") from exc

    @staticmethod
    def _raise_command_failure(result: CommandResult) -> None:
        mapped = _EXIT_FAILURES.get(result.returncode)
        if mapped is not None:
            raise GatewayFailure(*mapped)
        upper_error = result.stderr[:MAX_OUTPUT_BYTES].upper()
        for token, failure in _TOKEN_FAILURES.items():
            if token in upper_error:
                raise GatewayFailure(*failure)
        raise GatewayFailure("invalid_output", "OpenCLI 命令没有返回可识别结果")

    @staticmethod
    def _plugin_commands_present(raw_output: str) -> bool:
        if len(raw_output.encode("utf-8")) > MAX_OUTPUT_BYTES:
            return False
        try:
            payload = json.loads(raw_output)
        except json.JSONDecodeError:
            return False

        if not isinstance(payload, dict) or payload.get("site") != "price-compare-jd":
            return False
        commands = payload.get("commands")
        if not isinstance(commands, list):
            return False
        found = {
            command["name"]
            for command in commands
            if isinstance(command, dict) and isinstance(command.get("name"), str)
        }
        return {"search", "verify"} <= found
