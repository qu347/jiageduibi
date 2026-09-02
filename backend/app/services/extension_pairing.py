import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.settings import AppSetting


PAIRING_KEY = "extension_pairing_code"
TOKEN_KEY = "extension_token_hash"


class PairingError(ValueError):
    pass


class PairingCodeConsumed(PairingError):
    pass


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_pairing_code(db: Session) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    set_setting(
        db,
        PAIRING_KEY,
        {
            "code_hash": hash_secret(code),
            "used": False,
            "created_at": datetime.now(UTC).isoformat(),
        },
    )
    db.commit()
    return code


def issue_extension_token(db: Session, code: str) -> str:
    setting = get_setting(db, PAIRING_KEY)
    if setting is None:
        raise PairingError("请先在本地设置页生成配对码")
    record = json.loads(setting.value_json)
    if record.get("used"):
        raise PairingCodeConsumed("配对码已使用")
    if not hmac.compare_digest(str(record.get("code_hash", "")), hash_secret(code)):
        raise PairingError("配对码不正确")

    token = secrets.token_urlsafe(32)
    record["used"] = True
    record["consumed_at"] = datetime.now(UTC).isoformat()
    setting.value_json = json.dumps(record)
    setting.updated_at = datetime.now(UTC)
    set_setting(db, TOKEN_KEY, {"token_hash": hash_secret(token)})
    db.commit()
    return token


def verify_extension_token(db: Session, token: str) -> bool:
    setting = get_setting(db, TOKEN_KEY)
    if setting is None:
        return False
    record = json.loads(setting.value_json)
    return hmac.compare_digest(str(record.get("token_hash", "")), hash_secret(token))


def get_setting(db: Session, key: str) -> AppSetting | None:
    return db.scalar(select(AppSetting).where(AppSetting.key == key))


def set_setting(db: Session, key: str, value: dict[str, object]) -> AppSetting:
    setting = get_setting(db, key)
    now = datetime.now(UTC)
    if setting is None:
        setting = AppSetting(key=key, value_json=json.dumps(value), updated_at=now)
        db.add(setting)
        db.flush()
    else:
        setting.value_json = json.dumps(value)
        setting.updated_at = now
    return setting
