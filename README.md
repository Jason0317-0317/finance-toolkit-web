# 財析台｜FinanceToolkit Web

可公開分享的股票市場與財務分析網站，使用 FinanceToolkit 作為分析引擎。

## 功能

- 一次比較最多 5 檔股票
- 標準化價格趨勢
- 期間報酬、年化波動、最大回撤及單日風險
- 設定 Financial Modeling Prep API 金鑰後顯示獲利、流動性、償債與估值比率
- 支援美股及 Yahoo Finance 可識別的代號，例如台股 `2330.TW`

## 本機啟動

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## 部署至 Streamlit Community Cloud

1. 將此資料夾推送到 GitHub repository。
2. 在 Streamlit Community Cloud 建立 App。
3. Main file path 設為 `finance-toolkit-web/app.py`。
4. Advanced settings → Secrets 加入：

```toml
FMP_API_KEY = "你的金鑰"
```

未設定金鑰時，網站仍能提供市場價格、報酬與風險分析；財務比率頁面會停用。

## 注意

- 真正的 API 金鑰不可提交到 Git。
- FinanceToolkit 採 BSD-3-Clause 授權；本網站保留工具來源說明。
- 公開服務可能受到資料供應商的方案、速率限制及再散布條款約束。
- 本網站僅供研究與資訊整理，不構成投資建議。
