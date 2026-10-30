"""Create a local coverage manifest for the external research dataset."""
import argparse
import json
from pathlib import Path

from engine.research_data import build_coverage_report, get_research_root


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None, help="Research repository clone root")
    parser.add_argument("--output", default="data/research_coverage.csv")
    args = parser.parse_args()
    report = build_coverage_report(args.root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(output, index=False)
    metadata = {
        "source_repository": "https://github.com/aswinv90/indian-market-historical-data",
        "local_root": str(get_research_root(args.root)),
        "generated_at_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "datasets_present": int(report["exists"].sum()),
        "datasets_checked": int(len(report)),
        "coverage_file": str(output),
        "important": "Presence and schema checks do not establish financial accuracy, TRI status, dividend completeness, or investible total returns."
    }
    Path("data/research_coverage.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(report.to_string(index=False))
    print(f"\nSaved {output} and data/research_coverage.json")


if __name__ == "__main__":
    main()
