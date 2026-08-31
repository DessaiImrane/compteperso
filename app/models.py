from __future__ import annotations

import datetime

from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

transaction_tags = Table(
    "transaction_tags",
    Base.metadata,
    Column("transaction_id", ForeignKey("transactions.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


class Banque(Base):
    __tablename__ = "banques"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(unique=True)

    comptes: Mapped[list["CompteVirtuel"]] = relationship(back_populates="banque")


class CompteVirtuel(Base):
    __tablename__ = "comptes_virtuels"

    id: Mapped[int] = mapped_column(primary_key=True)
    banque_id: Mapped[int] = mapped_column(ForeignKey("banques.id"))
    nom: Mapped[str]
    actif: Mapped[bool] = mapped_column(default=True)

    banque: Mapped["Banque"] = relationship(back_populates="comptes")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(unique=True)


class Creancier(Base):
    __tablename__ = "creanciers"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str]
    montant_defaut: Mapped[float]
    compte_source_id: Mapped[int] = mapped_column(ForeignKey("comptes_virtuels.id"))
    compte_destination_id: Mapped[int | None] = mapped_column(
        ForeignKey("comptes_virtuels.id"), nullable=True
    )
    date_prochaine_echeance: Mapped[datetime.date | None]
    recurrence: Mapped[str]
    intervalle_jours: Mapped[int | None] = mapped_column(nullable=True)
    fin_type: Mapped[str] = mapped_column(default="jamais")
    fin_date: Mapped[datetime.date | None] = mapped_column(nullable=True)
    fin_occurrences: Mapped[int | None] = mapped_column(nullable=True)
    occurrences_generees: Mapped[int] = mapped_column(default=0)
    actif: Mapped[bool] = mapped_column(default=True)

    compte_source: Mapped["CompteVirtuel"] = relationship(foreign_keys=[compte_source_id])
    compte_destination: Mapped["CompteVirtuel | None"] = relationship(
        foreign_keys=[compte_destination_id]
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[datetime.date]
    compte_virtuel_id: Mapped[int] = mapped_column(ForeignKey("comptes_virtuels.id"))
    montant: Mapped[float]
    libelle: Mapped[str]
    pointe: Mapped[bool] = mapped_column(default=False)
    creancier_id: Mapped[int | None] = mapped_column(ForeignKey("creanciers.id"), nullable=True)
    transfer_link_id: Mapped[str | None] = mapped_column(nullable=True)

    compte_virtuel: Mapped["CompteVirtuel"] = relationship()
    tags: Mapped[list["Tag"]] = relationship(secondary=transaction_tags)


class MappingParsing(Base):
    __tablename__ = "mappings_parsing"

    id: Mapped[int] = mapped_column(primary_key=True)
    banque_id: Mapped[int] = mapped_column(ForeignKey("banques.id"), unique=True)
    colonne_date: Mapped[int]
    colonne_libelle: Mapped[int]
    colonne_montant: Mapped[int]
    separateur: Mapped[str] = mapped_column(default="\t")


class TagLearning(Base):
    __tablename__ = "tag_learning"

    id: Mapped[int] = mapped_column(primary_key=True)
    libelle_pattern: Mapped[str]
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"))

    tag: Mapped["Tag"] = relationship()


class RapprochementSession(Base):
    __tablename__ = "rapprochement_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    banque_id: Mapped[int] = mapped_column(ForeignKey("banques.id"))
    date: Mapped[datetime.date]
    total_banque_pointe: Mapped[float]
    total_banque_a_venir: Mapped[float]
    total_pointe_calcule: Mapped[float]
    ecart: Mapped[float]
