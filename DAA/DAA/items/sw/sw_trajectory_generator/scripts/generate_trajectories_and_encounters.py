from cam_track_gen import generate_plot, gen_track, save_to_csv
from types import SimpleNamespace
import numpy as np


KNOT_TO_FTPS = 1.68780972222222
n_key = 'north_ft'
e_key = 'east_ft'
u_key = 'up_ft'
psi_key = 'psi_rad'


def is_time_key(key_name):
    key_name = key_name.lower()
    return key_name in ('time', 'time_s', 't', 't_s', 't_sec') or 'time' in key_name

def is_attitude_key(key_name):
    key_name = key_name.lower()
    attitude_tokens = (
        'phi', 'theta', 'psi', 'phi_rad', 'theta_rad', 'psi_rad',
        'roll', 'pitch', 'yaw', 'roll_rad', 'pitch_rad', 'yaw_rad',
        'p_rad', 'q_rad', 'r_rad',
        'p_deg', 'q_deg', 'r_deg',
    )
    return any(token in key_name for token in attitude_tokens)

def track_rotate(track, rotation_angle_deg, rotation_point_N_ft_E_ft=[0,0]):
    if rotation_angle_deg is None:
        return track
    # Calculate current bearing
    x0, y0 = track[e_key][0], track[n_key][0]
    x1, y1 = track[e_key][-1], track[n_key][-1]
    dx, dy = x1 - x0, y1 - y0
    current_bearing = np.degrees((np.pi/2.0 - np.arctan2(dy, dx))) % 360
    desired_bearing = rotation_angle_deg % 360
    rot_angle = np.radians(desired_bearing - current_bearing)
    cos_a, sin_a = np.cos(rot_angle), np.sin(rot_angle)
    for i in range(len(track[n_key])):
        x, y = track[e_key][i] - rotation_point_N_ft_E_ft[0], track[n_key][i] - rotation_point_N_ft_E_ft[1]
        x_rot = x * cos_a - y * sin_a
        y_rot = x * sin_a + y * cos_a
        track[n_key][i] = y_rot + rotation_point_N_ft_E_ft[1]
        track[e_key][i] = x_rot + rotation_point_N_ft_E_ft[0]
    track[psi_key] = (track[psi_key] + rot_angle) % (2 * np.pi)
    return track

def track_update_altitude(track, alt_start, alt_end):
    if alt_start is None or alt_end is None:
        return track
    alt_0 = track[u_key][0]
    alt_n = track[u_key][-1]
    delta_0 = alt_start - alt_0
    delta_n = alt_end - alt_n
    track[u_key] += np.linspace(delta_0, delta_n, len(track[u_key]))
    # TODO: Adjust pitch (airplane modes only) to match the new altitude profile. For now, we keep 
    # the same pitch, which will track in unrealistic maneuvers if the altitude rate is significant.
    return track

def track_offset_initial_position(own_track, intr_track, lateral_offset_ft=0.0, vertical_offset_ft=0.0):
    if lateral_offset_ft is None:
        lateral_offset_ft = 0.0
    if vertical_offset_ft is None:
        vertical_offset_ft = 0.0

    delta_e = intr_track[e_key][1] - intr_track[e_key][0]
    delta_n = intr_track[n_key][1] - intr_track[n_key][0]

    norm = np.hypot(delta_e, delta_n)
    if norm > 0 and lateral_offset_ft != 0:
        unit_e = delta_e / norm
        unit_n = delta_n / norm
        perp_e = -unit_n
        perp_n = unit_e
        intr_track[e_key] += lateral_offset_ft * perp_e
        intr_track[n_key] += lateral_offset_ft * perp_n

    target_intruder_first_alt = own_track[u_key][0] + vertical_offset_ft
    delta_alt = target_intruder_first_alt - intr_track[u_key][0]
    intr_track[u_key] += delta_alt

    return intr_track

