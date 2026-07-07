"""
Generate a single specific encounter using generate_encounters.generate_single_encounter(...).
"""
from pathlib import Path

from .generate_encounters import generate_single_encounter


def run_single_encounter_demo():
    
    # Example 1: Parameter-based encounter generation
    param_spec = {
        "Ownship_speed": 40,
        "Ownship_altitude": 400,
        "Ownship_altitude_end": 450,
        "Ownship_category": "HB10",
        "Ownship_straight_line": False,
        "Intruder_speed": 30,
        "Intruder_altitude": 380,
        "Intruder_altitude_end": 430,
        "Intruder_category": "LU10",
        "Intruder_azimuth": 60,
        "Intruder_lateral_offset": 500,
        "Intruder_vertical_offset": 100,
        "Intruder_straight_line": True,
        "Path_converging": True,
        "flight_duration": 240,
        "seed": False,
    }
    # 3 possible ways to generate an encounter
    generate_single_encounter(param_spec, return_mode="plot")
    encounter_index, args, encounter = generate_single_encounter(param_spec, return_mode="generator")
    counter_h5_path = generate_single_encounter(param_spec, return_mode="h5_path")
    
    # Example 2: csv-based encounter generation (in this case, only for the intruder)
    csv_path = Path(__file__).resolve().parent.parent / "examples" / "example_lla_points.csv"
    param_spec = {
        "Ownship_speed": 40,
        "Ownship_altitude": 400,
        "Ownship_altitude_end": 450,
        "Ownship_category": "HB10",
        "Ownship_straight_line": False,
        "Intruder_speed": 30,
        "Intruder_altitude": 380,
        "Intruder_altitude_end": 430,
        "Intruder_azimuth": 60,
        "Intruder_lateral_offset": 500,
        "Intruder_vertical_offset": 100,
        "Intruder_trajectory_csv_filename":str(csv_path),
        "Path_converging": True,
        "flight_duration": 240,
        "seed": False,
    }
    # 3 possible ways to generate an encounter
    generate_single_encounter(param_spec, return_mode="plot")
    encounter_index, args, encounter = generate_single_encounter(param_spec, return_mode="generator")
    counter_h5_path = generate_single_encounter(param_spec, return_mode="h5_path")   
    

if __name__ == "__main__":
    run_single_encounter_demo()
