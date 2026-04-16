import json
import os

_medicines_cache = None
_instructions_cache = None

def get_medicines() -> dict:
    global _medicines_cache
    if _medicines_cache is None:
        try:
            with open("data/medicines.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                _medicines_cache = {str(k).lower(): v for k, v in data.items()}
        except Exception:
            _medicines_cache = {}
    return _medicines_cache

def get_instructions() -> dict:
    global _instructions_cache
    if _instructions_cache is None:
        try:
            with open("data/instructions.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                _instructions_cache = {str(k).lower(): v for k, v in data.items()}
        except Exception:
            _instructions_cache = {}
    return _instructions_cache
