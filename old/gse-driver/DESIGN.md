# GSE Embedded Software Design

## 0 - Read Pipeline

Bootup process:

1. Wait for a trigger from a virtual channel that indicates we start data
saving.
2. Grab the currently active range.
3. Fetch all the GSE DAQ read channels. "gse_ai_*".
4. Pull configuration parameters from the active range.
5. Open a new writer to Synnax.
6. Read from the DAQ
7. Apply calibrations to the data.
8. Write to Synnax.
