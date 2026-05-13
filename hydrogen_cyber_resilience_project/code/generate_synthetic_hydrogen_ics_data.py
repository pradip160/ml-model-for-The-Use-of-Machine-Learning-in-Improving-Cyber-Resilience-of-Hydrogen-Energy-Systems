from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def generate_dataset(n_samples: int = 6000, seed: int = 42) -> pd.DataFrame:
    """Generate a controlled hydrogen ICS-style cyber-anomaly dataset.

    The data are synthetic and intended for educational experimentation only. The
    attack scenarios are deliberately interpretable so that the downstream report can
    connect feature changes to OT threat narratives.
    """
    if n_samples < 5600:
        raise ValueError("n_samples must be at least 5600 for the configured attack windows.")

    rng = np.random.default_rng(seed)
    t = np.arange(n_samples)

    # Normal operating dynamics: smooth multivariate process behaviour + bounded noise.
    pressure = 28 + 1.8 * np.sin(t / 130) + rng.normal(0, 0.35, n_samples)
    temperature = 36 + 1.2 * np.sin(t / 190 + 0.6) + rng.normal(0, 0.25, n_samples)
    flow = 75 + 6.0 * np.sin(t / 105 + 0.9) + rng.normal(0, 1.3, n_samples)
    tank_level = 58 + 8.0 * np.sin(t / 300 + 1.2) + rng.normal(0, 0.8, n_samples)
    electrolyzer_current = 420 + 25 * np.sin(t / 115 + 0.2) + rng.normal(0, 5, n_samples)

    valve_state = (flow > np.median(flow)).astype(int)
    compressor_state = (pressure < 28.5).astype(int)

    network_latency = 14 + rng.normal(0, 1.2, n_samples)
    packet_rate = 220 + rng.normal(0, 12, n_samples)
    command_rate = 18 + rng.normal(0, 2.2, n_samples)

    label = np.zeros(n_samples, dtype=int)
    attack_type = np.array(["normal"] * n_samples, dtype=object)

    # Four attack scenarios. The fourth is intentionally lower-amplitude and more
    # ambiguous to make evaluation less trivial than a purely separable dataset.
    attack_regions = [
        (900, 1220, "false_data_injection"),
        (2350, 2680, "denial_of_service"),
        (4200, 4550, "actuator_spoofing"),
        (5200, 5480, "stealthy_sensor_drift"),
    ]

    for start, end, kind in attack_regions:
        idx = slice(start, end)
        n = end - start
        label[idx] = 1
        attack_type[idx] = kind

        if kind == "false_data_injection":
            pressure[idx] += rng.normal(7.5, 0.8, n)
            tank_level[idx] -= rng.normal(12, 1.5, n)
            command_rate[idx] += rng.normal(3, 0.8, n)
        elif kind == "denial_of_service":
            network_latency[idx] += rng.normal(42, 5, n)
            packet_rate[idx] += rng.normal(180, 28, n)
            command_rate[idx] += rng.normal(10, 2, n)
        elif kind == "actuator_spoofing":
            valve_state[idx] = 1 - valve_state[idx]
            compressor_state[idx] = 1 - compressor_state[idx]
            pressure[idx] += rng.normal(-4, 0.6, n)
            flow[idx] += rng.normal(-13, 2.2, n)
        elif kind == "stealthy_sensor_drift":
            # A subtle, gradual bias that is harder to distinguish from normal
            # operating variation than the other attacks.
            drift = np.linspace(0.0, 2.3, n)
            pressure[idx] += drift + rng.normal(0, 0.25, n)
            flow[idx] -= 0.55 * drift + rng.normal(0, 0.35, n)
            tank_level[idx] += 0.45 * drift + rng.normal(0, 0.25, n)
            command_rate[idx] += rng.normal(1.0, 0.5, n)

    data = pd.DataFrame(
        {
            "timestamp_index": t,
            "pressure_bar": pressure,
            "temperature_c": temperature,
            "flow_nm3h": flow,
            "tank_level_pct": tank_level,
            "electrolyzer_current_a": electrolyzer_current,
            "valve_state": valve_state,
            "compressor_state": compressor_state,
            "network_latency_ms": network_latency,
            "packet_rate_pps": packet_rate,
            "command_rate_per_min": command_rate,
            "attack_label": label,
            "attack_type": attack_type,
        }
    )
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic hydrogen ICS cyber-anomaly dataset.")
    parser.add_argument("--samples", type=int, default=6000, help="Number of time steps to generate.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/hydrogen_ics_synthetic.csv"),
        help="Output CSV path.",
    )
    args = parser.parse_args()

    df = generate_dataset(n_samples=args.samples, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"Wrote {len(df):,} rows to {args.output}")
    print(df["attack_type"].value_counts().to_string())


if __name__ == "__main__":
    main()
