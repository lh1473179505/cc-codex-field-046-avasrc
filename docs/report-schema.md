# 报告 schema

| 字段 | 类型 | 含义 |
|---|---|---|
| audio | string | |
| clock | string | |
| decision | string | `ok` 或 `reject` |
| reason_codes | string[] | |
| clap_error_ms | number | 输出中响板相对目标视频时间的误差 |
| tail_error_ms | number 或 null | 尾点标记误差 |
| drift_ppm | number | 估计的录音时钟偏差 |
| output_rate | integer | |
| output_frames | integer | |
