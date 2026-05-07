from pydantic import BaseModel

class OverrideRequest(BaseModel):
    action: str
    engineer: str