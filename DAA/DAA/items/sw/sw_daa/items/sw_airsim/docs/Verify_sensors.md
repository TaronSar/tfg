# Verify_sensors - Methods Organization

```mermaid
graph LR
    subgraph "Initialization"
        A1["__init__"] --> A2["_configure_sensor_lists"]
        A2 --> A3["_load_sensor_names"]
    end
    
    subgraph "Configuration"
        B1["_get_sensor_group_configs"]
        B2["_build_representative_sensor_registry"]
        B3["_build_ros_topics"]
    end
    
    subgraph "API Verification"
        C1["_verify_imu"]
        C2["_verify_gps"]
        C3["_verify_barometer"]
        C4["_verify_magnetometer"]
        C5["_verify_lidar"]
        C6["_measure_api_frequency"]
    end
    
    subgraph "ROS Verification"
        D1["_verify_topics"]
        D2["_report_discovered_message_types"]
        D3["Measure ROS frequencies"]
    end
    
    subgraph "Reporting"
        E1["_report_sensor_group_results"]
        E2["_separator"]
    end
    
    subgraph "Public Methods"
        F1["run_api_verification"]
        F2["run_ros_verification"]
        F3["run"]
    end
    
    A1 --> B1
    B1 --> B2
    B1 --> B3
    
    F1 --> C1
    F1 --> C2
    F1 --> C3
    F1 --> C4
    F1 --> C5
    F1 --> C6
    F1 --> E1
    
    F2 --> D1
    F2 --> D2
    F2 --> D3
    
    E1 --> E2
    
    F3 --> F1
    F3 --> F2
    
    style A1 fill:#50C878,stroke:#2E7D4E,stroke-width:2px,color:#fff
    style A2 fill:#50C878,stroke:#2E7D4E,stroke-width:2px,color:#fff
    style A3 fill:#50C878,stroke:#2E7D4E,stroke-width:2px,color:#fff
    
    style B1 fill:#4A90E2,stroke:#2E5C8A,stroke-width:2px,color:#fff
    style B2 fill:#4A90E2,stroke:#2E5C8A,stroke-width:2px,color:#fff
    style B3 fill:#4A90E2,stroke:#2E5C8A,stroke-width:2px,color:#fff
    
    style C1 fill:#FF9500,stroke:#C67000,stroke-width:2px,color:#fff
    style C2 fill:#FF9500,stroke:#C67000,stroke-width:2px,color:#fff
    style C3 fill:#FF9500,stroke:#C67000,stroke-width:2px,color:#fff
    style C4 fill:#FF9500,stroke:#C67000,stroke-width:2px,color:#fff
    style C5 fill:#FF9500,stroke:#C67000,stroke-width:2px,color:#fff
    style C6 fill:#FF9500,stroke:#C67000,stroke-width:2px,color:#fff
    
    style D1 fill:#9B59B6,stroke:#5F3B7D,stroke-width:2px,color:#fff
    style D2 fill:#9B59B6,stroke:#5F3B7D,stroke-width:2px,color:#fff
    style D3 fill:#9B59B6,stroke:#5F3B7D,stroke-width:2px,color:#fff
    
    style E1 fill:#E74C3C,stroke:#A13520,stroke-width:2px,color:#fff
    style E2 fill:#E74C3C,stroke:#A13520,stroke-width:2px,color:#fff
    
    style F1 fill:#00AA44,stroke:#005A28,stroke-width:3px,color:#fff
    style F2 fill:#00AA44,stroke:#005A28,stroke-width:3px,color:#fff
    style F3 fill:#00AA44,stroke:#005A28,stroke-width:3px,color:#fff
```

---

## Colors legend

| Color | Category | Description |
|-------|-----------|-------------|
| 🟢 Light Green | **Initialization** | Initial load from JSON |
| 🔵 Blue | **Configuration** | Registers configuration and mapping |
| 🟠 Orange | **API Verification** | Verification via AirSim API |
| 🟣 Purple | **ROS Verification** | Verification via ROS topics |
| 🔴 Red | **Reporting** | Reports Generation |
| 🟢 Dark Green | **Public Methods** | Methods of public entry |

## Relaciones

- **Initialization** → **Configuration**: The initial methods prepare configurations
- **Public Methods** → **API Verification**: `run_api_verification()` uses all the API verification methods
- **Public Methods** → **ROS Verification**: `run_ros_verification()` uses all the ROS verification method
- **Public Methods** → **Reporting**: Both verifications use report methods
