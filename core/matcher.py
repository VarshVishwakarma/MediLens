import json
import re
import logging
from typing import List, Dict, Any

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

class MedicineMatcher:
    """
    An advanced, production-grade medicine name matching engine.
    Utilizes multi-strategy fuzzy matching, sliding n-gram windows,
    and OCR-specific text preprocessing to detect medicines in noisy text.
    """

    def __init__(self, json_path: str = "data/medicines.json"):
        """
        Initializes the matcher, loads the medicine database, and 
        pre-compiles normalized search terms for sub-millisecond matching.
        """
        self.medicines = self._load_medicines(json_path)
        self._compile_search_terms()

    def _load_medicines(self, json_path: str) -> Dict[str, Any]:
        """Loads the medicine JSON dataset safely with a built-in fallback."""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load {json_path} ({e}). Using default fallback dataset.")
            return {
                "paracetamol": {
                    "aliases": ["acetaminophen", "calpol", "dolo"],
                    "category": "analgesic"
                },
                "ibuprofen": {
                    "aliases": ["brufen", "advil"],
                    "category": "nsaid"
                },
                "amoxicillin": {
                    "aliases": ["amoxil", "trimox", "moxatag"],
                    "category": "antibiotic"
                }
            }

    def _compile_search_terms(self):
        """Normalizes and deduplicates all primary names and aliases at startup."""
        self.search_map = {}
        for primary_name, data in self.medicines.items():
            aliases = data.get("aliases", [])
            terms = [primary_name] + aliases
            
            # Reference terms don't get aggressive OCR letter replacements
            clean_terms = list(set([self.preprocess_text(t, is_query=False) for t in terms if t]))
            self.search_map[primary_name] = clean_terms

    def preprocess_text(self, text: str, is_query: bool = True) -> str:
        """
        Cleans text: lowercases, removes special chars, normalizes spaces.
        If is_query=True, corrects common OCR substitutions (0->o, 1->l, 5->s).
        """
        if not text:
            return ""
        
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        
        if is_query:
            # Aggressive OCR character correction for noisy input
            text = text.translate(str.maketrans('015', 'ols'))
            
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _get_sliding_windows(self, words: List[str], max_n: int = 4) -> List[str]:
        """Generates n-gram chunks from the text to catch fragmented words."""
        windows = []
        for n in range(1, max_n + 1):
            windows.extend([" ".join(words[i:i+n]) for i in range(len(words) - n + 1)])
        return windows

    def match(self, text: str, threshold: float = 65.0, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Executes a multi-strategy matching pipeline (Partial, Token, Sliding Window).
        Filters by dynamic thresholds, deduplicates, and ranks by confidence.
        """
        if not text:
            return []

        clean_text = self.preprocess_text(text, is_query=True)
        spaceless_text = clean_text.replace(" ", "")
        words = clean_text.split()
        
        # Generate sliding windows (1 to 4 words) for localized matching
        windows = self._get_sliding_windows(words, max_n=4)
        
        results = {}

        for primary_name, terms in self.search_map.items():
            best_score = 0.0
            best_match_type = ""
            best_fragment = ""

            for term in terms:
                # 1. Global Multi-Strategy Scoring
                strategies = [
                    (fuzz.partial_ratio(term, clean_text), "partial_ratio", clean_text),
                    (fuzz.token_set_ratio(term, clean_text), "token_set", clean_text),
                    (fuzz.token_sort_ratio(term, clean_text), "token_sort", clean_text)
                ]
                
                # 2. Spaceless Strategy (Captures extreme spacing like "p a r a c e t a m o l")
                term_spaceless = term.replace(" ", "")
                if len(term_spaceless) >= 4:
                    spaceless_score = fuzz.partial_ratio(term_spaceless, spaceless_text)
                    strategies.append((spaceless_score, "spaceless_partial", spaceless_text))

                # 3. Sliding Window Strategy (Captures localized broken chunks)
                for window in windows:
                    strategies.extend([
                        (fuzz.ratio(term, window), "window_ratio", window),
                        (fuzz.token_sort_ratio(term, window), "window_token_sort", window)
                    ])

                # Identify the highest scoring strategy for this specific term
                for score, match_type, fragment in strategies:
                    if score > best_score:
                        best_score = score
                        best_match_type = match_type
                        best_fragment = fragment

            # Dynamic Threshold Filter (Ignore matches below the minimum threshold)
            if best_score >= threshold:
                results[primary_name] = {
                    "name": primary_name,
                    "confidence": round(best_score, 2),
                    "match_type": best_match_type,
                    "matched_fragment": best_fragment,
                    "category": self.medicines[primary_name].get("category", "unknown")
                }

        # Deduplicate, rank descending by confidence, and truncate to top_k
        sorted_results = sorted(results.values(), key=lambda x: x["confidence"], reverse=True)
        return sorted_results[:top_k]

# ==============================================================================
# Execution Test Block
# ==============================================================================
if __name__ == "__main__":
    matcher = MedicineMatcher()
    
    # Simulating severe OCR noise and broken spacing
    test_text = "Take p a r a c e t a m 0 l s00mg twice daily and Ibu profen if pain persists. Also taking am0xil."
    
    print(f"Raw Input: '{test_text}'\n")
    matches = matcher.match(test_text, threshold=65.0)
    
    print("Detected Medicines:")
    print(json.dumps(matches, indent=2))
