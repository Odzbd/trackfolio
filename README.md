# � trackfolio

A premium, high-performance portfolio tracking application built with **Streamlit**, **Plotly**, and **yfinance**. It supports multi-currency assets (Thai Stocks, International Stocks, and Cash) with advanced risk analytics and beautiful dynamic visualizations.

![Premium Dashboard](https://img.shields.io/badge/UI-Premium-blueviolet) ![License](https://img.shields.io/badge/License-MIT-green) ![Python](https://img.shields.io/badge/Python-3.8%2B-blue)

## ✨ Features

- **🚀 Live Dashboard:** Real-time stock price updates via Yahoo Finance API.
- **📊 Advanced Analytics:** 
  - **Win Rate:** Calculated from realized profit/loss transactions.
  - **Profit/Loss (P/L):** Total and period-specific gains.
  - **Risk-Reward Ratio (RRR):** Average Win vs. Average Loss analysis.
  - **Maximum Drawdown (MDD):** Visualizes the largest peak-to-trough decline.
- **📈 Dynamic Performance Chart:** 
  - Segmented green/red line based on baseline performance.
  - Seamless color transitions at intersection points.
  - Area fills for visual clarity.
- **🏦 Cash & Cost Basis History:** Visualize your cash levels vs. invested capital over time.
- **🌐 Dual Currency Support:** Automatic conversion between USD and THB with historical rate repair.
- **🍱 Asset Allocation:** Visual breakdown by asset class and individual symbols.

## 🛠️ Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/smart-portfolio-tracker.git
   cd smart-portfolio-tracker
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   streamlit run app.py
   ```

## 📝 Usage

- **Add Stocks:** Use the sidebar to record BUY transactions.
- **Sell Stocks:** Record SELL transactions to calculate realized P/L and Win Rate.
- **Set Cash:** Track your available cash balance.
- **Timeframes:** Switch between 5D, 1M, YTD, and 1Y to see dynamic analytics.

## 🔒 Security Note

Your data is stored locally in `portfolio_ledger.csv`. This file is ignored by `.gitignore` to ensure your financial details are never uploaded to GitHub.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
