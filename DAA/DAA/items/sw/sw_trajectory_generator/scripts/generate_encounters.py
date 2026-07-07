
"""
Python script to generate all encounters.
"""
from pathlib import Path
from types import SimpleNamespace
import h5py
import itertools
import json
import hashlib
import numpy as np
import time

from .generate_trajectories_and_encounters import generate_trajectory_or_encounter

# Define paths
SCRIPTS_DIR = Path(__file__).parent
EXAMPLES_DIR = SCRIPTS_DIR.parent / "examples"
EXCLUDED_ENCOUNTER_ARGS = {"Output_folder", "seed", "save_csv", "show_plot"}


def _default_param_specs():
    
    NMAC_h = 500
    NMAC_v = 100
    WC_h = 2000
    WC_v = 225
    
    return {
        "Ownship_speed": {"values": list(range(30, 71, 10))},               # knots
        "Ownship_altitude": {"values": [400]},                              # feet    
        "Ownship_altitude_end": {"values": list(range(300, 550, 100))},     # feet
        "Ownship_category": {"values": ["HB10", "LU10"]},                   # category (see genrate_trajectories_and_encounters.py)
        "Ownship_straight_line": {"values": [False]},                       # boolean
        "Intruder_straight_line": {"values": [False]},                      # boolean
        "Intruder_speed": {"values": list(range(10, 165, 35))},             # knots
        "Intruder_altitude": {"values": list(range(300, 550, 100))},        # feet
        "Intruder_altitude_end": {"values": list(range(300, 550, 100))},    # feet
        "Intruder_category": {"values": ["G", "HB10", "LU10", "U"]},        # category (see genrate_trajectories_and_encounters.py)
        "Intruder_azimuth": {"values": list(range(0, 360, 30))},            # degrees
        "Intruder_lateral_offset": {                                        # feet
            "values": [0, NMAC_h, WC_h],
            "random_delta": "uniform",
            "random_delta_min": -100,
            "random_delta_max": 100,
        },
        "Intruder_vertical_offset": {                                       # feet
            "values": [0, NMAC_v, WC_v],
            "random_delta": "uniform",
            "random_delta_min": -50,
            "random_delta_max": 50,
        },
        "Path_converging": {"values": [True]},                              # boolean
        "flight_duration": {"values": [240]},                               # seconds
        "Output_folder": {"values": [EXAMPLES_DIR]},                        # path
        "seed": {"values": [True]},                                         # False/None: random per call, True: deterministic, int: fixed
        "save_csv": {"values": [False]},                                    # boolean
        "show_plot": {"values": [False]},                                   # boolean
    }


def _write_value(group, name, value):
    if isinstance(value, dict):
        sub_group = group.create_group(name)
        for sub_key, sub_value in value.items():
            _write_value(sub_group, str(sub_key), sub_value)
        return

    if isinstance(value, (list, tuple)):
        value = np.asarray(value)

    if isinstance(value, np.ndarray):
        if value.dtype.kind in {"U", "S"}:
            group.create_dataset(name, data=value.astype(h5py.string_dtype(encoding="utf-8")))
        elif value.dtype.kind == "O":
            group.create_dataset(name, data=np.asarray([str(v) for v in value], dtype=h5py.string_dtype(encoding="utf-8")))
        else:
            group.create_dataset(name, data=value)
        return

    if isinstance(value, (str, Path)):
        group.create_dataset(name, data=str(value), dtype=h5py.string_dtype(encoding="utf-8"))
        return

    if np.isscalar(value):
        group.create_dataset(name, data=value)
        return

    group.create_dataset(name, data=str(value), dtype=h5py.string_dtype(encoding="utf-8"))


def _store_encounter(h5_file, encounter_index, args, encounter):
    encounter_args = {
        key: value
        for key, value in vars(args).items()
        if key not in EXCLUDED_ENCOUNTER_ARGS
    }
    encounter_seed = getattr(args, "seed", None)
    encounter_args_json = dict(encounter_args)
    if encounter_seed is not None:
        encounter_args_json["seed"] = int(encounter_seed)

    encounter_group = h5_file.create_group(f"encounters/{encounter_index:08d}")
    encounter_group.create_dataset(
        "args_json",
        data=json.dumps(encounter_args_json, default=str),
        dtype=h5py.string_dtype(encoding="utf-8"),
    )
    if encounter_seed is not None:
        encounter_group.create_dataset("seed", data=int(encounter_seed))

    args_group = encounter_group.create_group("args")
    for key, value in encounter_args.items():
        _write_value(args_group, str(key), value)
    if encounter_seed is not None:
        _write_value(args_group, "seed", int(encounter_seed))

    results_group = encounter_group.create_group("results")
    if isinstance(encounter, list):
        for track_index, track in enumerate(encounter):
            _write_value(results_group, f"track_{track_index}", track)
    else:
        _write_value(results_group, "track_0", encounter)


