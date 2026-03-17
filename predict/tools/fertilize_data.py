"""
CLI tool to generate synthetic training data for PREDICT AI models.

Usage:
    python -m predict.tools.fertilize_data
    python -m predict.tools.fertilize_data --normal 1000 --per-failure 100 --augment 5
    python -m predict.tools.fertilize_data --scenarios alternator_failing,worn_spark_plugs
    python -m predict.tools.fertilize_data --list-scenarios
    python -m predict.tools.fertilize_data --list-cascades
    python -m predict.tools.fertilize_data --archetype sports_car
    python -m predict.tools.fertilize_data --no-artifacts --no-correlations
    python -m predict.tools.fertilize_data --split --validate
    python -m predict.tools.fertilize_data --db-insert --profile-id 1

"""

import argparse
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s -- %(message)s",
)
logger = logging.getLogger("predict.tools.fertilize_data")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic training data for PREDICT AI models",
    )
    # Core parameters
    parser.add_argument(
        "--normal", type=int, default=500,
        help="Number of normal/healthy driving sequences (default: 500)",
    )
    parser.add_argument(
        "--per-failure", type=int, default=50,
        help="Number of sequences per failure scenario (default: 50)",
    )
    parser.add_argument(
        "--augment", type=int, default=3,
        help="Augmentation factor -- copies per original (default: 3)",
    )
    parser.add_argument(
        "--seq-len", type=int, default=60,
        help="Sequence length in time steps (default: 60)",
    )
    parser.add_argument(
        "--scenarios", type=str, default=None,
        help="Comma-separated scenario names (default: all)",
    )

    # Quality layers
    parser.add_argument(
        "--archetype", type=str, default=None,
        help="Vehicle archetype: economy_sedan, suv_truck, sports_car, old_vehicle, diesel (default: random mix)",
    )
    parser.add_argument(
        "--no-artifacts", action="store_true",
        help="Disable OBD sensor artifacts (quantization, dropout, stuck values)",
    )
    parser.add_argument(
        "--no-correlations", action="store_true",
        help="Disable cross-sensor physical correlations",
    )
    parser.add_argument(
        "--no-cascades", action="store_true",
        help="Disable cascading multi-fault scenarios",
    )
    parser.add_argument(
        "--artifact-intensity", type=float, default=1.0,
        help="Artifact intensity multiplier 0.0-2.0 (default: 1.0)",
    )

    # Output options
    parser.add_argument(
        "--split", action="store_true",
        help="Also save stratified train/val/test splits",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Run quality validation checks on generated data",
    )
    parser.add_argument(
        "--list-scenarios", action="store_true",
        help="List all available failure scenarios and exit",
    )
    parser.add_argument(
        "--list-cascades", action="store_true",
        help="List all available cascade chains and exit",
    )
    parser.add_argument(
        "--list-archetypes", action="store_true",
        help="List all vehicle archetypes and exit",
    )
    parser.add_argument(
        "--no-save", action="store_true",
        help="Don't save to disk (useful for testing)",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Custom output filename (default: fertilized_<timestamp>.npz)",
    )
    parser.add_argument(
        "--db-insert", action="store_true",
        help="Also insert synthetic records into the database (requires running DB)",
    )
    parser.add_argument(
        "--profile-id", type=int, default=1,
        help="Vehicle profile ID for DB records (default: 1)",
    )
    parser.add_argument(
        "--stats-only", action="store_true",
        help="Generate and print stats, don't save",
    )

    args = parser.parse_args()

    try:
        from predict.core.ai.training.data_fertilizer import (
            CASCADE_CHAINS,
            DataFertilizer,
            FAILURE_SCENARIOS,
            SENSOR_ORDER,
            VEHICLE_ARCHETYPES,
        )
    except ImportError:
        logger.error("data_fertilizer module was removed in v3 AI cleanup. This tool is no longer available.")
        sys.exit(1)

    # --list-scenarios
    if args.list_scenarios:
        print("\n  Available failure scenarios:\n")
        print(f"  {'Name':<35} {'Component':<20} {'Severity':<10} Duration (days)")
        print(f"  {'-' * 35} {'-' * 20} {'-' * 10} {'-' * 15}")
        for name, spec in FAILURE_SCENARIOS.items():
            lo, hi = spec["duration_days"]
            print(f"  {name:<35} {spec['component']:<20} {spec['severity']:<10} {lo}-{hi}")
        print(f"\n  Sensors ({len(SENSOR_ORDER)}): {', '.join(SENSOR_ORDER)}")
        print(f"  Total scenarios: {len(FAILURE_SCENARIOS)}")
        return

    # --list-cascades
    if args.list_cascades:
        print("\n  Cascading multi-fault chains:\n")
        for name, chain in CASCADE_CHAINS.items():
            stages = " -> ".join(s["scenario"] for s in chain["stages"])
            print(f"  {name}")
            print(f"    {chain['description']}")
            print(f"    Stages: {stages}")
            print()
        return

    # --list-archetypes
    if args.list_archetypes:
        print("\n  Vehicle archetypes:\n")
        for name, arch in VEHICLE_ARCHETYPES.items():
            print(f"  {name:<20} {arch['description']}")
            print(f"    RPM scale: {arch['rpm_scale']:.2f}  "
                  f"Voltage offset: {arch['voltage_offset']:+.1f}V  "
                  f"Noise: {arch.get('noise_multiplier', 1.0):.1f}x")
            print()
        return

    # Validate archetype
    if args.archetype and args.archetype not in VEHICLE_ARCHETYPES:
        logger.error("Unknown archetype: %s", args.archetype)
        logger.info("Available: %s", ", ".join(VEHICLE_ARCHETYPES.keys()))
        sys.exit(1)

    # Parse scenarios
    scenarios = None
    if args.scenarios:
        scenarios = [s.strip() for s in args.scenarios.split(",")]
        invalid = [s for s in scenarios if s not in FAILURE_SCENARIOS]
        if invalid:
            logger.error("Unknown scenarios: %s", invalid)
            logger.info("Use --list-scenarios to see available options")
            sys.exit(1)

    # Generate
    t0 = time.time()
    logger.info("Starting data fertilization...")
    logger.info("  Quality layers: correlations=%s, artifacts=%s (%.1fx), cascades=%s",
                not args.no_correlations, not args.no_artifacts,
                args.artifact_intensity, not args.no_cascades)

    fert = DataFertilizer(
        sequence_length=args.seq_len,
        archetype=args.archetype,
        enable_artifacts=not args.no_artifacts,
        enable_correlations=not args.no_correlations,
        artifact_intensity=args.artifact_intensity,
    )
    X, y, meta = fert.create_training_dataset(
        n_normal=args.normal,
        n_per_failure=args.per_failure,
        scenarios=scenarios,
        augmentation_factor=args.augment,
        include_cascades=not args.no_cascades,
    )

    elapsed = time.time() - t0
    stats = fert.get_dataset_stats(X, y)

    # Print stats
    print(f"\n  Dataset generated in {elapsed:.1f}s")
    print(f"  Shape: {X.shape}  ({stats['n_samples']} samples x {stats['seq_len']} steps x {stats['n_sensors']} sensors)")
    print(f"  Labels: {stats['healthy_count']} healthy | {stats.get('degrading_count', 0)} degrading | {stats['failure_count']} near-failure")
    print(f"  Label mean: {stats['label_mean']:.3f}  std: {stats['label_std']:.3f}")
    print()

    # Sensor correlation check
    if "sensor_correlation_matrix" in stats:
        corr = stats["sensor_correlation_matrix"]
        print("  Sensor correlations (quality indicator):")
        print(f"    RPM-Speed:     {corr['rpm_speed']:+.3f}")
        print(f"    RPM-MAF:       {corr['rpm_maf']:+.3f}")
        print(f"    Throttle-Load: {corr['throttle_load']:+.3f}")
        print(f"    Coolant-Oil:   {corr['coolant_oil']:+.3f}")
        print()

    # Scenario breakdown
    scenario_counts = fert._count_scenarios(meta)
    print("  Scenario breakdown:")
    for name, count in sorted(scenario_counts.items(), key=lambda x: -x[1]):
        marker = " [cascade]" if name.startswith("cascade_") else ""
        print(f"    {name:<35} {count:>5} samples{marker}")
    print()

    # Validate
    if args.validate:
        quality = fert.validate_dataset_quality(X, y, meta)
        print(f"  Quality validation: {quality['verdict']}")
        for p in quality["passed"]:
            print(f"    [PASS] {p}")
        for w in quality["warnings"]:
            print(f"    [WARN] {w}")
        for f in quality["failures"]:
            print(f"    [FAIL] {f}")
        print()

    if args.stats_only:
        print("  --stats-only: skipping save")
        return

    # Save
    if not args.no_save:
        path = fert.save_to_npz(X, y, meta, filename=args.output)
        print(f"  Saved to: {path}")
        print(f"  Metadata: {path.with_suffix('.meta.json')}")

        # Optionally save splits
        if args.split:
            splits = fert.split_dataset(X, y, meta)
            import numpy as np
            split_dir = path.parent
            stem = path.stem
            for split_name in ("train", "val", "test"):
                split_path = split_dir / f"{stem}_{split_name}.npz"
                np.savez_compressed(
                    str(split_path),
                    X=splits[f"{split_name}_X"],
                    y=splits[f"{split_name}_y"],
                    sensor_order=SENSOR_ORDER,
                )
                n = len(splits[f"{split_name}_y"])
                print(f"  Split saved: {split_path} ({n} samples)")
    else:
        print("  --no-save: skipping file output")

    # Optional DB insert
    if args.db_insert:
        logger.info("Inserting synthetic records into database for profile_id=%d...", args.profile_id)
        _insert_to_db(fert, scenarios or list(FAILURE_SCENARIOS.keys()), args.profile_id)

    print("\n  Done.")


def _insert_to_db(fert: "DataFertilizer", scenarios: list, profile_id: int) -> None:
    """Insert synthetic records into the database (async)."""
    import asyncio

    async def _do_insert():
        from predict.core.db.session import get_db_session

        inserted_data = 0
        inserted_labels = 0

        async for session in get_db_session():
            for scenario_name in scenarios:
                rows, label = fert.generate_db_records(scenario_name, profile_id)

                from predict.core.db.models.vehicle import VehicleData
                for row_data in rows:
                    record = VehicleData(**row_data)
                    session.add(record)
                    inserted_data += 1

                from predict.core.db.models.prediction import MLTrainingLabel
                training_label = MLTrainingLabel(**label)
                session.add(training_label)
                inserted_labels += 1

            await session.commit()
            logger.info(
                "Inserted %d VehicleData records + %d MLTrainingLabel records",
                inserted_data, inserted_labels,
            )

    try:
        asyncio.run(_do_insert())
    except Exception as e:
        logger.error("DB insert failed (is the database running?): %s", e)
        logger.info("The .npz file was still saved -- you can retry DB insert later")


if __name__ == "__main__":
    main()
