import datetime


def parse_date_fr(s: str) -> datetime.date:
    day, month, year = s.strip().split("/")
    return datetime.date(int(year), int(month), int(day))


def parse_montant_fr(s: str) -> float:
    cleaned = s.strip().replace("€", "").replace(" ", "").replace("\xa0", "").replace(",", ".")
    return float(cleaned)


def parse_pasted_text(text: str, mapping) -> list[dict]:
    rows = []
    for line in text.strip().splitlines():
        if not line.strip():
            continue
        cols = line.split(mapping.separateur)
        needed = max(mapping.colonne_date, mapping.colonne_libelle, mapping.colonne_montant)
        if len(cols) <= needed:
            continue
        rows.append(
            {
                "date": parse_date_fr(cols[mapping.colonne_date]),
                "libelle": cols[mapping.colonne_libelle].strip(),
                "montant": parse_montant_fr(cols[mapping.colonne_montant]),
            }
        )
    return rows
