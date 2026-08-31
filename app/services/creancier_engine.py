import datetime
import uuid

from sqlalchemy.orm import Session

from app.models import Creancier, Transaction

_DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _add_months(d: datetime.date, months: int) -> datetime.date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    max_day = _DAYS_IN_MONTH[month - 1]
    if month == 2 and _is_leap(year):
        max_day = 29
    return datetime.date(year, month, min(d.day, max_day))


def next_date(
    current: datetime.date, recurrence: str, intervalle_jours: int | None = None
) -> datetime.date | None:
    if recurrence == "mensuelle":
        return _add_months(current, 1)
    if recurrence == "hebdomadaire":
        return current + datetime.timedelta(days=7)
    if recurrence == "custom":
        if not intervalle_jours:
            raise ValueError("intervalle_jours requis pour une récurrence custom")
        return current + datetime.timedelta(days=intervalle_jours)
    if recurrence == "aucune":
        return None
    raise ValueError(f"récurrence inconnue: {recurrence}")


def generate_due_echeances(db: Session, today: datetime.date) -> list[Transaction]:
    created: list[Transaction] = []
    creanciers = db.query(Creancier).filter(Creancier.actif.is_(True)).all()

    for creancier in creanciers:
        while (
            creancier.date_prochaine_echeance is not None
            and creancier.date_prochaine_echeance <= today
        ):
            echeance_date = creancier.date_prochaine_echeance

            if creancier.compte_destination_id is not None:
                transfer_id = str(uuid.uuid4())
                debit = Transaction(
                    date=echeance_date,
                    compte_virtuel_id=creancier.compte_source_id,
                    montant=-abs(creancier.montant_defaut),
                    libelle=creancier.nom,
                    pointe=False,
                    creancier_id=creancier.id,
                    transfer_link_id=transfer_id,
                )
                credit = Transaction(
                    date=echeance_date,
                    compte_virtuel_id=creancier.compte_destination_id,
                    montant=abs(creancier.montant_defaut),
                    libelle=creancier.nom,
                    pointe=False,
                    creancier_id=creancier.id,
                    transfer_link_id=transfer_id,
                )
                db.add_all([debit, credit])
                created.extend([debit, credit])
            else:
                # Externe: pas de compte destination pour fixer la direction, donc
                # le signe saisi sur le créancier fait foi (négatif = sort vers
                # l'externe, positif = rentre depuis l'externe, ex: CAF).
                mouvement = Transaction(
                    date=echeance_date,
                    compte_virtuel_id=creancier.compte_source_id,
                    montant=creancier.montant_defaut,
                    libelle=creancier.nom,
                    pointe=False,
                    creancier_id=creancier.id,
                )
                db.add(mouvement)
                created.append(mouvement)

            creancier.occurrences_generees += 1

            stop = False
            if creancier.fin_type == "occurrences" and creancier.fin_occurrences is not None:
                if creancier.occurrences_generees >= creancier.fin_occurrences:
                    stop = True
            if creancier.fin_type == "date" and creancier.fin_date is not None:
                if echeance_date >= creancier.fin_date:
                    stop = True
            if creancier.recurrence == "aucune":
                stop = True

            if stop:
                creancier.actif = False
                creancier.date_prochaine_echeance = None
                break

            creancier.date_prochaine_echeance = next_date(
                echeance_date, creancier.recurrence, creancier.intervalle_jours
            )

    db.commit()
    return created
