"""Package raw source files for upload to the landing volume.

CSV:  each file is gzipped into its own dataset folder, so each one loads into its own bronze table.
      csv/<dataset>/<batch>/<dataset>.csv.gz
FHIR: per-patient bundles are split into one resource per line (NDJSON), grouped by resource type,
      which is the shape of a FHIR bulk export.
      fhir/<batch>/<ResourceType>-<part>.ndjson.gz

Only the file format changes; every record is carried over as it is.

Usage: python scripts/prepare_landing.py data/synthea data/landing 2026-11-06
"""

import gzip
import json
import shutil
import sys
from pathlib import Path

LINES_PER_PART = 100_000


def prepare_csv(source: Path, out: Path, batch: str) -> None:
    for csv_file in sorted((source / "csv").glob("*.csv")):
        dataset = csv_file.stem
        target = out / "csv" / dataset / batch / f"{dataset}.csv.gz"
        target.parent.mkdir(parents=True, exist_ok=True)
        with csv_file.open("rb") as src, gzip.open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)
        print(f"csv  {dataset}")


class PartWriter:
    """Writes NDJSON lines for one resource type, starting a new file every LINES_PER_PART lines."""

    def __init__(self, folder: Path, resource_type: str):
        self.folder, self.resource_type = folder, resource_type
        self.part, self.lines, self.handle = 0, 0, None

    def write(self, line: str) -> None:
        if self.handle is None or self.lines == LINES_PER_PART:
            self.close()
            self.part += 1
            path = self.folder / f"{self.resource_type}-{self.part:04d}.ndjson.gz"
            self.handle = gzip.open(path, "wt", encoding="utf-8")
            self.lines = 0
        self.handle.write(line + "\n")
        self.lines += 1

    def close(self) -> None:
        if self.handle is not None:
            self.handle.close()
            self.handle = None


def prepare_fhir(source: Path, out: Path, batch: str) -> None:
    folder = out / "fhir" / batch
    folder.mkdir(parents=True, exist_ok=True)
    writers: dict[str, PartWriter] = {}
    bundles = sorted((source / "fhir").glob("*.json"))
    for i, bundle_file in enumerate(bundles, 1):
        bundle = json.loads(bundle_file.read_text(encoding="utf-8"))
        for entry in bundle.get("entry", []):
            resource = entry["resource"]
            rtype = resource["resourceType"]
            writer = writers.setdefault(rtype, PartWriter(folder, rtype))
            writer.write(json.dumps(resource, separators=(",", ":"), ensure_ascii=False))
        if i % 100 == 0 or i == len(bundles):
            print(f"fhir {i}/{len(bundles)} bundles")
    for writer in writers.values():
        writer.close()
    print("fhir resource types:", ", ".join(sorted(writers)))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    source_dir, out_dir, batch_label = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    prepare_csv(source_dir, out_dir, batch_label)
    prepare_fhir(source_dir, out_dir, batch_label)
