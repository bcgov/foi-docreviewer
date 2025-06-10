# def needs_ocr1(doc):
#     try:
#         for page in doc:
#             print("\nneeds_ocr-page:",page)
#             if not page.get_text():  # If no text found, this page is likely scanned
#                 return True
#         print("\nneeds_ocr-false")
#         return False  # All checked pages contain text, assume searchable
#     except Exception as e:
#         print(f"Error while parsing and searching PDF: {e}")
#         return None  # Handle errors safely
    

def needs_ocr(doc):
    try:
        for page in doc:
            blocks = page.get_text("dict")["blocks"]
            has_text = any(b["type"] == 0 and b.get("text", "").strip() for b in blocks)
            has_images = bool(page.get_images(full=True))
            if not has_text and has_images:
                return True  # OCR needed
        return False  # All pages have text
    except Exception as e:
        print(f"Error checking OCR : {e}")
        return None

def has_fillable_forms(doc):
    try:
        # for page in doc.pages():
        #     if page.widgets():
        #         print("??",len(list(page.widgets())))
        #         for widget in page.widgets():
        #             print("\n-->",widget)
        print("has_fillable_forms->>",(len(list(page.widgets()))>0 for page in doc.pages()))
        return any(len(list(page.widgets()))>0 for page in doc.pages())  # Check if any page has form fields
    except Exception as e:
        print(f"Error while parsing and searching PDF: {e}")
        return None
    
def is_pdf_searchable(doc):
    try:
        for page in doc:
            if page.get_text("text"):  # Extracts selectable text
                return True  # PDF is searchable
        return False  # No selectable text found, likely a scanned image
    except Exception as e:
        print(f"Error while parsing and searching PDF: {e}")
        return None