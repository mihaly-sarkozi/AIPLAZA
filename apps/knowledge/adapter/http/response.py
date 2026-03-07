from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class KBOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: str
    name: str
    description: Optional[str]
    qdrant_collection_name: str
    created_at: datetime
    updated_at: datetime