def _store_param_grid_args(h5_file, param_grid_args):
    root_group = h5_file.create_group("param_grid_args")
    for key, value in param_grid_args.items():
        _write_value(root_group, str(key), value)


def _deterministic_seed_from_values(values):
    payload = json.dumps(values, sort_keys=True, default=str).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:4], "big")


def _resolve_seed(args_dict, param_specs):
    user_seed = args_dict.get("seed", None)

    if user_seed is None:
        user_seed = False

    if isinstance(user_seed, bool):
        if user_seed is False:
            return int(np.random.default_rng().integers(0, np.iinfo(np.uint32).max + 1))
        random_signature = _random_specs_signature(param_specs)
        seed_payload = {
            "args": args_dict,
            "random_specs": random_signature,
        }
        return _deterministic_seed_from_values(seed_payload)

    if np.isscalar(user_seed):
        return int(user_seed)

    payload = json.dumps(user_seed, sort_keys=True, default=str).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:4], "big")


def _merge_param_specs(base_specs, override_specs):
    if not isinstance(override_specs, dict):
        return base_specs

    merged = {key: dict(value) for key, value in base_specs.items()}
    for key, value in override_specs.items():
        if isinstance(value, dict):
            merged[key] = {**merged.get(key, {}), **value}
        else:
            merged[key] = {"values": value}
    return merged


def _random_specs_signature(param_specs):
    signature = {}
    for key, spec in param_specs.items():
        if not isinstance(spec, dict):
            continue
        mode = spec.get("random_delta")
        if mode is None:
            continue
        signature[key] = {
            "random_delta": mode,
            "random_delta_min": spec.get("random_delta_min"),
            "random_delta_max": spec.get("random_delta_max"),
        }
    return signature


def _apply_random_specs(args, param_specs):
    rng = np.random.default_rng(int(getattr(args, "seed", 0)))
    for key, spec in param_specs.items():
        if not isinstance(spec, dict):
            continue
        if key not in vars(args):
            continue

        value = getattr(args, key)
        if isinstance(value, (bool, str, Path)) or not np.isscalar(value):
            continue

        mode = str(spec.get("random_delta", "")).lower()
        if not mode:
            continue

        if "random_delta_min" not in spec or "random_delta_max" not in spec:
            continue

        delta_min = float(spec["random_delta_min"])
        delta_max = float(spec["random_delta_max"])
        if delta_min > delta_max:
            delta_min, delta_max = delta_max, delta_min

        if mode == "uniform":
            delta = float(rng.uniform(delta_min, delta_max))
        elif mode == "normal":
            sigma_min = abs(delta_min)
            sigma_max = abs(delta_max)
            if sigma_min > sigma_max:
                sigma_min, sigma_max = sigma_max, sigma_min
            sigma = float(rng.uniform(sigma_min, sigma_max))
            delta = float(rng.normal(0.0, sigma))
        else:
            continue

        setattr(args, f"{key}_base", value)
        setattr(args, f"{key}_delta", delta)
        setattr(args, key, float(value) + delta)

    return args


def _param_grid_names(param_specs):
    return [name for name, spec in param_specs.items() if isinstance(spec, dict) and "values" in spec]


def _build_param_grid(param_specs):
    names = _param_grid_names(param_specs)
    values = [param_specs[name]["values"] for name in names]
    return names, itertools.product(*values)


def _run_single_encounter_from_args_dict(args_dict, param_specs):
    encounter_args_dict = dict(args_dict)
    encounter_args_dict["seed"] = _resolve_seed(encounter_args_dict, param_specs)

    args = SimpleNamespace(**encounter_args_dict)
    args = _apply_random_specs(args, param_specs)
    encounter = generate_trajectory_or_encounter(args)
    return args, encounter


def _as_values_dict(param_spec):
    specs = _default_param_specs()
    for key, value in param_spec.items():
        if isinstance(value, dict):
            spec_override = dict(value)
            if "values" not in spec_override:
                raise ValueError(f"param_spec['{key}'] dict must include a 'values' field")
            if not isinstance(spec_override["values"], (list, tuple)):
                spec_override["values"] = [spec_override["values"]]
            specs[key] = {**specs.get(key, {}), **spec_override}
        else:
            specs[key] = {**specs.get(key, {}), "values": [value]}
    return specs


def _generate_encounters(param_specs, max_encounters=None):
    param_names, param_grid = _build_param_grid(param_specs)

    for encounter_index, combo in enumerate(param_grid):
        args_dict = dict(zip(param_names, combo))
        args, encounter = _run_single_encounter_from_args_dict(args_dict, param_specs)
        print(f"Running index: {encounter_index}")
        yield encounter_index, args, encounter

        if max_encounters is not None and encounter_index >= max_encounters - 1:
            print(f"Generated {max_encounters} encounters, exiting.")
            break

