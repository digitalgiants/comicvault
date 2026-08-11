"""Builds a small SQLite fixture matching the real GCD schema (verified
against an actual dump -- see README) with just enough tables/rows to
exercise filtering, extraction, and FK-integrity edge cases:

- two qualifying English comics series, plus one non-English, one
  non-comics-publication, and one soft-deleted series that must all be
  excluded
- a soft-deleted issue that must be excluded
- an issue with a self-referencing `variant_of_id` (tests the two-phase
  insert logic's input) and one with a `brand_id` pointing at a brand row
  that doesn't exist (tests dangling-FK handling)
- a story credit pointing at a creator_name_detail row that doesn't exist
  (same kind of dangling-FK gap found in the real GCD dump)
"""

from __future__ import annotations

import sqlite3

import pytest

SCHEMA = """
CREATE TABLE stddata_language (id INTEGER PRIMARY KEY, code TEXT, name TEXT, native_name TEXT);
CREATE TABLE stddata_country (id INTEGER PRIMARY KEY, code TEXT, name TEXT);
CREATE TABLE gcd_publisher (id INTEGER PRIMARY KEY, name TEXT, country_id INTEGER, year_began INTEGER, year_ended INTEGER, notes TEXT, url TEXT);
CREATE TABLE gcd_indicia_publisher (id INTEGER PRIMARY KEY, name TEXT, parent_id INTEGER, country_id INTEGER, year_began INTEGER, year_ended INTEGER, is_surrogate INTEGER, notes TEXT, url TEXT);
CREATE TABLE gcd_brand_group (id INTEGER PRIMARY KEY, name TEXT, parent_id INTEGER, year_began INTEGER, year_ended INTEGER, notes TEXT, url TEXT);
CREATE TABLE gcd_brand (id INTEGER PRIMARY KEY, name TEXT, year_began INTEGER, year_ended INTEGER, notes TEXT, url TEXT, generic INTEGER);
CREATE TABLE gcd_brand_emblem_group (id INTEGER PRIMARY KEY, brand_id INTEGER, brandgroup_id INTEGER);
CREATE TABLE gcd_series (
    id INTEGER PRIMARY KEY, name TEXT, sort_name TEXT, format TEXT, year_began INTEGER, year_ended INTEGER,
    publication_dates TEXT, is_current INTEGER, publisher_id INTEGER, country_id INTEGER, language_id INTEGER,
    notes TEXT, issue_count INTEGER, is_comics_publication INTEGER, deleted INTEGER
);
CREATE TABLE gcd_issue (
    id INTEGER PRIMARY KEY, number TEXT, title TEXT, volume TEXT, series_id INTEGER, indicia_publisher_id INTEGER,
    brand_id INTEGER, variant_of_id INTEGER, variant_name TEXT, isbn TEXT, barcode TEXT, publication_date TEXT,
    key_date TEXT, on_sale_date TEXT, sort_code INTEGER, price TEXT, page_count REAL, rating TEXT, editing TEXT,
    notes TEXT, deleted INTEGER
);
CREATE TABLE gcd_story_type (id INTEGER PRIMARY KEY, name TEXT, sort_code INTEGER);
CREATE TABLE gcd_credit_type (id INTEGER PRIMARY KEY, name TEXT, sort_code INTEGER);
CREATE TABLE gcd_creator (id INTEGER PRIMARY KEY, gcd_official_name TEXT, sort_name TEXT, disambiguation TEXT);
CREATE TABLE gcd_creator_name_detail (
    id INTEGER PRIMARY KEY, name TEXT, sort_name TEXT, is_official_name INTEGER, creator_id INTEGER,
    family_name TEXT, given_name TEXT
);
CREATE TABLE gcd_story (
    id INTEGER PRIMARY KEY, title TEXT, feature TEXT, sequence_number INTEGER, page_count REAL, issue_id INTEGER,
    type_id INTEGER, job_number TEXT, genre TEXT, script TEXT, pencils TEXT, inks TEXT, colors TEXT, letters TEXT,
    editing TEXT, characters TEXT, synopsis TEXT, reprint_notes TEXT, notes TEXT, deleted INTEGER
);
CREATE TABLE gcd_story_credit (
    id INTEGER PRIMARY KEY, story_id INTEGER, creator_id INTEGER, credit_type_id INTEGER, credited_as TEXT,
    credit_name TEXT, is_credited INTEGER, is_signed INTEGER, uncertain INTEGER, deleted INTEGER
);
"""

