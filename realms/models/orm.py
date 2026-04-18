"""SQLAlchemy ORM models for REALMS.

Mirrors the schema in docs/DATA_MODEL.md. Tables are created via
scripts/bootstrap_realms_db.py using Base.metadata.create_all().
"""
from __future__ import annotations

from datetime import datetime, date
from typing import Any, Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Boolean,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for REALMS ORM models."""


class IngestionSource(Base):
    __tablename__ = "ingestion_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(500), nullable=False)
    authors: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    publication_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    journal_or_venue: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    volume_issue: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pages: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    doi: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    isbn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    access_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    retrieval_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    original_language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    translation_info: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    credibility_score: Mapped[Optional[float]] = mapped_column(
        Float,
        CheckConstraint("credibility_score >= 0 AND credibility_score <= 1"),
        nullable=True,
    )
    peer_reviewed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    citation_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    altmetrics: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    ingestion_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    storage_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    access_restrictions: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ethical_considerations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    ingested_entities: Mapped[list["IngestedEntity"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class IngestedEntity(Base):
    __tablename__ = "ingested_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ingestion_sources.id", ondelete="CASCADE"), nullable=True, index=True
    )
    extraction_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    llm_model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    llm_temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    llm_prompt_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    raw_extracted_data: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    normalized_data: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    entity_name_raw: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    entity_name_normalized: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, index=True)
    extraction_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        CheckConstraint("extraction_confidence >= 0 AND extraction_confidence <= 1"),
        nullable=True,
        index=True,
    )
    extraction_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    quote_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="raw", index=True)
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    source: Mapped[Optional[IngestionSource]] = relationship(back_populates="ingested_entities")


class EntityCategory(Base):
    __tablename__ = "entity_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entity_categories.id"), nullable=True
    )
    icon_emoji: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    provenance_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sources: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    classes: Mapped[list["EntityClass"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )


class EntityClass(Base):
    __tablename__ = "entity_classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entity_categories.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    alternate_names: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    core_powers: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    associated_plants: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    cultural_origin: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    hierarchy_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hierarchy_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    provenance_sources: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    category: Mapped[Optional[EntityCategory]] = relationship(back_populates="classes")
    entities: Mapped[list["Entity"]] = relationship(back_populates="entity_class")


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_class_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entity_classes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    alignment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    realm: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    hierarchy_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hierarchy_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    alternate_names: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    powers: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    domains: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    associated_animals: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    plant_teachers: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    geographical_associations: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    cultural_associations: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    provenance_sources: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    extraction_instances: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    consensus_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        CheckConstraint("consensus_confidence >= 0 AND consensus_confidence <= 1"),
        nullable=True,
        index=True,
    )
    conflict_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    entity_class: Mapped[Optional[EntityClass]] = relationship(back_populates="entities")
    outgoing_relationships: Mapped[list["EntityRelationship"]] = relationship(
        foreign_keys="EntityRelationship.source_entity_id",
        back_populates="source_entity",
        cascade="all, delete-orphan",
    )
    incoming_relationships: Mapped[list["EntityRelationship"]] = relationship(
        foreign_keys="EntityRelationship.target_entity_id",
        back_populates="target_entity",
        cascade="all, delete-orphan",
    )
    plant_connections: Mapped[list["PlantSpiritConnection"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )


class EntityRelationship(Base):
    __tablename__ = "entity_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    strength: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    provenance_sources: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    extraction_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        CheckConstraint("extraction_confidence >= 0 AND extraction_confidence <= 1"),
        nullable=True,
    )
    cultural_context: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    historical_period: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    source_entity: Mapped[Entity] = relationship(
        foreign_keys=[source_entity_id], back_populates="outgoing_relationships"
    )
    target_entity: Mapped[Entity] = relationship(
        foreign_keys=[target_entity_id], back_populates="incoming_relationships"
    )


class PlantSpiritConnection(Base):
    __tablename__ = "plant_spirit_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    compound_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    preparation_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    context_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cultural_association: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    geographical_association: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    provenance_sources: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    extraction_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        CheckConstraint("extraction_confidence >= 0 AND extraction_confidence <= 1"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    entity: Mapped[Entity] = relationship(back_populates="plant_connections")


class Culture(Base):
    __tablename__ = "cultures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    language_family: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    countries: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tradition_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    primary_plants: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    entity_pantheon: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    sources: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GeographicRegion(Base):
    __tablename__ = "geographic_regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    region_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    countries: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    center_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    center_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    boundary_geojson: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    cultural_overlap: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    endemic_entities: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    shared_entities: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    sources: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
