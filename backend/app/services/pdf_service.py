import io

import pdfplumber
from flask import current_app

# Both upload endpoints are open to signed-out visitors (four-doors spec,
# ruling 1), and a parse holds one of gunicorn's gthread slots (2 workers x 8
# threads, shared with every multi-minute analysis stream) for as long as it
# runs. 10 MB of PDF can carry thousands of pages, and laying each one out
# could hold a slot for minutes. A CV is a few pages, and the submit refuses
# more than CV_TEXT_MAX characters anyway: reading stops at whichever of the
# two bounds comes first.
MAX_PAGES = 30


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Plain text from a PDF byte stream: at most its first MAX_PAGES pages,
    and at most CV_TEXT_MAX characters. Returns '' on parse failure."""
    limit = current_app.config["CV_TEXT_MAX"]
    try:
        text_parts = []
        length = 0          # of the joined text so far, separators included
        with pdfplumber.open(io.BytesIO(file_bytes), pages=list(range(1, MAX_PAGES + 1))) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    part = page_text.strip()
                    length += len(part) + (2 if text_parts else 0)
                    text_parts.append(part)
                    if length >= limit:
                        break
        return "\n\n".join(text_parts)[:limit]
    except Exception:
        return ""
