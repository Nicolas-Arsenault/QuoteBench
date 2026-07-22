import json

# Product catalog data
# in real world data we would have indexing with the PK of course, here its just an example...
products = [
    {
        "sku": "SMC-MCU-32F4",
        "product_name": "32-Bit ARM Cortex-M4 Microcontroller",
        "unit_price_usd": 3.45,
        "minimum_quantity": 500,
        "lead_time_weeks": 12,
        "supported_application": "IoT Edge Devices, Industrial Automation",
        "max_discount": "15% (orders > 5,000)"
    },
    {
        "sku": "SMC-PWR-GAN65",
        "product_name": "650V GaN Power Transistor",
        "unit_price_usd": 2.15,
        "minimum_quantity": 1000,
        "lead_time_weeks": 16,
        "supported_application": "EV Chargers, Server Power Supplies",
        "max_discount": "18% (orders > 10,000)"
    },
    {
        "sku": "SMC-RF-5GPA",
        "product_name": "5G Sub-6GHz Power Amplifier IC",
        "unit_price_usd": 4.80,
        "minimum_quantity": 250,
        "lead_time_weeks": 10,
        "supported_application": "Mobile Handsets, 5G Small Cells",
        "max_discount": "12% (orders > 2,500)"
    },
    {
        "sku": "SMC-MEM-DDR4",
        "product_name": "8Gb LPDDR4X Memory Chip",
        "unit_price_usd": 5.90,
        "minimum_quantity": 1000,
        "lead_time_weeks": 14,
        "supported_application": "Smartphones, Automotive Infotainment",
        "max_discount": "20% (orders > 10,000)"
    },
    {
        "sku": "SMC-SEN-IMU6",
        "product_name": "6-Axis Inertial Measurement Unit (IMU)",
        "unit_price_usd": 1.25,
        "minimum_quantity": 2000,
        "lead_time_weeks": 8,
        "supported_application": "Drones, Wearables, AR/VR Headsets",
        "max_discount": "22% (orders > 20,000)"
    },
    {
        "sku": "SMC-PMIC-8CH",
        "product_name": "8-Channel PMIC for SoC Power",
        "unit_price_usd": 1.85,
        "minimum_quantity": 1500,
        "lead_time_weeks": 12,
        "supported_application": "Embedded Systems, Single-Board Computers",
        "max_discount": "15% (orders > 15,000)"
    }
]