CREATE INDEX IF NOT EXISTS ix_zones_risk ON zones(risk_category, risk_score);
CREATE INDEX IF NOT EXISTS ix_reports_zone_created ON citizen_reports(zone_id, created_at);
CREATE INDEX IF NOT EXISTS ix_emergency_priority ON emergencies(priority, status);
