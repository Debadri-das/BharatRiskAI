class LivePopulationProvider:
    def density(self, *_):
        raise RuntimeError("Live population provider is not configured in demo mode.")


class DemoPopulationProvider:
    def density(self, *_):
        return {"population_density": 24000, "source": "demo"}
