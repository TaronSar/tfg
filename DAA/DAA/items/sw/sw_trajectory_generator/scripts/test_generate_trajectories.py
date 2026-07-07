"""
Python script to replicate the steps in run_example.bat using function calls.
Assumes the corresponding Python scripts expose callable entrypoint functions.
"""
from types import SimpleNamespace
from pathlib import Path

from generate_trajectories_and_encounters import generate_trajectory_or_encounter


def run_generate_trajectories_demo():

    # Parameter-based mode
    args = SimpleNamespace(
        filename='HB10',
        flight_duration=240,
        total_tracks=50,
        show_plot=True,
    )
    generate_trajectory_or_encounter(args)    

    # CSV-based mode
    csv_path = Path(__file__).resolve().parent.parent / "examples" / "example_lla_points.csv"
    args = SimpleNamespace(
        show_plot=True,
        desired_speed_kt=140.0,
        trajectory_csv_filename=str(csv_path),
    )
    generate_trajectory_or_encounter(args)
          
if __name__ == "__main__":
    run_generate_trajectories_demo()
