import streamlit as st
import requests

# --- CONFIGURATION ---
BACKEND_URL = "http://localhost:8000"

st.set_page_config(
    page_title="MediLens Platform",
    page_icon="💊",
    layout="centered"
)

def main():
    st.title("💊 MediLens – Prescription Scanner")
    st.markdown("Upload a prescription image to instantly extract text and identify medicines using our AI backend.")

    # --- FILE UPLOADER ---
    uploaded_file = st.file_uploader("Upload Medical Image", type=['png', 'jpg', 'jpeg'])

    if uploaded_file is not None:
        st.image(uploaded_file, caption="Uploaded Prescription", use_container_width=True)
        
        if st.button("🚀 Scan Prescription", type="primary"):
            with st.spinner("Processing image through backend API..."):
                try:
                    # Prepare the file for the API request
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                    response = requests.post(f"{BACKEND_URL}/scan", files=files, timeout=60)
                    
                    if response.status_code == 200:
                        result = response.json()
                        medicines = result.get("medicines", [])
                        extracted_text = result.get("text", "")
                        
                        st.success("✅ Scanning Complete!")
                        
                        # --- DISPLAY MEDICINES ---
                        st.subheader("🔍 Detected Medicines")
                        if medicines:
                            for med in medicines:
                                name = med.get("name", "Unknown")
                                score = med.get("score", 0)
                                st.markdown(f"- **{name}** (Confidence: {score}%)")
                        else:
                            st.warning("No medicines detected in this image.")
                            
                        # --- DISPLAY EXTRACTED TEXT ---
                        st.subheader("📄 Extracted Text")
                        if extracted_text.strip():
                            st.text_area("Raw Text", value=extracted_text, height=200, disabled=True)
                        else:
                            st.info("No readable text could be extracted.")
                            
                    else:
                        error_msg = "Unknown error occurred"
                        try:
                            error_msg = response.json().get("error", error_msg)
                        except ValueError:
                            pass
                        st.error(f"⚠️ API Error ({response.status_code}): {error_msg}")
                        
                except requests.exceptions.RequestException as e:
                    st.error(f"⚠️ Connection Error: Unable to reach the backend API. Ensure the server is running at {BACKEND_URL}. Details: {e}")

    # --- DISCLAIMER ---
    st.markdown("---")
    st.warning("⚠️ **MEDICAL DISCLAIMER:** This is not a medical diagnosis. The extracted information may contain inaccuracies. Always consult a certified doctor or pharmacist before taking any medication.")

if __name__ == "__main__":
    main()