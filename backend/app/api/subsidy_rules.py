from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.catalog import get_db
from app.schemas.subsidy import SubsidyRuleInput, SubsidyRuleList, SubsidyRuleView
from app.services.subsidy_rules import create_rule, list_rules, update_rule


router = APIRouter(prefix="/api/subsidy-rules", tags=["subsidy-rules"])


@router.get("", response_model=SubsidyRuleList)
def get_rules(db: Session = Depends(get_db)) -> SubsidyRuleList:
    return SubsidyRuleList(items=list_rules(db))


@router.post("", response_model=SubsidyRuleView, status_code=status.HTTP_201_CREATED)
def post_rule(value: SubsidyRuleInput, db: Session = Depends(get_db)) -> SubsidyRuleView:
    return create_rule(db, value)


@router.put("/{rule_id}", response_model=SubsidyRuleView)
def put_rule(rule_id: int, value: SubsidyRuleInput, db: Session = Depends(get_db)) -> SubsidyRuleView:
    try:
        return update_rule(db, rule_id, value)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
