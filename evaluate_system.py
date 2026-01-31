import sys
import os
import time

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from src.platform_services import IdentificationService
    from src.safety import SafetyGuard, FailurePolicy, Severity
except ImportError:
    print("❌ Error: Could not import MediLens services. Run this from the project root.")
    sys.exit(1)

# --- TEST DATASETS ---

# 1. Identification Tests
# Format: (Input Text, Expected Medicine Name, Should Match?)
ID_TEST_CASES = [
    ("Please give me Paracetamol 500mg", "Paracetamol", True),
    ("I need Tylenol for my headache", "Paracetamol", True), # Alias Check
    ("Patient needs Amoxil 250mg three times daily", "Amoxicillin", True), # Alias Check
    ("Prescription: Lisinopril 10mg OD", "Lisinopril", True),
    ("Take one pill of Azithromycin", "Azithromycin", True),
    ("Random garbage text xyz 123", None, False), # Should Refuse
    ("I want a burger and fries", None, False), # Should Refuse
    ("Take Metformin 500mg with food", "Metformin", True)
]

# 2. Safety Interaction Tests
# Format: (List of Meds, Expect Warning?)
INTERACTION_TESTS = [
    (["Lisinopril", "Ibuprofen"], True), # Known interaction (Moderate)
    (["Paracetamol", "Amoxicillin"], False), # Safe combination
    (["Atorvastatin", "Azithromycin"], True), # Known interaction (Moderate)
    (["Levothyroxine", "Omeprazole"], True), # Absorption issue
    (["Cetirizine", "Loratadine"], False) # Generally safe (duplicate therapy warning maybe, but not high risk interaction in this DB)
]

def run_evaluation():
    print("==================================================")
    print("🧪  MediLens Medical-Grade System Evaluation      ")
    print("==================================================")
    print(f"Policy: Min Confidence Threshold = {FailurePolicy.MIN_ID_CONFIDENCE}%")
    print(f"Policy: High Risk Blocking = {FailurePolicy.BLOCK_HIGH_RISK}")
    print("--------------------------------------------------\n")
    
    # Initialize Services
    print("⚙️  Initializing Engine...")
    start_time = time.time()
    id_service = IdentificationService()
    safety = SafetyGuard(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
    print(f"✅ Services ready in {time.time() - start_time:.2f}s\n")
    
    # --- RUN ID TESTS ---
    print("--- 1. Identification & Refusal Accuracy ---")
    id_correct = 0
    
    for input_text, expected, should_match in ID_TEST_CASES:
        results = id_service.identify(input_text)
        matched = len(results) > 0
        top_match = results[0]['name'] if matched else None
        score = results[0]['score'] if matched else 0
        
        # Validation Logic
        success = False
        if should_match:
            if matched and top_match == expected:
                success = True
        else:
            if not matched: # We expected it to fail, and it did (Refusal success)
                success = True
            
        if success:
            id_correct += 1
            icon = "✅"
        else:
            icon = "❌"
            
        print(f"{icon} Input: '{input_text[:30]}...' -> Got: {top_match} ({score}%) | Expected: {expected}")

    id_accuracy = (id_correct / len(ID_TEST_CASES)) * 100
    print(f">> ID Accuracy: {id_accuracy:.1f}%\n")

    # --- RUN SAFETY TESTS ---
    print("--- 2. Safety Interaction Logic ---")
    safety_correct = 0
    
    for meds, expect_warning in INTERACTION_TESTS:
        report = safety.check_interactions(meds)
        has_warning = len(report["warnings"]) > 0
        
        success = (has_warning == expect_warning)
        if success:
            safety_correct += 1
            icon = "✅"
        else:
            icon = "❌"
            
        print(f"{icon} Meds: {meds} -> Warnings Found: {len(report['warnings'])}")

    safety_accuracy = (safety_correct / len(INTERACTION_TESTS)) * 100
    print(f">> Safety Logic Accuracy: {safety_accuracy:.1f}%\n")
    
    # --- SUMMARY ---
    print("==================================================")
    print("📊  FINAL SCORECARD")
    print("==================================================")
    print(f"Identification Accuracy: {id_accuracy:.1f}%")
    print(f"Safety Logic Accuracy:   {safety_accuracy:.1f}%")
    
    if id_accuracy == 100 and safety_accuracy == 100:
        print("\n🏆 RESULT: SYSTEM IS PRODUCTION READY")
    else:
        print("\n⚠️ RESULT: SYSTEM REQUIRES TUNING")

if __name__ == "__main__":
    run_evaluation()