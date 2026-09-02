from pydantic import BaseModel, ConfigDict, Field


class CatalogBrandInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)


class CatalogSeriesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brand: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)


class CatalogModelInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=160)
    code: str = Field(min_length=1, max_length=120)
    category: str = Field(default="手机", min_length=1, max_length=40)
    aliases: list[str] = Field(default_factory=list)


class CatalogVariantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_code: str = Field(min_length=1, max_length=120)
    sku_code: str = Field(min_length=1, max_length=120)
    storage: str = Field(min_length=1, max_length=32)
    memory: str | None = Field(default=None, max_length=32)
    color: str = Field(min_length=1, max_length=80)
    region_version: str = Field(min_length=1, max_length=80)
    condition: str = Field(min_length=1, max_length=32)


class CatalogImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brands: list[CatalogBrandInput] = Field(default_factory=list)
    series: list[CatalogSeriesInput] = Field(default_factory=list)
    models: list[CatalogModelInput] = Field(default_factory=list)
    variants: list[CatalogVariantInput] = Field(default_factory=list)


class CatalogVariantView(BaseModel):
    id: int
    sku_code: str
    storage: str
    memory: str | None
    color: str
    region_version: str
    condition: str


class CatalogModelSummary(BaseModel):
    id: int
    model_code: str
    model_name: str
    series_name: str
    brand: str
    category: str
    score: int
    variants: list[CatalogVariantView]


class CatalogSearchResponse(BaseModel):
    items: list[CatalogModelSummary]


class CatalogExport(BaseModel):
    brands: list[dict[str, str]]
    series: list[dict[str, str]]
    models: list[dict[str, object]]
    variants: list[dict[str, object]]
