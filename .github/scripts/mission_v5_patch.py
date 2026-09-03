from pathlib import Path
p=Path('components/asic/bm1370.c')
s=p.read_text()
def r(a,b):
    global s
    if s.count(a)!=1: raise SystemExit('V5 patch anchor mismatch')
    s=s.replace(a,b,1)
r('    MB_MODE_HCN_950,\n    MB_MODE_HCN_975,\n    MB_MODE_HCN_980,\n    MB_MODE_HCN_1000,','    MB_MODE_HCN_950,\n    MB_MODE_HCN_960,\n    MB_MODE_HCN_970,\n    MB_MODE_HCN_975,\n    MB_MODE_HCN_980,\n    MB_MODE_HCN_985,\n    MB_MODE_HCN_990,\n    MB_MODE_HCN_995,\n    MB_MODE_HCN_1000,')
r('    {MB_MODE_HCN_950, "HCN95", 0.95, 0},\n    {MB_MODE_HCN_975, "HCN97.5", 0.975, 0},\n    {MB_MODE_HCN_980, "HCN98", 0.98, 0},\n    {MB_MODE_HCN_1000, "HCN100", 1.0, 0},','    {MB_MODE_HCN_950, "HCN95", 0.95, 0},\n    {MB_MODE_HCN_960, "HCN96", 0.96, 0},\n    {MB_MODE_HCN_970, "HCN97", 0.97, 0},\n    {MB_MODE_HCN_975, "HCN97.5", 0.975, 0},\n    {MB_MODE_HCN_980, "HCN98", 0.98, 0},\n    {MB_MODE_HCN_985, "HCN98.5", 0.985, 0},\n    {MB_MODE_HCN_990, "HCN99", 0.99, 0},\n    {MB_MODE_HCN_995, "HCN99.5", 0.995, 0},\n    {MB_MODE_HCN_1000, "HCN100", 1.0, 0},')
r('    if (u >= 256 && d == 0 && inv < MB_V3_INVALID_ABORT_LIMIT && score > mb_tuner.best_score) {','    bool v5_ok = u >= MB_V4_MIN_UNIQUE && d == 0 && inv == 0;\n    ESP_LOGI(TAG, "MB_V5_GATE mode=%s ok=%d samples=%u dup=%u invalid=%u", mb_cfg(mb_effective_mode)->name, v5_ok, u, d, inv);\n    if (v5_ok && score > mb_tuner.best_score) {')
r('        mb_tuner.candidate_index = 1;\n        mb_start_candidate((mb_mode_t)mb_tuner.candidate_index, now);','        mb_tuner.candidate_index = MB_MODE_HCN_950;\n        mb_start_candidate((mb_mode_t)mb_tuner.candidate_index, now);')
r('#define MB_V3_CAL_MAX_INTERVAL_MS 1000','#define MB_V3_CAL_MAX_INTERVAL_MS 1500')
r('            int safe_ms = (int)((mb_measured_wrap_us / 1000ULL) * 95ULL / 100ULL);','            int safe_ms = (int)((mb_measured_wrap_us / 1000ULL) * 97ULL / 100ULL);')
r('            if (safe_ms > MB_V3_DEFAULT_INTERVAL_MS) safe_ms = MB_V3_DEFAULT_INTERVAL_MS;','            if (safe_ms > 900) safe_ms = 900;')
r('        ESP_LOGI(TAG, "MB_AUTOTUNE start warmup=120s policy=sample-driven target_unique=1024 max_window=720s raw_auto=0");','        ESP_LOGI(TAG, "MB_AUTOTUNE start V5 warmup=120s policy=fine-hcn target_unique=1024 range=95..100 raw_auto=0 wrap_max_ms=1500");')
r('        ESP_LOGI(TAG, "MB_AUTOTUNE winner=%s score=%.4f", mb_cfg(mb_tuner.best_mode)->name, mb_tuner.best_score);','        ESP_LOGI(TAG, "MB_AUTOTUNE V5 winner=%s score=%.4f", mb_cfg(mb_tuner.best_mode)->name, mb_tuner.best_score);')
p.write_text(s)
print('Mission Block Trick17 V5 patch applied')
