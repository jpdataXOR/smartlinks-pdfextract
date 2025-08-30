import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import requests
import json
import io
import base64

# ======================
# Helper Class
# ======================
class GoogleFlashOCR:
    def __init__(self, api_key, model="google/gemini-2.5-flash-image-preview:free"):
        self.api_key = api_key
        self.model = model
        self.url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def extract_invoice_amount(self, image_bytes):
        # Encode image to base64
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        image_url = f"data:image/png;base64,{b64}"

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "You are an invoice extraction system. "
                                "From this invoice image, extract ONLY the total invoice amount "
                                "and return JSON in the form: {amount: <number>, coordinates: [x,y]}"
                            )
                        },
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
        }

        resp = requests.post(self.url, headers=self.headers, data=json.dumps(payload))
        if resp.status_code != 200:
            return {"error": resp.text}
        try:
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return {"error": str(e)}

# ======================
# Streamlit UI
# ======================
st.title("Invoice Amount Extractor (AI Only, Multi-Page PDF)")

# ✅ Use st.query_params (new API)
query_params = st.query_params
default_api_key = query_params.get("api_key", [None])[0] if "api_key" in query_params else None

# Show textbox for API key
api_key = st.text_input("OpenRouter API Key", value=default_api_key or "", type="password")

if not api_key:
    st.warning("⚠️ Please paste your OpenRouter API key above to continue.")
else:
    uploaded_file = st.file_uploader("Upload Invoice PDF", type=["pdf"])
    if uploaded_file:
        # Open PDF
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        st.write(f"📄 PDF has **{len(doc)} pages**")

        # Preview thumbnails
        st.subheader("Preview Pages")
        # Preview thumbnails (better resolution)
        st.subheader("Preview Pages")
        for i, page in enumerate(doc):
            # Use higher scale for clarity (2 = ~144 DPI)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            st.image(img, caption=f"Page {i+1}", use_container_width=True)


        if st.button("Extract with AI (all pages)"):
            gocr = GoogleFlashOCR(api_key=api_key)

            all_results = []
            for i, page in enumerate(doc):
                # Render page full res for AI
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # higher DPI
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                buf = io.BytesIO()
                img.save(buf, format="PNG")

                with st.spinner(f"Processing page {i+1}..."):
                    ai_result = gocr.extract_invoice_amount(buf.getvalue())

                all_results.append({"page": i+1, "result": ai_result})

            st.subheader("AI Extraction Results")
            st.json(all_results)
