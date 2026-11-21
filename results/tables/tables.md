# Result tables

## Overall comparison (test seeds, mean and 95% CI; violations in %)

| group               | policy                                     | setting        |   isvr |   isvr_ci95 |   rsvr |   rsvr_ci95 |     cost |   cost_ci95 |   carbon |   carbon_ci95 |   p99_ttft_ms |   scaling_changes |   p_isvr |   p_carbon |
|:--------------------|:-------------------------------------------|:---------------|-------:|------------:|-------:|------------:|---------:|------------:|---------:|--------------:|--------------:|------------------:|---------:|-----------:|
| hysteresis-equipped | SLA-Guarded (alpha=0.5)                    | rel0.75, m=2   |  4.49  |       0.287 |  9.684 |       0.821 | 1154.8   |      18.336 |    0.475 |         0.006 |       1441.25 |             447.4 |  nan     |    nan     |
| hysteresis-equipped | SLA-Guarded (alpha=0)                      | rel0.75, m=1.5 |  2.792 |       0.182 |  9.585 |       0.593 |  273.732 |      16.852 |    1.351 |         0.026 |       1214.85 |             103.4 |    0.002 |      0.002 |
| hysteresis-equipped | SLA-Guarded (alpha=1)                      | rel0.75, m=2   |  4.844 |       0.285 |  9.636 |       0.798 | 1377.27  |      21.39  |    0.694 |         0.014 |       1489.45 |             624.7 |    0.004 |      0.002 |
| hysteresis-equipped | Spreading variant (inverse-weight routing) | rel0.5, m=2    |  4.455 |       0.273 |  9.651 |       0.815 | 1337.31  |      14.474 |    1.5   |         0.016 |       1421.73 |            1820   |    0.77  |      0.002 |
| hysteresis-equipped | LatencyFirst+H                             | rel0.75, m=2.5 |  4.358 |       0.223 |  8.548 |       0.7   | 3277.35  |      42.346 |    3.484 |         0.044 |       1429.07 |             730.5 |    0.268 |      0.002 |
| hysteresis-equipped | CostFirst+H                                | rel0.75, m=1.5 |  4.257 |       0.212 | 12.37  |       0.725 |  248.311 |       3.566 |    1.249 |         0.019 |       1405.75 |             158.3 |    0.107 |      0.002 |
| hysteresis-equipped | CarbonFirst+H                              | rel0.75, m=2.5 |  8.885 |       0.276 |  8.367 |       0.471 | 1394.19  |      19.891 |    0.543 |         0.006 |       2015.98 |            1290   |    0.002 |      0.002 |
| hysteresis-equipped | RoundRobin+H                               | rel0.75, m=1.5 |  4.917 |       0.321 |  9.864 |       0.73  | 1468.73  |      16.528 |    1.673 |         0.019 |       1458.48 |             452.1 |    0.008 |      0.002 |
| own capacity rule   | LatencyFirst                               | -              | 55.913 |       0.6   | 52.893 |       0.624 | 1537.18  |      14.279 |    1.632 |         0.016 |       8123.41 |            5482.3 |    0.002 |      0.002 |
| own capacity rule   | CostFirst                                  | -              | 30.344 |       0.352 | 45.962 |       0.822 |  183.374 |       1.613 |    0.904 |         0.009 |       4830.32 |            2768.1 |    0.002 |      0.002 |
| own capacity rule   | CarbonFirst                                | -              | 58.344 |       0.345 | 52.457 |       0.513 |  641.282 |       5.92  |    0.237 |         0.003 |       8503.32 |            5640.8 |    0.002 |      0.002 |
| own capacity rule   | RoundRobin                                 | -              | 34.073 |       0.366 | 40.958 |       0.851 | 1036.72  |       9.446 |    1.178 |         0.011 |       5000.57 |           10666   |    0.002 |      0.002 |
| own capacity rule   | QLM_style                                  | -              | 30.344 |       0.352 | 45.962 |       0.822 |  183.374 |       1.613 |    0.904 |         0.009 |       4830.32 |            2768.1 |    0.002 |      0.002 |
| own capacity rule   | SOLA_style                                 | -              | 33.458 |       0.281 | 46.59  |       0.739 | 1530.91  |      14.423 |    1.591 |         0.015 |       5275.17 |            3407.5 |    0.002 |      0.002 |
| own capacity rule   | ThresholdBased                             | -              | 75.51  |       0.451 | 50.615 |       0.579 |  540.061 |       7.651 |    0.339 |         0.01  |      10938.5  |            4053.4 |    0.002 |      0.002 |
| own capacity rule   | HPA_Stab                                   | -              | 25.181 |       3.49  |  8.282 |       0.598 |  917.526 |      81.808 |    0.698 |         0.114 |       3819.74 |             494.5 |    0.002 |      0.002 |
| own capacity rule   | CarbonAdvisor_Style                        | -              | 86.365 |       0.459 | 59.664 |       0.48  |  586.584 |       5.716 |    0.2   |         0.003 |      12324.3  |            5554.1 |    0.002 |      0.002 |

