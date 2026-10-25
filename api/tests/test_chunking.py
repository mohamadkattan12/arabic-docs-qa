import pymupdf

from api.chunking import MAX_CHARS, OVERLAP, chunk_markdown, chunk_pdf, detect_lang, split_text

AR = "يحق للموظف الحصول على إجازة سنوية مدفوعة الأجر مدتها ثلاثون يوماً."


def test_markdown_chunks_carry_section_heading() -> None:
    chunks = chunk_markdown(
        f"intro text\n\n# الإجازات\n\n{AR}\n\n## Remote work\n\nTwo days.", "hr"
    )
    assert [c.location for c in chunks] == ["hr", "الإجازات", "Remote work"]
    assert chunks[1].content == f"الإجازات\n\n{AR}"


def test_long_paragraph_is_split_with_overlap() -> None:
    pieces = split_text("x" * (MAX_CHARS * 2))
    assert len(pieces) == 3
    assert all(len(p) <= MAX_CHARS for p in pieces)
    assert sum(len(p) for p in pieces) == MAX_CHARS * 2 + OVERLAP * 2


def test_paragraphs_are_grouped_up_to_limit() -> None:
    para = "word " * 300  # ~1500 chars
    assert len(split_text(f"{para}\n\n{para}\n\n{para}")) == 3


def test_detect_lang() -> None:
    assert detect_lang(AR) == "ar"
    assert detect_lang("Employees get 30 days of annual leave.") == "en"
    assert detect_lang(f"{AR} (Annual Leave Policy)") == "ar"


def test_pdf_chunks_are_cited_by_page() -> None:
    doc = pymupdf.open()
    for text in ("First page about leave.", "Second page about expenses."):
        doc.new_page().insert_text((72, 72), text)
    chunks = chunk_pdf(doc.tobytes())
    assert [(c.location, c.content.strip()) for c in chunks] == [
        ("page 1", "First page about leave."),
        ("page 2", "Second page about expenses."),
    ]
