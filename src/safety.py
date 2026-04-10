from enum import Enum
from typing import Dict, List, Optional, Any, Tuple

# --- CONSTANTS ---
DISCLAIMER = "This system is for informational purposes only and is not a substitute for professional medical advice."

class FailurePolicy:
    """Defines strict safety thresholds for the MediLens system."""
    MIN_ID_CONFIDENCE: int = 65
    MAX_MEDICINES_RETURNED: int = 5
    MIN_TEXT_LENGTH: int = 3


class FailureMode(Enum):
    """Enumeration of possible critical failures during the extraction/identification pipeline."""
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    NO_TEXT_DETECTED = "NO_TEXT_DETECTED"
    TOO_MANY_MATCHES = "TOO_MANY_MATCHES"
    SYSTEM_ERROR = "SYSTEM_ERROR"


def validate_ocr_output(raw_text: str) -> Optional[FailureMode]:
    """
    Validates the extracted text from the OCR service.
    Returns NO_TEXT_DETECTED if the text is empty or falls below the minimum length.
    """
    if not raw_text or len(raw_text.strip()) < FailurePolicy.MIN_TEXT_LENGTH:
        return FailureMode.NO_TEXT_DETECTED
    return None


def validate_identification_results(results: List[Dict[str, Any]]) -> Tuple[Optional[FailureMode], List[Dict[str, Any]]]:
    """
    Validates the identified medicines.
    Ensures minimum confidence is met and caps the maximum number of returned items.
    """
    if not results:
        return FailureMode.LOW_CONFIDENCE, []
    
    # Check top candidate's score (assuming results are sorted by score descending)
    top_score = results[0].get("score", 0)
    if top_score < FailurePolicy.MIN_ID_CONFIDENCE:
        return FailureMode.LOW_CONFIDENCE, []
    
    # Trim results to the maximum allowed limit for safety/overload prevention
    if len(results) > FailurePolicy.MAX_MEDICINES_RETURNED:
        trimmed = results[:FailurePolicy.MAX_MEDICINES_RETURNED]
        return None, trimmed
        
    return None, results


def safe_response(data: Optional[Dict[str, Any]], failure: Optional[FailureMode]) -> Dict[str, Any]:
    """
    Formats the final output. If a failure exists, it structures a safe error message.
    Otherwise, returns the successful payload.
    """
    if failure:
        # Map failure modes to user-friendly safe messages
        messages = {
            FailureMode.LOW_CONFIDENCE: "Unable to confidently identify medicines. Please provide a clearer image.",
            FailureMode.NO_TEXT_DETECTED: "No readable text detected in the image. Ensure the image is focused and well-lit.",
            FailureMode.TOO_MANY_MATCHES: "Too many potential matches found. Results have been restricted for safety.",
            FailureMode.SYSTEM_ERROR: "An internal system error occurred while processing the request."
        }
        
        return {
            "status": "failure",
            "reason": failure.name,
            "message": messages.get(failure, "An unknown safety constraint was triggered.")
        }
        
    return {
        "status": "success",
        "data": data or {}
    }