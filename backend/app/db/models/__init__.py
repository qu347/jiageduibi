from app.db.models.catalog import Brand, ProductAlias, ProductModel, ProductSeries, ProductVariant
from app.db.models.automation import CollectionCandidate, CollectionRegionTask, CollectionRun
from app.db.models.offers import (
    AdapterRun,
    ManualCorrection,
    Offer,
    OfferMatch,
    Platform,
    PlatformProduct,
    PriceComponent,
    PriceSnapshot,
    SearchSession,
    Shop,
)


__all__ = [
    "AdapterRun",
    "Brand",
    "CollectionCandidate",
    "CollectionRegionTask",
    "CollectionRun",
    "ManualCorrection",
    "Offer",
    "OfferMatch",
    "Platform",
    "PlatformProduct",
    "PriceComponent",
    "PriceSnapshot",
    "ProductAlias",
    "ProductModel",
    "ProductSeries",
    "ProductVariant",
    "SearchSession",
    "Shop",
]
