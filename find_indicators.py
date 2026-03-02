import pandas as pd

df = pd.read_csv('data/dataset_2026-01-29T20_09_46.399406532Z_DEFAULT_INTEGRATION_IMF.RES_WEO_9.0.0.csv')

# Find indicators related to debt
debt_indicators = df[df['INDICATOR'].str.contains('debt|Debt', case=False, na=False)]['INDICATOR'].unique()
print('[TEST] Debt indicators:')
for ind in debt_indicators[:10]:
    print(f'  {ind}')

# Find indicators related to growth
growth_indicators = df[df['INDICATOR'].str.contains('growth|GDP|Gross', case=False, na=False)]['INDICATOR'].unique()
print('\n[TEST] Growth/GDP indicators:')
for ind in growth_indicators[:15]:
    print(f'  {ind}')

print(f'\n[TEST] Total unique indicators: {df["INDICATOR"].nunique()}')
