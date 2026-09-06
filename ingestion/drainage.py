class LiveDrainageProvider:
    def score(self, *_):
        raise RuntimeError("Live drainage provider is not configured in demo mode.")


class DemoDrainageProvider:
    def score(self, *_):
        return {"drainage_score": 38, "source": "demo"}
