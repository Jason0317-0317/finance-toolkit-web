from __future__ import annotations

import os
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from financetoolkit import Toolkit


st.set_page_config(
    page_title="財析台｜FinanceToolkit",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      :root { --ink:#102b28; --green:#0b6b5d; --paper:#f6f7f2; --gold:#dcae46; }
      .stApp { background:var(--paper); color:var(--ink); }
      .block-container { max-width:1180px; padding-top:2.2rem; padding-bottom:4rem; }
      [data-testid="stHeader"] { background:transparent; }
      .hero { padding:2.5rem 0 1.2rem; border-top:1px solid #dfe6de; }
      .eyebrow { color:var(--green); font-size:.75rem; font-weight:800; letter-spacing:.16em; }
      .hero h1 { font-size:clamp(2.7rem,7vw,5.5rem); line-height:1; letter-spacing:-.055em; margin:.7rem 0 1rem; }
      .hero p { color:#566a65; font-size:1.08rem; max-width:700px; line-height:1.75; }
      div[data-testid="stMetric"] { background:white; border:1px solid #dfe6de; padding:1rem; border-radius:16px; }
      div[data-testid="stMetricLabel"] { color:#667a74; }
      .note { border-radius:14px; padding:1rem 1.2rem; background:#fff3d3; color:#765411; font-size:.9rem; }
      .footer { margin-top:3rem; padding-top:1.5rem; border-top:1px solid #dfe6de; color:#6d7e79; font-size:.82rem; }
      .stButton button { background:var(--ink); color:white; border:0; border-radius:12px; min-height:46px; font-weight:700; }
    </style>
    <div class="eyebrow">FINANCIAL ANALYSIS, MADE CLEAR</div>
    <div class="hero">
      <h1>把市場資料，<br>變成清楚的判斷。</h1>
      <p>輸入股票代號，快速檢查價格趨勢、報酬、波動與公開財務比率。分析引擎由開源 FinanceToolkit 提供。</p>
    </div>
    """,
    unsafe_allow_html=True,
)


def get_secret(name: str) -> str:
    value = os.getenv(name, "")
    if value:
        return value
    try:
        return str(st.secrets.get(name, ""))
    except FileNotFoundError:
        return ""


def normalize_tickers(raw: str) -> list[str]:
    values = raw.replace("，", ",").replace(" ", ",").split(",")
    return list(dict.fromkeys(value.strip().upper() for value in values if value.strip()))[:5]


def ticker_candidates(ticker: str) -> list[str]:
    """Expand a plain four-digit Taiwan code without changing explicit symbols."""
    if ticker.isdigit() and len(ticker) == 4:
        return [f"{ticker}.TW", f"{ticker}.TWO"]
    return [ticker]


def ticker_history(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if not isinstance(frame.columns, pd.MultiIndex):
        return frame.copy()
    for level in range(frame.columns.nlevels):
        if ticker in frame.columns.get_level_values(level):
            return frame.xs(ticker, axis=1, level=level).copy()
    raise KeyError(f"找不到 {ticker} 的市場資料")


def find_column(frame: pd.DataFrame, *names: str) -> pd.Series:
    lookup = {str(column).lower(): column for column in frame.columns}
    for name in names:
        if name.lower() in lookup:
            return pd.to_numeric(frame[lookup[name.lower()]], errors="coerce").dropna()
    raise KeyError(f"資料缺少欄位：{', '.join(names)}")


@st.cache_data(ttl=3600, show_spinner=False)
def load_market_data(
    tickers: tuple[str, ...], start_date: str, api_key: str
) -> dict[str, dict[str, object]]:
    """Load each ticker independently so one bad symbol cannot break the batch."""
    results: dict[str, dict[str, object]] = {}
    for requested in tickers:
        errors: list[str] = []
        for candidate in ticker_candidates(requested):
            close = pd.Series(dtype="float64")
            source = "FinanceToolkit"
            try:
                toolkit = Toolkit(
                    tickers=[candidate],
                    api_key=api_key or None,
                    start_date=start_date,
                    benchmark_ticker=None,
                )
                frame = ticker_history(toolkit.get_historical_data(), candidate)
                close = find_column(frame, "Adj Close", "Close")
            except Exception as exc:
                errors.append(f"FinanceToolkit {candidate}: {exc}")

            close = clean_close(close)
            if close.empty:
                source = "Yahoo Finance"
                try:
                    frame = yf.download(
                        candidate,
                        start=start_date,
                        auto_adjust=False,
                        progress=False,
                        threads=False,
                        timeout=12,
                    )
                    if isinstance(frame.columns, pd.MultiIndex):
                        frame = frame.droplevel(-1, axis=1)
                    close = clean_close(find_column(frame, "Adj Close", "Close"))
                except Exception as exc:
                    errors.append(f"Yahoo Finance {candidate}: {exc}")

            if len(close) >= 2:
                results[requested] = {
                    "resolved": candidate,
                    "close": close,
                    "source": source,
                    "error": "",
                }
                break
        else:
            results[requested] = {
                "resolved": requested,
                "close": pd.Series(dtype="float64"),
                "source": "",
                "error": " | ".join(errors[-2:]),
            }
    return results


def clean_close(series: pd.Series) -> pd.Series:
    if series.empty:
        return pd.Series(dtype="float64")
    cleaned = pd.to_numeric(series, errors="coerce").replace([float("inf"), float("-inf")], pd.NA)
    cleaned = cleaned.dropna()
    cleaned = cleaned[cleaned > 0]
    cleaned = cleaned[~cleaned.index.duplicated(keep="last")].sort_index()
    return cleaned.astype("float64")


@st.cache_data(ttl=21600, show_spinner=False)
def load_ratios(tickers: tuple[str, ...], start_date: str, api_key: str) -> dict[str, pd.DataFrame]:
    toolkit = Toolkit(tickers=list(tickers), api_key=api_key, start_date=start_date)
    return {
        "獲利能力": toolkit.ratios.collect_profitability_ratios(),
        "流動性": toolkit.ratios.collect_liquidity_ratios(),
        "償債能力": toolkit.ratios.collect_solvency_ratios(),
        "估值": toolkit.ratios.collect_valuation_ratios(),
    }


with st.form("analysis-form"):
    left, middle, right = st.columns([2.2, 1, 1])
    with left:
        ticker_input = st.text_input(
            "股票代號（最多 5 檔，以逗號分隔）",
            value="AAPL, MSFT",
            help="美股如 AAPL；台股 Yahoo Finance 代號如 2330.TW。",
        )
    with middle:
        years = st.selectbox("回看期間", [1, 3, 5, 10], index=2)
    with right:
        st.write("")
        submitted = st.form_submit_button("開始分析", width="stretch")

tickers = normalize_tickers(ticker_input)
api_key = get_secret("FMP_API_KEY")

if not tickers:
    st.info("請輸入至少一個股票代號。")
    st.stop()

if submitted or "has_run" not in st.session_state:
    st.session_state.has_run = True
    start = (date.today() - timedelta(days=365 * years + 14)).isoformat()
    try:
        with st.spinner("正在取得公開市場資料並計算指標…"):
            market_data = load_market_data(tuple(tickers), start, api_key)
    except Exception as exc:
        st.error("目前無法取得資料。請確認股票代號，或稍後再試。")
        with st.expander("技術資訊"):
            st.code(str(exc))
        st.stop()

    st.subheader("市場概覽")
    metric_columns = st.columns(min(len(tickers), 5))
    histories: dict[str, pd.Series] = {}
    resolved_tickers: list[str] = []
    for index, ticker in enumerate(tickers):
        try:
            result = market_data[ticker]
            close = result["close"]
            if not isinstance(close, pd.Series):
                raise TypeError("價格資料格式錯誤")
            if close.empty:
                raise ValueError(f"{ticker} 沒有可用的價格資料")
            returns = close.pct_change().dropna()
            total_return = close.iloc[-1] / close.iloc[0] - 1 if len(close) > 1 else 0
            annual_volatility = returns.std() * (252**0.5) if len(returns) else 0
            histories[ticker] = close
            resolved = str(result["resolved"])
            resolved_tickers.append(resolved)
            with metric_columns[index]:
                st.metric(ticker, f"{close.iloc[-1]:,.2f}", f"期間報酬 {total_return:+.1%}")
                suffix = f" · 查詢代號 {resolved}" if resolved != ticker else ""
                st.caption(f"年化波動 {annual_volatility:.1%}{suffix}")
        except (KeyError, IndexError, TypeError, ValueError):
            with metric_columns[index]:
                st.metric(ticker, "—")
                st.caption("沒有足夠資料")

    if histories:
        chart = go.Figure()
        for ticker, close in histories.items():
            normalized = close / close.iloc[0] * 100
            chart_dates = (
                normalized.index.to_timestamp()
                if isinstance(normalized.index, pd.PeriodIndex)
                else normalized.index
            )
            chart.add_trace(go.Scatter(x=chart_dates, y=normalized, name=ticker, mode="lines"))
        chart.update_layout(
            height=430,
            margin=dict(l=10, r=10, t=36, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="white",
            title="標準化價格走勢（起點 = 100）",
            yaxis_title="指數化價格",
            hovermode="x unified",
            legend_orientation="h",
        )
        st.plotly_chart(chart, width="stretch")
    else:
        st.warning("查無可用的市場資料，請檢查股票代號後再試。")

    st.subheader("報酬與風險")
    summary_rows = []
    for ticker, close in histories.items():
        returns = close.pct_change().dropna()
        drawdown = close / close.cummax() - 1
        summary_rows.append(
            {
                "股票": ticker,
                "最新價格": close.iloc[-1],
                "期間報酬": close.iloc[-1] / close.iloc[0] - 1,
                "年化波動": returns.std() * (252**0.5),
                "最大回撤": drawdown.min(),
                "最佳單日": returns.max(),
                "最差單日": returns.min(),
            }
        )
    if summary_rows:
        summary = pd.DataFrame(summary_rows).set_index("股票")
        st.dataframe(
            summary.style.format(
                {"最新價格": "{:,.2f}", "期間報酬": "{:+.1%}", "年化波動": "{:.1%}", "最大回撤": "{:.1%}", "最佳單日": "{:+.1%}", "最差單日": "{:+.1%}"}
            ),
            width="stretch",
        )

    st.subheader("財務比率")
    if not api_key:
        st.info("網站管理者尚未設定 Financial Modeling Prep API 金鑰；目前先提供免金鑰的市場走勢與風險分析。")
    else:
        try:
            with st.spinner("正在計算公開財報比率…"):
                ratio_groups = load_ratios(tuple(resolved_tickers), start, api_key)
            tabs = st.tabs(list(ratio_groups))
            for tab, (label, ratio_frame) in zip(tabs, ratio_groups.items()):
                with tab:
                    st.dataframe(ratio_frame, width="stretch")
        except Exception as exc:
            st.warning("財務比率暫時無法載入；市場資料分析仍可正常使用。")
            with st.expander("技術資訊"):
                st.code(str(exc))

st.markdown(
    """
    <div class="note">資料可能延遲、缺漏或因供應商定義而異。本網站僅供研究與資訊整理，不構成投資建議，也不保證任何投資結果。</div>
    <div class="footer">分析引擎：FinanceToolkit（BSD-3-Clause） · 市場與財報資料權利屬原資料提供者所有</div>
    """,
    unsafe_allow_html=True,
)
