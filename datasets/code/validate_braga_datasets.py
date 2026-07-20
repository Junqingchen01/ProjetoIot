#!/usr/bin/env python3
"""
Validate Braga datasets against backend detection rules.

This is an offline validator: it reads each telemetry.csv, runs the backend
analyze_telemetry function, and compares generated alerts with truth.json.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import types
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
DEFAULT_DATASET_ROOT = REPO_ROOT / "datasets" / "braga"

os.environ.setdefault("INFLUX_TOKEN", "validation-token")
os.environ.setdefault("INFLUX_ORG", "validation-org")
os.environ.setdefault("INFLUX_BUCKET", "Iot")
os.environ.setdefault("INFLUX_URL", "http://localhost:8086")
os.environ.setdefault("API_KEY_EDGE", "validation-key")
os.environ.setdefault("MQTT_BROKER", "localhost")
os.environ.setdefault("MQTT_PORT", "1883")
os.environ.setdefault("MQTT_TLS_ENABLED", "false")

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(BACKEND_ROOT))

from import_dataset import discover_scenarios, read_csv, telemetry_payload  # noqa: E402


def _load_detection_with_project_dependencies():
    from app.models.sensor import SensorData  # noqa: E402
    from app.services.detection import analyze_telemetry, reset_detection_state  # noqa: E402

    return SensorData, analyze_telemetry, reset_detection_state


class _FallbackSensorData:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if key == "timestamp" and isinstance(value, str):
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            setattr(self, key, value)


class _FallbackAlertData:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        data = dict(self.__dict__)
        if mode == "json":
            for key, value in list(data.items()):
                if isinstance(value, datetime):
                    data[key] = value.isoformat()
        return data


class _FallbackSettings:
    THRESHOLD_FALL_ACCEL = float(os.getenv("THRESHOLD_FALL_ACCEL", "20.0"))
    THRESHOLD_HARD_BRAKE = float(os.getenv("THRESHOLD_HARD_BRAKE", "-6.0"))
    THRESHOLD_JAM_SPEED = float(os.getenv("THRESHOLD_JAM_SPEED", "2.0"))
    THRESHOLD_OBSTACLE_FRONT_M = float(os.getenv("THRESHOLD_OBSTACLE_FRONT_M", "0.45"))
    THRESHOLD_OBSTACLE_SPEED = float(os.getenv("THRESHOLD_OBSTACLE_SPEED", "6.0"))
    JAM_TIME_WINDOW_SEC = int(os.getenv("JAM_TIME_WINDOW_SEC", "60"))
    JAM_MIN_CONSECUTIVE_SAMPLES = int(os.getenv("JAM_MIN_CONSECUTIVE_SAMPLES", "60"))
    ALERT_COOLDOWN_SEC = int(os.getenv("ALERT_COOLDOWN_SEC", "15"))


def _install_detection_stubs() -> None:
    app_module = sys.modules.setdefault("app", types.ModuleType("app"))
    models_module = sys.modules.setdefault("app.models", types.ModuleType("app.models"))
    core_module = sys.modules.setdefault("app.core", types.ModuleType("app.core"))

    sensor_module = types.ModuleType("app.models.sensor")
    sensor_module.SensorData = _FallbackSensorData
    alert_module = types.ModuleType("app.models.alert")
    alert_module.AlertData = _FallbackAlertData
    config_module = types.ModuleType("app.core.config")
    config_module.settings = _FallbackSettings()

    app_module.models = models_module
    app_module.core = core_module
    sys.modules["app.models.sensor"] = sensor_module
    sys.modules["app.models.alert"] = alert_module
    sys.modules["app.core.config"] = config_module


def _load_detection_with_stubs():
    _install_detection_stubs()
    detection_path = BACKEND_ROOT / "app" / "services" / "detection.py"
    spec = importlib.util.spec_from_file_location("validation_detection", detection_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load detection module from {detection_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return _FallbackSensorData, module.analyze_telemetry, module.reset_detection_state


try:
    SensorData, analyze_telemetry, reset_detection_state = _load_detection_with_project_dependencies()
except ModuleNotFoundError:
    SensorData, analyze_telemetry, reset_detection_state = _load_detection_with_stubs()


def expected_events(truth_path: Path | None) -> list[dict[str, Any]]:
    if truth_path is None:
        return []
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    return truth.get("events", [])


def detect_events(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    reset_detection_state()
    detected = []
    for row in rows:
        sensor = SensorData(**telemetry_payload(row))
        alert = analyze_telemetry(sensor)
        if alert:
            detected.append(alert.model_dump(mode="json"))
    return detected


def compare(expected: list[dict[str, Any]], detected: list[dict[str, Any]]) -> dict[str, Any]:
    expected_counts = Counter(event["event_type"] for event in expected)
    detected_counts = Counter(event["event_type"] for event in detected)

    missing = []
    false_positives = []

    for event_type, count in expected_counts.items():
        deficit = count - detected_counts.get(event_type, 0)
        missing.extend([event_type] * max(0, deficit))

    for event_type, count in detected_counts.items():
        surplus = count - expected_counts.get(event_type, 0)
        false_positives.extend([event_type] * max(0, surplus))

    return {
        "expected": dict(expected_counts),
        "detected": dict(detected_counts),
        "missing": missing,
        "false_positives": false_positives,
        "passed": not missing and not false_positives,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Braga datasets against backend detection.")
    parser.add_argument("--dataset-root", default=str(DEFAULT_DATASET_ROOT), help="Root folder containing scenario folders.")
    parser.add_argument("--scenario", action="append", default=[], help="Scenario id to validate. Can be used multiple times.")
    parser.add_argument("--json-output", help="Optional path to write detailed validation results.")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 if any scenario fails.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    scenarios = discover_scenarios(Path(args.dataset_root), args.scenario)

    results = []
    failed = 0
    for scenario in scenarios:
        rows = read_csv(scenario.telemetry_path)
        expected = expected_events(scenario.truth_path)
        detected = detect_events(rows)
        summary = compare(expected, detected)
        if not summary["passed"]:
            failed += 1
        result = {
            "scenario_id": scenario.scenario_id,
            "rows": len(rows),
            "expected_events": expected,
            "detected_events": detected,
            **summary,
        }
        results.append(result)
        status = "PASS" if summary["passed"] else "FAIL"
        print(
            f"{status} {scenario.scenario_id}: "
            f"expected={summary['expected']} detected={summary['detected']} "
            f"missing={summary['missing']} false_positives={summary['false_positives']}"
        )

    report = {
        "total_scenarios": len(results),
        "failed_scenarios": failed,
        "passed_scenarios": len(results) - failed,
        "results": results,
    }

    if args.json_output:
        output_path = Path(args.json_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.strict and failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