def track_offset_final_position(own_track, intr_track, lateral_offset_ft=0.0, vertical_offset_ft=0.0):
    if lateral_offset_ft is None:
        lateral_offset_ft = 0.0
    if vertical_offset_ft is None:
        vertical_offset_ft = 0.0

    if len(intr_track[n_key]) >= 2 and lateral_offset_ft != 0:
        delta_e = intr_track[e_key][-1] - intr_track[e_key][-2]
        delta_n = intr_track[n_key][-1] - intr_track[n_key][-2]
        norm = np.hypot(delta_e, delta_n)
        if norm > 0:
            unit_e = delta_e / norm
            unit_n = delta_n / norm
            perp_e = -unit_n
            perp_n = unit_e
            intr_track[e_key] += lateral_offset_ft * perp_e
            intr_track[n_key] += lateral_offset_ft * perp_n

    target_intruder_last_alt = own_track[u_key][-1] + vertical_offset_ft
    delta_alt = target_intruder_last_alt - intr_track[u_key][-1]
    intr_track[u_key] += delta_alt

    return intr_track

def bearing_from_to(e0, n0, e1, n1):
    return np.degrees((np.pi / 2.0 - np.arctan2(n1 - n0, e1 - e0))) % 360

def track_last_bearing(track):
    if len(track[n_key]) < 2:
        return 0.0
    return bearing_from_to(track[e_key][-2], track[n_key][-2], track[e_key][-1], track[n_key][-1])

def track_align_final_position(own_track, intr_track):
    delta_n = own_track[n_key][-1] - intr_track[n_key][-1]
    delta_e = own_track[e_key][-1] - intr_track[e_key][-1]
    delta_u = own_track[u_key][-1] - intr_track[u_key][-1]
    intr_track[n_key] += delta_n
    intr_track[e_key] += delta_e
    intr_track[u_key] += delta_u
    return intr_track

def track_rotate_for_final_ownship_to_intruder_azimuth_value(own_track, intr_track, relative_azimuth_deg):
    own_end_bearing = track_last_bearing(own_track)
    intr_end_bearing = track_last_bearing(intr_track)
    desired_intr_end_bearing = (own_end_bearing + (relative_azimuth_deg % 360)) % 360
    # Bearing angles are clockwise from North; Cartesian rotation is counterclockwise from East.
    # Therefore, bearing delta must be negated before applying 2D rotation matrix.
    rot_angle = -np.radians(desired_intr_end_bearing - intr_end_bearing)
    cos_a, sin_a = np.cos(rot_angle), np.sin(rot_angle)
    rotation_e = intr_track[e_key][-1]
    rotation_n = intr_track[n_key][-1]
    for i in range(len(intr_track[n_key])):
        x = intr_track[e_key][i] - rotation_e
        y = intr_track[n_key][i] - rotation_n
        x_rot = x * cos_a - y * sin_a
        y_rot = x * sin_a + y * cos_a
        intr_track[e_key][i] = x_rot + rotation_e
        intr_track[n_key][i] = y_rot + rotation_n
    intr_track[psi_key] = (intr_track[psi_key] + rot_angle) % (2 * np.pi)
    return intr_track


