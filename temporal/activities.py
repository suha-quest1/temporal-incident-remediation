from temporalio import activity
from temporal.logger import logger
from data.error_map import ERROR_MAP



#where do i put this?? oh this is where the logger message is supposed to go...smh
#logger.info(f"Classifying: {error_message}")

@activity.defn
async def classifyIncident(err_msg: str) -> dict:
    logger.info(f"Classifying incident: {err_msg}")
    
    error= err_msg.lower()
    for keyword, classification in ERROR_MAP.items():
        if keyword.lower() in error:
            return classification
        
    return { "incident_type": "Unknown", "severity": "P2"}
            
    