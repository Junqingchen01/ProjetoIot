# Braga Micromobility Simulation Dataset

Dataset representing shared bicycles and shared scooters operating in Braga, Portugal, generated for an IoT-based collaborative urban mobility platform. The dataset was designed to support backend ingestion, real-time event detection, alert generation, dashboard visualization, QoS-oriented experiments, and reproducible validation of critical urban-mobility events.

Routes were generated over real Braga street and cycleway geometry obtained from OpenStreetMap through the Overpass API. Telemetry values were then synthesized to emulate connected micromobility vehicles producing GPS, inertial, ultrasonic, battery, and operational state data at a 1-second sampling period.

List of sensor families:

- GPS: `lat`, `lon`, `speed`, `gps_accuracy_m`
- IMU: `accel_x`, `accel_y`, `accel_z`, `gyro_x`, `gyro_y`, `gyro_z`
- Ultrasonic: `range_front_m`, `range_left_m`, `ultrasonic_valid`
- Operational fields: `battery`, `dock_status`, `charging`, `trip_id`, `sequence`, `timestamp`

Additional bicycle-only operational metadata:

- `start_station_id`, `start_station_name`
- `end_station_id`, `end_station_name`

This dataset includes:

- 100x trajectories in total.
- 50x scooter scenarios.
- 50x bicycle scenarios.
- 1x global `manifest.json` file with publication and indexing metadata.
- 1x `bike_stations.json` file describing the bicycle docking stations used by bike scenarios.
- 100x `truth.json` files with expected event annotations, one per scenario.
- 100x `telemetry.csv` files with time-series sensor data, one per scenario.
- 1x copied code package in `../code/` for generation, validation, replay, and simulation.

## Design Rationale

This dataset was intentionally designed as a scenario-oriented validation corpus. It is not a long-term operational archive of 100 real vehicles following repeated daily routines. Instead, each trajectory represents a controlled mobility scenario chosen to test specific components of the IoT platform.

The main design goals are:

- evaluate normal telemetry ingestion without false positives;
- test critical-event detection under known conditions;
- provide event ground truth for backend and algorithm validation;
- supply meaningful histories for frontend dashboards;
- support repeatable demonstrations and technical reports.

Because of that, different vehicles intentionally contain different route types. Some vehicles carry normal scenarios, while others carry commute, hard-brake, fall/accident, traffic-jam, obstacle-risk, or mixed-event scenarios.

## How To Interpret Vehicles And Scenarios

The dataset is organized by vehicle type, then by vehicle identifier, then by scenario:

- `scooters/<device_id>/<scenario_id>/`
- `bicycles/<device_id>/<scenario_id>/`

Examples:

- `scooters/scooter_braga_001/normal_001/`
- `bicycles/bike_braga_001/bike_normal_center_001/`

This layout is useful for publication and browsing, but the semantics are important:

- `device_id` identifies the simulated vehicle used in the dataset;
- `scenario_id` identifies the route family and expected behavior;
- the dataset is scenario-driven, so different numbered vehicles intentionally correspond to different behaviors.

In the current release, each of the 50 scooter identifiers and each of the 50 bicycle identifiers is associated with one scenario. Therefore, yes, the 50 bikes and 50 scooters are not copies of the same route family; they were deliberately diversified to cover multiple validation conditions.

## Telemetry Content

Each `telemetry.csv` file contains 29 columns:

- `scenario_id`
- `device_id`
- `timestamp`
- `source`
- `type`
- `vehicle_type`
- `trip_id`
- `sequence`
- `start_station_id`
- `start_station_name`
- `end_station_id`
- `end_station_name`
- `dock_status`
- `charging`
- `lat`
- `lon`
- `speed`
- `accel_x`
- `accel_y`
- `accel_z`
- `gyro_x`
- `gyro_y`
- `gyro_z`
- `gps_accuracy_m`
- `range_front_m`
- `range_left_m`
- `ultrasonic_valid`
- `battery`
- `event_label`

Scooter trajectories mainly use the general telemetry and operational fields.
Bicycle trajectories additionally populate station-related fields for dock-aware mobility workflows.

## Ground Truth And Event Semantics

Each scenario directory includes a `truth.json` file describing the expected events, the route length, the sensor families involved, and a route preview. Event annotations are used to validate whether the backend and detection algorithms identify the correct behavior.

The dataset currently covers the following event families:

- normal mobility
- commute-style routes
- evening return routes
- stop-and-go movement
- rough pavement without true accident
- hard braking
- fall / accident
- traffic jam
- obstacle risk
- mixed hard-brake + traffic-jam scenarios

Across the 100 scenarios, the current manifest reports:

- 30 scenarios containing `hard_brake`
- 15 scenarios containing `fall_accident`
- 22 scenarios containing `traffic_jam`
- 8 scenarios containing `obstacle_risk`

The number of telemetry samples per scenario ranges from 178 to 909 rows, with an average of 497.6 rows.

## Bicycle Docking Metadata

Bike scenarios are linked to 8 docking stations in Braga through `bike_stations.json`. At the end of a bicycle trip, some samples keep the vehicle stopped with `charging=true`, allowing the simulator to emit operational events such as `dock_data_dump` and enabling experiments with trip completion and delayed upload workflows.

## File Structure

The data folder is organized as follows:

- `manifest.json`: global metadata, scenario index, publication metadata, and vehicle grouping.
- `bike_stations.json`: docking station metadata for bike scenarios.
- `scooters/`: scooter trajectories grouped by `device_id`.
- `bicycles/`: bicycle trajectories grouped by `device_id`.

Each scenario directory contains:

- `telemetry.csv`: time-series telemetry samples.
- `truth.json`: expected events and scenario metadata.

## Associated Code Package

Copies of the most relevant Python files are provided in `../code/` for archival and publication purposes:

- parsing and replay into the backend;
- validation of generated scenarios;
- synthetic dataset generation from OSM geometry;
- continuous fleet simulation for demos.

## Regeneration

```powershell
python scripts\generate_braga_datasets.py
```

To force a fresh OpenStreetMap download:

```powershell
python scripts\generate_braga_datasets.py --force-osm
```

## Attribution

Street geometry is derived from OpenStreetMap data.
Attribution: OpenStreetMap contributors.