## Pareto dominance in (interval violation, cost, carbon) over the 12 hysteresis/margin settings of each baseline vs the settings of SLA-Guarded at the listed alpha values

| sla_guarded_alphas   | policy                                     |   settings |   dominated_by_SLA_Guarded |   SLA_Guarded_settings_dominated |
|:---------------------|:-------------------------------------------|-----------:|---------------------------:|---------------------------------:|
| 0,0.5                | Spreading variant (inverse-weight routing) |         12 |                         12 |                                0 |
| 0,0.5                | CostFirst+H                                |         12 |                          2 |                                4 |
| 0,0.5                | RoundRobin+H                               |         12 |                         12 |                                0 |
| 0,0.5                | CarbonFirst+H                              |         12 |                         11 |                                0 |
| 0,0.5                | LatencyFirst+H                             |         12 |                         12 |                                0 |
| 0,0.5,1              | Spreading variant (inverse-weight routing) |         12 |                         12 |                                0 |
| 0,0.5,1              | CostFirst+H                                |         12 |                          2 |                                4 |
| 0,0.5,1              | RoundRobin+H                               |         12 |                         12 |                                0 |
| 0,0.5,1              | CarbonFirst+H                              |         12 |                         11 |                                1 |
| 0,0.5,1              | LatencyFirst+H                             |         12 |                         12 |                                0 |

## Ablation study (alpha=0.5)

| variant                                 |   isvr |   isvr_ci95 |   rsvr |   rsvr_ci95 |     cost |   cost_ci95 |   carbon |   carbon_ci95 |   p99_ttft_ms |   scaling_changes |   p_isvr |   p_carbon |
|:----------------------------------------|-------:|------------:|-------:|------------:|---------:|------------:|---------:|--------------:|--------------:|------------------:|---------:|-----------:|
| SLA-Guarded (alpha=0.5)                 |  4.49  |       0.287 |  9.684 |       0.821 | 1154.8   |      18.336 |    0.475 |         0.006 |       1441.25 |             447.4 |  nan     |    nan     |
| w/o guardrail                           | 17.024 |       0.798 | 24.931 |       1     |  761.587 |      13.806 |    0.3   |         0.007 |       3084.71 |             349.5 |    0.002 |      0.002 |
| w/o prediction                          |  4.583 |       0.256 |  9.85  |       0.78  | 1143.6   |      14.882 |    0.472 |         0.007 |       1450.69 |             452.8 |    0.004 |      0.01  |
| w/o hysteresis                          | 26.222 |       0.259 | 34.395 |       0.781 |  801.082 |       7.527 |    0.31  |         0.003 |       4326    |            4477.7 |    0.002 |      0.002 |
| w/o safety margin (m=1)                 | 13.896 |       0.479 | 23.651 |       0.819 |  770.108 |      14.492 |    0.319 |         0.004 |       2689.28 |             271.8 |    0.002 |      0.002 |
| w/o cold-start-aware switching          |  4.896 |       0.264 | 10.208 |       0.761 | 1150     |      17.954 |    0.474 |         0.007 |       1495.27 |             459.6 |    0.002 |      0.014 |
| with spreading (inverse-weight routing) |  1.34  |       0.177 |  3.589 |       0.572 | 1775.01  |      19.357 |    2.011 |         0.024 |       1015.21 |             269.3 |    0.002 |      0.002 |

## Effect of the cost-carbon weight alpha

|   alpha | setting        |   isvr |   isvr_ci95 |   rsvr |     cost |   carbon |   scaling_changes |
|--------:|:---------------|-------:|------------:|-------:|---------:|---------:|------------------:|
|    0    | rel0.75, m=1.5 |  2.792 |       0.182 |  9.585 |  273.732 |    1.351 |             103.4 |
|    0.25 | rel0.75, m=2   |  1.205 |       0.134 |  5.001 |  367.433 |    1.679 |             124.9 |
|    0.5  | rel0.75, m=2   |  4.49  |       0.287 |  9.684 | 1154.8   |    0.475 |             447.4 |
|    0.75 | rel0.75, m=2   |  4.372 |       0.305 |  9.482 | 1157.28  |    0.47  |             419   |
|    1    | rel0.75, m=2   |  4.844 |       0.285 |  9.636 | 1377.27  |    0.694 |             624.7 |

## Cost and carbon per SLO-compliant request

| policy                                     |   rsvr |   usd_per_1k_compliant_req |   g_co2e_per_compliant_req |
|:-------------------------------------------|-------:|---------------------------:|---------------------------:|
| SLA-Guarded (alpha=0.5)                    |  9.684 |                      0.435 |                      0.179 |
| SLA-Guarded (alpha=0)                      |  9.585 |                      0.103 |                      0.508 |
| Spreading variant (inverse-weight routing) |  9.651 |                      0.504 |                      0.565 |
| CostFirst+H                                | 12.37  |                      0.096 |                      0.485 |
| RoundRobin+H                               |  9.864 |                      0.554 |                      0.631 |
| CarbonFirst+H                              |  8.367 |                      0.518 |                      0.202 |
| LatencyFirst+H                             |  8.548 |                      1.219 |                      1.296 |
| HPA_Stab                                   |  8.282 |                      0.34  |                      0.259 |
| SOLA_style                                 | 46.59  |                      0.975 |                      1.013 |
| CarbonAdvisor_Style                        | 59.664 |                      0.495 |                      0.169 |