def track_update_speeds(own_track, intr_track, own_speed_knots, intr_speed_knots):
    own_speed_ftps = own_speed_knots * KNOT_TO_FTPS
    intr_speed_ftps = intr_speed_knots * KNOT_TO_FTPS
    
    def adjust_speed(track, target_speed_ftps):
        # Adjusts the average speed to match the requirement
        north_diff = np.diff(track['n_key'])
        east_diff = np.diff(track['e_key'])
        up_diff = np.diff(track['u_key'])
        total_distance = np.sum(np.sqrt(north_diff**2 + east_diff**2 + up_diff**2))
        max_time = total_distance / target_speed_ftps 
        track['time'] = track['time'] - track['time'][0]  # Ensure time starts at 0
        new_time = track['time'] * (max_time / track['time'][-1])
        track['time'] = new_time
        return track
    
    def rebuild_time_axis(own_track, intr_track):
        # Find the lowest end time between the two tracks and rebuild the time axis to match that duration, 
        # while keeping the relative time points of each track
        own_time = own_track['time'] - own_track['time'][0]
        intr_time = intr_track['time'] - intr_track['time'][0]
        # Find who has minimum duration, and what that duration is
        intr_is_shorter = own_time[-1] > intr_time[-1]
        min_duration = min(own_time[-1], intr_time[-1])
        # Cut results to the minimum duration, which is the one of the shorter track
        own_track = {key: value[own_time <= min_duration] for key, value in own_track.items()}
        intr_track = {key: value[intr_time <= min_duration] for key, value in intr_track.items()}
        # Interpolate all parameters to have the same time points, which are the ones of the longer track
        if len(own_track['time']) < len(intr_track['time']):
            own_track = {key: np.interp(intr_track['time'], own_track['time'], value) for key, value in own_track.items()}
            own_track['time'] = intr_track['time']
        else:
            intr_track = {key: np.interp(own_track['time'], intr_track['time'], value) for key, value in intr_track.items()}
            intr_track['time'] = own_track['time']

        return own_track, intr_track
    
    own_track = adjust_speed(own_track, own_speed_ftps)
    intr_track = adjust_speed(intr_track, intr_speed_ftps)
    own_track, intr_track = rebuild_time_axis(own_track, intr_track)
    # TODO: adjust attitudes to match the new speeds. For now, we keep the same attitudes, which will result in unrealistic 
    # maneuvers if the speed change is significant, but will preserve the general shape of the encounter.
    # NOTE: this speed adjustment is currently not used, as the gen_track function can directly generate tracks with the 
    # desired speed, which is more efficient and preserves the original track shape better than post-hoc speed adjustment.
    # The function is kept here for reference in case post-hoc speed adjustments are needed in the future, but for now it 
    # is not called from the main logic.
    return own_track, intr_track

def track_reverse(track):
    
    def rebuild_time_axis(reversed_time_values):
        time_values = np.asarray(reversed_time_values, dtype=float)
        rebuilt_time = np.zeros_like(time_values, dtype=float)
        if time_values.size > 1:
            rebuilt_time[1:] = np.cumsum(-np.diff(time_values))
        return rebuilt_time

    for key, value in track.items():
        if isinstance(value, np.ndarray):
            if value.ndim >= 1 and value.size > 1:
                reversed_value = value[::-1].copy()
                if is_time_key(key):
                    reversed_value = rebuild_time_axis(reversed_value)
                elif is_attitude_key(key):
                    reversed_value = -reversed_value
                track[key] = reversed_value
        elif isinstance(value, list):
            if len(value) > 1:
                reversed_value = list(reversed(value))
                if is_time_key(key):
                    reversed_value = rebuild_time_axis(reversed_value).tolist()
                elif is_attitude_key(key):
                    reversed_value = [-v for v in reversed_value]
                track[key] = reversed_value
    return track

