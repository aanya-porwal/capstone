import pandas as pd


def create_portfolio(allocation):
    assets = pd.read_csv("data/assets.csv")

    portfolio = {}

    for category, category_weight in allocation.items():
        category_assets = assets[assets["category"] == category]

        if len(category_assets) == 0:
            continue

        asset_weight = category_weight / len(category_assets)

        for asset in category_assets["asset_name"]:
            portfolio[asset] = asset_weight

    return portfolio