## Interval SLO violation (%) vs cold-start delay

| policy                                     |   0 s |   30 s |   60 s |   120 s |   240 s |
|:-------------------------------------------|------:|-------:|-------:|--------:|--------:|
| CarbonFirst+H                              |  0    |   8.06 |   8.89 |   10.26 |   12.46 |
| CostFirst                                  |  0    |  22.52 |  30.34 |   40.12 |   49.82 |
| CostFirst+H                                |  1.56 |   4.02 |   4.26 |    4.59 |    5.27 |
| HPA_Stab                                   | 24.5  |  24.62 |  25.18 |   26.23 |   28.24 |
| LatencyFirst                               |  0    |  45.16 |  55.91 |   66.53 |   76.24 |
| LatencyFirst+H                             |  0    |   4.06 |   4.36 |    4.86 |    5.83 |
| RoundRobin+H                               |  2.57 |   4.7  |   4.92 |    5.28 |    5.85 |
| SLA-Guarded (alpha=0)                      |  1.06 |   2.65 |   2.79 |    2.99 |    3.35 |
| SLA-Guarded (alpha=0.5)                    |  0    |   4.2  |   4.49 |    4.93 |    5.53 |
| SOLA_style                                 |  0    |  25.29 |  33.46 |   43.21 |   53.2  |
| Spreading variant (inverse-weight routing) |  0    |   4    |   4.45 |    5.16 |    6.33 |

## Interval violation (%) / cost (USD) under alternative cold-start models (ln60/ln120: log-normal start-up, mean 60/120 s; sd2: delayed scale-down; bill_ready: billed when ready)

| policy                                     | fixed 60 s   | ln60        | ln120       | sd2         | bill_ready   |
|:-------------------------------------------|:-------------|:------------|:------------|:------------|:-------------|
| SLA-Guarded (alpha=0.5)                    | 4.5 / 1,155  | 4.4 / 1,155 | 4.8 / 1,155 | 1.9 / 1,510 | 4.5 / 1,108  |
| Spreading variant (inverse-weight routing) | 4.5 / 1,337  | 4.4 / 1,337 | 5.1 / 1,337 | 1.7 / 1,661 | 4.5 / 1,256  |
| CostFirst+H                                | 4.3 / 248    | 4.2 / 248   | 4.4 / 248   | 1.6 / 328   | 4.3 / 241    |
| RoundRobin+H                               | 4.9 / 1,469  | 5.0 / 1,469 | 5.2 / 1,469 | 2.0 / 1,944 | 4.9 / 1,434  |

## Partial rank correlation coefficients (* p < 0.01)

| parameter                       | isvr   | cost   | carbon   |
|:--------------------------------|:-------|:-------|:---------|
| hysteresis band h_lo [0.3, 1.0] | -0.75* | +0.43* | +0.47*   |
| safety margin m [1.2, 3.0]      | -0.58* | +0.36* | +0.42*   |
| RTT budget [5, 80] ms           | -0.35* | -0.40* | -0.57*   |
| alpha [0, 1]                    | +0.02  | +0.65* | -0.74*   |
| churn penalty eta [0, 0.1]      | -0.07  | +0.02  | -0.04    |
| cold-start delay [0, 240] s     | +0.48* | +0.12  | +0.07    |
| horizon H [1, 32]               | +0.05  | +0.08  | -0.08    |
| U_max [0.80, 0.95]              | +0.01  | -0.02  | +0.02    |

## Mean interval violation (%) by safety margin (rows) and hysteresis band h_lo (columns)

| margin_bin   |   (0.299, 0.53] |   (0.53, 0.77] |   (0.77, 1.0] |
|:-------------|----------------:|---------------:|--------------:|
| (1.199, 1.8] |            18.6 |            7.7 |           1.8 |
| (1.8, 2.4]   |             9.3 |            3.8 |           1.2 |
| (2.4, 3.0]   |             5.1 |            2.7 |           0.7 |

## Joint sensitivity summary

|   samples |   median_isvr |   share_meeting_5pct |   r2_main_effects |   r2_with_interactions |
|----------:|--------------:|---------------------:|------------------:|-----------------------:|
|       300 |         2.448 |               65.333 |              0.53 |                  0.829 |

## Analytic M/M/k vs discrete-event p99 waiting time (s)

