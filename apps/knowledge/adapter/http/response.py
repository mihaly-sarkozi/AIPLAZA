from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class KBOut(BaseModel):
    uuid: str
    name: str
    description: Optional[str]
    qdrant_collection_name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
