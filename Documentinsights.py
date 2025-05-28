import streamlit as st  
from PyPDF2 import PdfReader
import tempfile
import os
import requests
from dotenv import load_dotenv
import pypandoc
import json

load_dotenv()

API_KEY = os.getenv("API_KEY")
PROJECT_ID = os.getenv("PROJECT_ID")

Insurance_Claim_Prompt = '''Summarixe and get key insights from the given document in all details in structured table format.: 
'''

# Function to extract text directly from PDF
def extract_text_from_pdf(uploaded_pdf):
    """Extract text directly from PDF without OCR"""
    try:
        reader = PdfReader(uploaded_pdf)
        total_pages = len(reader.pages)
        
        extracted_text = {}
        status = st.empty()
        
        for i, page in enumerate(reader.pages):
            status.markdown(f"📄 **Extracting text from Page {i+1}/{total_pages}...**")
            
            # Extract text directly from the page
            page_text = page.extract_text()
            
            if page_text.strip():  # Only add non-empty pages
                extracted_text[f"Page {i+1}"] = page_text
            else:
                extracted_text[f"Page {i+1}"] = "[No extractable text found on this page]"
        
        status.markdown("✅ **Text extraction completed!**")
        return extracted_text
        
    except Exception as e:
        st.error(f"Error extracting text from PDF: {str(e)}")
        return {}

def chunk_pages(extracted_dict, chunk_size=15):
    """Split pages into chunks for processing"""
    pages = list(extracted_dict.items())
    return [dict(pages[i:i + chunk_size]) for i in range(0, len(pages), chunk_size)]

def get_ibm_access_token(api_key):
    """Get IBM Watson access token"""
    url = "https://iam.cloud.ibm.com/identity/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
        "apikey": api_key
    }
    response = requests.post(url, headers=headers, data=data)
    return response.json()["access_token"]

def send_chunk_to_watsonx(chunk_text, access_token):
    """Send text chunk to Watson for analysis"""
    url = "https://us-south.ml.cloud.ibm.com/ml/v1/text/generation?version=2024-01-15"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}"
    }

    payload = {
        "input": Insurance_Claim_Prompt + "\n\nDOCUMENT CONTENT:\n" + chunk_text,
        "parameters": {
            "decoding_method": "greedy",
            "max_new_tokens": 8100,
            "min_new_tokens": 0,
            "stop_sequences": [],
            "repetition_penalty": 1
        },
        "model_id": "meta-llama/llama-3-3-70b-instruct",
        "project_id": PROJECT_ID
    }

    response = requests.post(url, headers=headers, json=payload)

    try:
        result = response.json()
        return result["results"][0]["generated_text"]
    except Exception as e:
        return f"[Watsonx response error: {str(e)} - Raw: {response.text}]"

def save_to_word_from_markdown(markdown_text, upload_file_name):
    """Convert markdown analysis to Word document"""
    try:
        pypandoc.download_pandoc()
        base_name = os.path.splitext(upload_file_name)[0]
        file_name = f"{base_name}_Insurance_Claim_Analysis.docx"
        output_path = os.path.join(os.getcwd(), file_name)
        pypandoc.convert_text(markdown_text, 'docx', format='md', outputfile=output_path)
        return output_path
    except Exception as e:
        st.error(f"Error creating Word document: {str(e)}")
        return None

# 🔥 Streamlit UI
st.set_page_config(page_title="Insurance Claim Analyzer", layout="wide")
st.title("🛡️ Insurance Claim Document Analyzer")
st.markdown("**Analyze insurance claim documents and extract key insights in structured table format**")

# File uploader
uploaded_file = st.file_uploader(
    "📄 Upload Insurance Claim PDF Document", 
    type=["pdf"],
    help="Upload a PDF containing insurance claim information"
)

if uploaded_file:
    # Extract text from PDF
    with st.spinner("📄 Extracting text from PDF..."):
        extracted_pages = extract_text_from_pdf(uploaded_file)
    
    if extracted_pages:
        # Show extracted text (optional, for debugging)
        with st.expander("🔍 View Extracted Text (Optional)"):
            for page_name, page_text in extracted_pages.items():
                st.subheader(page_name)
                st.text_area(f"Content of {page_name}", value=page_text[:1000] + "..." if len(page_text) > 1000 else page_text, height=200)
        
        try:
            # Get IBM Watson token
            with st.spinner("🔐 Getting IBM Watsonx Token..."):
                token = get_ibm_access_token(API_KEY)

            # Process text in chunks
            chunks = chunk_pages(extracted_pages, chunk_size=90)
            watsonx_outputs = []

            for i, chunk in enumerate(chunks):
                chunk_text = "\n".join(chunk.values())
                with st.spinner(f"🤖 Analyzing Chunk {i + 1} of {len(chunks)} with AI..."):
                    result = send_chunk_to_watsonx(chunk_text, token)
                    watsonx_outputs.append(result)

            # Combine results
            final_output = "\n\n".join(watsonx_outputs)
            
            # Display results
            st.subheader("📊 Insurance Claim Analysis Results")
            st.markdown(final_output)

            # Generate Word document
            if "word_generated" not in st.session_state:
                with st.spinner("📄 Generating Word document..."):
                    word_path = save_to_word_from_markdown(final_output, uploaded_file.name)
                    if word_path:
                        st.session_state.word_generated = True
                        st.session_state.word_path = word_path

            # Download button
            if "word_path" in st.session_state and os.path.exists(st.session_state.word_path):
                with open(st.session_state.word_path, "rb") as f:
                    st.download_button(
                        "📥 Download Analysis Report (Word)",
                        f,
                        file_name=os.path.basename(st.session_state.word_path),
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )

        except Exception as e:
            st.error(f"❌ Error during analysis: {e}")
    else:
        st.error("❌ No text could be extracted from the PDF. Please ensure the PDF contains readable text.")

# Footer
st.markdown("---")
st.markdown("*Insurance Claim Analyzer - Powered by AI*")