|   k |   rho | service                | arrivals   |   analytic_p99_wait |   des_p99_wait |   analytic_p_wait |   des_p_wait |   des_over_analytic |
|----:|------:|:-----------------------|:-----------|--------------------:|---------------:|------------------:|-------------:|--------------------:|
|  10 |  0.5  | exp                    | poisson    |               1.306 |          1.299 |             0.036 |        0.036 |               0.995 |
|  10 |  0.5  | lognormal_tokens       | poisson    |               1.306 |          1.029 |             0.036 |        0.035 |               0.788 |
|  10 |  0.5  | lognormal_tokens_heavy | poisson    |               1.306 |          3.98  |             0.036 |        0.128 |               3.048 |
|  10 |  0.5  | lognormal_tokens       | bursty5s   |               1.306 |          3.857 |             0.036 |        0.128 |               2.954 |
|  10 |  0.7  | exp                    | poisson    |               5.253 |          4.979 |             0.222 |        0.225 |               0.948 |
|  10 |  0.7  | lognormal_tokens       | poisson    |               5.253 |          3.648 |             0.222 |        0.211 |               0.694 |
|  10 |  0.7  | lognormal_tokens_heavy | poisson    |               5.253 |         22.006 |             0.222 |        0.591 |               4.189 |
|  10 |  0.7  | lognormal_tokens       | bursty5s   |               5.253 |         12.691 |             0.222 |        0.391 |               2.416 |
|  10 |  0.8  | exp                    | poisson    |               9.438 |          8.939 |             0.409 |        0.417 |               0.947 |
|  10 |  0.8  | lognormal_tokens       | poisson    |               9.438 |          6.325 |             0.409 |        0.388 |               0.67  |
|  10 |  0.8  | lognormal_tokens_heavy | poisson    |               9.438 |        455.374 |             0.409 |        0.993 |              48.249 |
|  10 |  0.8  | lognormal_tokens       | bursty5s   |               9.438 |         21.114 |             0.409 |        0.567 |               2.237 |
|  10 |  0.9  | exp                    | poisson    |              21.374 |         21.408 |             0.669 |        0.678 |               1.002 |
|  10 |  0.9  | lognormal_tokens       | poisson    |              21.374 |         12.973 |             0.669 |        0.642 |               0.607 |
|  10 |  0.9  | lognormal_tokens_heavy | poisson    |              21.374 |      13704.7   |             0.669 |        1     |             641.178 |
|  10 |  0.9  | lognormal_tokens       | bursty5s   |              21.374 |         36.971 |             0.669 |        0.768 |               1.73  |
|  10 |  0.95 | exp                    | poisson    |              44.892 |         61.842 |             0.826 |        0.837 |               1.378 |
|  10 |  0.95 | lognormal_tokens       | poisson    |              44.892 |         25.158 |             0.826 |        0.798 |               0.56  |
|  10 |  0.95 | lognormal_tokens_heavy | poisson    |              44.892 |      19592     |             0.826 |        1     |             436.428 |
|  10 |  0.95 | lognormal_tokens       | bursty5s   |              44.892 |         79.659 |             0.826 |        0.869 |               1.774 |
|  50 |  0.5  | exp                    | poisson    |               0     |          0     |             0     |        0     |             nan     |
|  50 |  0.5  | lognormal_tokens       | poisson    |               0     |          0     |             0     |        0     |             nan     |
|  50 |  0.5  | lognormal_tokens_heavy | poisson    |               0     |          0     |             0     |        0.001 |             nan     |
|  50 |  0.5  | lognormal_tokens       | bursty5s   |               0     |          2.776 |             0     |        0.06  |             nan     |
|  50 |  0.7  | exp                    | poisson    |               0.033 |          0.014 |             0.011 |        0.01  |               0.414 |
|  50 |  0.7  | lognormal_tokens       | poisson    |               0.033 |          0     |             0.011 |        0.01  |               0     |
|  50 |  0.7  | lognormal_tokens_heavy | poisson    |               0.033 |          2.988 |             0.011 |        0.263 |              90.299 |
|  50 |  0.7  | lognormal_tokens       | bursty5s   |               0.033 |          6.993 |             0.011 |        0.272 |             211.365 |
|  50 |  0.8  | exp                    | poisson    |               1.1   |          1.058 |             0.087 |        0.087 |               0.962 |
|  50 |  0.8  | lognormal_tokens       | poisson    |               1.1   |          0.725 |             0.087 |        0.077 |               0.659 |
|  50 |  0.8  | lognormal_tokens_heavy | poisson    |               1.1   |         90.492 |             0.087 |        0.983 |              82.271 |
|  50 |  0.8  | lognormal_tokens       | bursty5s   |               1.1   |         20.321 |             0.087 |        0.489 |              18.474 |
|  50 |  0.9  | exp                    | poisson    |               3.656 |          3.541 |             0.364 |        0.376 |               0.969 |
|  50 |  0.9  | lognormal_tokens       | poisson    |               3.656 |          2.199 |             0.364 |        0.334 |               0.601 |
|  50 |  0.9  | lognormal_tokens_heavy | poisson    |               3.656 |       2739.42  |             0.364 |        1     |             749.334 |
|  50 |  0.9  | lognormal_tokens       | bursty5s   |               3.656 |         28.307 |             0.364 |        0.719 |               7.743 |
|  50 |  0.95 | exp                    | poisson    |               8.425 |         11.855 |             0.629 |        0.657 |               1.407 |
|  50 |  0.95 | lognormal_tokens       | poisson    |               8.425 |          4.708 |             0.629 |        0.58  |               0.559 |
|  50 |  0.95 | lognormal_tokens_heavy | poisson    |               8.425 |       3915.98  |             0.629 |        1     |             464.784 |
|  50 |  0.95 | lognormal_tokens       | bursty5s   |               8.425 |         60.511 |             0.629 |        0.852 |               7.182 |
| 200 |  0.5  | exp                    | poisson    |               0     |          0     |             0     |        0     |             nan     |
| 200 |  0.5  | lognormal_tokens       | poisson    |               0     |          0     |             0     |        0     |             nan     |
| 200 |  0.5  | lognormal_tokens_heavy | poisson    |               0     |          0     |             0     |        0     |             nan     |
| 200 |  0.5  | lognormal_tokens       | bursty5s   |               0     |          2.588 |             0     |        0.058 |             nan     |
| 200 |  0.7  | exp                    | poisson    |               0     |          0     |             0     |        0     |             nan     |
| 200 |  0.7  | lognormal_tokens       | poisson    |               0     |          0     |             0     |        0     |             nan     |
| 200 |  0.7  | lognormal_tokens_heavy | poisson    |               0     |          0.211 |             0     |        0.037 |             nan     |
| 200 |  0.7  | lognormal_tokens       | bursty5s   |               0     |          7.984 |             0     |        0.27  |             nan     |
| 200 |  0.8  | exp                    | poisson    |               0     |          0     |             0.001 |        0.002 |             nan     |
| 200 |  0.8  | lognormal_tokens       | poisson    |               0     |          0     |             0.001 |        0     |             nan     |
| 200 |  0.8  | lognormal_tokens_heavy | poisson    |               0     |         21.929 |             0.001 |        0.963 |             nan     |
| 200 |  0.8  | lognormal_tokens       | bursty5s   |               0     |         11.212 |             0.001 |        0.439 |             nan     |
| 200 |  0.9  | exp                    | poisson    |               0.571 |          0.657 |             0.094 |        0.111 |               1.151 |
| 200 |  0.9  | lognormal_tokens       | poisson    |               0.571 |          0.314 |             0.094 |        0.077 |               0.55  |
| 200 |  0.9  | lognormal_tokens_heavy | poisson    |               0.571 |        683.989 |             0.094 |        1     |            1197.77  |
| 200 |  0.9  | lognormal_tokens       | bursty5s   |               0.571 |         26.277 |             0.094 |        0.702 |              46.016 |
| 200 |  0.95 | exp                    | poisson    |               1.83  |          2.83  |             0.365 |        0.403 |               1.546 |
| 200 |  0.95 | lognormal_tokens       | poisson    |               1.83  |          0.959 |             0.365 |        0.31  |               0.524 |
| 200 |  0.95 | lognormal_tokens_heavy | poisson    |               1.83  |        977.923 |             0.365 |        1     |             534.426 |
| 200 |  0.95 | lognormal_tokens       | bursty5s   |               1.83  |         43.531 |             0.365 |        0.872 |              23.79  |

