import pandas as pd
import re

df = pd.read_csv('data/dataset_2026-01-29T20_09_46.399406532Z_DEFAULT_INTEGRATION_IMF.RES_WEO_9.0.0.csv')
treatment_series = df[df['SERIES_NAME'].str.contains(re.escape('Net lending (+) / net borrowing (-)'), case=False, na=False, regex=True)]
print(f'Found {len(treatment_series)} rows for treatment series')
print(f'Unique countries: {treatment_series["COUNTRY"].nunique()}')
print(f'\nSample series names:')
for s in treatment_series['SERIES_NAME'].unique()[:3]:
    print(f'  - {s}')

# Also check outcome
outcome_series = df[df['SERIES_NAME'].str.contains('Gross domestic product', case=False, na=False, regex=False)]
print(f'\nFound {len(outcome_series)} rows for outcome (GDP) series')
print(f'Unique countries: {outcome_series["COUNTRY"].nunique()}')
