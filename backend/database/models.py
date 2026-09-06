from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database.connection import Base


class Zone(Base):
    __tablename__ = "zones"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    rainfall_24h: Mapped[float] = mapped_column(Float)
    rainfall_7d: Mapped[float] = mapped_column(Float)
    elevation: Mapped[float] = mapped_column(Float)
    drainage_score: Mapped[float] = mapped_column(Float)
    population_density: Mapped[float] = mapped_column(Float)
    population: Mapped[int] = mapped_column(Integer)
    historical_flood_count: Mapped[int] = mapped_column(Integer)
    citizen_report_count: Mapped[int] = mapped_column(Integer, default=0)
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    risk_category: Mapped[str] = mapped_column(String(20), default="LOW")
    area_km2: Mapped[float] = mapped_column(Float, default=2.5)

    reports = relationship("CitizenReport", back_populates="zone")


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"), index=True)
    score: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CitizenReport(Base):
    __tablename__ = "citizen_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("zones.id"), nullable=True, index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    water_level_cm: Mapped[float] = mapped_column(Float)
    description: Mapped[str] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    severity: Mapped[str] = mapped_column(String(20))
    credible: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    zone = relationship("Zone", back_populates="reports")


class Emergency(Base):
    __tablename__ = "emergencies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    emergency_type: Mapped[str] = mapped_column(String(60))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    people: Mapped[int] = mapped_column(Integer)
    vulnerable: Mapped[str] = mapped_column(String(255), default="")
    priority: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(40), default="QUEUED")
    assigned_resource_id: Mapped[int | None] = mapped_column(ForeignKey("resources.id"), nullable=True)
    ttl: Mapped[int] = mapped_column(Integer, default=10)
    hop_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Resource(Base):
    __tablename__ = "resources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(60), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer)
    available: Mapped[int] = mapped_column(Integer)
    road_status: Mapped[str] = mapped_column(String(60), default="OPEN")


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("zones.id"), nullable=True)
    priority: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(120))
    resource_type: Mapped[str] = mapped_column(String(60))
    quantity: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Shelter(Base):
    __tablename__ = "shelters"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    capacity: Mapped[int] = mapped_column(Integer)
    available_capacity: Mapped[int] = mapped_column(Integer)


class Road(Base):
    __tablename__ = "roads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"))
    status: Mapped[str] = mapped_column(String(40), default="OPEN")


class SyncQueue(Base):
    __tablename__ = "sync_queue"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload_type: Mapped[str] = mapped_column(String(60))
    payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


Index("ix_zones_risk_category_score", Zone.risk_category, Zone.risk_score)
