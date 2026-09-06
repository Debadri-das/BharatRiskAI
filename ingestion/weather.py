class LiveWeatherProvider:
    def latest(self, latitude: float, longitude: float):
        raise RuntimeError("Live weather provider is not configured in demo mode.")


class DemoWeatherProvider:
    def latest(self, latitude: float, longitude: float):
        return {"rainfall_24h": 180, "rainfall_7d": 500, "source": "demo"}


def get_weather_provider(live: bool = False):
    return LiveWeatherProvider() if live else DemoWeatherProvider()
