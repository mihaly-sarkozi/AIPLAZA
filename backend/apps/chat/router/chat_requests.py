# Ez a fájl az adott modul HTTP útvonalait és kérés-válasz illesztését tartalmazza.
from pydantic import BaseModel, Field, model_validator

_MAX_QUESTION_CHARS = 2400
_MAX_HISTORY_ITEMS = 30
_MAX_HISTORY_CONTENT_CHARS = 1400
_MAX_RETRIEVAL_ITEMS = 20
_MAX_RETRIEVAL_ITEM_CHARS = 600


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=_MAX_QUESTION_CHARS, description="Non-empty question text")
    kb_uuid: str | None = Field(default=None, description="Opcionális tudástár UUID scope")
    debug: bool = Field(default=False, description="Debug context visszaadása")
    conversation_history: list[dict[str, str]] = Field(
        default_factory=list,
        max_length=_MAX_HISTORY_ITEMS,
        description="Korábbi chat kérdés-válasz előzmény",
    )
    retrieval_history: list[str] = Field(
        default_factory=list,
        max_length=_MAX_RETRIEVAL_ITEMS,
        description="Korábbi kérdésekből megőrzött Qdrant találati snippetek",
    )
    conversation_id: str | None = Field(default=None, description="Backend-managed chat session azonosító")
    channel_id: str | None = Field(default=None, description="Csatorna azonosító (pl. web, widget, api)")
    base_prompt_id: str | None = Field(default=None, description="Opcionális base prompt / policy azonosító")

    @model_validator(mode="after")
    def validate_payload_sizes(self) -> "AskRequest":
        for row in self.conversation_history:
            if not isinstance(row, dict):
                raise ValueError("conversation_history elemek csak objektumok lehetnek.")
            content = str(row.get("content") or row.get("text") or "")
            if len(content) > _MAX_HISTORY_CONTENT_CHARS:
                raise ValueError("conversation_history elem túl hosszú.")
        for item in self.retrieval_history:
            if len(str(item or "")) > _MAX_RETRIEVAL_ITEM_CHARS:
                raise ValueError("retrieval_history elem túl hosszú.")
        return self


class ChatFeedbackRequest(BaseModel):
    trace_id: str = Field(..., min_length=1)
    helpful: bool | None = None
    note: str | None = None


class ChannelCredentialCreateRequest(BaseModel):
    channel_type: str = Field(default="widget", description="widget vagy api")
    name: str = Field(..., min_length=1, max_length=120)
    allowed_kb_uuids: list[str] = Field(default_factory=list, description="Credential scope: engedélyezett tudástár UUID-k")
    daily_limit: int = Field(default=200, ge=1, le=100000, description="Credential scope: napi rate limit policy")
    per_minute_limit: int = Field(default=30, ge=1, le=10000, description="Credential scope: percenkénti rate limit policy")
    allowed_origins: list[str] = Field(default_factory=list, description="Widget esetén origin host lista")
    allowed_ip_ranges: list[str] = Field(default_factory=list, description="API credential IP allowlist CIDR lista")
    require_signed_requests: bool = Field(default=False, description="Credential scope: API credential HMAC signature + nonce replay védelem")
    expires_at: str | None = Field(default=None, description="ISO dátum/idő opcionális")

    @model_validator(mode="after")
    def validate_widget_origin_policy(self) -> "ChannelCredentialCreateRequest":
        channel_type = str(self.channel_type or "widget").strip().lower()
        if channel_type == "widget":
            if not list(self.allowed_origins or []):
                raise ValueError("Widget credentialhez legalább egy allowed_origin kötelező.")
            if any("*" in str(item or "") for item in self.allowed_origins):
                raise ValueError("Wildcard origin nem engedélyezett.")
        if channel_type == "api":
            if not list(self.allowed_ip_ranges or []) and not bool(self.require_signed_requests):
                raise ValueError("API credentialhez allowed_ip_ranges vagy require_signed_requests kötelező.")
        return self


class ChannelCredentialPolicyUpdateRequest(BaseModel):
    allowed_kb_uuids: list[str] | None = None
    daily_limit: int | None = Field(default=None, ge=1, le=100000)
    per_minute_limit: int | None = Field(default=None, ge=1, le=10000)
    allowed_origins: list[str] | None = None
    allowed_ip_ranges: list[str] | None = None
    require_signed_requests: bool | None = None
    expires_at: str | None = None

    @model_validator(mode="after")
    def validate_wildcard(self) -> "ChannelCredentialPolicyUpdateRequest":
        if self.allowed_origins is not None and any("*" in str(item or "") for item in self.allowed_origins):
            raise ValueError("Wildcard origin nem engedélyezett.")
        return self


class ChannelAskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=_MAX_QUESTION_CHARS, description="Non-empty question text")
    kb_uuid: str | None = Field(default=None, description="Opcionális tudástár UUID scope")
    debug: bool = Field(default=False, description="Debug context visszaadása")
    conversation_history: list[dict[str, str]] = Field(default_factory=list, max_length=_MAX_HISTORY_ITEMS)
    retrieval_history: list[str] = Field(default_factory=list, max_length=_MAX_RETRIEVAL_ITEMS)

    @model_validator(mode="after")
    def validate_payload_sizes(self) -> "ChannelAskRequest":
        for row in self.conversation_history:
            if not isinstance(row, dict):
                raise ValueError("conversation_history elemek csak objektumok lehetnek.")
            content = str(row.get("content") or row.get("text") or "")
            if len(content) > _MAX_HISTORY_CONTENT_CHARS:
                raise ValueError("conversation_history elem túl hosszú.")
        for item in self.retrieval_history:
            if len(str(item or "")) > _MAX_RETRIEVAL_ITEM_CHARS:
                raise ValueError("retrieval_history elem túl hosszú.")
        return self


class ChannelFeedbackCaptureRequest(BaseModel):
    query_run_id: str | None = None
    trace_id: str | None = None
    helpful: bool | None = None
    reason: str | None = None
    note: str | None = None


class ChannelFeedbackTriageRequest(BaseModel):
    triage_status: str = Field(default="reviewed", min_length=2, max_length=24)
    triage_owner: str | None = Field(default=None, max_length=120)
    triage_note: str | None = None
