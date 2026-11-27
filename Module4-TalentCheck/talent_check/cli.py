"""Command line: python -m talent_check <command>

  run        --profile FILE --company NAME|--company-id N [--out FILE]
  companies  [--q TEXT]
  check-data                      verifies the Supabase/CSV source end to end
  export-snapshot [--out FILE]    writes talent_check_company_skillsets.json from the live source
  serve                           starts the HTTP API
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from .company_data import directory_to_snapshot
from .errors import TalentCheckError
from .repository import COMPANY_JSON, DataRepository
from .service import TalentCheckService


def _print(obj) -> None:
    sys.stdout.write(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="talent_check", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--profile", required=True)
    r.add_argument("--company")
    r.add_argument("--company-id")
    r.add_argument("--out")
    c = sub.add_parser("companies")
    c.add_argument("--q", default="")
    sub.add_parser("check-data")
    e = sub.add_parser("export-snapshot")
    e.add_argument("--out")
    sub.add_parser("serve")
    args = ap.parse_args(argv)

    try:
        if args.cmd == "serve":
            from .server import serve
            serve()
            return 0
        repo = DataRepository()
        svc = TalentCheckService(repo)
        if args.cmd == "run":
            try:
                with open(args.profile, "r", encoding="utf-8-sig") as fh:
                    profile = json.load(fh)
            except (OSError, ValueError) as exc:
                sys.stderr.write(f"Cannot read profile {args.profile}: {exc}\n")
                return 2
            result = svc.run(profile, company=args.company, company_id=args.company_id)
            if args.out:
                with open(args.out, "w", encoding="utf-8") as fh:
                    json.dump(result, fh, indent=2, ensure_ascii=False)
                print(f"Saved {args.out}  (readiness {result['readiness_score']} - {result['readiness_label']})")
            else:
                _print(result)
        elif args.cmd == "companies":
            _print(svc.companies(args.q))
        elif args.cmd == "check-data":
            h = repo.health()
            rubric = repo.get_rubric()
            _print({**h, "rubric_levels": sum(len(v) for v in rubric.topics.values()),
                    "rubric_warnings": rubric.warnings})
        elif args.cmd == "export-snapshot":
            directory, source = repo.get_directory(force_refresh=True)
            import os
            out = args.out or os.path.join(repo.settings.data_dir, COMPANY_JSON)
            with open(out, "w", encoding="utf-8") as fh:
                json.dump(directory_to_snapshot(directory), fh, indent=2, ensure_ascii=False)
            print(f"Wrote {len(directory)} companies from {source} -> {out}")
        return 0
    except TalentCheckError as exc:
        sys.stderr.write(f"ERROR [{exc.code}]: {exc.message}\n")
        if exc.details:
            sys.stderr.write(json.dumps(exc.details, indent=2, ensure_ascii=False) + "\n")
        return 1
