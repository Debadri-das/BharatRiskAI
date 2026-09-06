class LiveElevationProvider:
    def elevation(self, *_):
        raise RuntimeError("Live elevation provider is not configured in demo mode.")


class DemoElevationProvider:
    def elevation(self, *_):
        return {"elevation_m": 6.2, "source": "demo"}