# Series ids: 1, 2 = qualifying English comics; 3 = French; 4 = English but
# not a comics publication; 5 = English comics but soft-deleted.
DATA = """
INSERT INTO stddata_language (id, code, name, native_name) VALUES (1, 'en', 'English', 'English'), (2, 'fr', 'French', 'Français');
INSERT INTO stddata_country (id, code, name) VALUES (1, 'us', 'United States');
INSERT INTO gcd_publisher (id, name, country_id, year_began, year_ended, notes, url) VALUES (1, 'Test Publisher', 1, 1980, NULL, '', '');
INSERT INTO gcd_brand_group (id, name, parent_id, year_began, year_ended, notes, url) VALUES (1, 'Test Imprint', 1, 1980, NULL, '', '');
INSERT INTO gcd_brand (id, name, year_began, year_ended, notes, url, generic) VALUES (1, 'Existing Brand', 1980, NULL, '', '', 0);
INSERT INTO gcd_brand_emblem_group (id, brand_id, brandgroup_id) VALUES (1, 1, 1);

INSERT INTO gcd_series (id, name, sort_name, format, year_began, year_ended, publication_dates, is_current, publisher_id, country_id, language_id, notes, issue_count, is_comics_publication, deleted) VALUES
    (1, 'English Comic One', 'English Comic One', '', 1980, NULL, '', 1, 1, 1, 1, '', 2, 1, 0),
    (2, 'English Comic Two', 'English Comic Two', '', 1990, NULL, '', 1, 1, 1, 1, '', 1, 1, 0),
    (3, 'French Comic', 'French Comic', '', 1980, NULL, '', 1, 1, 1, 2, '', 1, 1, 0),
    (4, 'English Fanzine', 'English Fanzine', '', 1980, NULL, '', 1, 1, 1, 1, '', 1, 0, 0),
    (5, 'Deleted English Comic', 'Deleted English Comic', '', 1980, NULL, '', 1, 1, 1, 1, '', 1, 1, 1);

INSERT INTO gcd_issue (id, number, title, volume, series_id, indicia_publisher_id, brand_id, variant_of_id, variant_name, isbn, barcode, publication_date, key_date, on_sale_date, sort_code, price, page_count, rating, editing, notes, deleted) VALUES
    (101, '1', '', '', 1, NULL, 1, NULL, '', '', '', '1980-01', '1980-01-00', '', 0, '', 32, '', '', '', 0),
    (102, '2', '', '', 1, NULL, 99, NULL, '', '', '', '1980-02', '1980-02-00', '', 1, '', 32, '', '', '', 0),
    (103, '1', '', '', 2, NULL, NULL, 101, '', '', '', '1990-01', '1990-01-00', '', 0, '', 32, '', '', '', 0),
    (104, '1', '', '', 1, NULL, NULL, NULL, '', '', '', '1980-03', '1980-03-00', '', 2, '', 32, '', '', '', 1),
    (105, '1', '', '', 3, NULL, NULL, NULL, '', '', '', '1980-01', '1980-01-00', '', 0, '', 32, '', '', '', 0);

INSERT INTO gcd_story_type (id, name, sort_code) VALUES (1, 'comic story', 0);
INSERT INTO gcd_credit_type (id, name, sort_code) VALUES (1, 'script', 0), (2, 'pencils', 1);

INSERT INTO gcd_creator (id, gcd_official_name, sort_name, disambiguation) VALUES (1, 'Jane Doe', 'Doe, Jane', '');
INSERT INTO gcd_creator_name_detail (id, name, sort_name, is_official_name, creator_id, family_name, given_name) VALUES
    (1, 'Jane Doe', 'Doe, Jane', 1, 1, 'Doe', 'Jane');

INSERT INTO gcd_story (id, title, feature, sequence_number, page_count, issue_id, type_id, job_number, genre, script, pencils, inks, colors, letters, editing, characters, synopsis, reprint_notes, notes, deleted) VALUES
    (201, 'Story A', '', 0, 32, 101, 1, '', '', '', '', '', '', '', '', '', '', '', '', 0),
    (202, 'Story B', '', 0, 32, 102, 1, '', '', '', '', '', '', '', '', '', '', '', '', 1),
    (203, 'Story C', '', 0, 32, 105, 1, '', '', '', '', '', '', '', '', '', '', '', '', 0);

INSERT INTO gcd_story_credit (id, story_id, creator_id, credit_type_id, credited_as, credit_name, is_credited, is_signed, uncertain, deleted) VALUES
    (301, 201, 1, 1, '', '', 1, 0, 0, 0),
    (302, 201, 999, 2, '', '', 1, 0, 0, 0);
"""


@pytest.fixture
def fixture_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA + DATA)
    yield conn
    conn.close()
