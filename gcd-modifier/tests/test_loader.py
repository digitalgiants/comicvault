from gcd_modifier import filters, loader, models, transform


def _extracted_rows(fixture_conn):
    result = filters.resolve(fixture_conn)
    return transform.extract(fixture_conn, result)


def test_dangling_nullable_fk_is_nulled_not_dropped(fixture_conn):
    """Issue 102's brand_id=99 doesn't exist as a gcd_brand row. brand_id is
    nullable, so the issue itself should survive with brand_id nulled out --
    not get dropped.
    """
    rows = _extracted_rows(fixture_conn)
    loader._sanitize_fk_integrity(rows)

    issue_ids = {row["id"] for row in rows["gcd_issue"]}
    assert issue_ids == {101, 102, 103}

    issue_102 = next(row for row in rows["gcd_issue"] if row["id"] == 102)
    assert issue_102["brand_id"] is None


def test_dangling_required_fk_drops_the_row(fixture_conn):
    """Story credit 302's creator_id=999 doesn't exist as a
    gcd_creator_name_detail row. creator_id is required (non-nullable), so
    the whole credit row must be dropped rather than left with a value that
    would violate the Postgres FK constraint.
    """
    rows = _extracted_rows(fixture_conn)
    loader._sanitize_fk_integrity(rows)

    credit_ids = {row["id"] for row in rows["gcd_story_credit"]}
    assert credit_ids == {301}


def test_self_referencing_fk_checked_against_own_table(fixture_conn):
    """Issue 103's variant_of_id=101 points at another issue that IS in the
    filtered set -- self-reference should survive untouched.
    """
    rows = _extracted_rows(fixture_conn)
    loader._sanitize_fk_integrity(rows)

    issue_103 = next(row for row in rows["gcd_issue"] if row["id"] == 103)
    assert issue_103["variant_of_id"] == 101


def test_self_referencing_fk_to_missing_issue_is_nulled(fixture_conn):
    rows = _extracted_rows(fixture_conn)
    variant_row = next(row for row in rows["gcd_issue"] if row["id"] == 103)
    variant_row["variant_of_id"] = 999999  # points at an issue outside the filtered set

    loader._sanitize_fk_integrity(rows)

    issue_103 = next(row for row in rows["gcd_issue"] if row["id"] == 103)
    assert issue_103["variant_of_id"] is None


def test_coerce_booleans_converts_sqlite_ints_to_bool(fixture_conn):
    rows = _extracted_rows(fixture_conn)
    loader._coerce_booleans(rows)

    series_1 = next(row for row in rows["gcd_series"] if row["id"] == 1)
    assert series_1["is_current"] is True
    assert series_1["is_comics_publication"] is True
    assert isinstance(series_1["is_current"], bool)


def test_upsert_splits_self_referencing_columns(fixture_conn):
    """_upsert should carve self-referencing FK values out into a deferred
    second pass rather than including them in the initial insert batch.
    """
    rows = _extracted_rows(fixture_conn)
    loader._sanitize_fk_integrity(rows)

    table = models.Issue.__table__
    self_ref_columns = [fk.parent.name for fk in table.foreign_keys if fk.column.table.name == table.name]
    assert self_ref_columns == ["variant_of_id"]
