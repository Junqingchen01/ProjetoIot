#!/usr/bin/env python3
"""
Replay Braga micromobility simulation datasets into the IoT backend.

Examples:
  python import_dataset.py --mode rest --api-key %API_KEY_EDGE%
  python import_dataset.py --mode mqtt --mqtt-tls --mqtt-ca-cert .\\mosquitto-ca.crt --mqtt-host localhost --mqtt-port 8883
  python import_dataset.py --mode dry-run --scenario fall_accident_001
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET_ROOT = REPO_ROOT / "datasets" / "braga"
DEFAULT_API_URL = f"http://127.0.0.1:{os.getenv('BACKEND_HOST_PORT', '8000')}/api/v1/sensors"
DEFAULT_MQTT_PORT = 8883

SEND_FIELDS = {
    "device_id",
    "timestamp",
    "source",
    "type",
    "session_id",
    "vehicle_type",
    "trip_id",
    "sequence",
    "start_station_id",
    "start_station_name",
    "end_station_id",
    "end_station_name",
    "dock_status",
    "charging",
    "lat",
    "lon",
    "speed",
    "accel_x",
    "accel_y",
    "accel_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
    "gps_accuracy_m",
    "range_front_m",
    "range_left_m",
    "ultrasonic_valid",
    "battery",
}

FLOAT_FIELDS = {
    "lat",
    "lon",
    "speed",
    "accel_x",
    "accel_y",
    "accel_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
    "gps_accuracy_m",
    "range_front_m",
    "range_left_m",
    "battery",
}

INT_FIELDS = {"sequence"}
BOOL_FIELDS = {"ultrasonic_valid", "charging"}


@dataclass
class Scenario:
    scenario_id: str
    telemetry_path: Path
    truth_path: Path | None
    vehicle_type: str = "scooter"
    metadata: dict[str, Any] | None = None


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "sim"}


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def telemetry_payload(row: dict[str, str]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in SEND_FIELDS:
        value = row.get(key)
        if value is None or value == "":
            continue
        if key in FLOAT_FIELDS:
            payload[key] = float(value)
        elif key in INT_FIELDS:
            payload[key] = int(float(value))
        elif key in BOOL_FIELDS:
            payload[key] = parse_bool(value)
        else:
            payload[key] = value
    return payload


def alert_payload(event: dict[str, Any], row: dict[str, str]) -> dict[str, Any]:
    payload = {
        "device_id": row["device_id"],
        "timestamp": event["timestamp"],
        "source": "simulated_truth",
        "type": "alert",
        "event_type": event["event_type"],
        "session_id": row.get("session_id") or None,
        "severity": event.get("severity") or severity_for_event(event["event_type"]),
        "vehicle_type": row.get("vehicle_type") or None,
        "lat": float(event.get("lat", row["lat"])),
        "lon": float(event.get("lon", row["lon"])),
        "trigger": event.get("expected_trigger", "truth_event"),
        "speed": float(row.get("speed") or 0.0),
        "accel_x": float(row.get("accel_x") or 0.0),
        "accel_y": float(row.get("accel_y") or 0.0),
        "accel_z": float(row.get("accel_z") or 0.0),
    }
    for key in ("gyro_x", "gyro_y", "gyro_z", "range_front_m", "range_left_m"):
        if row.get(key):
            payload[key] = float(row[key])
    if row.get("ultrasonic_valid"):
        payload["ultrasonic_valid"] = parse_bool(row["ultrasonic_valid"])
    return payload


def severity_for_event(event_type: str) -> str:
    if event_type == "fall_accident":
        return "critical"
    if event_type == "obstacle_risk":
        return "high"
    if event_type in {"hard_brake", "traffic_jam"}:
        return "warning"
    if event_type == "dock_data_dump":
        return "info"
    return "info"


def default_session_id(prefix: str = "replay") -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def discover_scenarios(dataset_root: Path, selected: list[str]) -> list[Scenario]:
    if not dataset_root.exists():
        raise FileNotFoundError(f"Dataset root not found: {dataset_root}")

    names = set(selected)
    scenarios: list[Scenario] = []
    for telemetry_path in sorted(dataset_root.rglob("telemetry.csv")):
        scenario_dir = telemetry_path.parent
        if any(part.startswith("_") for part in scenario_dir.relative_to(dataset_root).parts):
            continue
        if names and scenario_dir.name not in names:
            continue
        truth_path = scenario_dir / "truth.json"
        metadata = None
        vehicle_type = "scooter"
        if truth_path.exists():
            try:
                metadata = json.loads(truth_path.read_text(encoding="utf-8"))
                vehicle_type = str(metadata.get("vehicle_type") or vehicle_type)
            except json.JSONDecodeError:
                metadata = None
        scenarios.append(
            Scenario(
                scenario_id=scenario_dir.name,
                telemetry_path=telemetry_path,
                truth_path=truth_path if truth_path.exists() else None,
                vehicle_type=vehicle_type,
                metadata=metadata,
            )
        )

    missing = names - {scenario.scenario_id for scenario in scenarios}
    if missing:
        raise FileNotFoundError(f"Unknown scenario(s): {', '.join(sorted(missing))}")
    if not scenarios:
        raise FileNotFoundError(f"No scenarios with telemetry.csv found in {dataset_root}")
    return scenarios


def wait_for_replay(previous_row: dict[str, str] | None, row: dict[str, str], realtime: bool, speedup: float) -> None:
    if not realtime or previous_row is None:
        return
    previous = parse_timestamp(previous_row["timestamp"])
    current = parse_timestamp(row["timestamp"])
    delay = max(0.0, (current - previous).total_seconds())
    if speedup > 0:
        delay = delay / speedup
    if delay > 0:
        time.sleep(delay)


def send_rest(payload: dict[str, Any], api_url: str, api_key: str, timeout: float) -> None:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(api_url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"Unexpected REST status {response.status}")


def mqtt_client_from_args(args: argparse.Namespace):
    try:
        import paho.mqtt.client as mqtt
        from paho.mqtt.enums import CallbackAPIVersion
    except ImportError as exc:
        raise RuntimeError("paho-mqtt is required for --mode mqtt. Install backend/requirements.txt first.") from exc

    client = mqtt.Client(CallbackAPIVersion.VERSION2)
    if args.mqtt_username or args.mqtt_password:
        client.username_pw_set(args.mqtt_username, args.mqtt_password)
    if args.mqtt_tls:
        ca_cert = (args.mqtt_ca_cert or "").strip() or None
        if ca_cert:
            client.tls_set(ca_certs=ca_cert, cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
            client.tls_insecure_set(False)
        else:
            client.tls_set(
                cert_reqs=ssl.CERT_NONE if args.mqtt_tls_insecure else ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )
            client.tls_insecure_set(bool(args.mqtt_tls_insecure))
    client.connect(args.mqtt_host, args.mqtt_port, 60)
    client.loop_start()
    return client


def replay_scenario(
    scenario: Scenario,
    args: argparse.Namespace,
    mqtt_client=None,
) -> dict[str, Any]:
    rows = read_csv(scenario.telemetry_path)
    truth_events: dict[str, list[dict[str, Any]]] = {}
    if scenario.truth_path and args.publish_truth_alerts:
        truth = json.loads(scenario.truth_path.read_text(encoding="utf-8"))
        for event in truth.get("events", []):
            truth_events.setdefault(event["timestamp"], []).append(event)

    sent = 0
    failed = 0
    previous_row = None

    for row in rows:
        wait_for_replay(previous_row, row, args.realtime, args.speedup)
        payload = telemetry_payload(row)
        if args.session_id:
            payload["session_id"] = args.session_id

        try:
            if args.mode == "rest":
                send_rest(payload, args.api_url, args.api_key, args.timeout)
            elif args.mode == "mqtt":
                topic = f"/bike/{payload['device_id']}/telemetry"
                result = mqtt_client.publish(topic, json.dumps(payload), qos=0)
                if result.rc != 0:
                    raise RuntimeError(f"MQTT publish failed with rc={result.rc}")
            sent += 1
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            failed += 1
            print(f"[WARN] {scenario.scenario_id} {row.get('timestamp')}: {exc}")
            if not args.continue_on_error:
                raise

        if args.mode == "mqtt" and truth_events:
            for event in truth_events.get(row["timestamp"], []):
                row["session_id"] = args.session_id
                alert = alert_payload(event, row)
                topic = f"/bike/{alert['device_id']}/alert"
                result = mqtt_client.publish(topic, json.dumps(alert), qos=1)
                if result.rc != 0:
                    failed += 1
                    print(f"[WARN] {scenario.scenario_id} alert publish failed rc={result.rc}")

        previous_row = row

    return {"scenario_id": scenario.scenario_id, "sent": sent, "failed": failed, "rows": len(rows)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay Braga simulation datasets into REST or MQTT.")
    parser.add_argument("--dataset-root", default=str(DEFAULT_DATASET_ROOT), help="Root folder containing scenario folders.")
    parser.add_argument("--scenario", action="append", default=[], help="Scenario id to replay. Can be used multiple times.")
    parser.add_argument("--mode", choices=["rest", "mqtt", "dry-run"], default="rest", help="Replay transport.")
    parser.add_argument("--api-url", default=os.getenv("IOT_API_URL", DEFAULT_API_URL), help="REST endpoint URL.")
    parser.add_argument("--api-key", default=os.getenv("API_KEY_EDGE") or os.getenv("IOT_API_KEY", ""), help="REST API key.")
    parser.add_argument("--session-id", default=os.getenv("IOT_SESSION_ID", ""), help="Simulation session id to attach to telemetry and truth alerts.")
    parser.add_argument("--timeout", type=float, default=10.0, help="REST request timeout in seconds.")
    parser.add_argument("--mqtt-host", default=os.getenv("MQTT_BROKER", "localhost"), help="MQTT broker host.")
    parser.add_argument("--mqtt-port", type=int, default=int(os.getenv("MQTT_HOST_PORT") or os.getenv("MQTT_PORT", str(DEFAULT_MQTT_PORT))), help="MQTT broker port.")
    parser.add_argument("--mqtt-username", default=os.getenv("MQTT_USERNAME", ""), help="MQTT username.")
    parser.add_argument("--mqtt-password", default=os.getenv("MQTT_PASSWORD", ""), help="MQTT password.")
    parser.add_argument("--mqtt-tls", action="store_true", help="Enable MQTT TLS.")
    parser.add_argument("--mqtt-ca-cert", default=os.getenv("MQTT_TLS_CA_CERT", ""), help="Path to CA cert for MQTT TLS.")
    parser.add_argument("--mqtt-tls-insecure", action="store_true", help="Disable MQTT TLS certificate verification.")
    parser.add_argument("--publish-truth-alerts", action="store_true", help="Also publish truth.json alerts to /bike/{id}/alert with QoS 1 in MQTT mode.")
    parser.add_argument("--realtime", action="store_true", help="Sleep according to dataset timestamps.")
    parser.add_argument("--speedup", type=float, default=1.0, help="Replay speed multiplier when --realtime is used.")
    parser.add_argument("--continue-on-error", action="store_true", help="Continue after transport errors.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.mode != "dry-run" and args.session_id == "auto":
        args.session_id = default_session_id()
    dataset_root = Path(args.dataset_root)
    scenarios = discover_scenarios(dataset_root, args.scenario)

    if args.mode == "dry-run":
        for scenario in scenarios:
            rows = read_csv(scenario.telemetry_path)
            truth_events = []
            if scenario.truth_path:
                truth = json.loads(scenario.truth_path.read_text(encoding="utf-8"))
                truth_events = [event["event_type"] for event in truth.get("events", [])]
            print(f"{scenario.scenario_id}: vehicle_type={scenario.vehicle_type} rows={len(rows)} truth_events={truth_events}")
        return

    mqtt_client = mqtt_client_from_args(args) if args.mode == "mqtt" else None
    try:
        total_sent = 0
        total_failed = 0
        for scenario in scenarios:
            result = replay_scenario(scenario, args, mqtt_client=mqtt_client)
            total_sent += result["sent"]
            total_failed += result["failed"]
            print(f"{result['scenario_id']}: sent={result['sent']} failed={result['failed']} rows={result['rows']}")
        print(f"Done: sent={total_sent} failed={total_failed} mode={args.mode}")
    finally:
        if mqtt_client is not None:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()


if __name__ == "__main__":
    main()
