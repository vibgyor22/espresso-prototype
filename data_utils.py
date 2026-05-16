import pandas as pd

def load_data(path):
    """Load a CSV file into memory"""
    return pd.read_csv(path)

def is_panel_data(df, unit_col, time_col):
    """
    Check if the data has both unit and time columns
    (needed for certain statistical methods)
    """
    if unit_col is None or time_col is None:
        return False
    return unit_col in df.columns and time_col in df.columns

def treatment_varies(df, treatment, unit):
    """
    Check if the treatment variable actually changes
    within each unit (otherwise we can't measure its effect)
    """
    if treatment is None or unit is None:
        return False
    if treatment not in df.columns or unit not in df.columns:
        return False
    # Check if treatment changes for at least one unit
    return df.groupby(unit)[treatment].nunique().gt(1).any()


def get_column_samples(df, n=5):
    """
    Return up to `n` sample values (as strings) for each column.
    This is used to provide the LLM with concrete examples of column contents
    so it can infer what each column represents even if the header is irregular.
    Returns a dict: {column_name: [sample_values...]}
    """
    samples = {}
    for col in df.columns:
        # take unique non-null values, converted to strings
        vals = df[col].dropna().astype(str).unique().tolist()
        samples[col] = vals[:n]
    return samples


def find_indicator_column(df):
    """
    Find the column containing human-readable indicator/series names.

    Priority order:
      1. Columns whose name is exactly 'indicator' or 'series_name' (case-insensitive)
      2. Columns containing 'indicator' in the name but NOT 'code'
      3. Columns containing 'series' + 'name' (e.g. SERIES_NAME)
      4. Columns containing 'name' but not 'code'
      5. Columns containing 'series' (fallback, may be a code column)

    Within each tier prefer columns with more unique values (names > codes).
    """
    lc = {c: c.lower() for c in df.columns}

    def n_unique(col):
        try:
            return df[col].nunique()
        except Exception:
            return 0

    def best(cols):
        return max(cols, key=n_unique) if cols else None

    tier1 = [c for c, l in lc.items() if l in ('indicator', 'series_name', 'seriesname')]
    if tier1:
        return best(tier1)

    tier2 = [c for c, l in lc.items() if 'indicator' in l and 'code' not in l]
    if tier2:
        return best(tier2)

    tier3 = [c for c, l in lc.items() if 'series' in l and 'name' in l]
    if tier3:
        return best(tier3)

    tier4 = [c for c, l in lc.items() if 'name' in l and 'code' not in l]
    if tier4:
        return best(tier4)

    tier5 = [c for c, l in lc.items() if 'series' in l]
    return best(tier5) if tier5 else None


def get_year_columns(df):
    """
    Return a list of columns that look like year columns (e.g., '1980', '2020').
    """
    years = []
    for c in df.columns:
        try:
            y = int(str(c))
            if 1800 <= y <= 2100:
                years.append(c)
        except Exception:
            continue
    return years


def pivot_indicator_panel(df, unit_col=None, indicator_col=None, year_cols=None):
    """
    Convert a wide 'indicator' style dataset into a long panel with columns:
    [unit_col, 'year', indicator_col, 'value']

    If `unit_col` or `indicator_col` are None, the function will try to detect them.
    """
    if indicator_col is None:
        indicator_col = find_indicator_column(df)
    if indicator_col is None:
        raise ValueError('No indicator column found to pivot')

    if unit_col is None:
        # common unit column names
        for candidate in ['country', 'COUNTRY', 'Country', 'country_name', 'LOCATION', 'Country_Name']:
            if candidate in df.columns:
                unit_col = candidate
                break
    if unit_col is None:
        # fallback to the first non-year, non-indicator column
        yc = set(get_year_columns(df))
        for c in df.columns:
            if c not in yc and c != indicator_col:
                unit_col = c
                break

    if year_cols is None:
        year_cols = get_year_columns(df)

    if not year_cols:
        raise ValueError('No year-like columns found to pivot')

    id_vars = [unit_col, indicator_col]
    long = df.melt(id_vars=id_vars, value_vars=year_cols, var_name='year', value_name='value')
    return long, unit_col, indicator_col
