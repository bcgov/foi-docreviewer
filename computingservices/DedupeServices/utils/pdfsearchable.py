def needs_ocr(doc):
    try:
        for page in doc:
            if not page.get_text():  # If no text found, this page is likely scanned
                return True
        return False  # All checked pages contain text, assume searchable
    except Exception as e:
        print(f"Error while parsing and searching PDF: {e}")
        return None  # Handle errors safely

def has_fillable_forms(doc):
    try:
        # for page in doc.pages():
        #     if page.widgets():
        #         print("??",len(list(page.widgets())))
        #         for widget in page.widgets():
        #             print("\n-->",widget)
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