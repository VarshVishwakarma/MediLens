import streamlit as st
import sys
import os
import time

# Ensure the current directory is in the Python path so we can import src modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the core logic services directly for Monolithic/Local Mode
# In a real distributed cloud setup, this file would make HTTP requests to api_server.py
try:
    from src.platform_services import OCRService, IdentificationService, KnowledgeService # type: ignore
except ImportError:
    st.error("⚠️ Critical Error: Core services not found.")
    st.info("Please make sure 'src/platform_services.py' exists.")
    st.stop()

# --- PLATFORM CONFIG ---
st.set_page_config(
    page_title="MediLens Platform", 
    page_icon="🩺", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS STYLING ---
st.markdown("""
    <style>
    .report-box { border-left: 5px solid #007bff; padding-left: 15px; background-color: #f8f9fa; }
    .disclaimer { font-size: 0.8em; color: #666; background-color: #fff3cd; padding: 10px; border-radius: 5px; margin-top: 20px;}
    </style>
    """, unsafe_allow_html=True)

# --- LAZY SERVICE INITIALIZATION (CRITICAL FIX) ---

@st.cache_resource
def load_services():
    print("🔥 Lazy loading services...")
    try:
        ocr = OCRService()
        ident = IdentificationService()
        rag = KnowledgeService()
        print("✅ Services loaded")
        return ocr, ident, rag
    except Exception as e:
        print("❌ Service init failed:", e)
        return None, None, None

def get_services():
    if "services" not in st.session_state:
        st.session_state.services = load_services()
    return st.session_state.services

# --- SESSION STATE ---
if 'scan_results' not in st.session_state: st.session_state.scan_results = []
if 'confirmed_meds' not in st.session_state: st.session_state.confirmed_meds = []
if 'chat_history' not in st.session_state: st.session_state.chat_history = []

# --- UI COMPONENTS ---

def sidebar_nav():
    with st.sidebar:
        st.title("🩺 MediLens")
        st.caption("Production Medical AI Platform")
        st.markdown("---")
        mode = st.radio("Select Mode", ["📸 Instant Scan", "💬 Knowledge Chat"])
        
        st.markdown("---")
        st.info(f"**Verified Database:** WHO EML (23rd Ed)")
        st.warning("**Status:** Online (Local Host)")
        
        # Manual Override
        if st.checkbox("Show Manual Context Selector"):
            _, id_engine, _ = get_services()
            
            if not id_engine:
                st.error("⚠️ Services not available")
            else:
                all_meds = list(id_engine.known_db.values())
                # Use set to dedup, sorted for neatness
                unique_meds = sorted(list(set(all_meds))) if all_meds else []
                selected = st.multiselect("Active Medicines:", unique_meds, default=st.session_state.confirmed_meds)
                # Sync selection
                if selected != st.session_state.confirmed_meds:
                    st.session_state.confirmed_meds = selected
                    st.rerun()
                
        return mode

def render_scan_mode():
    st.header("📸 Instant Prescription Analysis")
    st.markdown("Upload a printed box or handwritten prescription. The system uses **Hybrid OCR** to extract medical signals.")
    
    col1, col2 = st.columns([1, 1.2])
    
    with col1:
        uploaded_file = st.file_uploader("Upload Medical Image", type=['png', 'jpg', 'jpeg'])
        
        if uploaded_file:
            st.image(uploaded_file, caption="Source Image", use_column_width=True)
            if st.button("🚀 Analyze Image", type="primary"):
                with st.spinner("Running Hybrid OCR & Signal Extraction..."):
                    try:
                        ocr_engine, id_engine, rag_engine = get_services()

                        if not ocr_engine or not id_engine:
                            st.error("⚠️ Services not available")
                            return

                        # 1. Extraction
                        signals = ocr_engine.extract_signals(uploaded_file)
                        
                        if "error" in signals:
                            st.error(f"OCR Error: {signals['error']}")
                        else:
                            # 2. Identification
                            # Use raw text from signals
                            raw_text = signals.get('raw_text', '')
                            candidates = id_engine.identify(raw_text, threshold=60)
                            st.session_state.scan_results = candidates
                            
                            # Display extracted signals (Safety Transparency)
                            with st.expander("🔍 View Extracted Signals (Debug)"):
                                st.json(signals)
                                
                    except Exception as e:
                        st.error(f"Analysis Failed: {str(e)}")

    with col2:
        if st.session_state.scan_results:
            st.subheader("🔍 Identified Candidates")
            st.info("Please confirm the medicines detected below:")
            
            for cand in st.session_state.scan_results:
                name = cand['name']
                score = cand['score']
                
                # Confidence Meter
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.progress(score)
                    st.caption(f"Confidence: {score}%")
                with col_b:
                    # If already confirmed, show checkmark
                    if name in st.session_state.confirmed_meds:
                        st.success("Confirmed")
                    else:
                        if st.button(f"Confirm {name}", key=f"confirm_{name}"):
                            st.session_state.confirmed_meds.append(name)
                            st.rerun()
            
        elif uploaded_file and not st.session_state.scan_results:
             st.warning("No high-confidence matches found. Try Manual Search in sidebar.")

        # Confirmed List & Report Generation
        if st.session_state.confirmed_meds:
            st.markdown("---")
            st.success(f"**Active Context:** {', '.join(st.session_state.confirmed_meds)}")
            
            if st.button("📄 Generate Clinical Report", type="primary"):
                with st.spinner("Retrieving verified WHO data..."):
                    try:
                        _, _, rag_engine = get_services()

                        if not rag_engine:
                            st.error("⚠️ AI engine not available")
                            return

                        report_text = rag_engine.get_analysis(st.session_state.confirmed_meds)
                        
                        # Display as a chat message for consistency
                        st.session_state.chat_history.append({"role": "ai", "content": report_text})
                        
                        # Render here
                        st.markdown(f"<div class='report-box'>{report_text}</div>", unsafe_allow_html=True)
                        
                    except Exception as e:
                        st.error(f"Report Generation Error: {e}")

def render_chat_mode():
    st.header("💬 Verified Medical Chat")
    
    if not st.session_state.confirmed_meds:
        st.info("👈 Please select medicines using **Instant Scan** or the **Manual Selector** in the sidebar to start a context-aware chat.")
    else:
        st.write(f"Context: **{', '.join(st.session_state.confirmed_meds)}**")

    # Render History
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat Input
    user_query = st.chat_input("Ask about dosage, side effects, or interactions...")
    
    if user_query:
        # Display User Message
        st.session_state.chat_history.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)
        
        # Generate Answer
        with st.chat_message("ai"):
            with st.spinner("Consulting Knowledge Base..."):
                if not st.session_state.confirmed_meds:
                    response = "Please select a medicine context first."
                else:
                    try:
                        _, _, rag_engine = get_services()

                        if not rag_engine:
                            response = "⚠️ AI system not ready."
                        else:
                            response = rag_engine.get_analysis(st.session_state.confirmed_meds, user_query)
                    except Exception as e:
                        response = f"Error generating response: {str(e)}"
                
                st.markdown(response)
                st.session_state.chat_history.append({"role": "ai", "content": response})

# --- MAIN APP ---
def main():
    mode = sidebar_nav()
    
    if mode == "📸 Instant Scan":
        render_scan_mode()
    elif mode == "💬 Knowledge Chat":
        render_chat_mode()
        
    # Footer Disclaimer
    st.markdown("---")
    st.markdown("""
    <div class="disclaimer">
    <strong>🚨 MEDICAL DISCLAIMER:</strong> This AI system is for educational/informational purposes only. 
    It identifies medicines based on visual signals and retrieves standard data from the WHO Essential Medicines List. 
    It DOES NOT diagnose conditions or prescribe treatments. 
    Always consult a licensed physician or pharmacist before taking any medication.
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
