import os
import json
import sys
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

# --- CONFIGURATION ---
# Define paths relative to this script
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "medical_knowledge_base")
JSON_SOURCE = os.path.join(BASE_DIR, "data", "medicines.json")
MODEL_NAME = "all-MiniLM-L6-v2"

def flatten_medicine_data(item: dict) -> str:
    """
    Converts structured JSON (WHO Schema) into a rich semantic text chunk for RAG.
    Handles nested dictionaries (dosage) and lists (aliases) to ensure the LLM
    receives a coherent text block.
    """
    name = item.get('name', 'Unknown')
    
    # Handle Aliases list
    aliases_list = item.get('aliases', [])
    aliases_str = ", ".join(aliases_list) if aliases_list else "None"
    
    # Handle Dosage dictionary (Adult vs Child)
    dosage_raw = item.get('dosage', 'N/A')
    if isinstance(dosage_raw, dict):
        dosage_str = f"Adults: {dosage_raw.get('adult', 'N/A')}; Children: {dosage_raw.get('child', 'N/A')}"
    else:
        dosage_str = str(dosage_raw)

    # Construct the semantic document
    # This text is what the AI actually "reads" during retrieval
    page_content = (
        f"Medicine Name: {name}\n"
        f"Aliases/Brand Names: {aliases_str}\n"
        f"Category: {item.get('category', 'N/A')}\n"
        f"Uses: {item.get('uses', 'N/A')}\n"
        f"Dosage Information: {dosage_str}\n"
        f"How to Take: {item.get('how_to_take', 'N/A')}\n"
        f"Side Effects: {item.get('side_effects', 'N/A')}\n"
        f"Warnings & Precautions: {item.get('warnings', 'N/A')}\n"
        f"Pregnancy Safety: {item.get('pregnancy', 'N/A')}\n"
        f"Source: {item.get('source', 'Manual')}"
    )
    return page_content

def load_data():
    """
    Loads and validates the medicines.json file.
    """
    if os.path.exists(JSON_SOURCE):
        print(f"📂 Loading data from: {JSON_SOURCE}")
        try:
            with open(JSON_SOURCE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Basic Schema Validation
            if "medicines" not in data:
                raise ValueError("❌ Invalid Schema: Missing 'medicines' root key in JSON.")
            
            meta = data.get("_meta", {})
            print(f"✅ Loaded Knowledge Base v{meta.get('version', '?')}")
            print(f"ℹ️  Source: {meta.get('source', 'Unknown')}")
            print(f"ℹ️  Disclaimer: {meta.get('disclaimer', 'None')}")
            
            return data["medicines"], meta
        except json.JSONDecodeError as e:
            print(f"❌ JSON Error: Could not parse medicines.json. Check syntax.\n{e}")
            return [], {}
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            return [], {}
    else:
        print(f"⚠️  File not found: {JSON_SOURCE}")
        print("Please ensure 'data/medicines.json' exists.")
        return [], {}

def create_vector_db():
    print("------------------------------------------------")
    print("   MediLens Knowledge Base Builder (Phase 1)    ")
    print("------------------------------------------------")
    
    print("⚙️  Initializing Embedding Model (this may take a moment)...")
    try:
        embeddings = HuggingFaceEmbeddings(model_name=MODEL_NAME)
    except Exception as e:
        print(f"❌ Failed to load embedding model: {e}")
        return

    # Load Data
    medical_data, meta_info = load_data()

    if not medical_data:
        print("❌ No data found to ingest. Aborting.")
        return

    documents = []
    print(f"🔄 Vectorizing {len(medical_data)} medicines...")
    
    for item in medical_data:
        # Create text chunk
        content = flatten_medicine_data(item)
        
        # Metadata is crucial for the ID Service to find names/aliases
        # We store aliases as a list so the Identify service can iterate over them
        metadata = {
            "name": item.get('name', 'Unknown'),
            "aliases": item.get('aliases', []), 
            "id": item.get('id', 'N/A'),
            "kb_version": meta_info.get("version", "1.0")
        }
        
        doc = Document(page_content=content, metadata=metadata)
        documents.append(doc)

    if not documents:
        print("❌ No documents created. Check data format.")
        return

    # Create and Save FAISS Index
    print(f"💾 Creating FAISS Index with {len(documents)} documents...")
    try:
        vector_store = FAISS.from_documents(documents, embeddings)
        
        # Ensure directory exists
        if not os.path.exists(DATA_PATH):
            os.makedirs(DATA_PATH)

        vector_store.save_local(DATA_PATH)
        print(f"✅ Knowledge Base successfully built and saved to:")
        print(f"   {DATA_PATH}")
        print("------------------------------------------------")
        print("Ready to launch platform.")
        
    except Exception as e:
        print(f"❌ Failed to save Vector Store: {e}")

if __name__ == "__main__":
    create_vector_db()