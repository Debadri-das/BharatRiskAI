from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import numpy as np
except ImportError:
    np = None

try:
    import httpx
except ImportError:
    httpx = None

try:
    import rasterio
    from rasterio.io import MemoryFile
except ImportError:
    rasterio = None
    MemoryFile = None

from backend.config.settings import get_settings



class LiveSatelliteProvider:
    def __init__(self):
        self.settings = get_settings()

    def _access_token(self) -> str:
        if self.settings.copernicus_username and self.settings.copernicus_password:
            data = {
                "grant_type": "password",
                "client_id": "cdse-public",
                "username": self.settings.copernicus_username,
                "password": self.settings.copernicus_password,
            }
        elif self.settings.copernicus_client_id and self.settings.copernicus_client_secret:
            data = {
                "grant_type": "client_credentials",
                "client_id": self.settings.copernicus_client_id,
                "client_secret": self.settings.copernicus_client_secret,
            }
        else:
            raise RuntimeError("Copernicus user credentials are not configured.")
        response = httpx.post(
            self.settings.copernicus_token_url,
            data=data,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def latest_scene(self, latitude: float, longitude: float, lookback_days: int = 30) -> dict:
        token = self._access_token()
        start = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
        point = f"POINT ({longitude} {latitude})"
        filters = (
            "Collection/Name eq 'SENTINEL-1' and "
            "not contains(Name, '_COG') and "
            f"ContentDate/Start gt {start} and "
            f"OData.CSC.Intersects(area=geography'SRID=4326;{point}')"
        )
        response = httpx.get(
            self.settings.copernicus_catalog_url,
            params={"$filter": filters, "$orderby": "ContentDate/Start desc", "$top": 1},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        response.raise_for_status()
        products = response.json().get("value", [])
        if not products:
            return {"available": False, "source": "copernicus", "latitude": latitude, "longitude": longitude}
        product = products[0]
        return {
            "available": True,
            "source": "copernicus",
            "product_id": product.get("Id"),
            "name": product.get("Name"),
            "content_date": product.get("ContentDate", {}).get("Start"),
            "online": product.get("Online"),
            "latitude": latitude,
            "longitude": longitude,
        }

    def download_product(self, product: dict, output_dir: str = "data/satellite") -> dict:
        product_id = product.get("product_id")
        if not product_id:
            raise ValueError("A product id is required to download a satellite scene.")
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        name = product.get("name") or f"sentinel-1-{product_id}.zip"
        filename = Path(name).name
        target = output_path / filename
        token = self._access_token()
        download_url = f"{self.settings.copernicus_catalog_url}({product_id})/$zip"
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(timeout=300, follow_redirects=False) as client:
            for _ in range(5):
                response = client.get(download_url, headers=headers)
                if response.status_code not in (301, 302, 303, 307, 308):
                    break
                redirect_url = response.headers.get("location")
                response.close()
                if not redirect_url:
                    raise RuntimeError("Copernicus returned a download redirect without a location.")
                download_url = str(httpx.URL(download_url).join(redirect_url))
            else:
                raise RuntimeError("Copernicus returned too many download redirects.")
            with client.stream("GET", download_url, headers=headers, follow_redirects=False) as response:
                response.raise_for_status()
                with target.open("wb") as output:
                    for chunk in response.iter_bytes():
                        output.write(chunk)
        return {"path": str(target), "bytes": target.stat().st_size, **product}

    def water_extent(self, *_):
        raise NotImplementedError("Satellite scene found; flood extent classification is the next processing step.")

    def process_zone(self, latitude: float, longitude: float, days: int = 14) -> dict:
        """Request a small Sentinel-1 raster and analyze it without writing it to disk."""
        token = self._access_token()
        margin = 0.025
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)
        payload = {
            "input": {
                "bounds": {
                    "bbox": [longitude - margin, latitude - margin, longitude + margin, latitude + margin],
                    "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
                },
                "data": [{
                    "type": "sentinel-1-grd",
                    "dataFilter": {
                        "timeRange": {"from": start.isoformat(), "to": now.isoformat()},
                        "acquisitionMode": "IW",
                        "polarization": "DV",
                        "resolution": "HIGH",
                        "mosaickingOrder": "mostRecent",
                    },
                    "processing": {"orthorectify": True, "backCoeff": "SIGMA0_ELLIPSOID"},
                }],
            },
            "output": {
                "width": 128,
                "height": 128,
                "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}],
            },
            "evalscript": """//VERSION=3
function setup() {
  return { input: [{ bands: [\"VV\", \"VH\", \"dataMask\"] }], output: { bands: 3, sampleType: \"FLOAT32\" } };
}
function evaluatePixel(sample) { return [sample.VV, sample.VH, sample.dataMask]; }
""",
        }
        response = httpx.post(
            self.settings.copernicus_process_url,
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
        response.raise_for_status()
        with MemoryFile(response.content) as memory_file:
            with memory_file.open() as dataset:
                bands = dataset.read(masked=True)
                valid = np.asarray(bands[2].filled(0)) > 0
                if not valid.any():
                    raise RuntimeError("Sentinel-1 returned no valid pixels for this zone.")
                vv = np.asarray(bands[0].filled(np.nan))[valid]
                vh = np.asarray(bands[1].filled(np.nan))[valid]
                return {
                    "source": "copernicus-process-api",
                    "mode": "in-memory",
                    "observed_from": start.isoformat(),
                    "observed_to": now.isoformat(),
                    "width": dataset.width,
                    "height": dataset.height,
                    "valid_pixels": int(valid.sum()),
                    "vv_mean": round(float(np.nanmean(vv)), 4),
                    "vh_mean": round(float(np.nanmean(vh)), 4),
                    "latitude": latitude,
                    "longitude": longitude,
                }


class DemoSatelliteProvider:
    def latest_scene(self, latitude: float, longitude: float, lookback_days: int = 30) -> dict:
        return {
            "available": True,
            "source": "copernicus-sentinel1-demo",
            "product_id": "S1A_IW_GRDH_1SDV_DEMO_KOLKATA",
            "name": "S1A_IW_GRDH_1SDV_20260909_KOLKATA.SAFE",
            "content_date": datetime.now(timezone.utc).isoformat(),
            "online": True,
            "latitude": latitude,
            "longitude": longitude,
        }

    def download_product(self, product: dict, output_dir: str = "data/satellite") -> dict:
        return {
            "path": "data/satellite/demo_sentinel1.zip",
            "bytes": 10485760,
            "source": "demo",
            **product,
        }

    def process_zone(self, latitude: float, longitude: float, days: int = 14) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "source": "copernicus-process-api-demo",
            "mode": "in-memory",
            "observed_from": (now - timedelta(days=days)).isoformat(),
            "observed_to": now.isoformat(),
            "width": 128,
            "height": 128,
            "valid_pixels": 16384,
            "vv_mean": -12.45,
            "vh_mean": -18.92,
            "water_fraction": 0.38,
            "latitude": latitude,
            "longitude": longitude,
        }

    def water_extent(self, *_):
        return {"flood_extent_km2": 8.4, "confidence": 0.78, "source": "demo"}


def get_satellite_provider(live: bool = False):
    settings = get_settings()
    has_creds = bool((settings.copernicus_username and settings.copernicus_password) or (settings.copernicus_client_id and settings.copernicus_client_secret))
    if live and has_creds:
        return LiveSatelliteProvider()
    return DemoSatelliteProvider()

