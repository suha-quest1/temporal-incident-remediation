from dataclasses import dataclass

@dataclass
class IncidentDetails:
    alertId: str
    severity: str
    service: str
    errorMessage: str 
    runbookTags: list[str]

@dataclass
class OverrideSignal:
    action: str
    engineer: str