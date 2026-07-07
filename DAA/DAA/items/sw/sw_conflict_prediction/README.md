# Trajectory Simulator

Simulates vision-based intruder tracking for DAA (Detect and Avoid). Given two aircraft trajectories, it generates synthetic camera measurements (azimuth, elevation, range), recovers the intruder state with an Unscented Kalman Filter, and predicts conflicts.

## Project Structure

```
scripts/
    estimators/                  # State estimation library
        state_estimator.py       #   Abstract base class
        unscented_kalman_filter_base.py
        unscented_kalman_filter_cv.py   # Constant Velocity model
        unscented_kalman_filter_ca.py   # Constant Acceleration (NED)
        unscented_kalman_filter_cab.py  # Constant Acceleration (body-frame)
    generate_test_true_trajectories.py  # Create synthetic truth trajectories
    caa_to_true_trajectory.py           # Convert CAA data to truth format
    trajectory_to_vision.py             # Truth trajectory -> vision measurements
    vision_to_trajectory.py             # Vision measurements -> UKF recovery
    conflict_prediction.py              # TCPA / cylinder distance analysis
    visualize_trajectories.py           # Animated 3D trajectory comparison
    visualize_extrapolation.py          # Extrapolation quality surface plots
    ellipsoid_to_cylinder_distance.py   # Geometry utility
    run_example.bat                     # End-to-end demo pipeline
examples/                        # Sample CSV data (generated, git-ignored)
```

## Quick Start

```bash
.\scripts\run_example.bat
```

This runs the full pipeline: generate truth -> compute measurements -> UKF recovery -> conflict analysis -> visualization.

## Pipeline Steps

### 1. Generate measurements from a true trajectory

```bash
python scripts/trajectory_to_vision.py -i truth.csv -o measurements.csv
```

### 2. Recover intruder trajectory with UKF

```bash
python scripts/vision_to_trajectory.py -i measurements.csv -o recovered.csv --estimator cab
```

Estimator choices: `cv` (constant velocity), `ca` (constant acceleration NED), `cab` (constant acceleration body-frame).

### 3. Conflict prediction

```bash
python scripts/conflict_prediction.py --ownship measurements.csv --intruder recovered.csv --output conflict.csv --estimator cab
```

### 4. Visualization

```bash
python scripts/visualize_trajectories.py -m measurements.csv -t truth.csv -r recovered.csv -c conflict.csv
```

## Dependencies

```bash
pip install numpy pandas matplotlib
```

### Interpolation

When trajectory time points don't match exactly, the script uses linear interpolation to create synchronized measurements.

## Troubleshooting

### Common Issues

1. **"Aircraft ID not found"**: Check that the specified aircraft IDs exist in your CSV file
2. **"No vision measurements calculated"**: Ensure trajectories have overlapping time ranges  
3. **Import errors**: Install required packages with `pip install pandas numpy matplotlib scipy`
4. **Uncertainty ellipsoids not showing**: Ensure both `--ukf-trajectory` and `--show-uncertainty` flags are provided
5. **Batch file syntax errors**: Check line continuation characters (`^`) in Windows batch files

### Checking Available Aircraft

The script will list available aircraft IDs when run, or you can check manually:
```python
import pandas as pd
data = pd.read_csv('your_file.csv')
print(data['Aircraft_ID'].unique())
```