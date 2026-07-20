#!/usr/bin/env python3
"""
Continuous demo simulator for a fleet of Braga micromobility vehicles.

Each simulated vehicle gets a stable type, repeatedly picks one Braga dataset of
that type, rewrites the device_id and timestamp, and streams telemetry to the
backend by REST or MQTT.
For bicycle datasets, the simulator can also publish a QoS 1 dock/data-dump
event when the bicycle is returned to a charging station.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import signal
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from import_dataset import (
    DEFAULT_API_URL,
    DEFAULT_DATASET_ROOT,
    DEFAULT_MQTT_PORT,
    Scenario,
    alert_payload,
    default_session_id,
    discover_scenarios,
    parse_timestamp,
    read_csv,
    send_rest,
    telemetry_payload,
)


def mqtt_client_from_args(args: argparse.Namespace):
    try:
        import paho.mqtt.client as mqtt
        from paho.mqtt.enums import CallbackAPIVersion
    except ImportError as exc:
        raise RuntimeError("paho-mqtt is required for --mode mqtt. Run: python -m pip install paho-mqtt") from exc

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


def row_delay(previous_row: dict[str, str] | None, row: dict[str, str], speedup: float) -> float:
    if previous_row is None:
        return 0.0
    previous = parse_timestamp(previous_row["timestamp"])
    current = parse_timestamp(row["timestamp"])
    delay = max(0.0, (current - previous).total_seconds())
    return delay / speedup if speedup > 0 else 0.0


def build_payload(row: dict[str, str], device_id: str, scenario_id: str, vehicle_type: str, trip_id: str, session_id: str) -> dict[str, Any]:
    payload = telemetry_payload(row)
    payload["device_id"] = device_id
    payload["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    payload["source"] = f"fleet_simulation:{scenario_id}"
    payload["type"] = "telemetry"
    payload["session_id"] = session_id
    payload["vehicle_type"] = vehicle_type
    payload["trip_id"] = trip_id
    return payload


def build_truth_alert(
    event: dict[str, Any],
    row: dict[str, str],
    telemetry: dict[str, Any],
    device_id: str,
    scenario_id: str,
    trip_id: str,
    session_id: str,
) -> dict[str, Any]:
    alert = alert_payload(event, row)
    alert["device_id"] = device_id
    alert["timestamp"] = telemetry["timestamp"]
    alert["source"] = f"fleet_simulation_truth:{scenario_id}"
    alert["type"] = "alert"
    alert["session_id"] = session_id
    alert["trip_id"] = trip_id
    return alert


def build_dock_dump_alert(
    scenario: Scenario,
    truth: dict[str, Any],
    rows: list[dict[str, str]],
    device_id: str,
    trip_id: str,
    sent: int,
    failed: int,
    received: int | None,
    session_id: str,
) -> dict[str, Any]:
    last_row = rows[-1]
    expected = len(rows)
    verified_count = sent if received is None else received
    missing = max(0, expected - verified_count)
    end_station = truth.get("end_station") or {}
    first_battery = float(rows[0].get("battery") or 0.0)
    last_battery = float(last_row.get("battery") or first_battery)
    completeness = 100.0 if expected == 0 else max(0.0, min(100.0, (verified_count / expected) * 100.0))
    return {
        "device_id": device_id,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "source": f"fleet_simulation_dock:{scenario.scenario_id}",
        "type": "alert",
        "event_type": "dock_data_dump",
        "session_id": session_id,
        "severity": "info" if missing == 0 else "warning",
        "vehicle_type": "bicycle",
        "trip_id": trip_id,
        "lat": float(end_station.get("lat", last_row["lat"])),
        "lon": float(end_station.get("lon", last_row["lon"])),
        "trigger": "dock_station_upload",
        "station_id": end_station.get("station_id") or last_row.get("end_station_id") or "",
        "station_name": end_station.get("name") or last_row.get("end_station_name") or "",
        "speed": 0.0,
        "accel_x": 0.0,
        "accel_y": 0.0,
        "accel_z": 9.81,
        "charging": True,
        "battery_before": first_battery,
        "battery_after": last_battery,
        "expected_count": expected,
        "sent_count": sent,
        "received_count": received,
        "failed_count": failed,
        "missing_count": missing,
        "completeness_pct": round(completeness, 2),
        "verification_status": "backend_verified" if received is not None else "publish_only",
    }


def send_payload(
    payload: dict[str, Any],
    args: argparse.Namespace,
    mqtt_client,
    mqtt_lock: threading.Lock,
) -> None:
    if args.mode == "rest":
        send_rest(payload, args.api_url, args.api_key, args.timeout)
        return

    topic = f"/bike/{payload['device_id']}/telemetry"
    with mqtt_lock:
        result = mqtt_client.publish(topic, json.dumps(payload), qos=0)
    if result.rc != 0:
        raise RuntimeError(f"MQTT publish failed with rc={result.rc}")


def send_truth_alert(
    alert: dict[str, Any],
    args: argparse.Namespace,
    mqtt_client,
    mqtt_lock: threading.Lock,
) -> None:
    if args.mode != "mqtt":
        return

    topic = f"/bike/{alert['device_id']}/alert"
    with mqtt_lock:
        result = mqtt_client.publish(topic, json.dumps(alert), qos=1)
    if result.rc != 0:
        raise RuntimeError(f"MQTT alert publish failed with rc={result.rc}")
    result.wait_for_publish(timeout=5.0)
    if not result.is_published():
        raise RuntimeError("MQTT alert publish timed out")


def count_received_trip_rows(api_url: str, api_key: str, timeout: float, device_id: str, trip_id: str) -> int:
    query = urllib.parse.urlencode(
        {
            "minutos": "240",
            "device_id": device_id,
            "trip_id": trip_id,
        }
    )
    separator = "&" if "?" in api_url else "?"
    request = urllib.request.Request(
        f"{api_url}{separator}{query}",
        headers={"X-API-Key": api_key} if api_key else {},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"Unexpected verification status {response.status}")
        data = json.loads(response.read().decode("utf-8"))
    return int(data.get("total_registos") or len(data.get("dados") or []))


def wait_for_received_trip_rows(
    args: argparse.Namespace,
    device_id: str,
    trip_id: str,
    expected: int,
) -> int | None:
    verify_url = args.dock_verify_api_url or args.api_url
    if not verify_url:
        return None

    deadline = time.time() + max(0.0, args.dock_verify_timeout_sec)
    last_count: int | None = None
    while time.time() <= deadline:
        try:
            last_count = count_received_trip_rows(verify_url, args.api_key, args.timeout, device_id, trip_id)
            if last_count >= expected:
                return last_count
        except (RuntimeError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
            print(f"[WARN] {device_id} dock verification failed once: {exc}", flush=True)
        time.sleep(max(0.1, args.dock_verify_poll_sec))
    return last_count


def load_truth(scenario: Scenario) -> dict[str, Any]:
    if scenario.truth_path is None:
        return {}
    return json.loads(scenario.truth_path.read_text(encoding="utf-8"))


def load_truth_events(truth: dict[str, Any], enabled: bool) -> dict[str, list[dict[str, Any]]]:
    if not enabled:
        return {}
    events: dict[str, list[dict[str, Any]]] = {}
    for event in truth.get("events", []):
        events.setdefault(event["timestamp"], []).append(event)
    return events


def replay_trip(
    device_id: str,
    scenario: Scenario,
    trip_id: str,
    args: argparse.Namespace,
    stop_event: threading.Event,
    mqtt_client,
    mqtt_lock: threading.Lock,
) -> tuple[int, int, int]:
    rows = read_csv(scenario.telemetry_path)
    truth = load_truth(scenario)
    vehicle_type = str(truth.get("vehicle_type") or scenario.vehicle_type or "scooter")
    truth_events = load_truth_events(truth, args.publish_truth_alerts)
    sent = 0
    alert_sent = 0
    failed = 0
    attempted = 0
    previous_row = None

    for row in rows:
        delay = row_delay(previous_row, row, args.speedup)
        if delay > 0 and stop_event.wait(delay):
            break

        payload = build_payload(row, device_id, scenario.scenario_id, vehicle_type, trip_id, args.session_id)
        attempted += 1
        try:
            send_payload(payload, args, mqtt_client, mqtt_lock)
            sent += 1
            if args.mode == "mqtt" and truth_events:
                for event in truth_events.get(row["timestamp"], []):
                    alert = build_truth_alert(event, row, payload, device_id, scenario.scenario_id, trip_id, args.session_id)
                    send_truth_alert(alert, args, mqtt_client, mqtt_lock)
                    alert_sent += 1
        except (RuntimeError, TimeoutError, urllib.error.URLError) as exc:
            failed += 1
            print(f"[WARN] {device_id} {scenario.scenario_id} {row.get('timestamp')}: {exc}", flush=True)
            if args.stop_on_error:
                stop_event.set()
                break

        previous_row = row

    if (
        args.mode == "mqtt"
        and args.publish_dock_dumps
        and vehicle_type == "bicycle"
        and rows
        and attempted == len(rows)
    ):
        try:
            received = wait_for_received_trip_rows(args, device_id, trip_id, len(rows))
            dock_alert = build_dock_dump_alert(scenario, truth, rows, device_id, trip_id, sent, failed, received, args.session_id)
            send_truth_alert(dock_alert, args, mqtt_client, mqtt_lock)
            alert_sent += 1
        except RuntimeError as exc:
            failed += 1
            print(f"[WARN] {device_id} dock dump failed: {exc}", flush=True)
            if args.stop_on_error:
                stop_event.set()
    elif args.mode == "mqtt" and args.publish_dock_dumps and vehicle_type == "bicycle" and rows:
        print(
            f"[{device_id}] skipped dock dump because trip was interrupted "
            f"attempted={attempted}/{len(rows)}",
            flush=True,
        )

    return sent, failed, alert_sent


def choose_scenario(
    scenarios: list[Scenario],
    scooter_index: int,
    trip_index: int,
    selection: str,
    rng: random.Random,
) -> Scenario:
    if selection == "random":
        return rng.choice(scenarios)
    return scenarios[(scooter_index + trip_index) % len(scenarios)]


def vehicle_type_for_index(device_index: int, scenarios: list[Scenario]) -> str:
    available = {scenario.vehicle_type for scenario in scenarios}
    if "bicycle" in available and "scooter" in available:
        return "bicycle" if device_index % 2 == 0 else "scooter"
    if "bicycle" in available:
        return "bicycle"
    return "scooter"


def scenarios_for_vehicle_type(scenarios: list[Scenario], vehicle_type: str) -> list[Scenario]:
    filtered = [scenario for scenario in scenarios if scenario.vehicle_type == vehicle_type]
    return filtered or scenarios


def device_id_for_vehicle(args: argparse.Namespace, device_index: int, vehicle_type: str) -> str:
    if vehicle_type == "bicycle":
        return f"{args.bike_device_prefix}{device_index + 1:03d}"
    return f"{args.device_prefix}{device_index + 1:03d}"


def make_trip_id(device_id: str, scenario_id: str, trip_index: int) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{device_id}_{scenario_id}_trip{trip_index + 1}_{timestamp}"


def vehicle_worker(
    device_index: int,
    scenarios: list[Scenario],
    args: argparse.Namespace,
    stop_event: threading.Event,
    mqtt_client,
    mqtt_lock: threading.Lock,
) -> None:
    rng = random.Random((args.seed or int(time.time())) + device_index)
    vehicle_type = vehicle_type_for_index(device_index, scenarios)
    vehicle_scenarios = scenarios_for_vehicle_type(scenarios, vehicle_type)
    device_id = device_id_for_vehicle(args, device_index, vehicle_type)

    initial_delay = device_index * args.start_stagger_sec
    if initial_delay > 0 and stop_event.wait(initial_delay):
        return

    trip_index = 0
    while not stop_event.is_set() and (args.trips_per_scooter == 0 or trip_index < args.trips_per_scooter):
        scenario = choose_scenario(vehicle_scenarios, device_index, trip_index, args.selection, rng)
        trip_id = make_trip_id(device_id, scenario.scenario_id, trip_index)
        print(
            f"[{device_id}] trip={trip_index + 1} vehicle={vehicle_type} "
            f"scenario={scenario.scenario_id} trip_id={trip_id}",
            flush=True,
        )
        sent, failed, alert_sent = replay_trip(device_id, scenario, trip_id, args, stop_event, mqtt_client, mqtt_lock)
        print(
            f"[{device_id}] finished scenario={scenario.scenario_id} "
            f"sent={sent} alerts_qos1={alert_sent} failed={failed}",
            flush=True,
        )
        trip_index += 1

        if stop_event.is_set() or args.pause_max_sec <= 0:
            continue
        pause = rng.uniform(args.pause_min_sec, args.pause_max_sec)
        stop_event.wait(pause)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a continuous Braga micromobility fleet simulation.")
    parser.add_argument("--dataset-root", default=str(DEFAULT_DATASET_ROOT), help="Root folder containing Braga scenarios.")
    parser.add_argument("--scenario", action="append", default=[], help="Limit simulation to this scenario. Can be repeated.")
    parser.add_argument("--mode", choices=["mqtt", "rest"], default="mqtt", help="Transport used by simulated vehicles.")
    parser.add_argument("--session-id", default=os.getenv("IOT_SESSION_ID", "auto"), help="Simulation session id; use 'auto' to create a new id at startup.")
    parser.add_argument("--fleet-size", type=int, default=7, help="Number of simulated vehicles.")
    parser.add_argument("--device-prefix", default="scooter_demo_", help="Prefix for generated device ids.")
    parser.add_argument("--bike-device-prefix", default="bike_demo_", help="Prefix for generated bicycle device ids.")
    parser.add_argument("--selection", choices=["round-robin", "random"], default="random", help="How vehicles choose datasets.")
    parser.add_argument("--trips-per-scooter", "--trips-per-device", dest="trips_per_scooter", type=int, default=0, help="Trips per simulated vehicle; 0 means run until Ctrl+C.")
    parser.add_argument("--speedup", type=float, default=5.0, help="Replay speed multiplier.")
    parser.add_argument("--start-stagger-sec", type=float, default=3.0, help="Delay between vehicle starts.")
    parser.add_argument("--pause-min-sec", type=float, default=5.0, help="Minimum pause between trips.")
    parser.add_argument("--pause-max-sec", type=float, default=20.0, help="Maximum pause between trips.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible scenario selection.")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop all vehicles on the first transport error.")
    parser.add_argument("--api-url", default=os.getenv("IOT_API_URL", DEFAULT_API_URL), help="REST endpoint URL.")
    parser.add_argument("--api-key", default=os.getenv("API_KEY_EDGE") or os.getenv("IOT_API_KEY", "iot"), help="REST API key.")
    parser.add_argument("--timeout", type=float, default=10.0, help="REST request timeout in seconds.")
    parser.add_argument("--dock-verify-api-url", default=os.getenv("IOT_DOCK_VERIFY_API_URL", ""), help="Sensor API URL used to verify how many trip rows reached the backend before publishing dock dumps.")
    parser.add_argument("--dock-verify-timeout-sec", type=float, default=8.0, help="Maximum time to wait for backend persistence before a bicycle dock dump.")
    parser.add_argument("--dock-verify-poll-sec", type=float, default=0.5, help="Polling interval while verifying bicycle dock dumps.")
    parser.add_argument("--mqtt-host", default=os.getenv("MQTT_BROKER", "localhost"), help="MQTT broker host.")
    parser.add_argument("--mqtt-port", type=int, default=int(os.getenv("MQTT_HOST_PORT") or os.getenv("MQTT_PORT", str(DEFAULT_MQTT_PORT))), help="MQTT broker port.")
    parser.add_argument("--mqtt-username", default=os.getenv("MQTT_USERNAME", "iot"), help="MQTT username.")
    parser.add_argument("--mqtt-password", default=os.getenv("MQTT_PASSWORD", "iot"), help="MQTT password.")
    parser.add_argument("--mqtt-tls", action="store_true", help="Enable MQTT TLS.")
    parser.add_argument("--mqtt-ca-cert", default=os.getenv("MQTT_TLS_CA_CERT", ""), help="Path to CA cert for MQTT TLS.")
    parser.add_argument("--mqtt-tls-insecure", action="store_true", help="Disable MQTT TLS certificate verification.")
    parser.add_argument("--publish-truth-alerts", action="store_true", help="Publish truth.json events to /bike/{id}/alert with MQTT QoS 1.")
    parser.add_argument("--no-publish-truth-alerts", dest="publish_truth_alerts", action="store_false", help="Do not publish truth.json critical events as MQTT QoS 1 alerts.")
    parser.add_argument("--no-publish-dock-dumps", dest="publish_dock_dumps", action="store_false", help="Disable bicycle dock/data-dump QoS 1 events.")
    parser.set_defaults(publish_dock_dumps=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.session_id == "auto":
        args.session_id = default_session_id("demo")
    if args.fleet_size < 1:
        raise ValueError("--fleet-size must be at least 1")

    scenarios = discover_scenarios(Path(args.dataset_root), args.scenario)
    stop_event = threading.Event()
    mqtt_lock = threading.Lock()
    mqtt_client = mqtt_client_from_args(args) if args.mode == "mqtt" else None
    if args.publish_truth_alerts and args.mode != "mqtt":
        print("[WARN] --publish-truth-alerts only publishes QoS 1 alerts in MQTT mode.", flush=True)

    def request_stop(signum, frame):  # noqa: ARG001
        print("Stopping fleet simulation...", flush=True)
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    print(
        f"Starting fleet simulation: vehicles={args.fleet_size} scenarios={len(scenarios)} "
        f"mode={args.mode} speedup={args.speedup} selection={args.selection} session={args.session_id}",
        flush=True,
    )

    threads = [
        threading.Thread(
            target=vehicle_worker,
            args=(index, scenarios, args, stop_event, mqtt_client, mqtt_lock),
            name=f"vehicle-{index + 1}",
        )
        for index in range(args.fleet_size)
    ]

    try:
        for thread in threads:
            thread.start()
        while any(thread.is_alive() for thread in threads):
            time.sleep(0.5)
    finally:
        stop_event.set()
        for thread in threads:
            thread.join(timeout=5)
        if mqtt_client is not None:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()


if __name__ == "__main__":
    main()
