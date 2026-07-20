# Braga Micromobility Simulation Datasets

Synthetic datasets for shared scooters and bicycles operating in Braga, Portugal. The routes are generated
on top of street and cycleway geometry derived from OpenStreetMap via the Overpass API.

## Design Rationale

This dataset was not designed as a long-term historical archive of 100 real vehicles. Instead, it was built
as a **controlled IoT validation dataset** for a smart-mobility platform.

The main design goals are:

- cover multiple event-detection cases required by the project;
- support reproducible testing of backend ingestion and alert generation;
- feed dashboards with realistic telemetry histories;
- provide scenario-level ground truth for technical validation;
- allow repeatable classroom demos and experimental comparisons.

Because of that, the dataset combines both **normal mobility scenarios** and **critical-event scenarios**.
Examples include:

- normal mobility;
- short commute patterns;
- evening return trips;
- hard braking;
- fall / accident simulation;
- traffic jam behavior;
- obstacle-risk detection through ultrasonic data;
- mixed scenarios combining more than one event.

## How To Interpret The Vehicles

The folders are grouped by vehicle type and then by vehicle identifier:

- `scooters/<device_id>/<scenario_id>/`
- `bicycles/<device_id>/<scenario_id>/`

Examples:

- `scooters/scooter_braga_001/normal_001/`
- `bicycles/bike_braga_001/bike_normal_center_001/`

This organization makes the dataset easier to browse and publish, but it is important to interpret it correctly:

- `device_id` identifies the simulated vehicle used in the dataset;
- `scenario_id` defines the route family and behavioral pattern;
- the dataset is scenario-oriented, so different numbered vehicles intentionally carry different scenario types.

In other words, the 50 bicycles and 50 scooters are **not meant to represent 100 vehicles all following the same behavior**.
They represent a balanced set of controlled telemetry samples used to validate distinct algorithmic and system behaviors.

## Scenario Diversity

The current distribution was chosen on purpose.
If every vehicle only contained normal riding data, the platform could not properly validate:

- false-positive resistance on normal routes;
- hard-brake detection;
- fall/accident detection;
- traffic-jam recognition;
- obstacle alerts;
- mixed-event handling.

For that reason, one vehicle folder may contain a `normal` route while another may contain `commute`, `hard_brake`,
`fall_accident`, `traffic_jam`, or `obstacle_risk` scenarios.

## Scenario Contents

Each scenario folder contains:

- `telemetry.csv`: time-series telemetry samples;
- `truth.json`: expected events for validation.

The file `manifest.json` summarizes the full dataset, including:

- global metadata;
- scenario-to-vehicle mapping;
- file paths;
- vehicle grouping;
- publication-oriented fields for GitHub / Zenodo packaging.

## Included Sensors

Each telemetry row includes at least 3 sensor families:

- GPS: `lat`, `lon`, `speed`, `gps_accuracy_m`
- IMU: `accel_x`, `accel_y`, `accel_z`, `gyro_x`, `gyro_y`, `gyro_z`
- Ultrasonic: `range_front_m`, `range_left_m`, `ultrasonic_valid`

Bicycle scenarios also include docking-related operational fields such as:

- `start_station_id`, `start_station_name`
- `end_station_id`, `end_station_name`
- `dock_status`
- `charging`

At the end of a bicycle trip, the bicycle remains stopped at the destination station for a few samples with
`charging=true`. The simulator uses those fields to publish a `dock_data_dump` operational event summarizing whether
all telemetry rows for that trip were successfully delivered to the backend.

## Dataset Lifecycle In This Repository

The dataset is accompanied by code that supports the full lifecycle:

- generation from Braga street geometry;
- validation against expected events;
- import into the backend by REST or MQTT;
- continuous fleet replay for demonstrations.

Copies of the most relevant Python scripts are available in `../code/` for publication and archival use.

## Regeneration

```powershell
python scripts\generate_braga_datasets.py
```

To force a fresh OSM download:

```powershell
python scripts\generate_braga_datasets.py --force-osm
```

## Attribution

Street geometry is derived from OpenStreetMap data.
Attribution: OpenStreetMap contributors.
