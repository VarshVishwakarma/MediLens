import json
import os
import re
from typing import List, Dict, Any, Optional
from enum import Enum

class Severity(str, Enum):
    INFO = "Informational"
    CAUTION = "Caution"
    HIGH_RISK = "High Risk"

class FailureMode(str, Enum):
    LOW_CONFIDENCE = "OCR/ID Confidence Below Threshold"
    AMBIGUOUS_MATCH = "Multiple Conflicting Candidates"
    MISSING_DATA = "Medicine Not in Verified Database"
    RETRIEVAL_FAILURE = "RAG Retrieval Yielded Zero Context"
    SAFETY_BLOCK = "High Risk Interaction Detected"
    POLICY_VIOLATION = "Request Violates Usage Policy (e.g. Diagnosis)"

class FailurePolicy:
    """
    Defines the non-negotiable thresholds for system failure.
    Changes here affect the entire platform's safety profile.
    """
    MIN_ID_CONFIDENCE = 65  # Percent (Strict refusal below this)
    MIN_RETRIEVAL_DOCS = 1  # Absolute count
    BLOCK_HIGH_RISK = True  # Strict blocking for high risk interactions

class SafetyGuard:
    """
    Governance Engine for MediLens.
    Enforces Safety, Interactions, and Disclaimers.
    """

    def __init__(self, data_path: str):
        self.interactions_file = os.path.join(data_path, "interactions.json")
        self.interactions_db = self._load_interactions()
        
        # Hardcoded disclaimer (Immutable)
        self.disclaimer_text = (
            "\n\n---\n"
            "**🚨 MEDICAL DISCLAIMER:** "
            "This system extracts text signals and retrieves verified WHO/FDA data. "
            "It is NOT a doctor. It does NOT diagnose, prescribe, or recommend treatment. "
            "If you feel unwell, contact a professional immediately."
        )

        # Regex patterns for refusal (Diagnosis attempts)
        self.diagnosis_patterns = [
            r"do i have \w+",
            r"is this \w+ serious",
            r"what is this rash",
            r"diagnose me",
            r"symptoms of",
            r"treatment for \w+$" # e.g. "treatment for flu" -> Refuse
        ]

    def _load_interactions(self) -> List[Dict]:
        if not os.path.exists(self.interactions_file):
            return []
        try:
            with open(self.interactions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def check_policy_violation(self, query: str) -> Optional[str]:
        """
        Checks if a user query violates the "No Diagnosis" contract.
        Returns a refusal message if violated, None otherwise.
        """
        if not query:
            return None
        
        q_lower = query.lower()
        for pattern in self.diagnosis_patterns:
            if re.search(pattern, q_lower):
                return (
                    "⚠️ REFUSAL: I cannot answer diagnostic questions. "
                    "I can only explain the uses and dosage of specific medicines found in my verified database."
                )
        return None

    def check_interactions(self, selected_meds: List[str]) -> Dict[str, Any]:
        """
        Checks for interactions. Returns a structured safety report.
        """
        report = {
            "status": "safe",
            "warnings": [],
            "highest_severity": None,
            "block_action": False
        }
        
        if len(selected_meds) < 2:
            return report

        selected_set = set(m.lower() for m in selected_meds)

        for rule in self.interactions_db:
            rule_meds = set(m.lower() for m in rule.get("medications", []))
            
            if rule_meds.issubset(selected_set):
                sev = rule.get("severity", "Caution")
                warning = {
                    "severity": sev,
                    "description": rule.get("description", "Interaction detected."),
                    "meds": rule.get("medications")
                }
                report["warnings"].append(warning)
                
                # Logic for Highest Severity
                if sev == Severity.HIGH_RISK:
                    report["highest_severity"] = Severity.HIGH_RISK
                    if FailurePolicy.BLOCK_HIGH_RISK:
                        report["block_action"] = True
                        report["status"] = "blocked"
                elif sev == Severity.CAUTION and report["highest_severity"] != Severity.HIGH_RISK:
                    report["highest_severity"] = Severity.CAUTION
                    if report["status"] != "blocked":
                        report["status"] = "warning"

        return report

    def inject_disclaimer(self, text: str) -> str:
        if self.disclaimer_text.strip() in text:
            return text
        return text + self.disclaimer_text

    @staticmethod
    def validate_schema(data: dict) -> bool:
        required_fields = ["name", "uses", "dosage", "side_effects", "warnings"]
        if "medicines" not in data: return False
        for item in data["medicines"]:
            for field in required_fields:
                if field not in item: return False
        return True