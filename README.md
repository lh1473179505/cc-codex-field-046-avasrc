# avasrc

把独立录音锁到摄像机时钟上的异步重采样工具。`probe` 已经能读 WAV 和视频时间戳列表，并给出响板峰值的粗位置。`sync` 还没有实现。

不要引入 libsamplerate、soxr、NumPy、SciPy 或 ffmpeg-python，也不要使用 Docker。请复用 `avasrc.wavio` 和 `avasrc.video`。异步重采样必须在本仓库里用加窗 sinc 实现。

## 命令

```
python -m avasrc probe --audio fixtures/take.wav --clock fixtures/video-clock.json
python -m avasrc sync \
  --audio fixtures/take.wav \
  --clock fixtures/video-clock.json \
  --policy fixtures/policy.json \
  --output /tmp/avasrc-locked.wav \
  --report /tmp/avasrc-report.json
```

规则见 `docs/sync-rules.md`，报告字段见 `docs/report-schema.md`。
