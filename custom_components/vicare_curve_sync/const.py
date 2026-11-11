
"""Constants for ViCare Heating Curve Sync."""

DOMAIN = "vicare_curve_sync"
CONF_VICARE_ENTRY_ID = "vicare_entry_id"
CONF_VICARE_DEVICE = "vicare_device"

# API-Heizkreis -> Home-Assistant-Helper
CIRCUIT_HELPERS = {
    0: {
        "slope": "input_number.steigung",
        "shift": "input_number.niveau",
        "name": "Heizkörper",
    },
    1: {
        "slope": "input_number.steigung_fbhz",
        "shift": "input_number.niveau_fbhz",
        "name": "Fußbodenheizung",
    },
}
