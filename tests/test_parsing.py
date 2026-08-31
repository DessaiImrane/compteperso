import datetime
import pytest
from app.services.parsing import parse_date_fr, parse_montant_fr, parse_pasted_text


class FakeMapping:
    def __init__(self, colonne_date=0, colonne_libelle=1, colonne_montant=2, separateur="\t"):
        self.colonne_date = colonne_date
        self.colonne_libelle = colonne_libelle
        self.colonne_montant = colonne_montant
        self.separateur = separateur


def test_parse_date_fr():
    assert parse_date_fr("05/08/2026") == datetime.date(2026, 8, 5)


def test_parse_montant_fr_negative_with_comma():
    assert parse_montant_fr("-45,90 €") == -45.90


def test_parse_montant_fr_positive_with_thousands_separator():
    assert parse_montant_fr("1 234,56") == 1234.56


def test_parse_pasted_text_splits_columns_by_mapping():
    text = "05/08/2026\tRestaurant Le Bon Coin\t-45,90\n06/08/2026\tSalaire\t1 500,00"
    mapping = FakeMapping()
    rows = parse_pasted_text(text, mapping)
    assert rows == [
        {"date": datetime.date(2026, 8, 5), "libelle": "Restaurant Le Bon Coin", "montant": -45.90},
        {"date": datetime.date(2026, 8, 6), "libelle": "Salaire", "montant": 1500.00},
    ]


def test_parse_pasted_text_skips_blank_and_short_lines():
    text = "05/08/2026\tRestaurant\t-45,90\n\nligne incomplete"
    mapping = FakeMapping()
    rows = parse_pasted_text(text, mapping)
    assert len(rows) == 1