def build_title(args, own_track, intr_track=None):
    def actual_speed_kt(track):
        return track.get('actual_speed', float(np.mean(track['speed_ftps']) / KNOT_TO_FTPS))

    def single_track_line(prefix, track, category, altitude, altitude_end, speed_cmd, straight_flag, csv_filename=None, azimuth=None, lateral_offset=None, vertical_offset=None):
        source = 'CSV' if csv_filename is not None else category
        line = (
            f"{prefix} cat:{source}, alt:{altitude}->{altitude_end}ft, "
            f"cmd spd:{speed_cmd}kt, actual spd:{actual_speed_kt(track):.1f}kt, "
            f"Straight:{bool(straight_flag)}"
        )
        if azimuth is not None or lateral_offset is not None or vertical_offset is not None:
            line = (
                f"{line}, Az:{azimuth}deg, LatOff:{lateral_offset}ft, VertOff:{vertical_offset}ft"
            )
        return line

    def csv_path_line(prefix, csv_filename):
        if csv_filename is None:
            return None
        return f"{prefix} csv:{csv_filename}"

    if intr_track is None:
        single_category = getattr(args, 'filename', 'CSV')
        single_altitude = getattr(args, 'altitude', 'n/a')
        single_altitude_end = getattr(args, 'altitude_end', 'n/a')
        single_speed = getattr(args, 'desired_speed_kt', getattr(args, 'speed', 'n/a'))
        single_straight = getattr(args, 'straight_flight', False)
        single_csv = getattr(args, 'trajectory_csv_filename', None)
        track_line = single_track_line(
            prefix='Track',
            track=own_track,
            category=single_category,
            altitude=single_altitude,
            altitude_end=single_altitude_end,
            speed_cmd=single_speed,
            straight_flag=single_straight,
            csv_filename=single_csv,
        )
        csv_line = csv_path_line('Track', single_csv)
        return f"{track_line}\n{csv_line}" if csv_line is not None else track_line

    own_line = single_track_line(
        prefix='Own',
        track=own_track,
        category=getattr(args, 'Ownship_category', 'n/a'),
        altitude=getattr(args, 'Ownship_altitude', 'n/a'),
        altitude_end=getattr(args, 'Ownship_altitude_end', 'n/a'),
        speed_cmd=getattr(args, 'Ownship_speed', 'n/a'),
        straight_flag=getattr(args, 'Ownship_straight_line', False),
        csv_filename=getattr(args, 'Ownship_trajectory_csv_filename', None),
    )
    intr_line = single_track_line(
        prefix='Int',
        track=intr_track,
        category=getattr(args, 'Intruder_category', 'n/a'),
        altitude=getattr(args, 'Intruder_altitude', 'n/a'),
        altitude_end=getattr(args, 'Intruder_altitude_end', 'n/a'),
        speed_cmd=getattr(args, 'Intruder_speed', 'n/a'),
        straight_flag=getattr(args, 'Intruder_straight_line', False),
        csv_filename=getattr(args, 'Intruder_trajectory_csv_filename', None),
        azimuth=getattr(args, 'Intruder_azimuth', 'n/a'),
        lateral_offset=getattr(args, 'Intruder_lateral_offset', 0.0),
        vertical_offset=getattr(args, 'Intruder_vertical_offset', 0.0),
    )
    title_lines = [own_line, intr_line]
    own_csv_line = csv_path_line('Own', getattr(args, 'Ownship_trajectory_csv_filename', None))
    intr_csv_line = csv_path_line('Int', getattr(args, 'Intruder_trajectory_csv_filename', None))
    if own_csv_line is not None:
        title_lines.append(own_csv_line)
    if intr_csv_line is not None:
        title_lines.append(intr_csv_line)
    return "\n".join(title_lines)

def build_track(category, speed_kt, straight_flight_flag, seed, duration, aircraft_category_files, csv_filename=None):
    if csv_filename is not None:
        if speed_kt is None:
            raise ValueError("desired speed is required for CSV trajectories.")
        # In CSV mode, both flight duration and straight_flight are ignored by design.
        return gen_track(
            vehicle_filename=None,
            duration=0,
            number_of_tracks=1,
            seed=seed,
            desired_speed_kt=speed_kt,
            straight_flight=False,
            trajectory_csv_filename=csv_filename,
        )[0]

    return gen_track(
        vehicle_filename=aircraft_category_files[category],
        duration=duration,
        number_of_tracks=1,
        seed=seed,
        desired_speed_kt=speed_kt,
        straight_flight=bool(straight_flight_flag),
    )[0]