def _decode_h5_value(value):
    if isinstance(value, bytes):
        return value.decode("utf-8")

    if hasattr(value, "dtype") and value.dtype.kind in {"S", "O"}:
        if getattr(value, "shape", ()) == ():
            item = value.item() if hasattr(value, "item") else value
            return item.decode("utf-8") if isinstance(item, bytes) else item

        decoded = []
        for item in value:
            decoded.append(item.decode("utf-8") if isinstance(item, bytes) else item)
        return decoded

    return value

def _read_h5_node(node):
    if isinstance(node, h5py.Group):
        return {key: _read_h5_node(node[key]) for key in sorted(node.keys())}

    return _decode_h5_value(node[()])

def get_encounter_from_h5(file_path, encounter_index=0):
    encounter_key = f"{int(encounter_index):08d}"

    with h5py.File(file_path, "r") as h5_file:
        encounters_group = h5_file["encounters"]
        if encounter_key not in encounters_group:
            raise KeyError(f"Encounter index {encounter_index} not found in {file_path}")

        encounter_group = encounters_group[encounter_key]
        args = json.loads(encounter_group["args_json"][()].decode("utf-8"))

        results_group = encounter_group["results"]
        encounter_tracks = []
        for track_key in sorted(results_group.keys()):
            encounter_tracks.append(_read_h5_node(results_group[track_key]))

        encounter = encounter_tracks[0] if len(encounter_tracks) == 1 else encounter_tracks

    return int(encounter_key), args, encounter


def generate_single_encounter(param_spec, return_mode="generator"):
    param_specs = _as_values_dict(param_spec)

    if return_mode == "generator":
        args_dict = {
            name: spec["values"][0]
            for name, spec in param_specs.items()
            if isinstance(spec, dict) and "values" in spec
        }
        args, encounter = _run_single_encounter_from_args_dict(args_dict, param_specs)
        return 0, args, encounter

    if return_mode == "h5_path":
        return generate_encounter(return_mode="h5_path", max_encounters=1, param_specs=param_specs)

    if return_mode == "plot":
        generate_encounter(return_mode="plot", max_encounters=1, param_specs=param_specs)
        return None

    raise ValueError("return_mode must be one of 'generator', 'h5_path', or 'plot'")


def generate_encounter(return_mode="generator", max_encounters=None, param_specs=None):
    
    # There are three ways to run this function:
    # 1. return_mode="generator": returns a generator that yields (encounter_index, args, encounter) for each generated encounter.
    #    Plots are disabled in this mode.
    # 2. return_mode="h5_path": generates all encounters and stores them in an HDF5 file, returning the path to the file.
    #    Plots are disabled in this mode.
    # 3. return_mode="plot": generates and plots encounters one by one.
    
    specs = _merge_param_specs(_default_param_specs(), param_specs)
    specs["show_plot"] = {**specs.get("show_plot", {}), "values": [return_mode == "plot"]}

    grid_names = _param_grid_names(specs)
    total_encounters = int(np.prod([len(specs[name]["values"]) for name in grid_names], dtype=np.int64))
    print(f"Total encounters to generate: {total_encounters}")

    # Set to None to generate all of them. The limit is to allow debugging the code with a manageable number of encounters before generating the full combinatorial explosion of encounters.

    store_args = {"param_specs": specs}

    if return_mode == "generator":
        return _generate_encounters(specs, max_encounters=max_encounters)

    elif return_mode == "plot":
        encounter_count = 0
        for _, _, _ in _generate_encounters(specs, max_encounters=max_encounters):
            encounter_count += 1
        return None

    elif return_mode == "h5_path":
        start_time = time.time()  # Start time
        h5_path = EXAMPLES_DIR / "all_encounters.h5"
        with h5py.File(h5_path, "w") as h5_file:
            _store_param_grid_args(h5_file, store_args)
            encounter_count = 0
            for encounter_index, args, encounter in _generate_encounters(
                specs,
                max_encounters=max_encounters,
            ):
                _store_encounter(h5_file, encounter_index, args, encounter)
                encounter_count += 1
                h5_file.flush()

            end_time = time.time()  # End time
            total_time = end_time - start_time
            if encounter_count == 0:
                print("No encounters were generated.")
                return h5_path
            print(f"Total time taken: {total_time} seconds for {encounter_count} encounters, which is an average of {total_time / encounter_count:.2f} seconds per encounter.")
            print(f"Encounters stored in: {h5_path}")
            print(f"Estimate time needed to generate all {total_encounters} encounters: {total_time / encounter_count * total_encounters / 3600:.2f} hours")
        return h5_path
    
    else:
        raise ValueError("Invalid return_mode. Must be one of 'generator', 'h5_path', or 'plot'.")
        
        
if __name__ == "__main__":
    generate_encounter()
