import json
import re
import logging
from typing import List, Dict, Any

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

class MedicineMatcher:
    """
    A robust, production-grade medicine name matching engine.
    Uses a multi-layered approach (Exact, Space-Invariant, Substring, Fuzzy)
    to identify medicine names from noisy OCR text.
    """

    def __init__(self, json_path: str = "data/medicines.json"):
        """
        Initializes the matcher by loading the database and pre-compiling 
        search terms to ensure blazing fast per-request execution.
        """
        self.medicines = self._load_medicines(json_path)
        self._compile_search_terms()

    def _load_medicines(self, json_path: str) -> Dict[str, Any]:
        """
        Loads the medicine JSON dataset safely. Includes a fallback dataset
        for immediate testing if the file hasn't been created yet.
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load {json_path} ({e}). Using default fallback dataset.")
            # Fallback dataset matching your requirements structure
            return {
                "paracetamol": {
                    "aliases": ["acetaminophen", "calpol", "dolo"],
                    "category": "analgesic"
                },
                "ibuprofen": {
                    "aliases": ["brufen", "advil"],
                    "category": "nsaid"
                }
            }

    def _compile_search_terms(self):
        """
        Pre-computes and normalizes all primary names and aliases at startup.
        Avoids redundant string manipulation during active requests.
        """
        self.search_map = {}
        for primary_name, data in self.medicines.items():
            aliases = data.get("aliases", [])
            
            # Pool primary name and its aliases together
            terms = [primary_name] + aliases
            
            # Clean all terms and remove duplicates within the same medicine group
            clean_terms = list(set([self.preprocess_text(t) for t in terms if t]))
            self.search_map[primary_name] = clean_terms

    def preprocess_text(self, text: str) -> str:
        """
        Cleans OCR text: lowercase, remove special characters, and normalize spaces.
        """
        if not text:
            return ""
        
        # 1. Lowercase
        text = text.lower()
        # 2. Remove special characters (keep only alphanumeric and spaces)
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        # 3. Normalize multiple spaces to a single space
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def _extract_context(self, text: str, start_idx: int, end_idx: int) -> str:
        """
        Determines the semantic context of the matched medicine by analyzing 
        a sliding window of surrounding words.
        """
        if start_idx < 0 or end_idx < 0:
            return "general"
            
        # Extract a 40-character window on either side of the matched term
        window_start = max(0, start_idx - 40)
        window_end = min(len(text), end_idx + 40)
        window = text[window_start:window_end]
        
        scores = {"dosage": 0, "instruction": 0, "warning": 0}
        
        # Simple but effective keyword flags
        if re.search(r'\b(mg|ml|g|mcg|twice|daily|dose|tablet|pill|drops)\b', window):
            scores["dosage"] += 1
        if re.search(r'\b(take|apply|drink|use|after|before|meal|morning|night)\b', window):
            scores["instruction"] += 1
        if re.search(r'\b(if|pain|persists|warning|caution|avoid|stop|severe)\b', window):
            scores["warning"] += 1
            
        best_context = max(scores, key=scores.get)
        return best_context if scores[best_context] > 0 else "general"

    def match(self, text: str, threshold: float = 0.70) -> List[Dict[str, Any]]:
        """
        Executes the 4-step matching pipeline against the input text.
        Returns a sorted, deduplicated list of detected medicines with smart confidence and positions.
        """
        if not text:
            return []

        # Process input text into comparable variants
        text_clean = self.preprocess_text(text)
        text_spaceless = text_clean.replace(" ", "")
        text_tokens = text_clean.split()
        
        results = {}

        for primary_name, terms in self.search_map.items():
            best_score = 0.0
            best_match_type = ""
            best_start = -1
            best_end = -1

            for term in terms:
                score = 0.0
                match_type = ""
                start, end = -1, -1
                
                term_spaceless = term.replace(" ", "")
                is_substring = term in text_clean
                is_space_invariant = (term_spaceless in text_spaceless) and (len(term_spaceless) >= 4)
                
                # ---------------------------------------------------------
                # LAYER 1: Exact Match (1.0) - Direct word match 
                # ---------------------------------------------------------
                exact_match = re.search(r'\b' + re.escape(term) + r'\b', text_clean)
                if exact_match:
                    score, match_type = 1.0, "exact"
                    start, end = exact_match.start(), exact_match.end()
                    
                # ---------------------------------------------------------
                # LAYER 2: Space-Invariant Match (0.95) - Handles "P a r a"
                # ---------------------------------------------------------
                elif is_space_invariant and not is_substring:
                    score, match_type = 0.95, "space_invariant"
                    pattern = r'\s*'.join(map(re.escape, term_spaceless))
                    si_match = re.search(pattern, text_clean)
                    if si_match:
                        start, end = si_match.start(), si_match.end()
                    
                # ---------------------------------------------------------
                # LAYER 3: Substring Match (0.90) - Embedded inside a word
                # ---------------------------------------------------------
                elif is_substring:
                    score, match_type = 0.90, "substring"
                    start = text_clean.find(term)
                    end = start + len(term)
                    
                # ---------------------------------------------------------
                # LAYER 4: Fuzzy Match (Normalized) - Handles misspellings
                # ---------------------------------------------------------
                else:
                    # Check sliding window partial ratio for compound misspellings
                    partial_score = fuzz.partial_ratio(term, text_clean) / 100.0
                    
                    # Check direct token ratio for precise word-level misspellings
                    best_token_score = 0.0
                    best_token = ""
                    for t in text_tokens:
                        ts = fuzz.ratio(term, t) / 100.0
                        if ts > best_token_score:
                            best_token_score = ts
                            best_token = t
                    
                    if best_token_score >= partial_score:
                        score, match_type = best_token_score, "fuzzy"
                        if best_token:
                            start = text_clean.find(best_token)
                            end = start + len(best_token)
                    else:
                        score, match_type = partial_score, "fuzzy"
                        if best_token: # Fallback approximation for partial bounds
                            start = text_clean.find(best_token)
                            end = start + len(best_token)

                # Track the highest scoring alias/term for this specific medicine
                if score > best_score:
                    best_score = score
                    best_match_type = match_type
                    best_start = start
                    best_end = end

            # If the ultimate best score clears the threshold, add to results
            if best_score >= threshold:
                context = self._extract_context(text_clean, best_start, best_end)
                results[primary_name] = {
                    "name": primary_name,
                    "confidence": round(best_score, 2),
                    "match_type": best_match_type,
                    "position": {
                        "start": best_start,
                        "end": best_end
                    },
                    "context": context,
                    "category": self.medicines[primary_name].get("category", "unknown")
                }

        # Deduplicate (implicitly handled by dict keys) and sort descending by confidence
        sorted_results = sorted(results.values(), key=lambda x: x["confidence"], reverse=True)
        
        return sorted_results

# ==============================================================================
# Execution Test Block
# ==============================================================================
if __name__ == "__main__":
    # Initialize the matcher
    matcher = MedicineMatcher()
    
    # Run the noisy OCR test case
    test_text = "Take P a r a c e t a m o l 500mg twice daily and Ibu profen if pain persists"
    
    print(f"Raw Input: '{test_text}'\n")
    
    matches = matcher.match(test_text)
    
    print("Detected Medicines:")
    print(json.dumps(matches, indent=2))