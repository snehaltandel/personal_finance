import pandas as pd


def normalize_amount_series(series: pd.Series) -> pd.Series:
    """Convert mixed-format currency values into numeric floats."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    cleaned = series.astype("string").str.strip()
    cleaned = cleaned.replace(
        {
            r"^\((.*)\)$": r"-\1",
            r"[\$,]": "",
            r"^\s*$": pd.NA,
        },
        regex=True,
    )
    return pd.to_numeric(cleaned, errors="coerce")
