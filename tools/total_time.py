import pandas as pd

df = pd.read_csv("results.csv")

total_seconds = df["time"].max()

print(f"{total_seconds/3600}h")