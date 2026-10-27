"""Complaint-guidance chatbot request/response schemas.

The server is stateless: the client sends the recent conversation (and an
optional location) with every request.
"""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, model_serializer, model_validator

from app.schemas.office import OfficeOut

MAX_MESSAGES = 20
MAX_MESSAGE_LENGTH = 1000


def _clean(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Message cannot be empty")
    return cleaned


MessageText = Annotated[str, Field(max_length=MAX_MESSAGE_LENGTH), AfterValidator(_clean)]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: MessageText


class LocationInput(BaseModel):
    """Either browser coordinates (shared with permission) or typed locality / PIN code."""

    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    text: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _one_form(self) -> "LocationInput":
        has_coords = self.latitude is not None or self.longitude is not None
        if self.text is not None:
            self.text = " ".join(self.text.split()) or None
        if has_coords and (self.latitude is None or self.longitude is None):
            raise ValueError("Send both latitude and longitude")
        if has_coords and self.text:
            raise ValueError("Send either coordinates or a locality, not both")
        if not has_coords and not self.text:
            raise ValueError("Send coordinates or a locality / PIN code")
        if self.text is not None and len(self.text) < 3:
            raise ValueError("Locality must be at least 3 characters")
        return self


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_MESSAGES)
    location: LocationInput | None = None

    @model_validator(mode="after")
    def _ends_with_user(self) -> "ChatRequest":
        if self.messages[-1].role != "user":
            raise ValueError("The last message must be from the user")
        return self


class CategoryRef(BaseModel):
    id: int | None
    slug: str
    name: str


class ResolvedLocation(BaseModel):
    latitude: float
    longitude: float
    label: str | None = None
    source: Literal["device", "geocoded"]
    coordinates_source: str | None = None
    in_coverage_area: bool


class FileComplaintLink(BaseModel):
    category_id: int


class ChatResponse(BaseModel):
    reply: str
    intent: str
    category: CategoryRef | None
    needs_location: bool
    location: ResolvedLocation | None = None
    location_status: Literal["not_provided", "resolved", "not_found", "unavailable"] = "not_provided"
    offices: list[OfficeOut] = []
    channels: list[OfficeOut] = []
    steps: list[str] = []
    # Only present when document requirements are verified from an official source.
    documents: list[str] | None = None
    suggestions: list[str] = []
    disclaimer: str
    file_complaint: FileComplaintLink | None = None
    generated_by: Literal["template", "gemini"] = "template"

    @model_serializer(mode="wrap")
    def _omit_unverified_documents(self, handler):
        data = handler(self)
        if data.get("documents") is None:
            data.pop("documents", None)
        return data
