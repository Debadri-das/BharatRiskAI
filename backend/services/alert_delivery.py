"""Configurable alert delivery with Supabase delivery tracking."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from backend.config.settings import get_settings
from backend.database.connection import get_supabase_admin_client


def deliver_alert(alert: dict[str, Any], destinations: list[dict[str, str]]) -> list[dict[str, Any]]:
    settings = get_settings()
    client = get_supabase_admin_client()
    results = []
    alert_key = str(alert.get("alert_key") or f"{alert.get('zone_id')}:{alert.get('alert_level')}:{alert.get('generated_at')}" )
    for destination in destinations:
        channel = destination["channel"]
        target = destination["destination"]
        payload = {"alert": alert, "channel": channel, "destination": target}
        row = {"alert_key": alert_key, "zone_id": alert.get("zone_id"), "channel": channel, "destination": target, "payload": payload, "status": "PENDING", "attempts": 0}
        client.table("alert_deliveries").upsert(row, on_conflict="alert_key,channel,destination").execute()
        try:
            if channel == "webhook":
                headers = {"Content-Type": "application/json"}
                if settings.alert_webhook_token:
                    headers["Authorization"] = f"Bearer {settings.alert_webhook_token}"
                response = httpx.post(target or settings.alert_webhook_url, json=payload, headers=headers, timeout=10)
                response.raise_for_status()
            elif channel == "sms_webhook":
                response = httpx.post(target or settings.alert_sms_webhook_url, json=payload, timeout=10)
                response.raise_for_status()
            else:
                raise ValueError(f"Unsupported alert channel: {channel}")
            client.table("alert_deliveries").update({"status": "DELIVERED", "attempts": 1, "delivered_at": datetime.now(timezone.utc).isoformat(), "last_error": None}).eq("alert_key", alert_key).eq("channel", channel).eq("destination", target).execute()
            results.append({"channel": channel, "destination": target, "status": "DELIVERED"})
        except Exception as error:
            client.table("alert_deliveries").update({"status": "FAILED", "attempts": 1, "last_error": str(error)}).eq("alert_key", alert_key).eq("channel", channel).eq("destination", target).execute()
            results.append({"channel": channel, "destination": target, "status": "FAILED", "error": str(error)})
    return results
