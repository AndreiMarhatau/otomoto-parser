from pydantic import BaseModel, HttpUrl


class CreateRequestPayload(BaseModel):
    url: HttpUrl


class CategoryPayload(BaseModel):
    name: str


class ListingCategoriesPayload(BaseModel):
    categoryIds: list[str]


class VehicleReportLookupPayload(BaseModel):
    registrationNumber: str
    dateFrom: str
    dateTo: str


class SettingsPayload(BaseModel):
    openaiApiKey: str | None = None