## DES p99 TTFT (s) at the capacity chosen by the analytic guardrail

|   lam |   k_analytic | service          | arrivals   |   des_p99_ttft_at_k_analytic |   k_des_min |
|------:|-------------:|:-----------------|:-----------|-----------------------------:|------------:|
|     2 |           16 | lognormal_tokens | poisson    |                        1.991 |          15 |
|     2 |           16 | lognormal_tokens | bursty5s   |                        8.303 |          16 |
|     5 |           32 | lognormal_tokens | poisson    |                        2.198 |          31 |
|     5 |           32 | lognormal_tokens | bursty5s   |                       19.568 |          32 |
|    10 |           59 | lognormal_tokens | poisson    |                        1.944 |          56 |
|    10 |           59 | lognormal_tokens | bursty5s   |                       21.171 |          59 |
|    20 |          110 | lognormal_tokens | poisson    |                        1.912 |         106 |
|    20 |          110 | lognormal_tokens | bursty5s   |                       46.971 |         110 |
|    40 |          213 | lognormal_tokens | poisson    |                        1.64  |         206 |
|    40 |          213 | lognormal_tokens | bursty5s   |                       24.21  |         213 |
|    80 |          417 | lognormal_tokens | poisson    |                        1.46  |         408 |
|    80 |          417 | lognormal_tokens | bursty5s   |                       48.98  |         417 |

## Capacity needed under within-interval bursts relative to the analytic guardrail

|   lam |   k_analytic |   k_needed_bursty |   ratio |
|------:|-------------:|------------------:|--------:|
|     5 |           32 |                57 |   1.781 |
|    10 |           59 |               102 |   1.729 |
|    20 |          110 |               221 |   2.009 |
|    40 |          213 |               378 |   1.775 |

## 2024 one-week traces (mean over 7 daily windows; violations in %; cost USD and carbon t per day)

