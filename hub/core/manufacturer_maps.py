"""
Manufacturer configuration maps for Smart Home Universal Hub.

Provides declarative configuration entries for all 17 supported manufacturers,
including protocol details, authentication types, device types, API endpoints,
payload field mappings, and discovery method configurations.
"""

from typing import Dict, Any

MANUFACTURER_MAPS: Dict[str, Dict[str, Any]] = {
    "philips_hue": {
        "protocol": "rest",
        "base_url_template": "http://{ip}/api/{username}",
        "auth_type": "bridge_token",
        "device_types": ["light"],
        "endpoints": {
            "get_lights": "/lights",
            "set_light": "/lights/{id}/state",
        },
        "payload_map": {
            "light": {
                "power": "on",
                "brightness": "bri",
                "color": "xy",
            }
        },
        "discovery": {
            "method": "upnp_ssdp",
            "ssdp_st": "urn:schemas-upnp-org:device:basic:1",
            "ssdp_mx": 3,
        },
    },
    "tp_link_kasa": {
        "protocol": "tcp",
        "port": 9999,
        "auth_type": "none",
        "device_types": ["plug", "light"],
        "payload_map": {
            "plug": {
                "system": {"set_relay_state": {"state": "power"}}
            },
            "light": {
                "smartlife.iot.dimmer": {
                    "set_brightness": {"brightness": "brightness"}
                },
            },
        },
        "discovery": {
            "method": "udp_broadcast",
            "port": 9999,
            "broadcast_addr": "255.255.255.255",
        },
    },
    "nest": {
        "protocol": "rest",
        "base_url": "https://smartdevicemanagement.googleapis.com/v1",
        "auth_type": "oauth2",
        "device_types": ["thermostat", "camera"],
        "endpoints": {
            "devices": "/enterprises/{project_id}/devices",
            "execute": "/enterprises/{project_id}/devices/{device_id}:executeCommand",
        },
        "payload_map": {
            "thermostat": {
                "mode": "thermostatMode",
                "target_temp": "heatCelsius",
            },
            "camera": {
                "power": "cameraEnabled",
            }
        },
        "discovery": {
            "method": "oauth_cloud",
        },
    },
    "wemo": {
        "protocol": "soap",
        "port": 49153,
        "auth_type": "none",
        "device_types": ["plug"],
        "payload_map": {
            "plug": {
                "power": "BinaryState",
            }
        },
        "discovery": {
            "method": "upnp_ssdp",
            "ssdp_st": "urn:Belkin:device:controllee:1",
        },
    },
    "lifx": {
        "protocol": "rest",
        "base_url_template": "https://api.lifx.com/v1",
        "auth_type": "bearer_token",
        "device_types": ["light"],
        "endpoints": {
            "lights": "/lights/all",
            "set_state": "/lights/{selector}/state",
        },
        "payload_map": {
            "light": {
                "power": "power",
                "brightness": "brightness",
                "color": "color",
            }
        },
        "discovery": {
            "method": "lan",
            "port": 56700,
        },
    },
    "govee": {
        "protocol": "rest",
        "base_url": "https://developer-api.govee.com/v1",
        "auth_type": "api_key",
        "device_types": ["light"],
        "endpoints": {
            "devices": "/devices",
            "control": "/devices/control",
        },
        "payload_map": {
            "light": {
                "power": "power",
                "brightness": "brightness",
                "color": "color",
            }
        },
        "discovery": {
            "method": "cloud_api",
        },
    },
    "wyze": {
        "protocol": "rest",
        "base_url": "https://api.wyzecam.com",
        "auth_type": "user_password",
        "device_types": ["light", "camera", "plug"],
        "endpoints": {
            "login": "/app/user/login",
            "devices": "/app/v2/home_page/list",
            "control": "/app/v2/device/set_property",
        },
        "payload_map": {
            "light": {
                "power": "switch_state",
                "brightness": "brightness",
            },
            "camera": {
                "power": "switch_state",
            },
            "plug": {
                "power": "switch_state",
            },
        },
        "discovery": {
            "method": "cloud_api",
        },
    },
    "ikea_tradfri": {
        "protocol": "coap",
        "port": 5684,
        "auth_type": "psk",
        "device_types": ["light", "plug"],
        "endpoints": {
            "auth": "/15011/9063",
            "devices": "/15001",
            "groups": "/15004",
        },
        "payload_map": {
            "light": {
                "power": "5850",
                "brightness": "5851",
                "color": "5706",
            },
            "plug": {
                "power": "5850",
            },
        },
        "discovery": {
            "method": "coap_dtls",
            "port": 5684,
        },
    },
    "ecobee": {
        "protocol": "rest",
        "base_url": "https://api.ecobee.com",
        "auth_type": "oauth2_pin",
        "device_types": ["thermostat"],
        "endpoints": {
            "auth": "/authorize",
            "token": "/token",
            "thermostat": "/1/thermostat",
        },
        "payload_map": {
            "thermostat": {
                "mode": "hvacMode",
                "target_temp": "holdTemp",
            }
        },
        "discovery": {
            "method": "oauth_cloud",
        },
    },
    "honeywell": {
        "protocol": "rest",
        "base_url": "https://api.honeywell.com/v2",
        "auth_type": "oauth2",
        "device_types": ["thermostat"],
        "endpoints": {
            "devices": "/devices",
            "control": "/devices/thermostats/{device_id}",
        },
        "payload_map": {
            "thermostat": {
                "mode": "mode",
                "target_temp": "heatSetpoint",
            }
        },
        "discovery": {
            "method": "oauth_cloud",
        },
    },
    "emerson_sensi": {
        "protocol": "rest",
        "base_url": "https://api.sensi.com",
        "auth_type": "oauth2",
        "device_types": ["thermostat"],
        "endpoints": {
            "auth": "/oauth/token",
            "devices": "/api/v1/thermostats",
            "control": "/api/v1/thermostats/{device_id}",
        },
        "payload_map": {
            "thermostat": {
                "mode": "operation_mode",
                "target_temp": "setpoint",
            }
        },
        "discovery": {
            "method": "oauth_cloud",
        },
    },
    "mysa": {
        "protocol": "rest",
        "base_url": "https://api.mysa.energy/v1",
        "auth_type": "bearer_token",
        "device_types": ["thermostat"],
        "endpoints": {
            "devices": "/devices",
            "control": "/devices/{device_id}",
        },
        "payload_map": {
            "thermostat": {
                "mode": "mode",
                "target_temp": "targetTemperature",
            }
        },
        "discovery": {
            "method": "cloud_api",
        },
    },
    "blink": {
        "protocol": "rest",
        "base_url": "https://rest-prod.immedia-semi.com",
        "auth_type": "user_password",
        "device_types": ["camera"],
        "endpoints": {
            "login": "/api/v2/login",
            "networks": "/api/v3/accounts/{account_id}/networks",
            "cameras": "/network/{network_id}/cameras",
            "thumbnail": "/media/production/{account_id}/{network_id}/{camera_id}/thumbnail",
        },
        "payload_map": {
            "camera": {
                "power": "enabled",
                "arm": "armed",
            }
        },
        "discovery": {
            "method": "cloud_api",
        },
    },
    "ring": {
        "protocol": "rest",
        "base_url": "https://api.ring.com/clients_api",
        "auth_type": "oauth2",
        "device_types": ["camera"],
        "endpoints": {
            "session": "/session",
            "dings": "/dings/active",
            "devices": "/ring_devices",
            "snapshots": "/snapshots/image/{doorbot_id}",
        },
        "payload_map": {
            "camera": {
                "power": "siren_status",
                "floodlight": "floodlight_on",
            }
        },
        "discovery": {
            "method": "oauth_cloud",
        },
    },
    "eoeeies": {
        "protocol": "rest",
        "base_url_template": "http://{ip}/api/v1",
        "auth_type": "basic_auth",
        "device_types": ["camera"],
        "endpoints": {
            "status": "/status",
            "snapshot": "/snapshot",
            "stream": "/stream",
            "control": "/control",
        },
        "payload_map": {
            "camera": {
                "power": "enabled",
            }
        },
        "discovery": {
            "method": "onvif",
            "port": 80,
        },
    },
    "sonoff": {
        "protocol": "rest",
        "base_url_template": "http://{ip}:8081/zeroconf",
        "auth_type": "bearer_token",
        "device_types": ["plug"],
        "endpoints": {
            "info": "/info",
            "switch": "/switch",
        },
        "payload_map": {
            "plug": {
                "power": "switch",
            }
        },
        "discovery": {
            "method": "mDNS",
            "service": "_ewelink._tcp.local",
        },
    },
    "meross": {
        "protocol": "mqtt",
        "base_url": "mqtt.meross.com",
        "auth_type": "user_password",
        "device_types": ["plug"],
        "endpoints": {
            "publish": "/appliance/pub/subscribe",
        },
        "payload_map": {
            "plug": {
                "power": "togglex",
            }
        },
        "discovery": {
            "method": "cloud_api",
        },
    },
    "lutron_caseta": {
        "protocol": "leap",
        "port": 8081,
        "auth_type": "certificate",
        "device_types": ["plug", "light"],
        "endpoints": {
            "auth": "/api/v1/auth",
            "devices": "/device",
            "control": "/device/{device_id}/command",
        },
        "payload_map": {
            "light": {
                "power": "ZoneStatus",
                "brightness": "Level",
            },
            "plug": {
                "power": "ZoneStatus",
            },
        },
        "discovery": {
            "method": "mDNS",
            "service": "_lutron._tcp.local",
        },
    },
    "generic_camera": {
        "protocol": "rtsp",
        "auth_type": "user_password",
        "device_types": ["camera"],
        "payload_map": {
            "camera": {
                "power": "power",
            }
        },
        "discovery": {
            "method": "manual",
        },
    },
}
