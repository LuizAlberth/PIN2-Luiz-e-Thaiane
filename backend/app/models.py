from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

JSONType = JSON().with_variant(JSONB(), 'postgresql')

def now():
    return datetime.now(timezone.utc)

def uid():
    return str(uuid4())

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default='ADMIN')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Config(Base):
    __tablename__ = 'monitoring_configs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    station_code: Mapped[str] = mapped_column(String(30))
    station_name: Mapped[str] = mapped_column(String(200))
    river: Mapped[str] = mapped_column(String(100), default='Rio Krauel')
    station_lat: Mapped[float] = mapped_column(Float)
    station_lon: Mapped[float] = mapped_column(Float)
    bbox: Mapped[list] = mapped_column(JSONType)
    threshold_cm: Mapped[float] = mapped_column(Float)
    threshold_source: Mapped[str] = mapped_column(Text)
    threshold_valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    threshold_responsible: Mapped[str] = mapped_column(String(150))
    collection_interval_min: Mapped[int] = mapped_column(Integer, default=30)
    baseline_min_days: Mapped[int] = mapped_column(Integer, default=15)
    baseline_max_days: Mapped[int] = mapped_column(Integer, default=30)
    post_window_days: Mapped[int] = mapped_column(Integer, default=15)
    source_mode: Mapped[str] = mapped_column(String(12), default='ANA')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))

class Reading(Base):
    __tablename__ = 'hydrometric_readings'
    __table_args__ = (UniqueConstraint('station_code', 'observed_at', 'mode'), Index('ix_reading_time', 'station_code', 'observed_at'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    station_code: Mapped[str] = mapped_column(String(30))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    water_level_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_status: Mapped[str] = mapped_column(String(20))
    raw_payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    correlation_id: Mapped[str] = mapped_column(String(36))
    mode: Mapped[str] = mapped_column(String(12), default='AO_VIVO')

class Event(Base):
    __tablename__ = 'flood_events'
    __table_args__ = (UniqueConstraint('trigger_reading_id'), Index('ix_event_status_time', 'status', 'started_at'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    config_id: Mapped[str] = mapped_column(ForeignKey('monitoring_configs.id'))
    trigger_reading_id: Mapped[str] = mapped_column(ForeignKey('hydrometric_readings.id'))
    trigger_level_cm: Mapped[float] = mapped_column(Float)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    below_streak: Mapped[int] = mapped_column(Integer, default=0)
    snapshot: Mapped[dict] = mapped_column(JSONType)
    status: Mapped[str] = mapped_column(String(30), default='AGUARDANDO_IMAGEM')
    mode: Mapped[str] = mapped_column(String(12))
    failure_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Job(Base):
    __tablename__ = 'processing_jobs'
    __table_args__ = (Index('ix_jobs_due', 'status', 'scheduled_for'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    event_id: Mapped[str | None] = mapped_column(ForeignKey('flood_events.id'), nullable=True)
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(24), default='PENDENTE')
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(36), default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Scene(Base):
    __tablename__ = 'event_scenes'
    __table_args__ = (UniqueConstraint('event_id', 'role', 'version'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    event_id: Mapped[str] = mapped_column(ForeignKey('flood_events.id'))
    role: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(Integer)
    provider_product_id: Mapped[str] = mapped_column(String(200))
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    instrument_mode: Mapped[str] = mapped_column(String(20))
    orbit_direction: Mapped[str] = mapped_column(String(24))
    relative_orbit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    polarization: Mapped[str] = mapped_column(String(12))
    selection_reason: Mapped[str] = mapped_column(Text)
    compatibility_status: Mapped[str] = mapped_column(String(24), default='COMPATIVEL')
    source: Mapped[str] = mapped_column(String(20))
    image_key: Mapped[str] = mapped_column(String(300))
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Attempt(Base):
    __tablename__ = 'integration_attempts'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey('processing_jobs.id'))
    provider: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(36))

class Audit(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(36))
    details: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