| trace      |   scale | policy_label                               |   isvr |   rsvr |     cost |   carbon |   mean_rate |
|:-----------|--------:|:-------------------------------------------|-------:|-------:|---------:|---------:|------------:|
| code_1week |       1 | SLA-Guarded (alpha=0.5)                    |  0.015 |  0.027 |  187.535 |    0.145 |      27.829 |
| code_1week |       1 | SLA-Guarded (alpha=0)                      |  1.582 |  2.134 |   52.021 |    0.208 |      27.829 |
| code_1week |       1 | Spreading variant (inverse-weight routing) |  0     |  0     |  233.283 |    0.264 |      27.829 |
| code_1week |       1 | LatencyFirst+H                             |  0     |  0     |  408.834 |    0.439 |      27.829 |
| code_1week |       1 | CostFirst+H                                |  1.473 |  1.583 |   49.726 |    0.197 |      27.829 |
| code_1week |       1 | RoundRobin+H                               |  2.884 |  0.697 |  197.568 |    0.227 |      27.829 |
| code_1week |       1 | CarbonFirst+H                              |  2.06  |  0.511 |  242.628 |    0.121 |      27.829 |
| code_1week |       1 | LatencyFirst                               |  0.363 |  0.038 |  248.467 |    0.26  |      27.829 |
| code_1week |       1 | CostFirst                                  |  0.367 |  0.07  |   46.532 |    0.175 |      27.829 |
| code_1week |       1 | SOLA_style                                 |  0.363 |  0.067 |  246.485 |    0.25  |      27.829 |
| code_1week |       1 | HPA_Stab                                   | 58.329 |  1.06  |   58.794 |    0.148 |      27.829 |
| code_1week |       2 | SLA-Guarded (alpha=0.5)                    |  0.035 |  0.018 |  333.362 |    0.243 |      55.658 |
| code_1week |       2 | SLA-Guarded (alpha=0)                      |  1.479 |  2.388 |   85.472 |    0.386 |      55.658 |
| code_1week |       2 | Spreading variant (inverse-weight routing) |  0     |  0     |  424.536 |    0.478 |      55.658 |
| code_1week |       2 | LatencyFirst+H                             |  0     |  0     |  761.126 |    0.817 |      55.658 |
| code_1week |       2 | CostFirst+H                                |  2.246 |  3.19  |   80.352 |    0.36  |      55.658 |
| code_1week |       2 | RoundRobin+H                               |  4.077 |  1.743 |  356.553 |    0.41  |      55.658 |
| code_1week |       2 | CarbonFirst+H                              |  3.408 |  0.755 |  416.805 |    0.174 |      55.658 |
| code_1week |       2 | LatencyFirst                               |  0.845 |  0.164 |  468.908 |    0.489 |      55.658 |
| code_1week |       2 | CostFirst                                  |  0.77  |  0.258 |   75.97  |    0.328 |      55.658 |
| code_1week |       2 | SOLA_style                                 |  0.839 |  0.252 |  469.821 |    0.476 |      55.658 |
| code_1week |       2 | HPA_Stab                                   | 19.583 |  0.247 |  115.16  |    0.282 |      55.658 |
| conv_1week |       1 | SLA-Guarded (alpha=0.5)                    |  0.055 |  0.041 |  435.048 |    0.331 |      45.167 |
| conv_1week |       1 | SLA-Guarded (alpha=0)                      |  3.276 |  2.195 |  105.89  |    0.494 |      45.167 |
| conv_1week |       1 | Spreading variant (inverse-weight routing) |  0     |  0     |  599.054 |    0.672 |      45.167 |
| conv_1week |       1 | LatencyFirst+H                             |  0     |  0     | 1187.31  |    1.264 |      45.167 |
| conv_1week |       1 | CostFirst+H                                |  3.276 |  2.195 |  105.89  |    0.494 |      45.167 |
| conv_1week |       1 | RoundRobin+H                               |  4.961 |  0.816 |  539.054 |    0.614 |      45.167 |
| conv_1week |       1 | CarbonFirst+H                              |  5.998 |  0.951 |  561.294 |    0.241 |      45.167 |
| conv_1week |       1 | LatencyFirst                               |  0.04  |  0.011 |  836.59  |    0.885 |      45.167 |
| conv_1week |       1 | CostFirst                                  |  0.025 |  0.016 |  111.404 |    0.52  |      45.167 |
| conv_1week |       1 | SOLA_style                                 |  0.025 |  0.017 |  833.185 |    0.855 |      45.167 |
| conv_1week |       1 | HPA_Stab                                   | 31.628 |  0.289 |  592.861 |    0.663 |      45.167 |
| conv_1week |       2 | SLA-Guarded (alpha=0.5)                    |  0.1   |  0.059 |  827.975 |    0.56  |      90.333 |
| conv_1week |       2 | SLA-Guarded (alpha=0)                      |  3.945 |  3.503 |  192.857 |    0.955 |      90.333 |
| conv_1week |       2 | Spreading variant (inverse-weight routing) |  0     |  0     | 1131.31  |    1.276 |      90.333 |
| conv_1week |       2 | LatencyFirst+H                             |  0     |  0     | 2282.81  |    2.427 |      90.333 |
| conv_1week |       2 | CostFirst+H                                |  3.945 |  3.503 |  192.857 |    0.955 |      90.333 |
| conv_1week |       2 | RoundRobin+H                               |  4.074 |  1.552 | 1025.14  |    1.169 |      90.333 |
| conv_1week |       2 | CarbonFirst+H                              |  6.608 |  1.097 | 1049.75  |    0.406 |      90.333 |
| conv_1week |       2 | LatencyFirst                               |  0.091 |  0.029 | 1622.84  |    1.714 |      90.333 |
| conv_1week |       2 | CostFirst                                  |  0.046 |  0.025 |  204.293 |    1.01  |      90.333 |
| conv_1week |       2 | SOLA_style                                 |  0.046 |  0.03  | 1630.29  |    1.672 |      90.333 |
| conv_1week |       2 | HPA_Stab                                   | 21.988 |  0.079 | 1181.77  |    1.302 |      90.333 |

