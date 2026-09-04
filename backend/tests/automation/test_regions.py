import re

import pytest

from app.automation.regions import MAINLAND_REGION_TARGETS, get_region_target


def test_mainland_region_targets_are_exactly_31_unique_entries() -> None:
    assert len(MAINLAND_REGION_TARGETS) == 31
    assert [item.sequence for item in MAINLAND_REGION_TARGETS] == list(range(1, 32))
    assert len({item.region_code for item in MAINLAND_REGION_TARGETS}) == 31
    assert not {"香港特别行政区", "澳门特别行政区", "台湾省"} & {
        item.province for item in MAINLAND_REGION_TARGETS
    }
    assert all(item.street.strip() for item in MAINLAND_REGION_TARGETS)
    assert all(
        re.fullmatch(r"[1-9]\d*-[1-9]\d*-[1-9]\d*-(?:0|[1-9]\d*)", item.jd_area_id)
        for item in MAINLAND_REGION_TARGETS
    )


def test_region_catalog_uses_approved_representative_districts() -> None:
    beijing = get_region_target("110100")
    guangdong = get_region_target("440100")
    xinjiang = get_region_target("650100")

    assert (beijing.province, beijing.city, beijing.district) == ("北京市", "北京市", "朝阳区")
    assert (guangdong.province, guangdong.city, guangdong.district) == (
        "广东省",
        "广州市",
        "天河区",
    )
    assert (xinjiang.province, xinjiang.city, xinjiang.district) == (
        "新疆维吾尔自治区",
        "乌鲁木齐市",
        "天山区",
    )
    assert beijing.street == "奥运村街道"
    assert beijing.jd_area_id == "1-72-55652-0"
    assert guangdong.street == "天河南街道"
    assert guangdong.jd_area_id == "19-1601-3633-63249"
    assert xinjiang.street == "解放南路街道"
    assert xinjiang.jd_area_id == "31-2652-36684-60610"


def test_unknown_region_code_is_rejected() -> None:
    with pytest.raises(KeyError):
        get_region_target("000000")
