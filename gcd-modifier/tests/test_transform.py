from gcd_modifier import filters, transform


def test_extract_returns_only_filtered_rows(fixture_conn):
    result = filters.resolve(fixture_conn)
    rows = transform.extract(fixture_conn, result)

    series_ids = {row["id"] for row in rows["gcd_series"]}
    assert series_ids == {1, 2}

    issue_ids = {row["id"] for row in rows["gcd_issue"]}
    assert issue_ids == {101, 102, 103}


def test_extract_silently_drops_dangling_references(fixture_conn):
    """A brand_id/creator_id referenced by a filtered row but not backed by
    an actual row in that table just doesn't come back -- there's nothing to
    SELECT. Confirms the gap loader._sanitize_fk_integrity has to close.
    """
    result = filters.resolve(fixture_conn)
    rows = transform.extract(fixture_conn, result)

    assert result.brand_ids == {1, 99}
    extracted_brand_ids = {row["id"] for row in rows["gcd_brand"]}
    assert extracted_brand_ids == {1}  # 99 doesn't exist as a gcd_brand row

    assert result.creator_name_detail_ids == {1, 999}
    extracted_cnd_ids = {row["id"] for row in rows["gcd_creator_name_detail"]}
    assert extracted_cnd_ids == {1}  # 999 doesn't exist


def test_lookup_tables_loaded_in_full(fixture_conn):
    result = filters.resolve(fixture_conn)
    rows = transform.extract(fixture_conn, result)

    # both languages are present even though only 'en' series are in scope
    assert {row["code"] for row in rows["stddata_language"]} == {"en", "fr"}


def test_extracted_row_columns_match_model_columns(fixture_conn):
    from gcd_modifier import models

    result = filters.resolve(fixture_conn)
    rows = transform.extract(fixture_conn, result)

    for model in models.LOAD_ORDER:
        table_rows = rows[model.__tablename__]
        if not table_rows:
            continue
        expected_columns = {c.name for c in model.__table__.columns}
        assert set(table_rows[0].keys()) == expected_columns