## 2023 one-hour traces (10 seeds; transient start and 10 min preconditioning)

| trace   | protocol       | policy_label                               |   isvr |   rsvr |   cost |   carbon |   mean_rate |
|:--------|:---------------|:-------------------------------------------|-------:|-------:|-------:|---------:|------------:|
| code    | preconditioned | SLA-Guarded (alpha=0.5)                    |  0     |  0.001 |  3.252 |    0.002 |       2.556 |
| code    | preconditioned | SLA-Guarded (alpha=0)                      |  1.739 |  6.272 |  1.318 |    0.003 |       2.556 |
| code    | preconditioned | Spreading variant (inverse-weight routing) |  0     |  0     |  3.933 |    0.004 |       2.556 |
| code    | preconditioned | LatencyFirst+H                             |  6.87  | 15.451 |  4.834 |    0.005 |       2.556 |
| code    | preconditioned | CostFirst+H                                | 15.652 | 41.945 |  1.068 |    0.002 |       2.556 |
| code    | preconditioned | RoundRobin+H                               |  0     |  0.033 |  3.248 |    0.003 |       2.556 |
| code    | preconditioned | CarbonFirst+H                              |  6     | 16.259 |  3.839 |    0.003 |       2.556 |
| code    | preconditioned | LatencyFirst                               | 36.261 | 54.567 |  2.158 |    0.002 |       2.556 |
| code    | preconditioned | CostFirst                                  | 36.522 | 60.697 |  0.977 |    0.002 |       2.556 |
| code    | preconditioned | SOLA_style                                 | 37.478 | 44.477 |  1.988 |    0.002 |       2.556 |
| code    | preconditioned | HPA_Stab                                   | 18.783 | 13.723 |  1.589 |    0.001 |       2.556 |
| code    | transient      | SLA-Guarded (alpha=0.5)                    |  3.478 |  5.63  |  3.124 |    0.002 |       2.556 |
| code    | transient      | SLA-Guarded (alpha=0)                      |  5.217 | 12.896 |  1.303 |    0.003 |       2.556 |
| code    | transient      | Spreading variant (inverse-weight routing) |  3.478 |  2.58  |  3.797 |    0.004 |       2.556 |
| code    | transient      | LatencyFirst+H                             |  9.13  | 17.89  |  4.8   |    0.005 |       2.556 |
| code    | transient      | CostFirst+H                                | 17.391 | 42.549 |  1.062 |    0.002 |       2.556 |
| code    | transient      | RoundRobin+H                               |  4.348 |  3.958 |  3.145 |    0.003 |       2.556 |
| code    | transient      | CarbonFirst+H                              |  7.217 | 17.108 |  3.558 |    0.003 |       2.556 |
| code    | transient      | LatencyFirst                               | 37.739 | 55.609 |  2.155 |    0.002 |       2.556 |
| code    | transient      | CostFirst                                  | 37.391 | 61.253 |  0.977 |    0.002 |       2.556 |
| code    | transient      | SOLA_style                                 | 39.13  | 44.538 |  1.979 |    0.002 |       2.556 |
| code    | transient      | HPA_Stab                                   | 25.043 | 20.858 |  1.473 |    0.001 |       2.556 |
| conv    | preconditioned | SLA-Guarded (alpha=0.5)                    |  0     |  0.001 |  5.925 |    0.004 |       5.471 |
| conv    | preconditioned | SLA-Guarded (alpha=0)                      |  6.78  |  2.567 |  1.954 |    0.006 |       5.471 |
| conv    | preconditioned | Spreading variant (inverse-weight routing) |  0     |  0     |  9.151 |    0.01  |       5.471 |
| conv    | preconditioned | LatencyFirst+H                             |  0     |  0     | 15.795 |    0.016 |       5.471 |
| conv    | preconditioned | CostFirst+H                                |  6.78  |  2.567 |  1.95  |    0.006 |       5.471 |
| conv    | preconditioned | RoundRobin+H                               |  9.915 |  0.271 |  7.58  |    0.008 |       5.471 |
| conv    | preconditioned | CarbonFirst+H                              |  5     |  0.244 |  8.737 |    0.005 |       5.471 |
| conv    | preconditioned | LatencyFirst                               |  2.119 |  1.034 | 11.337 |    0.011 |       5.471 |
| conv    | preconditioned | CostFirst                                  |  1.695 |  1.219 |  1.948 |    0.006 |       5.471 |
| conv    | preconditioned | SOLA_style                                 |  2.542 |  1.339 | 10.769 |    0.01  |       5.471 |
| conv    | preconditioned | HPA_Stab                                   | 98.983 | 11.144 |  3.53  |    0.005 |       5.471 |
| conv    | transient      | SLA-Guarded (alpha=0.5)                    |  2.881 |  1.217 |  5.875 |    0.004 |       5.471 |
| conv    | transient      | SLA-Guarded (alpha=0)                      | 11.864 |  4.382 |  1.94  |    0.006 |       5.471 |
| conv    | transient      | Spreading variant (inverse-weight routing) |  2.542 |  0.659 |  9.023 |    0.009 |       5.471 |
| conv    | transient      | LatencyFirst+H                             |  2.712 |  1.146 | 15.455 |    0.015 |       5.471 |
| conv    | transient      | CostFirst+H                                | 11.864 |  4.382 |  1.936 |    0.006 |       5.471 |
| conv    | transient      | RoundRobin+H                               | 15.593 |  1.455 |  7.569 |    0.008 |       5.471 |
| conv    | transient      | CarbonFirst+H                              |  7.034 |  1.565 |  8.675 |    0.005 |       5.471 |
| conv    | transient      | LatencyFirst                               |  2.966 |  1.272 | 11.334 |    0.011 |       5.471 |
| conv    | transient      | CostFirst                                  |  2.542 |  1.328 |  1.948 |    0.006 |       5.471 |
| conv    | transient      | SOLA_style                                 |  3.644 |  1.313 | 10.767 |    0.01  |       5.471 |
| conv    | transient      | HPA_Stab                                   | 99.153 | 13.144 |  3.517 |    0.005 |       5.471 |

