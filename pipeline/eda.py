
from pathlib import Path

import pandas as pd
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import seaborn as sns

from .load import get_engine, read_latest


# Stablecoin symbols used for the segment comparison.
STABLE_SYMBOLS = {
    "USDT", "USDC", "DAI", "USDS", "USDE", "FDUSD",
    "TUSD", "USDD", "GUSD", "PYUSD", "RLUSD"
}

# Columns used in the statistical analysis.
NUMERIC_COLUMNS = [
    "current_price",
    "market_cap",
    "total_volume",
    "volatility_pct",
    "price_change_percentage_24h",
    "liquidity_ratio",
]


def prepare_data(df):
    """Clean numeric columns and prepare the dataset for EDA."""

    df = df.copy()

    for column in NUMERIC_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].fillna("").astype(str).str.upper()

    return df


def save_summary_statistics(df, output_folder):
    """Generate descriptive statistics."""

    columns = [
        column for column in NUMERIC_COLUMNS
        if column in df.columns
    ]

    if not columns:
        return None

    summary = df[columns].describe().T
    path = output_folder / "summary_statistics.csv"
    summary.to_csv(path)

    return path


def detect_outliers(df, output_folder):
    """Detect outliers using the 1.5 × IQR rule."""

    metrics = [
        column for column in [
            "volatility_pct",
            "price_change_percentage_24h",
            "total_volume",
            "liquidity_ratio",
        ]
        if column in df.columns
    ]

    results = []

    for column in metrics:
        values = pd.to_numeric(df[column], errors="coerce").dropna()

        if len(values) < 4:
            continue

        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        mask = (
            pd.to_numeric(df[column], errors="coerce") < lower
        ) | (
            pd.to_numeric(df[column], errors="coerce") > upper
        )

        for _, coin in df[mask].iterrows():
            results.append({
                "symbol": coin.get("symbol", ""),
                "name": coin.get("name", ""),
                "metric": column,
                "value": coin[column],
                "lower_bound": lower,
                "upper_bound": upper,
            })

    path = output_folder / "outlier_analysis.csv"
    pd.DataFrame(results).to_csv(path, index=False)

    return path


def analyze_market_concentration(df, output_folder):
    """Calculate BTC, ETH and top-five market-cap shares."""

    if not {"symbol", "market_cap"}.issubset(df.columns):
        return None

    data = df.dropna(subset=["market_cap"]).copy()
    data = data[data["market_cap"] > 0]
    data = data.sort_values("market_cap", ascending=False)

    total = data["market_cap"].sum()

    if total <= 0:
        return None

    btc = data.loc[data["symbol"] == "BTC", "market_cap"].sum()
    eth = data.loc[data["symbol"] == "ETH", "market_cap"].sum()
    top5 = data.head(5)["market_cap"].sum()

    stable = data["symbol"].isin(STABLE_SYMBOLS)
    stable_cap = data.loc[stable, "market_cap"].sum()

    results = pd.DataFrame({
        "category": [
            "Bitcoin",
            "Ethereum",
            "Top 5 cryptocurrencies",
            "Stablecoins",
        ],
        "market_cap_usd": [
            btc,
            eth,
            top5,
            stable_cap,
        ],
        "market_share_percent": [
            btc / total * 100,
            eth / total * 100,
            top5 / total * 100,
            stable_cap / total * 100,
        ],
    })

    path = output_folder / "market_concentration.csv"
    results.to_csv(path, index=False)

    return path


