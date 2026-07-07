import math
from PyVeronte import PyVeronte
from bridge import config
from bridge.sensor_snapshot import SensorSnapshot


def _rotate_vec_mat(vec, mat):
    if vec is None or len(vec) < 3:
        return vec
    if mat is None or len(mat) != 3 or any(len(row) != 3 for row in mat):
        return vec

    x, y, z = float(vec[0]), float(vec[1]), float(vec[2])
    return [
        float(mat[0][0]) * x + float(mat[0][1]) * y + float(mat[0][2]) * z,
        float(mat[1][0]) * x + float(mat[1][1]) * y + float(mat[1][2]) * z,
        float(mat[2][0]) * x + float(mat[2][1]) * y + float(mat[2][2]) * z,
    ]

def data_sending_for_imu_debug(veronte: PyVeronte.PyVeronte, snapshot: SensorSnapshot):
    # --- VARIABLES DE PRUEBA PARA TU PFD (Ingresa los ángulos que desees probar) ---
    custom_roll = float(getattr(config, "IMU_DEBUG_ROLL_DEG", 10.0))
    custom_pitch = float(getattr(config, "IMU_DEBUG_PITCH_DEG", 15.0))
    custom_yaw = float(getattr(config, "IMU_DEBUG_YAW_DEG", 0.0))

    # 1. Convertir ángulos a radianes
    phi   = math.radians(custom_roll)
    theta = math.radians(custom_pitch)
    psi   = math.radians(custom_yaw)

    # 2. Calcular componentes trigonométricas
    s_phi, c_phi = math.sin(phi), math.cos(phi)
    s_the, c_the = math.sin(theta), math.cos(theta)
    s_psi, c_psi = math.sin(psi), math.cos(psi)

    # 3. Construir la matriz DCM (NED a Body)
    dcm_ned_to_body = [
        [c_the * c_psi,                               c_the * s_psi,                               -s_the],
        [s_phi * s_the * c_psi - c_phi * s_psi,       s_phi * s_the * s_psi + c_phi * c_psi,       s_phi * c_the],
        [c_phi * s_the * c_psi + s_phi * s_psi,       c_phi * s_the * s_psi - s_phi * c_psi,       c_phi * c_the]
    ]

    # 4. Definir vector de gravedad en NED (m/s^2)
    # Nota: Usamos -9.80665 porque una IMU real en reposo mide una fuerza hacia ARRIBA
    g_ned = [0.0, 0.0, -9.80665]

    # 5. Multiplicar DCM por el vector de gravedad (DCM * g_ned)
    simulated_acc = [
        dcm_ned_to_body[0][0]*g_ned[0] + dcm_ned_to_body[0][1]*g_ned[1] + dcm_ned_to_body[0][2]*g_ned[2],
        dcm_ned_to_body[1][0]*g_ned[0] + dcm_ned_to_body[1][1]*g_ned[1] + dcm_ned_to_body[1][2]*g_ned[2],
        dcm_ned_to_body[2][0]*g_ned[0] + dcm_ned_to_body[2][1]*g_ned[1] + dcm_ned_to_body[2][2]*g_ned[2]
    ]

    # Las tasas de giro se quedan en cero para simular actitud estática
    simulated_gyr = [0.0, 0.0, 0.0] 
    # ---------------------------------------------------------------------------------

    for i, imu in enumerate(snapshot.imu):
        if i >= config.VER_N_IMU:
            break
        imu_name = config.IMUS[i] if i < len(config.IMUS) else f"imu[{i}]"
        imu_slot_ids = getattr(config, "IMU_SLOT_IDS", {})
        slot_id = int(imu_slot_ids.get(imu_name, i + 2))
        
        # SUSTITUCIÓN: Usamos los vectores simulados en lugar de los reales del snapshot
        acc = list(simulated_acc)
        gyr = list(simulated_gyr)

        # Si la rotación de montaje está activa, transformará tu simulación al frame del chip
        if getattr(config, "APPLY_IMU_MOUNT_ROTATION", False) and i < len(config.IMUS):
            mount_mat = getattr(config, "IMU_MOUNT_ROT_MAT", {}).get(imu_name)
            if mount_mat is not None:
                acc = _rotate_vec_mat(acc, mount_mat)
                gyr = _rotate_vec_mat(gyr, mount_mat)
                    
        veronte.writeImu(id=slot_id, acc=acc, gyr=gyr, temp=imu.temp)