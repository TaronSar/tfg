# =============================================================
# Platform Creation Script for Vitis
# =============================================================
# 
# This script automates the creation of a Vitis platform.
# 
# IMPORTANT: This script cannot be run directly with Python:
# python create_platform.py (NOT SUPPORTED)
# 
# Instead, it must be executed through the Vitis tool:
# vitis -s create_platform.py (REQUIRED)
# 
# Ensure you have Vitis installed and properly configured.
# 
# =============================================================

import vitis
import os
import sys

# Verificar si el argumento fue pasado
if len(sys.argv) < 2:
    print("USAGE: create_platform.py [XSA FILE]")
    sys.exit(1)

# Obtener el archivo .xsa
xsa_file = sys.argv[1]
print(f"Processing XSA file: {xsa_file}")

# Get the current working directory
workspace_path = os.path.abspath(os.path.join(os.getcwd(), "../.."))
domain_name = "domain_psu_cortexa53_0"

if not os.path.exists(workspace_path):
    print(f"ERROR: Workspace path does not exist: {workspace_path}")
    sys.exit(1)

print(f"Path: {workspace_path}")

client = vitis.create_client()
client.set_workspace(path = workspace_path)

print(f"Creating platform...")

platform = client.create_platform_component(  
    name = "platform",
    hw_design = xsa_file,
    os = "standalone",
    cpu = "psu_cortexa53_0",
    domain_name = domain_name)

platform = client.get_component(name="platform")

status = platform.build()

vitis.dispose()