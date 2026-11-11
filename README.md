# ViCare Heating Curve Sync

Home Assistant custom integration for bidirectional synchronization
between ViCare heating curves and input_number helpers.

## Features

- Synchronizes heating curve slope and shift from ViCare to Home Assistant.
- Writes changes from Home Assistant helpers back to ViCare.
- Supports two heating circuits.

## Helper mapping

| Heating circuit | Slope | Shift |
|---|---|---|
| Heizkreis 2 – Heizkörper | input_number.steigung | input_number.niveau |
| Heizkreis 1 – Fußbodenheizung | input_number.steigung_fbhz | input_number.niveau_fbhz |

## Requirements

- Home Assistant
- Official ViCare integration
- Four input_number helpers listed above

## Installation

1. Add this repository to HACS as a custom repository.
2. Select the Integration category.
3. Install ViCare Heating Curve Sync.
4. Restart Home Assistant.
5. Add the integration through Settings → Devices & Services.
6. Select the existing ViCare integration.
7. Select the ViCare device that provides the two heating circuits.

## License

MIT
