"""PDF text extraction, bounded (four-doors final review, minor 4).

Both upload endpoints are open to signed-out visitors, and a parse holds a
gunicorn thread for as long as it runs: reading stops after 30 pages, or once
the text reaches CV_TEXT_MAX characters, and the text is cut to CV_TEXT_MAX.
"""
import io
from unittest.mock import patch

import pdfplumber.page
import pytest

from app.services import pdf_service
from app.services.pdf_service import extract_text_from_pdf


def _pdf(pages: list[str]) -> bytes:
    """A minimal valid PDF, one line of Helvetica text per page. Built by hand:
    no PDF library is a dependency. Texts must not contain ( ) or \\."""
    first_page = 4                      # 1 catalog, 2 page tree, 3 font
    kids = " ".join(f"{first_page + 2 * i} 0 R" for i in range(len(pages)))
    bodies = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for i, text in enumerate(pages):
        content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
        bodies.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {first_page + 2 * i + 1} 0 R >>".encode()
        )
        bodies.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(bodies, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(bodies) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(bodies) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def _pages(n: int) -> list[str]:
    return [f"PAGE-{i:02d} experience" for i in range(1, n + 1)]


@pytest.fixture
def reads():
    """Every page.extract_text() call, by page number, the real one still run."""
    seen = []
    real = pdfplumber.page.Page.extract_text

    def counting(page, *args, **kwargs):
        seen.append(page.page_number)
        return real(page, *args, **kwargs)

    with patch.object(pdfplumber.page.Page, "extract_text", autospec=True, side_effect=counting):
        yield seen


def test_a_short_pdf_is_read_whole(app):
    assert extract_text_from_pdf(_pdf(_pages(3))) == "\n\n".join(_pages(3))


def test_only_the_first_30_pages_are_read(app, reads):
    text = extract_text_from_pdf(_pdf(_pages(40)))
    assert pdf_service.MAX_PAGES == 30
    assert reads == list(range(1, 31))
    assert "PAGE-30" in text and "PAGE-31" not in text


def test_reading_stops_once_the_text_reaches_cv_text_max(app, reads):
    # Each page reads "PAGE-NN experience": 18 characters, 20 with the blank
    # line that joins it to the previous one. Pages 1-3 make 58.
    app.config["CV_TEXT_MAX"] = 50
    text = extract_text_from_pdf(_pdf(_pages(10)))
    assert reads == [1, 2, 3]
    assert len(text) == 50
    assert text == "\n\n".join(_pages(3))[:50]


def test_one_long_page_is_cut_to_cv_text_max(app):
    app.config["CV_TEXT_MAX"] = 12
    assert extract_text_from_pdf(_pdf(["PAGE-01 experience professionnelle"])) == "PAGE-01 expe"


def test_text_exactly_at_the_cap_is_kept_whole(app):
    app.config["CV_TEXT_MAX"] = len("PAGE-01 experience")
    assert extract_text_from_pdf(_pdf(_pages(2))) == "PAGE-01 experience"


def test_a_parse_failure_is_still_an_empty_string(app):
    assert extract_text_from_pdf(b"not a pdf body") == ""


def test_the_open_upload_endpoint_returns_the_bounded_text(client, app):
    data = {"file": (io.BytesIO(_pdf(_pages(40))), "cv.pdf", "application/pdf")}
    res = client.post("/api/upload/cv", data=data, content_type="multipart/form-data")
    assert res.status_code == 200
    body = res.get_json()
    assert "PAGE-30" in body["cv_text"] and "PAGE-31" not in body["cv_text"]
    assert body["char_count"] == len(body["cv_text"])
