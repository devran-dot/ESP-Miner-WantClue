from pathlib import Path


def one(s, old, new, label):
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 got {n}")
    return s.replace(old, new, 1)

bm = Path('components/asic/bm1370.c')
s = bm.read_text()

# Fix the legacy 32-bin version-space auditor. rolled16 is already version_bits >> 13,
# so shifting it by 11 collapsed the entire observed BM1370 range into one bin.
s = one(s,
        '    mb_version_bins[(rolled16 >> 11) & 31]++;',
        '    mb_version_bins[(rolled16 >> 3) & 31]++;',
        'version 32-bin fix')

# V4 uses a sample-count driven tournament. This avoids relying solely on a long wall-clock
# window and makes every candidate collect a comparable amount of real ASIC work.
s = one(s,
        '#define MB_V3_INVALID_ABORT_LIMIT 8\n',
        '#define MB_V3_INVALID_ABORT_LIMIT 8\n#define MB_V4_MIN_UNIQUE 1024U\n#define MB_V4_MAX_WINDOW_US (12ULL * 60ULL * 1000000ULL)\n#define MB_V4_HEARTBEAT_US (60ULL * 1000000ULL)\n',
        'v4 tuner constants')

s = one(s,
        'static mb_tuner_t mb_tuner;\n',
        'static mb_tuner_t mb_tuner;\nstatic uint64_t mb_v4_last_heartbeat_us;\n',
        'v4 heartbeat state')

old = '''static void mb_autotune_tick(uint64_t now)
{
    if (!mb_tuner.active) return;
    uint64_t elapsed = now - mb_tuner.started_us;
'''
new = '''static void mb_autotune_tick(uint64_t now)
{
    if (!mb_tuner.active) return;
    uint64_t real_now = (uint64_t)esp_timer_get_time();
    if (real_now > now) now = real_now;
    uint64_t elapsed = now >= mb_tuner.started_us ? now - mb_tuner.started_us : 0;
'''
s = one(s, old, new, 'v4 monotonic tuner clock')

old = '''    uint32_t u = mission_results_unique - mb_tuner.unique_start;
    uint32_t d = mission_results_duplicate - mb_tuner.dup_start;
    uint32_t inv = mission_invalid_jobs - mb_tuner.invalid_start;
    if (d >= MB_V3_DUP_ABORT_LIMIT || inv >= MB_V3_INVALID_ABORT_LIMIT) elapsed = MB_V3_TUNE_WINDOW_US;
    if (elapsed < MB_V3_TUNE_WINDOW_US) return;
    double seconds = elapsed / 1000000.0;
'''
new = '''    uint32_t u = mission_results_unique - mb_tuner.unique_start;
    uint32_t d = mission_results_duplicate - mb_tuner.dup_start;
    uint32_t inv = mission_invalid_jobs - mb_tuner.invalid_start;
    if (!mb_v4_last_heartbeat_us || now - mb_v4_last_heartbeat_us >= MB_V4_HEARTBEAT_US) {
        mb_v4_last_heartbeat_us = now;
        ESP_LOGI(TAG, "MB_V4_TUNE heartbeat mode=%s elapsed_s=%llu unique=%u dup=%u invalid=%u target_unique=%u",
                 mb_cfg(mb_effective_mode)->name, (unsigned long long)(elapsed / 1000000ULL),
                 u, d, inv, MB_V4_MIN_UNIQUE);
    }
    bool abort_bad = d >= MB_V3_DUP_ABORT_LIMIT || inv >= MB_V3_INVALID_ABORT_LIMIT;
    bool enough_samples = u >= MB_V4_MIN_UNIQUE;
    bool max_window = elapsed >= MB_V4_MAX_WINDOW_US;
    if (!abort_bad && !enough_samples && !max_window) return;
    double seconds = elapsed / 1000000.0;
'''
s = one(s, old, new, 'v4 sample driven tuner')

# Never test the undocumented RAW value automatically. It remains available as a manual
# research mode, but AUTO only evaluates the bounded HCN candidates.
s = one(s,
        '    if (mb_tuner.candidate_index >= MB_MODE_COUNT) {',
        '    if (mb_tuner.candidate_index >= MB_MODE_RAW_1EB5) {',
        'v4 raw manual only')

# Make the winner criteria explicit: enough real samples (unless a bad candidate was aborted),
# zero duplicates, bounded invalids. Add the unique ratio to the result log.
old = '''    double unique_per_s = seconds > 0 ? u / seconds : 0.0;
    double score = unique_per_s - (double)d * 50.0 - (double)inv * 5.0;
    ESP_LOGI(TAG, "MB_AUTOTUNE result mode=%s unique_s=%.4f dup=%u invalid=%u score=%.4f",
             mb_cfg(mb_effective_mode)->name, unique_per_s, d, inv, score);
    if (d == 0 && inv < MB_V3_INVALID_ABORT_LIMIT && score > mb_tuner.best_score) {
'''
new = '''    double unique_per_s = seconds > 0 ? u / seconds : 0.0;
    uint32_t tested_total = u + d;
    double unique_ratio = tested_total ? (double)u / tested_total : 1.0;
    double score = unique_per_s * unique_ratio - (double)d * 50.0 - (double)inv * 5.0;
    ESP_LOGI(TAG, "MB_AUTOTUNE result mode=%s elapsed_s=%.1f samples=%u unique_s=%.4f unique_ratio=%.6f dup=%u invalid=%u score=%.4f",
             mb_cfg(mb_effective_mode)->name, seconds, tested_total, unique_per_s, unique_ratio, d, inv, score);
    if (u >= 256 && d == 0 && inv < MB_V3_INVALID_ABORT_LIMIT && score > mb_tuner.best_score) {
'''
s = one(s, old, new, 'v4 result scoring')