def generate_trajectory_or_encounter(args=None):
    
    # Arguments accepted by generate_trajectory_or_encounter(args):
    #
    # Common optional arguments:
    #   - seed (optional, default False)
    #   - save_csv (optional, default False)
    #   - show_plot (optional, default False)
    #   - show_plot_equal_axes (optional, default False)
    #   - total_tracks (optional, default 2)
    #
    # Single-track legacy mode (MAT model):
    #   - filename: aircraft category key
    #       {'G','HA25','HU10','H10t25','HB10','LA25','LU10','L10t25','MA25','MB10','M10t25','U'}
    #   - flight_duration
    #
    # Single-track CSV mode:
    #   - trajectory_csv_filename
    #   - desired_speed_kt
    #   - flight_duration and straight-line flags are ignored in CSV mode
    #
    # Dual-track mode (ownship + intruder):
    #   - Required generation args for each track are either:
    #       1) <Track>_trajectory_csv_filename
    #       2) (<Track>_category, <Track>_altitude, <Track>_altitude_end, duration)
    #   - Speed args:
    #       - Ownship_speed / Intruder_speed are used when provided.
    #       - For CSV-sourced tracks, speed is required by gen_track.
    #   - Track identifiers are Ownship_* and Intruder_*.
    #   - Model categories:
    #       {'G','HA25','HU10','H10t25','HB10','LA25','LU10','L10t25','MA25','MB10','M10t25','U'}
    #   - Optional encounter geometry args:
    #   - Intruder_azimuth
    #   - Intruder_lateral_offset
    #   - Intruder_vertical_offset
    #   - flight_duration (duration; required only for tracks not sourced from CSV)
    #   - Ownship_straight_line (optional, default False)
    #   - Intruder_straight_line (optional, default False)
    #
    # Optional CSV overrides in dual-track mode:
    #   - Ownship_trajectory_csv_filename
    #   - Intruder_trajectory_csv_filename
    #   - trajectory_csv_filename (generic fallback for whichever per-track CSV is missing)
    #   - For tracks sourced from CSV, flight_duration and straight-line flags are ignored
    
    if args is None:
        args = SimpleNamespace()

    defaults = {
        'seed': False,
        'save_csv': False,
        'show_plot': False,
        'show_plot_equal_axes': True,
        'total_tracks': 2,
        'Ownship_straight_line': False,
        'Intruder_straight_line': False,
        'Intruder_lateral_offset': 0.0,
        'Intruder_vertical_offset': 0.0,
        'Intruder_azimuth': None,
    }
    for key, value in defaults.items():
        if not hasattr(args, key):
            setattr(args, key, value)

    aircraft_category_files = {
            'G': 'Gyrocopter_Data.mat',
            'HA25': 'Heavy_Aircraft_Above_25000_ft_Data.mat',
            'HU10': 'Heavy_Aircraft_Below_10000_ft_Data.mat',
            'H10t25': 'Heavy_Aircraft_Between_10000_and_25000_ft_Data.mat',
            'HB10': 'Helicopter_Below_10000_ft_Data.mat',
            'LA25': 'Light_Aircraft_Above_25000_ft_Data.mat',
            'LU10': 'Light_Aircraft_Below_10000_ft_Data.mat',
            'L10t25': 'Light_Aircraft_Between_10000_and_25000_ft_Data.mat',
            'MA25': 'Medium_Aircraft_Above_25000_ft_Data.mat',
            'MB10': 'Medium_Aircraft_Below_10000_ft_Data.mat',
            'M10t25': 'Medium_Aircraft_Between_10000_and_25000_ft_Data.mat',
            'U': 'Ultralight_Aircraft_Data.mat',
            }
    
    # Optional CSV inputs (can be used in single or dual-track calls).
    ownship_csv = getattr(args, 'Ownship_trajectory_csv_filename', None)
    intruder_csv = getattr(args, 'Intruder_trajectory_csv_filename', None)
    generic_csv = getattr(args, 'trajectory_csv_filename', None)

    ownship_input_present = any([ownship_csv is not None, getattr(args, 'Ownship_category', None) is not None])
    intruder_input_present = any([intruder_csv is not None, getattr(args, 'Intruder_category', None) is not None])
    dual_track_intent = ownship_input_present and intruder_input_present

    # For dual-track mode, each side can be generated either from CSV or from model args.
    has_duration = hasattr(args, 'flight_duration') and args.flight_duration is not None

    ownship_has_model_args = all([
        has_duration,
        hasattr(args, 'Ownship_category') and args.Ownship_category is not None,
        hasattr(args, 'Ownship_altitude') and args.Ownship_altitude is not None,
        hasattr(args, 'Ownship_altitude_end') and args.Ownship_altitude_end is not None,
    ])
    intruder_has_model_args = all([
        has_duration,
        hasattr(args, 'Intruder_category') and args.Intruder_category is not None,
        hasattr(args, 'Intruder_altitude') and args.Intruder_altitude is not None,
        hasattr(args, 'Intruder_altitude_end') and args.Intruder_altitude_end is not None,
    ])

    required_ownship = (ownship_csv is not None) or ownship_has_model_args
    required_intruder = (intruder_csv is not None) or intruder_has_model_args

    if dual_track_intent and required_ownship and required_intruder:
        # Generate two tracks: ownship and intruder
        own_results = build_track(
            category=getattr(args, 'Ownship_category', None),
            speed_kt=getattr(args, 'Ownship_speed', None),
            straight_flight_flag=getattr(args, 'Ownship_straight_line', False),
            seed=args.seed,
            duration=args.flight_duration,
            aircraft_category_files=aircraft_category_files,
            csv_filename=ownship_csv,
        )
        intr_results = build_track(
            category=getattr(args, 'Intruder_category', None),
            speed_kt=getattr(args, 'Intruder_speed', None),
            straight_flight_flag=getattr(args, 'Intruder_straight_line', False),
            seed=args.seed,
            duration=args.flight_duration,
            aircraft_category_files=aircraft_category_files,
            csv_filename=intruder_csv,
        )
                    
        own_results = track_update_altitude(own_results, getattr(args, 'Ownship_altitude', None), getattr(args, 'Ownship_altitude_end', None))
        intr_results = track_update_altitude(intr_results, getattr(args, 'Intruder_altitude', None), getattr(args, 'Intruder_altitude_end', None))

        intr_results = track_align_final_position(own_results, intr_results)
        intr_results = track_rotate_for_final_ownship_to_intruder_azimuth_value(own_results, intr_results, args.Intruder_azimuth)
        intr_results = track_offset_final_position(own_results, intr_results, args.Intruder_lateral_offset, args.Intruder_vertical_offset)

        # Alternative way to adjust speeds previously used is commented below. Kept here for reference but currently not used, as the gen_track 
        # function can directly generate tracks with the desired speed, which is more efficient and preserves the original track shape better  
        # than post-hoc speed adjustment.
        # own_results, intr_results = track_update_speeds(own_results, intr_results, args.Ownship_speed, args.Intruder_speed)
        RESULTS = []
        RESULTS.append(own_results)
        RESULTS.append(intr_results)
        
        if args.show_plot:
            generate_plot(RESULTS, title=build_title(args, own_results, intr_results), show_legend=False, equal_aspect=args.show_plot_equal_axes, colors=['blue', 'red'])
    elif dual_track_intent:
        raise ValueError(
            "Dual-track generation requires, for each track (ownship/intruder), either a trajectory CSV "
            "or the model argument set: category, altitude, altitude_end, and flight_duration."
        )
    else:
        # Single-result mode: either classic MAT model or CSV-defined trajectory.
        has_csv_trajectory = generic_csv is not None
        if has_csv_trajectory:
            if not hasattr(args, 'desired_speed_kt') or args.desired_speed_kt is None:
                raise ValueError("desired_speed_kt is required when using trajectory_csv_filename.")

            RESULTS = gen_track(
                vehicle_filename=None,
                duration=0,
                number_of_tracks=1,
                seed=args.seed,
                desired_speed_kt=args.desired_speed_kt,
                # In CSV mode, straight_flight is ignored by design.
                straight_flight=False,
                trajectory_csv_filename=generic_csv,
            )
        else:
            # Legacy single-result mode uses one generated track.
            RESULTS = gen_track(
                vehicle_filename=aircraft_category_files[args.filename],
                duration=args.flight_duration,
                number_of_tracks=1,
                seed=args.seed,
            )
        if args.save_csv:
            save_to_csv(RESULTS)
        if args.show_plot:
            generate_plot(RESULTS, title=build_title(args, RESULTS[0]), show_legend=False, equal_aspect=args.show_plot_equal_axes)
    
    return RESULTS
    
if __name__ == "__main__":
    generate_trajectory_or_encounter()
