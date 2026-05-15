# Backtesting — Report Generation

**Source**: QC Docs v2 > Cloud Platform > Backtesting > Report

---

## Overview

Generate comprehensive PDF reports with key statistics, return analysis, asset allocation, drawdown, rolling statistics, leverage, exposure, crisis event performance, and customizable HTML/CSS templates.

---

## Report Key Statistics

| Statistic | Description |
|---|---|
| Runtime Days | Total calendar days in backtest |
| Turnover | Portfolio turnover rate |
| CAGR | Compound Annual Growth Rate |
| Markets | Number of markets traded |
| Trades/day | Average trade frequency |
| Drawdown | Maximum peak-to-trough decline |
| Probabilistic Sharpe Ratio | Probability Sharpe > benchmark |
| Sharpe Ratio | Risk-adjusted return |
| Information Ratio | Active return per unit of tracking error |
| Strategy Capacity | Maximum deployable capital |

---

## Return Chart Types

| Chart | Format |
|---|---|
| Per-trade returns | Distribution histogram |
| Daily returns | Bar chart |
| Monthly returns | Heatmap |
| Annual returns | Bar chart |
| Cumulative returns | Line chart |

---

## Drawdown Analysis

- Shows peak-to-trough decline over time
- Top 5 drawdown periods highlighted
- Key metric for risk assessment in BOUNCE strategy

---

## Rolling Statistics

- **6-month rolling Beta**: Correlation with benchmark
- **12-month rolling Beta**: Longer-term correlation
- **6-month rolling Sharpe**: Short-term risk-adjusted performance
- **12-month rolling Sharpe**: Longer-term risk-adjusted performance

---

## Exposure Sections

- **Leverage time series**: Total portfolio leverage over time
- **Long-short exposure by asset class**: Breakdown of directional exposure

---

## Crisis Event Benchmarks

Reports include strategy performance during historical crisis periods:

| Crisis | Period |
|---|---|
| DotCom Bubble | 2000 |
| 9/11 | 2001 |
| Housing Bubble | 2003 |
| Financial Crisis | 2007–2011 |
| Flash Crash | 2010 |
| Fukushima | 2011 |
| US Credit Downgrade | 2011 |
| ECB Event | 2012 |
| European Debt Crisis | 2014 |
| Market Sell-Off | 2015 |
| Recovery | 2010–2012 |
| New Normal | 2014–2019 |
| COVID-19 | 2020 |
| Post-COVID | 2020–2021 |
| Meme Season | 2021 |
| Ukraine Invasion | 2022–2023 |
| AI Boom | 2022–Present |

---

## Custom Report Templates

Reports can be customized with HTML and CSS templates:

```html
<!-- report.html — Use template keys for dynamic content -->
{{$KPI-SHARPE}}           <!-- Sharpe Ratio value -->
{{$HTML-CRISIS-PLOTS}}    <!-- Crisis event charts -->
{{$PARAMETERS}}           <!-- Algorithm parameters -->
{{$TEXT-CRISIS-TITLE}}    <!-- Crisis section heading -->
{{$PLOT-CRISIS-CONTENT}}  <!-- Individual crisis chart -->
{{$KEY0}}, {{$VALUE0}}    <!-- Parameter key-value pairs -->
```

```css
/* report.css — Override default styling */
/* Place in project root alongside algorithm code */
```

---

## References

- QC Docs: Cloud Platform > Backtesting > Report
- `.github/skills/backtesting/backtesting_results_analysis.md` — live results UI
