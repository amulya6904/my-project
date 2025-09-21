import pandas as pd
import sys

# Read the CSV file
csv_file = sys.argv[1] if len(sys.argv) > 1 else 'transactions.csv'
df = pd.read_csv(csv_file)

print(f"=== Analysis of {csv_file} ===\n")
print(f"Total transactions: {len(df)}")
print(f"Columns: {', '.join(df.columns)}")
print(f"\nFirst 5 transactions:")
print(df.head())

# If there are debit/credit columns
if 'Debit' in df.columns and 'Credit' in df.columns:
    total_debit = df['Debit'].sum()
    total_credit = df['Credit'].sum()
    print(f"\nTotal Debits: {total_debit}")
    print(f"Total Credits: {total_credit}")
    print(f"Net: {total_credit - total_debit}")
