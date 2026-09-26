import uuid
import enum
from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Enum, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base

class SessionStatus(str, enum.Enum):
    active = "active"
    challenged = "challenged"
    terminated = "terminated"
    cleared = "cleared"

class Verdict(str, enum.Enum):
    genuine = "genuine"
    suspicious = "suspicious"
    synthetic_clone = "synthetic_clone"

class ActionTriggered(str, enum.Enum):
    otp_sent = "otp_sent"
    trusted_circle_alerted = "trusted_circle_alerted"
    call_blocked = "call_blocked"
    none = "none"

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_number = Column(String(20), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    contacts = relationship("TrustedContact", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("TelephonySession", back_populates="user", cascade="all, delete-orphan")


class TrustedContact(Base):
    __tablename__ = "trusted_contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    contact_name = Column(String(100), nullable=False)
    contact_phone = Column(String(20), nullable=False)
    relationship_type = Column("relationship", String(50), nullable=True)

    user = relationship("User", back_populates="contacts")


class TelephonySession(Base):
    __tablename__ = "telephony_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    caller_phone = Column(String(20), index=True)
    claimed_identity = Column(String(100), nullable=True)
    session_status = Column(Enum(SessionStatus), default=SessionStatus.active)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="sessions")
    scans = relationship("AudioScan", back_populates="session")


class AudioScan(Base):
    __tablename__ = "audio_scans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("telephony_sessions.id"), nullable=True)
    language = Column(String(20), nullable=True)
    impersonation_risk_score = Column(Float, nullable=False)
    verdict = Column(Enum(Verdict), nullable=False)
    audio_sha256 = Column(String(64), index=True)
    spectral_features = Column(JSONB, nullable=True)
    scanned_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("TelephonySession", back_populates="scans")
    audit_events = relationship("AuditEvent", back_populates="scan", cascade="all, delete-orphan")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id = Column(UUID(as_uuid=True), ForeignKey("audio_scans.id"))
    action_triggered = Column(Enum(ActionTriggered), default=ActionTriggered.none)
    payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    scan = relationship("AudioScan", back_populates="audit_events")