## SLA-Guarded (alpha=0) on the 2024 conversation trace: hysteresis band and margin

| setting        |   isvr |   rsvr |    cost |   carbon |   scal |
|:---------------|-------:|-------:|--------:|---------:|-------:|
| rel0.5, m=1.5  |  0.055 |  0.021 | 110.766 |    0.519 |  2.286 |
| rel0.5, m=2.0  |  0     |  0     | 133.795 |    0.641 |  2.143 |
| rel0.75, m=1.5 |  3.276 |  2.195 | 105.89  |    0.494 |  1     |
| rel0.75, m=2.0 |  0     |  0     | 128.219 |    0.612 |  1     |

## Control-loop time per interval (ms) and SLO violation (%) vs number of regions

|   n_regions |   mean_step_ms |   p99_step_ms |   routing_ms |   guardrail_ms |   capacity_search_ms |   hysteresis_ms |   isvr |   rsvr |   regions_used |
|------------:|---------------:|--------------:|-------------:|---------------:|---------------------:|----------------:|-------:|-------:|---------------:|
|           4 |          0.966 |         2.114 |        0.164 |          0.052 |                0.38  |           0.002 |  4.109 |  9.49  |          1.692 |
|           8 |          1.972 |         3.818 |        0.377 |          0.109 |                0.771 |           0.004 | 10.359 | 10.085 |          3.462 |
|          16 |          4.23  |         8.639 |        0.911 |          0.221 |                1.591 |           0.006 | 17.639 |  9.364 |          6.261 |
|          32 |          9.719 |        19.875 |        2.968 |          0.434 |                3.272 |           0.012 | 25.336 |  7.338 |          9.664 |
|          64 |         21.82  |        41.698 |        8.56  |          0.759 |                6.392 |           0.019 | 28.056 |  4.788 |         14.2   |
|         128 |         58.326 |       109.69  |       30.278 |          1.545 |               12.857 |           0.036 | 41.528 |  4.049 |         24.22  |

## Interval SLO violation (%) for aggregation windows of 30, 60 and 120 s

| policy                                     |   isvr_pooled_30s |   isvr_pooled_60s |   isvr_pooled_120s |   rsvr |   req_mean |   req_p5 |   frac_lt100 |
|:-------------------------------------------|------------------:|------------------:|-------------------:|-------:|-----------:|---------:|-------------:|
| SLA-Guarded (alpha=0)                      |              2.79 |              5.24 |               9.92 |   9.58 |    1020.84 |    10.06 |        15.65 |
| Spreading variant (inverse-weight routing) |              4.25 |              7.95 |              15.1  |   9.65 |    1020.84 |    10.06 |        15.65 |
| CostFirst+H                                |              4.26 |              7.9  |              14.75 |  12.37 |    1020.84 |    10.06 |        15.65 |
| SLA-Guarded (alpha=0.5)                    |              4.4  |              8.3  |              15.53 |   9.68 |    1020.84 |    10.06 |        15.65 |
| RoundRobin+H                               |              4.6  |              8.5  |              15.79 |   9.86 |    1020.84 |    10.06 |        15.65 |