# Reset heartbeat whenever a new candidate starts so the first progress line appears promptly.
s = one(s,
        '    mb_tuner.invalid_start = mission_invalid_jobs;\n    ESP_LOGI(TAG, "MB_AUTOTUNE candidate=%s interval_ms=%d", mb_cfg(mode)->name, mb_job_interval_ms);',
        '    mb_tuner.invalid_start = mission_invalid_jobs;\n    mb_v4_last_heartbeat_us = 0;\n    ESP_LOGI(TAG, "MB_AUTOTUNE candidate=%s interval_ms=%d", mb_cfg(mode)->name, mb_job_interval_ms);',
        'v4 candidate heartbeat reset')

# Force the detailed 256-bin/latency report to accompany each 2048-result diagnostic summary.
# There are two V1 summary sites; the last one is the normal unique-result path.
needle = '    if ((mission_results_total & 0x7ff) == 0) mission_log_result_summary();\n\n    result.job_id = job_id;'
repl = '    if ((mission_results_total & 0x7ff) == 0) { mission_log_result_summary(); mb_space_report(); }\n\n    result.job_id = job_id;'
s = one(s, needle, repl, 'v4 force space report')

# Add per-slot first/last result latency into the detailed V4 report. These arrays are already
# populated by V3 and give us a direct job-send -> ASIC-result timing signal.
old = '''    uint64_t avg = mb_interarrival_count ? mb_interarrival_sum_us / mb_interarrival_count : 0;
    double unique_ratio = mission_results_total ? (double)mission_results_unique / mission_results_total : 1.0;
    double nominal_ghs = (double)mb_frequency_mhz * 2040.0 / 1000.0;
    double unique_eff_ghs = nominal_ghs * unique_ratio;
    ESP_LOGI(TAG, "MB_SPACE report=%u nonce_empty=%u nonce_min=%u nonce_max=%u ver_empty=%u ver_min=%u ver_max=%u ia_avg_us=%llu ia_max_us=%llu unique_eff_ghs=%.2f",
        ++mb_space_reports, nempty, nmin, nmax, vempty, vmin, vmax,
        (unsigned long long)avg, (unsigned long long)mb_interarrival_max_us, unique_eff_ghs);
'''
new = '''    uint64_t avg = mb_interarrival_count ? mb_interarrival_sum_us / mb_interarrival_count : 0;
    uint64_t first_sum = 0, last_sum = 0; uint32_t lat_slots = 0;
    for (int i = 0; i < MB_V3_JOB_SLOTS; i++) {
        if (mb_job_result_count[i]) { first_sum += mb_job_first_latency_us[i]; last_sum += mb_job_last_latency_us[i]; lat_slots++; }
    }
    uint64_t first_avg = lat_slots ? first_sum / lat_slots : 0;
    uint64_t last_avg = lat_slots ? last_sum / lat_slots : 0;
    double unique_ratio = mission_results_total ? (double)mission_results_unique / mission_results_total : 1.0;
    double nominal_ghs = (double)mb_frequency_mhz * 2040.0 / 1000.0;
    double unique_eff_ghs = nominal_ghs * unique_ratio;
    ESP_LOGI(TAG, "MB_SPACE report=%u nonce_empty=%u nonce_min=%u nonce_max=%u ver_empty=%u ver_min=%u ver_max=%u ia_avg_us=%llu ia_max_us=%llu first_avg_us=%llu last_avg_us=%llu lat_slots=%u unique_eff_ghs=%.2f",
        ++mb_space_reports, nempty, nmin, nmax, vempty, vmin, vmax,
        (unsigned long long)avg, (unsigned long long)mb_interarrival_max_us,
        (unsigned long long)first_avg, (unsigned long long)last_avg, lat_slots, unique_eff_ghs);
'''
s = one(s, old, new, 'v4 latency report')

# Make startup identify the V4 policy clearly.
s = one(s,
        '        ESP_LOGI(TAG, "MB_AUTOTUNE start warmup=120s window=1200s");',
        '        ESP_LOGI(TAG, "MB_AUTOTUNE start warmup=120s policy=sample-driven target_unique=1024 max_window=720s raw_auto=0");',
        'v4 startup log')

bm.write_text(s)
print('Mission Block Trick17 V4 patch applied')
