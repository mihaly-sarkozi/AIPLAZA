from pydantic import BaseModel


class DemoUnsubscribeRequest(BaseModel):
    email: str
