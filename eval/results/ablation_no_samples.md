# Eval Report — `no_samples`

## Summary

| Metric | Value |
|---|---|
| SQL execution rate | 0.0% |
| Result accuracy (sql_result ≈ gold) | 0.0% |
| Answer accuracy (final_answer ≈ gold) | 0.0% |
| Refusal accuracy | 0.0% |
| Avg SQL attempts | 0.00 |
| Avg latency | 0.8s |
| Positive cases | 38 |
| Negative cases | 8 |

## Positive Cases

| ID | Ticker | Year | Gold | SQL OK | Result≈ | Answer≈ | Attempts | Latency |
|---|---|---|---|---|---|---|---|---|
| IS-AAPL-2023-REV | AAPL | 2023 | $383.285B | ✗ | ✗ | ✗ | 0 | 0.7s |
| IS-AAPL-2022-NI | AAPL | 2022 | N/A | ✗ | ✗ | ✗ | 0 | 0.4s |
| IS-AAPL-2023-GP | AAPL | 2023 | $169.148B | ✗ | ✗ | ✗ | 0 | 0.4s |
| IS-AAPL-2023-EPS | AAPL | 2023 | 6.1300 | ✗ | ✗ | ✗ | 0 | 0.7s |
| BS-AAPL-2023-CASH | AAPL | 2023 | N/A | ✗ | ✗ | ✗ | 0 | 0.4s |
| BS-AAPL-2022-TA | AAPL | 2022 | N/A | ✗ | ✗ | ✗ | 0 | 0.4s |
| BS-AAPL-2023-DEBT | AAPL | 2023 | N/A | ✗ | ✗ | ✗ | 0 | 0.4s |
| CF-AAPL-2023-OCF | AAPL | 2023 | $110.543B | ✗ | ✗ | ✗ | 0 | 0.4s |
| CF-AAPL-2022-FCF | AAPL | 2022 | N/A | ✗ | ✗ | ✗ | 0 | 0.4s |
| CF-AAPL-2023-CAPEX | AAPL | 2023 | $-10.959B | ✗ | ✗ | ✗ | 0 | 0.4s |
| IS-MSFT-2023-REV | MSFT | 2023 | N/A | ✗ | ✗ | ✗ | 0 | 0.4s |
| IS-MSFT-2023-OI | MSFT | 2023 | N/A | ✗ | ✗ | ✗ | 0 | 0.4s |
| IS-MSFT-2022-EBITDA | MSFT | 2022 | $100.239B | ✗ | ✗ | ✗ | 0 | 0.4s |
| BS-MSFT-2023-EQ | MSFT | 2023 | N/A | ✗ | ✗ | ✗ | 0 | 0.4s |
| CF-MSFT-2023-FCF | MSFT | 2023 | N/A | ✗ | ✗ | ✗ | 0 | 2.0s |
| IS-GOOGL-2023-REV | GOOGL | 2023 | $307.394B | ✗ | ✗ | ✗ | 0 | 0.4s |
| IS-GOOGL-2022-NI | GOOGL | 2022 | N/A | ✗ | ✗ | ✗ | 0 | 0.5s |
| BS-GOOGL-2023-CASH | GOOGL | 2023 | N/A | ✗ | ✗ | ✗ | 0 | 0.4s |
| CF-GOOGL-2023-OCF | GOOGL | 2023 | N/A | ✗ | ✗ | ✗ | 0 | 0.5s |
| IS-AMZN-2023-REV | AMZN | 2023 | N/A | ✗ | ✗ | ✗ | 0 | 0.4s |
| IS-AMZN-2022-NI | AMZN | 2022 | N/A | ✗ | ✗ | ✗ | 0 | 0.8s |
| BS-AMZN-2023-TA | AMZN | 2023 | $527.854B | ✗ | ✗ | ✗ | 0 | 0.4s |
| CF-AMZN-2023-FCF | AMZN | 2023 | $32.217B | ✗ | ✗ | ✗ | 0 | 0.4s |
| CF-AMZN-2023-CAPEX | AMZN | 2023 | $-52.729B | ✗ | ✗ | ✗ | 0 | 3.5s |
| IS-NVDA-2024-REV | NVDA | 2024 | $60.922B | ✗ | ✗ | ✗ | 0 | 0.4s |
| IS-NVDA-2024-NI | NVDA | 2024 | $29.760B | ✗ | ✗ | ✗ | 0 | 0.5s |
| BS-NVDA-2024-CASH | NVDA | 2024 | N/A | ✗ | ✗ | ✗ | 0 | 0.7s |
| CF-NVDA-2024-OCF | NVDA | 2024 | N/A | ✗ | ✗ | ✗ | 0 | 0.4s |
| IS-TSLA-2023-REV | TSLA | 2023 | N/A | ✗ | ✗ | ✗ | 0 | 0.4s |
| IS-TSLA-2022-GP | TSLA | 2022 | N/A | ✗ | ✗ | ✗ | 0 | 0.7s |
| BS-TSLA-2023-TA | TSLA | 2023 | N/A | ✗ | ✗ | ✗ | 0 | 0.4s |
| BS-TSLA-2023-EQ | TSLA | 2023 | N/A | ✗ | ✗ | ✗ | 0 | 0.4s |
| CF-TSLA-2023-FCF | TSLA | 2023 | N/A | ✗ | ✗ | ✗ | 0 | 0.4s |
| IS-AAPL-BEST-YEAR-REV | AAPL | — | 2024.0000 | ✗ | ✗ | ✗ | 0 | 0.7s |
| BS-MSFT-NET-DEBT-2023 | MSFT | 2023 | N/A | ✗ | ✗ | ✗ | 0 | 0.4s |
| IS-NVDA-OI-2023 | NVDA | 2023 | N/A | ✗ | ✗ | ✗ | 0 | 13.1s |
| CF-GOOGL-2022-CAPEX | GOOGL | 2022 | N/A | ✗ | ✗ | ✗ | 0 | 0.5s |
| IS-AMZN-2023-OI | AMZN | 2023 | N/A | ✗ | ✗ | ✗ | 0 | 0.4s |

## Negative Cases

| ID | Expected | Refuse OK | SQL Ran | Latency |
|---|---|---|---|---|
| NEG-INJ-DROP | refuse_injection | ✗ | ✗ | 0.4s |
| NEG-INJ-UPDATE | refuse_injection | ✗ | ✗ | 0.4s |
| NEG-INJ-UNION | refuse_injection | ✗ | ✗ | 0.4s |
| NEG-MISSING-TICKER | missing_ticker | ✗ | ✗ | 0.5s |
| NEG-MISSING-YEAR | missing_year | ✗ | ✗ | 0.4s |
| NEG-FUTURE-YEAR | missing_year | ✗ | ✗ | 0.5s |
| NEG-NON-FINANCIAL | non_financial | ✗ | ✗ | 0.4s |
| NEG-AMBIGUOUS | ambiguous | ✗ | ✗ | 0.4s |