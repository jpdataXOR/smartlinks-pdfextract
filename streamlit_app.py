import streamlit as st
import fitz  # PyMuPDF
import re
from PIL import Image

st.title("Invoice Amount Extractor")

# Upload PDF
uploaded_file = st.file_uploader("Upload Invoice PDF", type=["pdf"])
if uploaded_file:
    # Open PDF with PyMuPDF
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    
    # Convert first page to image for preview
    page = doc.load_page(0)
    pix = page.get_pixmap()
    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    st.image(image, caption="PDF First Page", use_container_width=True)

    # Extract text from all pages
    full_text = ""
    for page in doc:
        full_text += page.get_text()

    # Debug window hidden in an expander
    with st.expander("Show PDF Text (Debug)"):
        st.text_area("PDF Text", value=full_text, height=400)

    # --- Smarter invoice amount extraction ---
    priority_keywords = ["INVOICE TOTAL", "TOTAL", "AMOUNT DUE", "AMOUNT"]
    # Find all numbers in text with positions
    numbers = [(m.start(), m.group()) for m in re.finditer(r"[\d,.]+", full_text)]

    best_amount = None
    min_distance = float('inf')

    for kw in priority_keywords:
        for kw_match in re.finditer(kw, full_text, re.IGNORECASE):
            kw_pos = kw_match.start()
            for num_pos, num in numbers:
                # Skip numbers that are too long (ABN, phone, account numbers)
                if len(num.replace(",", "").replace(".", "").replace(" ", "")) > 8:
                    continue
                # Prefer numbers with decimals (likely invoice totals)
                if "." not in num:
                    continue
                # Find closest number to the keyword
                distance = abs(num_pos - kw_pos)
                if distance < min_distance:
                    min_distance = distance
                    best_amount = num

    if best_amount:
        st.success(f"Invoice Amount: {best_amount}")
    else:
        st.warning("Invoice amount not found.")