def generate_charts(folder="eda_output"):
    """Run EDA and generate charts and analysis reports."""

    output = Path(folder)
    output.mkdir(exist_ok=True, parents=True)

    df = read_latest(get_engine())

    if df.empty:
        raise RuntimeError(
            "No market data found. Run python -m pipeline.run first."
        )

    df = prepare_data(df)

    sns.set_theme(style="whitegrid")
    files = []

    def save_figure(fig, filename):
        path = output / filename
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        files.append(str(path))

    # 1. Top 10 most volatile cryptocurrencies.
    if {"symbol", "volatility_pct"}.issubset(df.columns):
        volatility = df.dropna(subset=["volatility_pct"])
        volatility = volatility.nlargest(10, "volatility_pct")
        volatility = volatility.sort_values("volatility_pct")

        if not volatility.empty:
            fig, ax = plt.subplots(figsize=(9, 5))
            sns.barplot(
                data=volatility,
                x="volatility_pct",
                y="symbol",
                ax=ax,
            )
            ax.set(
                title="Top 10 Most Volatile Cryptocurrencies",
                xlabel="Volatility (%)",
                ylabel="Cryptocurrency",
            )
            save_figure(fig, "top_volatility.png")

    # 2. Trading volume versus market capitalization.
    if {"market_cap", "total_volume"}.issubset(df.columns):
        scatter = df.dropna(
            subset=["market_cap", "total_volume"]
        )
        scatter = scatter[
            (scatter["market_cap"] > 0) &
            (scatter["total_volume"] > 0)
        ]

        if not scatter.empty:
            fig, ax = plt.subplots(figsize=(8, 5))
            sns.scatterplot(
                data=scatter,
                x="market_cap",
                y="total_volume",
                ax=ax,
            )
            ax.set_xscale("log")
            ax.set_yscale("log")
            ax.set(
                title="Trading Volume vs Market Capitalization",
                xlabel="Market Cap (USD, log scale)",
                ylabel="24h Trading Volume (USD, log scale)",
            )
            save_figure(fig, "volume_vs_market_cap.png")

    # 3. Distribution of 24-hour price changes.
    if "price_change_percentage_24h" in df.columns:
        changes = df["price_change_percentage_24h"].dropna()

        if not changes.empty:
            fig, ax = plt.subplots(figsize=(8, 5))
            sns.histplot(
                changes,
                bins=15,
                kde=True,
                ax=ax,
            )
            ax.axvline(0, linestyle="--", color="red")
            ax.set(
                title="Distribution of 24-Hour Price Changes",
                xlabel="Price Change (%)",
                ylabel="Number of Cryptocurrencies",
            )
            save_figure(fig, "price_change_distribution.png")

    # 4. Market sentiment: gainers, losers and flat assets.
    if "price_change_percentage_24h" in df.columns:
        changes = df["price_change_percentage_24h"].dropna()

        sentiment = pd.Series({
            "Gainers": int((changes > 0).sum()),
            "Losers": int((changes < 0).sum()),
            "Flat": int((changes == 0).sum()),
        })

        fig, ax = plt.subplots(figsize=(7, 4))
        sentiment.plot(kind="bar", ax=ax)
        ax.set(
            title="Market Sentiment",
            xlabel="Market Category",
            ylabel="Number of Cryptocurrencies",
        )
        save_figure(fig, "market_sentiment.png")

    # 5. Correlation heatmap.
    available = [
        column for column in NUMERIC_COLUMNS
        if column in df.columns
    ]

    if len(available) >= 2:
        correlation = df[available].corr()

        fig, ax = plt.subplots(figsize=(9, 7))
        sns.heatmap(
            correlation,
            annot=True,
            cmap="coolwarm",
            center=0,
            fmt=".2f",
            ax=ax,
        )
        ax.set_title("Cryptocurrency Market Correlation Matrix")
        save_figure(fig, "correlation_heatmap.png")

    # 6. Stablecoin versus other cryptocurrencies.
    if {"symbol", "volatility_pct"}.issubset(df.columns):
        df["asset_category"] = df["symbol"].isin(
            STABLE_SYMBOLS
        ).map({
            True: "Stablecoins",
            False: "Other cryptocurrencies",
        })

        segment = df.dropna(subset=["volatility_pct"])

        if not segment.empty:
            fig, ax = plt.subplots(figsize=(8, 5))
            sns.boxplot(
                data=segment,
                x="asset_category",
                y="volatility_pct",
                ax=ax,
            )
            ax.set(
                title="Volatility: Stablecoins vs Other Assets",
                xlabel="Asset Category",
                ylabel="Volatility (%)",
            )
            save_figure(fig, "stablecoin_comparison.png")

    # 7. Descriptive statistics report.
    summary_path = save_summary_statistics(df, output)
    if summary_path:
        files.append(str(summary_path))

    # 8. IQR outlier report.
    outlier_path = detect_outliers(df, output)
    files.append(str(outlier_path))

    # 9. Market concentration report.
    concentration_path = analyze_market_concentration(
        df, output
    )
    if concentration_path:
        files.append(str(concentration_path))

    return files


if __name__ == "__main__":
    generated_files = generate_charts()

    print("\nEDA completed successfully.")
    print("\nGenerated files:")

    for file in generated_files:
        print(file)
