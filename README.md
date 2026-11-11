
# ViCare Heating Curve Sync

Home Assistant custom integration for bidirectional synchronization between ViCare heating curves and `input_number` helpers.

## Features

- Synchronizes heating curve slope and shift from ViCare to Home Assistant.
- Writes changes from Home Assistant helpers back to ViCare.
- Supports two ViCare heating circuits.
- Uses the official Home Assistant ViCare integration.

## Helper mapping

| Heating circuit | Heating system | Slope | Shift |
|---|---|---|---|
| Heating circuit 1 | Radiators | `input_number.steigung` | `input_number.niveau` |
| Heating circuit 2 | Underfloor heating | `input_number.steigung_fbhz` | `input_number.niveau_fbhz` |

## Requirements

- Home Assistant
- Official ViCare integration
- Two ViCare heating circuits with supported heating curves
- Four `input_number` helpers listed above

## Installation

1. Add this repository to HACS as a custom repository.
2. Select the Integration category.
3. Install ViCare Heating Curve Sync.
4. Restart Home Assistant.
5. Add the integration through Settings → Devices & Services.
6. Select the existing ViCare integration.
7. Select the ViCare device that provides the two heating circuits.

## Tested functionality

The integration has been manually tested with Home Assistant Core 2026.11.1 and Home Assistant OS 18.4.

All four heating curve values were successfully tested in both directions:

| Heating circuit | Value | ViCare → Home Assistant | Home Assistant → ViCare |
|---|---|---|---|
| Circuit 1 – Radiators | Slope | Passed | Passed |
| Circuit 1 – Radiators | Shift | Passed | Passed |
| Circuit 2 – Underfloor heating | Slope | Passed | Passed |
| Circuit 2 – Underfloor heating | Shift | Passed | Passed |

The tests confirmed that changes made in the ViCare app are automatically transferred to Home Assistant and changes made to the Home Assistant helpers are written back to ViCare.

## License

MIT
