from gcd_modifier import filters


def test_resolves_only_english_comics_series(fixture_conn):
    result = filters.resolve(fixture_conn)

    # series 1, 2 qualify; 3 is French, 4 isn't a comics publication, 5 is soft-deleted
    assert result.series_ids == {1, 2}


def test_excludes_deleted_issues_and_stories(fixture_conn):
    result = filters.resolve(fixture_conn)

    # issue 104 belongs to series 1 but is soft-deleted
    assert result.issue_ids == {101, 102, 103}
    # story 202 belongs to a qualifying issue but is soft-deleted
    assert result.story_ids == {201}


def test_collects_referenced_ids_even_when_dangling(fixture_conn):
    """filters.resolve just collects referenced FK values -- it doesn't check
    they exist. Loader-side sanitization (tested separately) is what drops
    or nulls out ids that turn out not to point at a real row.
    """
    result = filters.resolve(fixture_conn)

    # issue 102's brand_id=99 doesn't exist as a gcd_brand row, but it's
    # still collected here -- transform.extract simply won't find a matching
    # row for it.
    assert result.brand_ids == {1, 99}
    assert result.publisher_ids == {1}


def test_story_credits_scoped_to_included_stories(fixture_conn):
    result = filters.resolve(fixture_conn)

    # both credits belong to story 201, which is included; story 202's
    # credits (if any) would be excluded since the story itself is deleted
    assert result.story_credit_ids == {301, 302}
    assert result.creator_name_detail_ids == {1, 999}


def test_no_matching_series_returns_empty_result(fixture_conn):
    fixture_conn.execute("UPDATE gcd_series SET deleted = 1")
    result = filters.resolve(fixture_conn)

    assert result.series_ids == set()
    assert result.issue_ids == set()
