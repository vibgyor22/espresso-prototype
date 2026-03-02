import pandas as pd

df = pd.read_csv('data/dataset_2026-01-29T20_09_46.399406532Z_DEFAULT_INTEGRATION_IMF.RES_WEO_9.0.0.csv')

# Show structure
print('[INFO] Sample of raw data:')
print(df[['COUNTRY', 'SERIES_CODE', 'INDICATOR']].head(20))

print('\n[INFO] Series code patterns:')
series_codes = df['SERIES_CODE'].unique()[:20]
for code in series_codes:
    ind = df[df['SERIES_CODE'] == code]['INDICATOR'].iloc[0]
    print(f'  {code} -> {ind[:60]}...')

# After pivot, the structure changes
from data_utils import pivot_indicator_panel

df_long, unit_col, indicator_col = pivot_indicator_panel(df)
print(f'\n[INFO] After pivot:')
print(f'  Shape: {df_long.shape}')
print(f'  Columns: {df_long.columns.tolist()}')
print(f'  Sample rows:')
print(df_long.head(10))

print(f'\n[INFO] Unique SERIES_CODE values in pivoted data: {df_long["SERIES_CODE"].nunique()}')
print('[INFO] Sample SERIES_CODE values:')
for code in df_long['SERIES_CODE'].unique()[:10]:
    print(f'  {code}')
