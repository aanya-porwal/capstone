import pandas as pd

data = pd.read_csv("data/assets.csv")

print("Number of assets:", len(data))
print("Asset categories:")
print(data["category"].unique())

print("\nAsset data:")
print(data)