from app.models import Book, InspirationImage


async def test_inspiration_row_roundtrips_and_book_relationship(db_session):
    book = Book(title="B")
    db_session.add(book)
    await db_session.flush()
    img = InspirationImage(book_id=book.id, image_path="inspiration/x.png", caption="hi")
    glob = InspirationImage(book_id=None, image_path="inspiration/y.png")
    db_session.add_all([img, glob])
    await db_session.commit()

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    loaded = (await db_session.execute(
        select(Book).options(selectinload(Book.inspiration_images)).where(Book.id == book.id)
    )).scalar_one()
    assert [i.image_path for i in loaded.inspiration_images] == ["inspiration/x.png"]
    assert glob.book_id is None
