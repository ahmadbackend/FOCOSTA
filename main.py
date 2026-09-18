#!/usr/bin/env python3
"""
Fotocasa property pipeline — single entry point.

The collection process is a chain of stages, each reading what the previous one
wrote. Every stage is an independent script under HOMES/ that can still be run on
its own; this driver wires them into one ordered journey, passes configuration
down through the environment, and refuses to start a stage whose input is missing.

    python main.py list                     show every stage and its input/output
    python main.py run scrape               run one stage
    python main.py pipeline                 run the whole chain
    python main.py pipeline --from dedupe   resume partway through
    python main.py pipeline --dry-run       print the plan, run nothing

Stage scripts read their settings from FC_* environment variables, falling back to
the defaults baked into each script, so running a stage directly behaves exactly as
it always did.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOMES = ROOT / "HOMES"


@dataclass
class Stage:
    name: str
    script: str
    summary: str
    produces: str
    consumes: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    optional: bool = False


# The pipeline, in execution order. `consumes`/`produces` are paths relative to
# HOMES/ and are what the driver checks before and after a stage runs.
STAGES: list[Stage] = [
    Stage(
        name="harvest-locations",
        script="combined_loc_harvest.py",
        summary="Query the Fotocasa suggest API to build the location tree (depth 3)",
        produces="fotocasa_locations_depth3.json",
    ),
    Stage(
        name="filter-locations",
        script="filter_unseen_locations.py",
        summary="Drop locations already covered by a previous run or by a parent region",
        consumes="fotocasa_locations_depth3.json",
        produces="fotocasa_locations_unseen.json",
    ),
    Stage(
        name="scrape",
        script="multi_thread_corrected.py",
        summary="Walk every location's paginated ad search; resumable, one worker per thread",
        consumes="fotocasa_locations_unseen.json",
        produces="fotocasa_clean_properties_urgent_2",
    ),
    Stage(
        name="retry",
        script="retry_missed_thread.py",
        summary="Re-request the pages logged as failed during scrape",
        consumes="missed_failed.log",
        produces="missed_properties_mt",
        optional=True,
    ),
    Stage(
        name="dedupe",
        script="dedupe_global.py",
        summary="Collapse duplicate property ids across every batch file into 5k-item batches",
        consumes="fotocasa_clean_properties_urgent_2",
        produces="fotocasa_clean_properties_global_deduped",
    ),
    Stage(
        name="map-features",
        script="features_mapper.py",
        summary="Map raw feature ids onto readable field names via manual_map.json",
        consumes="fotocasa_clean_properties_global_deduped",
        produces="mapped_final_urgent",
    ),
    Stage(
        name="filter-private",
        script="filter_particular_batches.py",
        summary="Keep only private-seller listings, rebatched",
        consumes="mapped_final_urgent",
        produces="particular_properties_urgent",
    ),
    Stage(
        name="enrich",
        script="feature_enrichment.py",
        summary="Normalize features and derive location fields per listing",
        consumes="particular_properties_urgent",
        produces="enriched_final_urgent",
    ),
    Stage(
        name="export",
        script="merge_enriched_to_csv.py",
        summary="Merge enriched batches into one JSON plus a flattened CSV",
        consumes="enriched_final_urgent",
        produces="enriched_final_urgent_merged.csv",
    ),
    Stage(
        name="agencies",
        script="extract_unique_agencies.py",
        summary="Extract the unique agency list from the enriched listings",
        consumes="enriched_final_urgent",
        produces="unique_agencies_urgent.json",
        optional=True,
    ),
    Stage(
        name="agencies-phone",
        script="enrich_phone_agencies.py",
        summary="Resolve agency phone numbers from their minisite pages",
        consumes="unique_agencies_urgent.json",
        produces="agencies_with_phone_urgent.json",
        optional=True,
    ),
    Stage(
        name="agencies-email",
        script="enrich_email.py",
        summary="Resolve agency email and website from their minisite pages",
        consumes="agencies_with_phone_urgent.json",
        produces="agencies_full.json",
        optional=True,
    ),
    Stage(
        name="split-regions",
        script="split_private_by_region.py",
        summary="Split the merged private listings into one file per province",
        consumes="enriched_final_urgent_merged.json",
        produces="private_urgent_by_region",
        optional=True,
    ),
]

BY_NAME = {s.name: s for s in STAGES}


def build_env(args: argparse.Namespace) -> dict[str, str]:
    """Translate global CLI options into the FC_* variables the stages read."""
    env = os.environ.copy()
    if args.proxy_file:
        env["FC_PROXY_FILE"] = str(Path(args.proxy_file).resolve())
    if args.threads:
        env["FC_NUM_THREADS"] = str(args.threads)
    if args.sleep is not None:
        env["FC_SLEEP"] = str(args.sleep)
    if args.page_size:
        env["FC_PAGE_SIZE"] = str(args.page_size)
    for item in args.set or []:
        if "=" not in item:
            sys.exit(f"--set expects NAME=VALUE, got {item!r}")
        key, value = item.split("=", 1)
        env[f"FC_{key.upper()}"] = value
    return env


def exists(rel: str) -> bool:
    path = HOMES / rel
    if path.is_dir():
        return any(path.iterdir())
    return path.exists()


def run_stage(stage: Stage, env: dict[str, str], dry_run: bool) -> bool:
    """Run one stage. Returns False if it failed."""
    script = HOMES / stage.script
    if not script.exists():
        print(f"  !! {stage.script} is missing")
        return False

    missing_input = bool(stage.consumes) and not exists(stage.consumes)

    # In a dry run the earlier stages have not produced anything yet, so a missing
    # input is expected — report it and keep walking the plan.
    if missing_input and not dry_run:
        if stage.optional:
            print(f"  -- skipping {stage.name}: {stage.consumes} not found")
            return True
        print(f"  !! {stage.name} needs {stage.consumes}, which does not exist")
        print("     run the earlier stages first, or pass --from to start later")
        return False

    print(f"\n==> {stage.name}  ({stage.script})")
    print(f"    {stage.summary}")
    if stage.consumes:
        note = "  (not present yet)" if missing_input else ""
        print(f"    in  {stage.consumes}{note}")
    print(f"    out {stage.produces}")

    if dry_run:
        return True

    started = time.time()
    stage_env = {**env, **stage.env}
    result = subprocess.run([sys.executable, stage.script], cwd=HOMES, env=stage_env)
    elapsed = time.time() - started

    if result.returncode != 0:
        print(f"    FAILED after {elapsed:.1f}s (exit {result.returncode})")
        return False

    produced = "ok" if exists(stage.produces) else "WARNING: expected output missing"
    print(f"    done in {elapsed:.1f}s — {produced}")
    return True


def cmd_list(_args: argparse.Namespace) -> int:
    width = max(len(s.name) for s in STAGES)
    print("Pipeline stages, in order:\n")
    for i, s in enumerate(STAGES, 1):
        flag = "  (optional)" if s.optional else ""
        here = "yes" if exists(s.produces) else "no"
        print(f"{i:>2}. {s.name:<{width}}  output present: {here:<3}{flag}")
        print(f"    {s.summary}")
        print(f"    {s.script}  ->  {s.produces}\n")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    stage = BY_NAME.get(args.stage)
    if stage is None:
        sys.exit(f"unknown stage {args.stage!r} — try: python main.py list")
    ok = run_stage(stage, build_env(args), args.dry_run)
    return 0 if ok else 1


def cmd_pipeline(args: argparse.Namespace) -> int:
    names = [s.name for s in STAGES]
    start = names.index(args.start) if args.start else 0
    stop = names.index(args.stop) + 1 if args.stop else len(STAGES)
    if start >= stop:
        sys.exit(f"--from {args.start} comes after --to {args.stop}")

    selected = STAGES[start:stop]
    env = build_env(args)

    print(f"Fotocasa pipeline — {len(selected)} stage(s)"
          f"{' [dry run]' if args.dry_run else ''}")

    began = time.time()
    for stage in selected:
        if not run_stage(stage, env, args.dry_run):
            print(f"\nStopped at {stage.name}.")
            return 1

    print(f"\nPipeline finished in {time.time() - began:.1f}s")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Fotocasa property pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run 'python main.py list' to see the stages.",
    )

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--proxy-file", help="proxy list, host:port:user:pass per line")
    common.add_argument("--threads", type=int, help="worker threads for scraping stages")
    common.add_argument("--sleep", type=float, help="delay between requests, seconds")
    common.add_argument("--page-size", type=int, help="results per search page")
    common.add_argument("--set", action="append", metavar="NAME=VALUE",
                        help="override any stage constant, e.g. --set OUTPUT_ROOT=run2")
    common.add_argument("--dry-run", action="store_true",
                        help="print what would run without running it")

    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="show the stages and which outputs exist")
    p_list.set_defaults(func=cmd_list)

    p_run = sub.add_parser("run", parents=[common], help="run a single stage")
    p_run.add_argument("stage", choices=[s.name for s in STAGES])
    p_run.set_defaults(func=cmd_run)

    p_pipe = sub.add_parser("pipeline", parents=[common], help="run stages in order")
    p_pipe.add_argument("--from", dest="start", choices=[s.name for s in STAGES],
                        help="first stage to run")
    p_pipe.add_argument("--to", dest="stop", choices=[s.name for s in STAGES],
                        help="last stage to run")
    p_pipe.set_defaults(func=cmd_pipeline)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
