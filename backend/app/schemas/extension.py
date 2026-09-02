from pydantic import BaseModel, ConfigDict, Field

from app.schemas.offers import RawOffer


class PairingCodeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^\d{6}$")


class PairingTokenResponse(BaseModel):
    token: str


class PairingCodeResponse(BaseModel):
    code: str


class ExtensionOfferSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search_session_id: int = Field(gt=0)
    platform: str
    platform_name: str | None = None
    adapter_version: str = "extension-v1"
    items: list[RawOffer]
