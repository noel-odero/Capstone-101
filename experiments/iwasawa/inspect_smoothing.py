import pandas as pd
from pathlib import Path

DATA_DIR = Path("data/raw/iwasawa/trajectories")

for strain_id in range(1, 5):
    path = DATA_DIR / f"strain{strain_id}.csv"
    df = pd.read_csv(path, index_col=0)

    print(f"\n{'=' * 70}")
    print(f"STRAIN {strain_id}")
    print(f"{'=' * 70}")

    print("Shape:", df.shape)
    print("Drugs:", list(df.index))
    print("Days:", len(df.columns))

    # Transpose so rows are days and columns are drugs.
    trajectory = df.T

    # Six-day trailing moving average, matching the smoothing window
    # described in the Iwasawa analysis.
    smoothed = trajectory.rolling(window=6, min_periods=6).mean()

    print("\nSmoothed trajectory:")
    print(smoothed.round(2).to_string())

    print("\nSmoothed Day 6 -> Day 27 change:")
    changes = smoothed.iloc[-1] - smoothed.iloc[5]
    print(changes.round(3).sort_values(ascending=False).to_string())
