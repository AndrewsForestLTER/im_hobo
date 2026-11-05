"""Consistency checks between the two citation metadata files.

CITATION.cff drives GitHub's "Cite this repository" box; .zenodo.json drives
the Zenodo deposit made on each GitHub release (Zenodo ignores CITATION.cff
when .zenodo.json exists). Both are edited by hand, so these tests fail CI if
they drift apart from each other or from the package version.
"""
import datetime
import json
import re
from pathlib import Path

import pytest
import yaml

import MET_hobo

REPO_ROOT = Path(__file__).resolve().parent.parent
CONCEPT_DOI = '10.5281/zenodo.22294811'


@pytest.fixture(scope='module')
def cff() -> dict:
    with (REPO_ROOT / 'CITATION.cff').open(encoding='utf-8') as f:
        return yaml.safe_load(f)


@pytest.fixture(scope='module')
def zenodo() -> dict:
    with (REPO_ROOT / '.zenodo.json').open(encoding='utf-8') as f:
        return json.load(f)


def test_versions_match_package(cff, zenodo):
    """Both files must carry the version the package reports."""
    assert str(cff['version']) == MET_hobo.__version__
    assert str(zenodo['version']) == MET_hobo.__version__


def test_date_released_is_iso_date(cff):
    """PyYAML parses an unquoted date to datetime.date; a quoted one stays a
    string -- accept either, as long as it is a valid YYYY-MM-DD."""
    value = cff['date-released']
    if not isinstance(value, datetime.date):
        datetime.date.fromisoformat(value)


def test_title_and_license_match(cff, zenodo):
    assert cff['title'] == zenodo['title']
    assert cff['license'] == zenodo['license']


def test_authors_match(cff, zenodo):
    """Same people, same order, same ORCIDs and affiliations. Zenodo writes
    names as "Family, Given" and ORCIDs bare; CFF splits names and uses the
    full ORCID URL."""
    cff_authors = [
        (f"{a['family-names']}, {a['given-names']}",
         a.get('orcid', '').removeprefix('https://orcid.org/'),
         a.get('affiliation', ''))
        for a in cff['authors']
    ]
    zenodo_authors = [
        (c['name'], c.get('orcid', ''), c.get('affiliation', ''))
        for c in zenodo['creators']
    ]
    assert cff_authors == zenodo_authors


def test_cff_doi_is_concept_doi(cff):
    """CITATION.cff cites the concept DOI, which always resolves to the latest
    Zenodo version -- not a per-version DOI that goes stale on the next
    release."""
    assert cff['doi'] == CONCEPT_DOI


def test_readme_badge_uses_concept_doi():
    readme = (REPO_ROOT / 'README.rst').read_text(encoding='utf-8')
    assert re.search(rf'doi\.org/{re.escape(CONCEPT_DOI)}\b', readme)
