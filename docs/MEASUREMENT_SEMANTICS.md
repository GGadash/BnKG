# BnKG — Measurement source, period and labelling rules

Standing user requirements recorded 2026-09-27. Apply to future changes across Dashboard, Frequency Analysis, tables/charts, saved-file readers, sessions and all exports/reports. These are requirements, not a claim that new modes are already implemented or supported by the connected SLM.

## Instrument values first

- Obtain Z-, C- and A-weighted values and one-third-octave spectra directly from the SLM wherever available. Preserve the instrument's raw values, descriptor conversion, units, frequency/time weighting, frequency axis, measurement identity, timestamps, validity and period.
- Decoding raw values with the device's advertised Scale/Offset is not the same as synthesizing a missing weighting. Do not replace an unavailable instrument A/C value with a calculation from Z and present it as measured.
- If a calculated result is needed, keep it separate and clearly labelled **Calculated**, with an explanation visible in the screen's information area/footer. Identify every affected series/value in its legend, tooltip or detail view as well, so mixed measured/calculated displays remain unambiguous. Explain the input source, operation (for example A/C weighting estimated from Z), time basis and limitations. Carry that provenance into saved data and exports.
- Unsupported or missing direct results remain unavailable unless an explicitly distinguished calculated view is being used. Never invent bands, coefficients, measurement periods or replacement readings. Invalid values are not zero. Demo remains explicitly synthetic and isolated.

## Three different measurement meanings

| Meaning | Example labels | Required interpretation |
| --- | --- | --- |
| Whole-measurement cumulative/aggregated equivalent level | `LAeq — measurement total`, `LCeq — measurement total`, `LZeq — measurement total` | Energy-equivalent result over the actual accumulated measurement period. Preserve measurement identity, duration and pause/completed state when available. Do not label it as a short current interval. |
| Short-term interval equivalent level | `LAeq,125 ms — interval`, `LZeq,125 ms — interval`, if those exact outputs are supported | Result over a defined short integration window. Show the actual verified duration and interval/time basis. The user's 125 ms example is a requested distinction, not evidence that every device provides that interval. |
| Current time-weighted level | `LAF — current Fast`, `LZF — current Fast` | A current time-weighted reading. Do not relabel it as interval Leq, cumulative Leq or a true peak/max value. |

Use conventional descriptor-backed names such as LAeq, LCeq and LZeq. Do not infer a new parameter from ambiguous shorthand. Preserve F/S/I and peak/max distinctions where applicable; do not assume LAFeq and LAeq are interchangeable.

**Do not infer a 125 ms interval Leq from a Fast/F designation.** Time weighting, integration-window duration, stream/output period, acquisition polling interval and UI refresh rate are different properties. Verify them independently. The currently documented BnKG REST example `CPBLZF250ms` is a current Fast spectrum with a verified output-period mapping; its suffix must not be reinterpreted as `LZeq,125 ms` or as interval Leq. Keep the actual descriptor information. If the measurement basis is unknown, say so and withhold misleading labels/calculations.

## Frequency charts and source modes

- Apply the distinction to every one-third-octave histogram/bar series, legend, tooltip, cursor value, table and broadband total. Display the weighting, quantity, period/measurement scope and origin in readable form.
- Live versus Saved describes data source/liveness; it does not establish whether a value is current Fast, short-term interval Leq or a whole-measurement total. Keep these dimensions separate in the UI and data model.
- Only compare/overlay values on compatible band axes with matching measurement/time bases, or explicitly identify the different scopes. A total column must match its plotted series and source; never mix a saved total with live bars.
- A saved measurement remains frozen and retains its original period and provenance while live acquisition continues. A current F spectrum is not a peak cap by default; overlays need an accurate quantity/period label.
- Range/zoom/style controls are local presentation preferences. They must not silently change SLM configuration or imply support for additional bands.

## Future implementation and acceptance

Carry source (instrument/calculated/simulation), parameter/weightings, aggregation kind (measurement total/interval/current time-weighted), verified interval or duration, time basis, measurement identity and band descriptors wherever supplied. Unknown metadata stays unknown rather than being guessed.

Future tests must distinguish a whole-measurement LAeq/LZeq, a verified 125 ms interval Leq, a current LAF/LZF, and a differently paced output such as the existing 250 ms current spectrum. Verify calculated labels and provenance survive view changes, saved-file loading and export. Confirm missing direct A/C outputs are never silently filled by Z-derived values. These are planned acceptance requirements; this documentation update makes no application changes.
