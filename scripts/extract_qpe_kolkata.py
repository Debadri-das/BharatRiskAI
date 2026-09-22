"""Decode INSAT HEM QPE and align it to the DEM grid."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingestion.real_data import align_to_grid, read_qpe, target_grid

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    source = next((ROOT / "data" / "insat" / "qpe" / "raw").glob("*.h5"))
    product = read_qpe(source)
    output = ROOT / "data" / "insat" / "qpe" / "processed" / f"{source.stem}.npz"
    output.parent.mkdir(parents=True, exist_ok=True)
    import numpy as np
    np.savez_compressed(output, observed_at=product["observed_at"], qpe=align_to_grid(product["qpe"], product["latitude"], product["longitude"], target_grid(ROOT / "data" / "dem" / "kolkata_dem.tif"), nearest=True))
    print(output)


if __name__ == "__main__":
    main()
