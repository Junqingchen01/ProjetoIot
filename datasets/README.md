# ProjetoIoT Dataset Package

This folder packages the Braga micromobility dataset in a publication-friendly structure.
It keeps the original project dataset path intact for code compatibility, while also adding
clear documentation and a dedicated code snapshot for dataset generation and replay.

## Package Layout

- `braga/`: published dataset contents. In the Zenodo-style sense, this is the `data` folder.
- `code/`: snapshot copies of the Python scripts used to generate, validate, import, and replay the dataset.

## Why The Dataset Is Structured This Way

The Braga dataset was designed for an IoT smart-mobility project whose goals include:

- ingesting heterogeneous telemetry from multiple devices;
- validating event-detection algorithms;
- demonstrating alerts, QoS, and dashboard playback;
- supporting repeatable demos and technical evaluation.

Because of that, the dataset is organized around **scenarios**, not around long-term real-world fleet history.
Each dataset sample represents a controlled route with a known behavior pattern, such as normal riding,
commuting, hard braking, fall/accident simulation, traffic jam, or obstacle-risk detection.

This means the dataset should be interpreted as a **validation and demonstration corpus**:

- `device_id` identifies the simulated vehicle used to carry a scenario;
- `scenario_id` identifies the behavioral pattern of that route;
- different vehicle folders may therefore contain different route families by design.

## Included Code Snapshot

The `code/` folder contains publication copies of the scripts most directly related to the dataset:

- `generate_braga_datasets.py`: generates the synthetic Braga scenarios from OSM geometry;
- `validate_braga_datasets.py`: checks whether truth events and generated telemetry remain consistent;
- `import_dataset.py`: replays dataset rows into the backend by REST or MQTT;
- `simulate_fleet.py`: continuously reuses the dataset to emulate a running fleet demo.

These are copied here so the dataset can be understood and reproduced without browsing the full project tree.
