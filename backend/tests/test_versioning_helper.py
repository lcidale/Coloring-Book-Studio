"""Unit tests for the shared record_version helper.

Uses the existing db_session fixture (isolated AsyncSession with tables created)
from conftest.py — does NOT use SessionLocal directly.
"""
import pytest
import types

from app.models import Book, Page, PageVersion
from app.services.versioning import record_version

pytestmark = pytest.mark.asyncio


async def test_record_version_sets_metadata_on_version_and_page(db_session):
    # Arrange: create a Book and Page in the test session
    book = Book(title="Test Book")
    db_session.add(book)
    await db_session.flush()

    page = Page(book_id=book.id, concept="a cute bear")
    db_session.add(page)
    await db_session.flush()

    report = types.SimpleNamespace(
        dpi=300,
        width_px=2550,
        height_px=3300,
        is_pure_bw=True,
        issues=[],
    )

    # Act
    pv = record_version(
        db_session,
        page,
        1,
        "books/b/p/v001.png",
        "books/b/p/v001.svg",
        "the prompt",
        report,
    )
    await db_session.commit()
    await db_session.refresh(pv)

    # Assert: PageVersion metadata
    assert pv.dpi == 300
    assert pv.width_px == 2550
    assert pv.height_px == 3300
    assert pv.is_pure_bw is True
    assert pv.prompt == "the prompt"
    assert pv.image_path == "books/b/p/v001.png"
    assert pv.svg_path == "books/b/p/v001.svg"
    assert pv.version_num == 1

    # Assert: Page fields updated
    assert page.image_path == "books/b/p/v001.png"
    assert page.image_dpi == 300
    assert page.image_width_px == 2550
    assert page.image_height_px == 3300
    assert page.is_pure_bw is True
    assert page.print_check_notes == "Passed"


async def test_record_version_with_issues(db_session):
    """When report.issues is non-empty, print_check_notes joins them."""
    book = Book(title="B2")
    db_session.add(book)
    await db_session.flush()

    page = Page(book_id=book.id, concept="dragon")
    db_session.add(page)
    await db_session.flush()

    report = types.SimpleNamespace(
        dpi=150,
        width_px=1200,
        height_px=1600,
        is_pure_bw=False,
        issues=["DPI too low", "Gray pixels detected"],
    )

    pv = record_version(
        db_session,
        page,
        2,
        "books/b2/p/v002.png",
        None,
        "negative prompt test",
        report,
    )
    await db_session.commit()
    await db_session.refresh(pv)

    assert pv.dpi == 150
    assert pv.is_pure_bw is False
    assert pv.svg_path is None
    assert page.print_check_notes == "DPI too low; Gray pixels detected"
    assert page.image_dpi == 150
