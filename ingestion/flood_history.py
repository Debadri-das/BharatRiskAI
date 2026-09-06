class LiveFloodHistoryProvider:
    def count(self, *_):
        raise RuntimeError("Live flood history provider is not configured in demo mode.")


class DemoFloodHistoryProvider:
    def count(self, *_):
        return {"historical_flood_count": 9, "source": "demo"}
