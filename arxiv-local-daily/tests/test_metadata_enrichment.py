from arxiv_local_daily.models import PaperMetadata, PaperVersionInput
from arxiv_local_daily.repositories import PaperRepository


def test_upsert_metadata_updates_paper_and_versions(db):
    repo = PaperRepository(db)
    metadata = PaperMetadata(
        arxiv_id="2606.00001",
        title="Title",
        abstract="Abstract",
        authors=["Ada Lovelace"],
        primary_category="cs.AI",
        categories=["cs.AI", "cs.LG"],
        abs_url="http://arxiv.org/abs/2606.00001v1",
        pdf_url="http://arxiv.org/pdf/2606.00001v1",
        published_at="2026-06-02T00:00:00Z",
        updated_at="2026-06-03T00:00:00Z",
        versions=[
            PaperVersionInput(
                version="v1",
                updated_at="2026-06-03T00:00:00Z",
                comment="12 pages",
            )
        ],
    )

    repo.upsert_metadata(metadata)

    paper = db.execute("SELECT * FROM papers WHERE arxiv_id = ?", ("2606.00001",)).fetchone()
    version = db.execute("SELECT * FROM paper_versions WHERE arxiv_id = ?", ("2606.00001",)).fetchone()

    assert paper["metadata_status"] == "complete"
    assert paper["title"] == "Title"
    assert paper["authors_json"] == '["Ada Lovelace"]'
    assert paper["categories_json"] == '["cs.AI", "cs.LG"]'
    assert version["version"] == "v1"
    assert version["comment"] == "12 pages"
