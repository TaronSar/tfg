#!/usr/bin/env python3

##############################################################################
# @author: 	David Tejero Ruiz (dtejero@catec.aero)
# @date:    2022-11-09
# @brief: 	this script is used to load all the settings and create a single
# custom json file
##############################################################################

import sys
import json
import os
import shutil
from loguru import logger

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

def read_args():
    if len(sys.argv) < 2:
        logger.error("Usage: ./settings/internal/setup.py <autopilot_type> [navigation_type]")
        logger.error("  autopilot_type: px4 | apm | simpleflight")
        logger.error("  navigation_type (px4/apm only): gnss | ext")
        sys.exit(1)

    autopilot_type = sys.argv[1]

    if autopilot_type not in ('px4', 'apm', 'simpleflight'):
        logger.error("Autopilot type must be px4, apm or simpleflight")
        sys.exit(1)

    navigation_type = None
    if autopilot_type in ('px4', 'apm'):
        if len(sys.argv) != 3:
            logger.error(f"Usage: ./settings/internal/setup.py {autopilot_type} <navigation_type>")
            sys.exit(1)
        navigation_type = sys.argv[2]
        if navigation_type not in ('gnss', 'ext'):
            logger.error("Navigation type must be gnss or ext")
            sys.exit(1)

    return autopilot_type, navigation_type

def load_all_settings(autopilot_type):

    # Load internal settings (fixed) — PX4/APM only
    params_px4_gnss = {}
    params_px4_ext = {}
    uav_px4 = {}
    uav_veronte = {}

    if autopilot_type in ('px4', 'apm'):
        with open('./params_px4_gnss.json') as f:
            params_px4_gnss = json.load(f)
        with open('./params_px4_ext.json') as f:
            params_px4_ext = json.load(f)
        with open('./uav_px4.json') as f:
            uav_px4 = json.load(f)
    elif autopilot_type == 'simpleflight':
        with open('./uav_veronte.json') as f:
            uav_veronte = json.load(f)

    # Load customizable settings
    with open('../config_simulation.json') as f:
        config_simulation = json.load(f)
    with open('../sensors.json') as f:
        sensors = json.load(f)

    return params_px4_gnss, params_px4_ext, uav_px4, uav_veronte, config_simulation, sensors

def save_json(settings):
    # Create path to file if it does not exist
    shared_dir = './shared'
    logger.debug(f"Current working directory: {os.getcwd()}")
    logger.debug(f"Attempting to create shared directory at: {os.path.abspath(shared_dir)}")
    
    try:
        if not os.path.exists(shared_dir):
            os.makedirs(shared_dir)
            logger.debug(f"Created directory {shared_dir}")
        else:
            logger.debug(f"Directory {shared_dir} already exists")
    except Exception as e:
        raise RuntimeError(f"ERROR: Failed to create directory {shared_dir}: {e}")
    
    settings_file = os.path.join(shared_dir, 'settings.json')
    logger.debug(f"Settings file path: {os.path.abspath(settings_file)}")
    
    # Remove settings.json if it exists (could be a directory from previous run)
    if os.path.exists(settings_file):
        try:
            if os.path.isdir(settings_file):
                shutil.rmtree(settings_file)
            else:
                os.remove(settings_file)
        except Exception as e:
            raise RuntimeError(f"ERROR: Failed to remove {settings_file}: {e}")
    
    try:
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=4)
        logger.info(f"  >>> settings.json created at {os.path.abspath(settings_file)}")
    except Exception as e:
        raise RuntimeError(f"ERROR: Failed to write settings.json: {e}")

def main():
    # Read arguments
    autopilot_type, navigation_type = read_args()

    # Load all settings
    params_px4_gnss, params_px4_ext, uav_px4, uav_veronte, config_simulation, sensors = load_all_settings(autopilot_type)

    # Clean old settings file if exists (save_json will create directories and file)
    if os.path.exists('./shared/settings.json'):
        os.remove('./shared/settings.json')

    # General config
    settings = {}
    for key in config_simulation:
        settings[key] = config_simulation[key]

    # UAV Autopilot
    if autopilot_type == 'px4':
        if navigation_type == 'gnss':
            for key in params_px4_gnss:
                uav_px4['PX4'][key] = params_px4_gnss[key]
        if navigation_type == 'ext':
            for key in params_px4_ext:
                uav_px4['PX4'][key] = params_px4_ext[key]
        settings['Vehicles'] = uav_px4

    elif autopilot_type == 'simpleflight':
        # Ensure structure exists
        if 'Vehicles' not in settings:
            settings['Vehicles'] = {}
        # Unir la configuración de uav_veronte y sensores bajo 'Veronte'
        settings['Vehicles']['Veronte'] = uav_veronte.get('Veronte', {})
        for key in sensors:
            settings['Vehicles']['Veronte'][key] = sensors[key]

    # Sensors (only for px4 mode — simpleflight already has sensors above)
    if autopilot_type == 'px4':
        # Ensure structure exists
        if 'Vehicles' not in settings:
            settings['Vehicles'] = {}
        if 'PX4' not in settings['Vehicles']:
            settings['Vehicles']['PX4'] = {}
        for key in sensors:
            settings['Vehicles']['PX4'][key] = sensors[key]

    # Save settings
    save_json(settings)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
