# ProjetoIoT Dataset Package

This package contains the Braga micromobility dataset prepared for publication, archival, and reproducible reuse.
The dataset represents shared scooters and bicycles operating in Braga, Portugal, and was designed for an IoT urban-mobility platform focused on telemetry ingestion, event detection, alert generation, dashboard playback, and system validation.

The dataset is synthetic but geographically grounded: routes were generated over real Braga street and cycleway geometry derived from OpenStreetMap through the Overpass API. Sensor values were then synthesized to resemble IoT telemetry collected by connected micromobility vehicles equipped with positioning, inertial, and proximity sensors.

List of sensor families included in the dataset:

- GPS: latitude, longitude, speed, and positioning accuracy.
- IMU: three-axis accelerometer and three-axis gyroscope readings.
- Ultrasonic sensing: front and lateral obstacle distance plus sensor validity.
- Operational telemetry: battery level, docking state, charging state, and trip/session metadata.

This dataset includes:

- 1x Braga micromobility dataset with 100 trajectories.
- 50x scooter scenarios.
- 50x bicycle scenarios.
- 1x dataset manifest describing all files, vehicles, and metadata.
- 1x bicycle-station metadata file for dock-aware scenarios.
- 1x publication snapshot of the Python code used to generate, validate, import, and replay the dataset.

The package layout is:

- `braga/`: the dataset itself.
- `code/`: copied Python files directly related to dataset generation and reuse.

The `code/` folder contains:

- `generate_braga_datasets.py`: generation of the synthetic Braga scenarios.
- `validate_braga_datasets.py`: validation of telemetry and expected events.
- `import_dataset.py`: replay of the dataset into the backend by REST or MQTT.
- `simulate_fleet.py`: continuous fleet simulation based on the dataset.

The dataset should be interpreted as a validation and demonstration corpus rather than as long-term historical fleet logging. Different vehicles intentionally carry different behavioral scenarios so that the project can evaluate normal mobility, hard braking, falls, congestion, obstacle risk, and mixed events.
