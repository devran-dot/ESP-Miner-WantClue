from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, got {n}")
    return text.replace(old, new, 1)

bm = Path("components/asic/bm1370.c")
s = bm.read_text()

anchor = "static bool mission_last_job_payload_valid;\n"
block = r'''static bool mission_last_job_payload_valid;

#define MB_V3_NONCE_BUCKETS 256
#define MB_V3_VERSION_BUCKETS 256
#define MB_V3_JOB_SLOTS 128
#define MB_V3_TUNE_WINDOW_US (20ULL * 60ULL * 1000000ULL)
#define MB_V3_WARMUP_US (2ULL * 60ULL * 1000000ULL)
#define MB_V3_CAL_MAX_INTERVAL_MS 1000
#define MB_V3_CAL_MIN_INTERVAL_MS 350
#define MB_V3_DEFAULT_INTERVAL_MS 500
#define MB_V3_DUP_ABORT_LIMIT 1
#define MB_V3_INVALID_ABORT_LIMIT 8

typedef enum {
    MB_MODE_AUTO = 0,
    MB_MODE_HCN_925,
    MB_MODE_HCN_950,
    MB_MODE_HCN_975,
    MB_MODE_HCN_980,
    MB_MODE_HCN_1000,
    MB_MODE_RAW_1EB5,
    MB_MODE_COUNT
} mb_mode_t;

typedef struct {
    mb_mode_t mode;
    const char *name;
    double percent;
    uint32_t raw;
} mb_mode_cfg_t;

static const mb_mode_cfg_t mb_modes[] = {
    {MB_MODE_AUTO, "AUTO", 0.95, 0},
    {MB_MODE_HCN_925, "HCN92.5", 0.925, 0},
    {MB_MODE_HCN_950, "HCN95", 0.95, 0},
    {MB_MODE_HCN_975, "HCN97.5", 0.975, 0},
    {MB_MODE_HCN_980, "HCN98", 0.98, 0},
    {MB_MODE_HCN_1000, "HCN100", 1.0, 0},
    {MB_MODE_RAW_1EB5, "RAW1EB5", 0.0, 0x00001EB5},
};

typedef struct {
    uint64_t started_us;
    uint32_t unique_start;
    uint32_t dup_start;
    uint32_t invalid_start;
    double best_score;
    mb_mode_t best_mode;
    uint8_t candidate_index;
    bool active;
    bool warmup;
} mb_tuner_t;

static mb_tuner_t mb_tuner;
static mb_mode_t mb_mode = MB_MODE_AUTO;
static mb_mode_t mb_effective_mode = MB_MODE_HCN_950;
static float mb_frequency_mhz;
static uint16_t mb_asic_count;
static uint16_t mb_cores;
static int mb_job_interval_ms = MB_V3_DEFAULT_INTERVAL_MS;
static uint32_t mb_nonce_hist[MB_V3_NONCE_BUCKETS];
static uint32_t mb_version_hist[MB_V3_VERSION_BUCKETS];
static uint32_t mb_job_first_latency_us[MB_V3_JOB_SLOTS];
static uint32_t mb_job_last_latency_us[MB_V3_JOB_SLOTS];
static uint32_t mb_job_result_count[MB_V3_JOB_SLOTS];
static uint64_t mb_job_send_us[MB_V3_JOB_SLOTS];
static uint32_t mb_same_job_refresh;
static uint32_t mb_new_payload;
static uint32_t mb_prevhash_change;
static uint32_t mb_premature_replace;
static uint32_t mb_core_anomaly_reports;
static uint32_t mb_space_reports;
static uint64_t mb_last_result_us;
static uint64_t mb_interarrival_sum_us;
static uint32_t mb_interarrival_count;
static uint64_t mb_interarrival_max_us;
static uint8_t mb_last_prevhash[32];
static bool mb_last_prevhash_valid;

#define MB_WRAP_ANCHORS 128
typedef struct { uint32_t nonce; uint32_t version; bool valid; } mb_wrap_anchor_t;
static mb_wrap_anchor_t mb_wrap_anchor[MB_WRAP_ANCHORS];
static uint16_t mb_wrap_anchor_count;
static uint8_t mb_wrap_job_id;
static uint64_t mb_wrap_job_start_us;
static uint64_t mb_measured_wrap_us;
static bool mb_wrap_calibrating;

static const mb_mode_cfg_t *mb_cfg(mb_mode_t mode)
{
    for (size_t i = 0; i < sizeof(mb_modes)/sizeof(mb_modes[0]); i++)
        if (mb_modes[i].mode == mode) return &mb_modes[i];
    return &mb_modes[2];
}

static void mb_apply_mode(mb_mode_t mode)
{
    const mb_mode_cfg_t *cfg = mb_cfg(mode);
    mb_effective_mode = mode;
    if (cfg->raw) {
        BM1370_set_hash_counting_number(cfg->raw);
        ESP_LOGW(TAG, "MB_V3 mode=%s raw_reg10=0x%08lx", cfg->name, (unsigned long)cfg->raw);
    } else {
        BM1370_set_nonce_space(cfg->percent, mb_frequency_mhz, mb_asic_count, mb_cores);
        ESP_LOGI(TAG, "MB_V3 mode=%s hcn=%.4f interval_ms=%d", cfg->name, cfg->percent, mb_job_interval_ms);
    }
}

void BM1370_mission_set_mode(int mode)
{
    if (mode < 0 || mode >= MB_MODE_COUNT) mode = MB_MODE_AUTO;
    mb_mode = (mb_mode_t)mode;
    if (mb_mode == MB_MODE_AUTO) {
        mb_tuner.active = true;
        mb_tuner.warmup = true;
        mb_tuner.candidate_index = 2;
        mb_tuner.best_score = -1.0;
        mb_tuner.best_mode = MB_MODE_HCN_950;
        mb_tuner.started_us = (uint64_t)esp_timer_get_time();
        mb_tuner.unique_start = mission_results_unique;
        mb_tuner.dup_start = mission_results_duplicate;
        mb_tuner.invalid_start = mission_invalid_jobs;
        mb_apply_mode(MB_MODE_HCN_950);
        ESP_LOGI(TAG, "MB_AUTOTUNE start warmup=120s window=1200s");
    } else {
        mb_tuner.active = false;
        mb_apply_mode(mb_mode);
    }
}

int BM1370_mission_get_mode(void) { return (int)mb_mode; }
int BM1370_mission_get_effective_mode(void) { return (int)mb_effective_mode; }
int BM1370_mission_get_job_interval_ms(void) { return mb_job_interval_ms; }
uint64_t BM1370_mission_get_measured_wrap_us(void) { return mb_measured_wrap_us; }

static void mb_start_candidate(mb_mode_t mode, uint64_t now)
{
    mb_apply_mode(mode);
    mb_tuner.started_us = now;
    mb_tuner.unique_start = mission_results_unique;
    mb_tuner.dup_start = mission_results_duplicate;
    mb_tuner.invalid_start = mission_invalid_jobs;
    ESP_LOGI(TAG, "MB_AUTOTUNE candidate=%s interval_ms=%d", mb_cfg(mode)->name, mb_job_interval_ms);
}

static void mb_autotune_tick(uint64_t now)
{
    if (!mb_tuner.active) return;
    uint64_t elapsed = now - mb_tuner.started_us;
    if (mb_tuner.warmup) {
        if (elapsed < MB_V3_WARMUP_US) return;
        mb_tuner.warmup = false;
        mb_tuner.candidate_index = 1;
        mb_start_candidate((mb_mode_t)mb_tuner.candidate_index, now);
        return;
    }
    uint32_t u = mission_results_unique - mb_tuner.unique_start;
    uint32_t d = mission_results_duplicate - mb_tuner.dup_start;
    uint32_t inv = mission_invalid_jobs - mb_tuner.invalid_start;
    if (d >= MB_V3_DUP_ABORT_LIMIT || inv >= MB_V3_INVALID_ABORT_LIMIT) elapsed = MB_V3_TUNE_WINDOW_US;
    if (elapsed < MB_V3_TUNE_WINDOW_US) return;
    double seconds = elapsed / 1000000.0;
    double unique_per_s = seconds > 0 ? u / seconds : 0.0;
    double score = unique_per_s - (double)d * 50.0 - (double)inv * 5.0;
    ESP_LOGI(TAG, "MB_AUTOTUNE result mode=%s unique_s=%.4f dup=%u invalid=%u score=%.4f",
             mb_cfg(mb_effective_mode)->name, unique_per_s, d, inv, score);
    if (d == 0 && inv < MB_V3_INVALID_ABORT_LIMIT && score > mb_tuner.best_score) {
        mb_tuner.best_score = score;
        mb_tuner.best_mode = mb_effective_mode;
    }
    mb_tuner.candidate_index++;
    if (mb_tuner.candidate_index >= MB_MODE_COUNT) {
        mb_tuner.active = false;
        mb_apply_mode(mb_tuner.best_mode);
        ESP_LOGI(TAG, "MB_AUTOTUNE winner=%s score=%.4f", mb_cfg(mb_tuner.best_mode)->name, mb_tuner.best_score);
        return;
    }
    mb_start_candidate((mb_mode_t)mb_tuner.candidate_index, now);
}

static void mb_space_report(void)
{
    uint32_t nmin = UINT32_MAX, nmax = 0, vmin = UINT32_MAX, vmax = 0;
    uint32_t nempty = 0, vempty = 0;
    for (int i = 0; i < MB_V3_NONCE_BUCKETS; i++) {
        uint32_t x = mb_nonce_hist[i]; if (!x) nempty++; if (x < nmin) nmin = x; if (x > nmax) nmax = x;
    }
    for (int i = 0; i < MB_V3_VERSION_BUCKETS; i++) {
        uint32_t x = mb_version_hist[i]; if (!x) vempty++; if (x < vmin) vmin = x; if (x > vmax) vmax = x;
    }
    uint64_t avg = mb_interarrival_count ? mb_interarrival_sum_us / mb_interarrival_count : 0;
    double unique_ratio = mission_results_total ? (double)mission_results_unique / mission_results_total : 1.0;
    double nominal_ghs = (double)mb_frequency_mhz * 2040.0 / 1000.0;
    double unique_eff_ghs = nominal_ghs * unique_ratio;
    ESP_LOGI(TAG, "MB_SPACE report=%u nonce_empty=%u nonce_min=%u nonce_max=%u ver_empty=%u ver_min=%u ver_max=%u ia_avg_us=%llu ia_max_us=%llu unique_eff_ghs=%.2f",
        ++mb_space_reports, nempty, nmin, nmax, vempty, vmin, vmax,
        (unsigned long long)avg, (unsigned long long)mb_interarrival_max_us, unique_eff_ghs);
}

static void mb_core_anomaly_report(void)
{
    if (mission_results_unique < 100000 || (mission_results_unique % 100000) > 32) return;
    double mean = mission_results_unique / 128.0;
    uint32_t low = 0, high = 0;
    for (int i = 0; i < 128; i++) {
        if (mission_core_hits[i] < mean * 0.50) low++;
        if (mission_core_hits[i] > mean * 1.50) high++;
    }
    ESP_LOGI(TAG, "MB_CORE samples=%u mean=%.1f low50=%u high150=%u report=%u",
             mission_results_unique, mean, low, high, ++mb_core_anomaly_reports);
}

static void mb_wrap_observe(uint8_t job_id, uint32_t nonce, uint32_t version, uint64_t now)
{
    if (!mb_wrap_calibrating) return;
    if (job_id != mb_wrap_job_id) {
        mb_wrap_job_id = job_id;
        mb_wrap_job_start_us = now;
        mb_wrap_anchor_count = 0;
        memset(mb_wrap_anchor, 0, sizeof(mb_wrap_anchor));
    }
    for (uint16_t i = 0; i < mb_wrap_anchor_count; i++) {
        if (mb_wrap_anchor[i].valid && mb_wrap_anchor[i].nonce == nonce && mb_wrap_anchor[i].version == version) {
            mb_measured_wrap_us = now - mb_wrap_job_start_us;
            mb_wrap_calibrating = false;
            int safe_ms = (int)((mb_measured_wrap_us / 1000ULL) * 95ULL / 100ULL);
            if (safe_ms < MB_V3_CAL_MIN_INTERVAL_MS) safe_ms = MB_V3_CAL_MIN_INTERVAL_MS;
            if (safe_ms > MB_V3_DEFAULT_INTERVAL_MS) safe_ms = MB_V3_DEFAULT_INTERVAL_MS;
            mb_job_interval_ms = safe_ms;
            ESP_LOGW(TAG, "MB_WRAP measured_us=%llu safe_interval_ms=%d", (unsigned long long)mb_measured_wrap_us, mb_job_interval_ms);
            return;
        }
    }
    if (mb_wrap_anchor_count < MB_WRAP_ANCHORS)
        mb_wrap_anchor[mb_wrap_anchor_count++] = (mb_wrap_anchor_t){nonce, version, true};
}

void BM1370_mission_start_wrap_calibration(void)
{
    mb_wrap_calibrating = true;
    mb_job_interval_ms = 600;
    mb_wrap_anchor_count = 0;
    mb_measured_wrap_us = 0;
    ESP_LOGW(TAG, "MB_WRAP calibration_start interval_ms=%d max_ms=%d", mb_job_interval_ms, MB_V3_CAL_MAX_INTERVAL_MS);
}
'''
s = replace_once(s, anchor, block, "V3 state")

needle = "        BM1370_set_nonce_space(MISSION_HCN_PERCENT, frequency, asic_count, cores);\n    }\n"
repl = "        BM1370_set_nonce_space(MISSION_HCN_PERCENT, frequency, asic_count, cores);\n    }\n    mb_frequency_mhz = frequency;\n    mb_asic_count = asic_count;\n    mb_cores = cores;\n    mb_job_interval_ms = MB_V3_DEFAULT_INTERVAL_MS;\n    BM1370_mission_set_mode(MB_MODE_AUTO);\n"
s = replace_once(s, needle, repl, "V3 init")

needle = "    uint64_t mission_now_us = (uint64_t)esp_timer_get_time();\n"
repl = r'''    uint64_t mission_now_us = (uint64_t)esp_timer_get_time();
    mb_autotune_tick(mission_now_us);
    bool mb_prev_changed = mb_last_prevhash_valid && memcmp(mb_last_prevhash, job.prev_block_hash, 32) != 0;
    if (!mb_last_prevhash_valid || mb_prev_changed) {
        memcpy(mb_last_prevhash, job.prev_block_hash, 32);
        mb_last_prevhash_valid = true;
        if (mb_prev_changed) { mb_prevhash_change++; ESP_LOGW(TAG, "MB_JOB class=NEW_PREVHASH count=%u fastpath=1", mb_prevhash_change); }
    }
    if (mission_last_job_payload_valid) {
        if (memcmp(((uint8_t *)&mission_last_job_payload) + 1, ((uint8_t *)&job) + 1, sizeof(BM1370_job) - 1) == 0) mb_same_job_refresh++;
        else mb_new_payload++;
    }
    uint8_t mb_slot = job.job_id & 0x7f;
    if (mb_job_send_us[mb_slot] && mission_now_us - mb_job_send_us[mb_slot] < (uint64_t)mb_job_interval_ms * 900ULL) mb_premature_replace++;
    mb_job_send_us[mb_slot] = mission_now_us;
    mb_job_first_latency_us[mb_slot] = 0;
    mb_job_last_latency_us[mb_slot] = 0;
    mb_job_result_count[mb_slot] = 0;
'''
s = replace_once(s, needle, repl, "V3 job telemetry")

needle = "    mission_results_total++;\n"
repl = r'''    mission_results_total++;
    uint64_t mb_now = result.timestamp_us;
    uint32_t mb_nonce_host = ntohl(asic_result.job.nonce);
    mb_nonce_hist[(mb_nonce_host >> 24) & 0xff]++;
    mb_version_hist[(version_bits >> 13) & 0xff]++;
    if (mb_last_result_us) {
        uint64_t d = mb_now - mb_last_result_us;
        mb_interarrival_sum_us += d; mb_interarrival_count++; if (d > mb_interarrival_max_us) mb_interarrival_max_us = d;
    }
    mb_last_result_us = mb_now;
    uint8_t mb_slot_r = job_id & 0x7f;
    if (mb_job_send_us[mb_slot_r] && mb_now >= mb_job_send_us[mb_slot_r]) {
        uint32_t lat = (uint32_t)(mb_now - mb_job_send_us[mb_slot_r]);
        if (mb_job_result_count[mb_slot_r] == 0) mb_job_first_latency_us[mb_slot_r] = lat;
        mb_job_last_latency_us[mb_slot_r] = lat; mb_job_result_count[mb_slot_r]++;
    }
    mb_wrap_observe(job_id, mb_nonce_host, rolled_version, mb_now);
    if ((mission_results_total & 0xfff) == 0) mb_space_report();
    mb_core_anomaly_report();
'''
s = replace_once(s, needle, repl, "V3 result telemetry")

needle = '        ESP_LOGI(TAG, "MB_DIAG jobs sent=%u replaced=%u repeated_payload=%u last_gap_us=%llu",\n                 mission_jobs_sent, mission_jobs_replaced, mission_repeated_payloads, gap_us);\n'
repl = '        ESP_LOGI(TAG, "MB_DIAG jobs sent=%u replaced=%u repeated_payload=%u last_gap_us=%llu same_refresh=%u new_payload=%u prevhash=%u premature=%u interval_ms=%d mode=%s",\n                 mission_jobs_sent, mission_jobs_replaced, mission_repeated_payloads, gap_us, mb_same_job_refresh, mb_new_payload, mb_prevhash_change, mb_premature_replace, mb_job_interval_ms, mb_cfg(mb_effective_mode)->name);\n'
s = replace_once(s, needle, repl, "V3 job summary")
bm.write_text(s)

h = Path("components/asic/include/bm1370.h")
hs = h.read_text()
hs = replace_once(hs, "void BM1370_set_nonce_space(double nonce_percent, float frequency, uint16_t asic_count, uint16_t cores);\n", "void BM1370_set_nonce_space(double nonce_percent, float frequency, uint16_t asic_count, uint16_t cores);\nvoid BM1370_mission_set_mode(int mode);\nint BM1370_mission_get_mode(void);\nint BM1370_mission_get_effective_mode(void);\nint BM1370_mission_get_job_interval_ms(void);\nuint64_t BM1370_mission_get_measured_wrap_us(void);\nvoid BM1370_mission_start_wrap_calibration(void);\n", "V3 header")
h.write_text(hs)

a = Path("components/asic/asic.c")
asrc = a.read_text()
asrc = asrc.replace("        case ASIC_TYPE_BM1370:\n            BM1370_set_nonce_space(nonce_percent, frequency, asic_count, cores);\n            break;", "        case ASIC_TYPE_BM1370:\n            ESP_LOGI(TAG, \"MB_V3 runtime controller owns BM1370 nonce-space\");\n            break;")
asrc = asrc.replace("        case ASIC_TYPE_BM1370:\n        case ASIC_TYPE_BM1373:\n            return asic_default_timeout_divided;", "        case ASIC_TYPE_BM1370:\n            return BM1370_mission_get_job_interval_ms();\n        case ASIC_TYPE_BM1373:\n            return asic_default_timeout_divided;")
a.write_text(asrc)

serial = Path("components/asic/serial.c")
ss = serial.read_text().replace("if ((mb_tx_calls & 0x7ff) == 0 || ret != len)", "if ((mb_tx_calls & 0x7f) == 0 || ret != len)")
serial.write_text(ss)

art = Path("main/tasks/asic_result_task.c")
t = art.read_text()
t = replace_once(t, 'static const char *TAG = "asic_result";\n', r'''static const char *TAG = "asic_result";
#define MB_SHARE_CACHE 128
typedef struct { uint32_t nonce, version, ntime, job_hash; uint64_t seen_us; bool valid; } mb_share_fp_t;
static mb_share_fp_t mb_share_cache[MB_SHARE_CACHE];
static uint32_t mb_share_pos, mb_share_duplicates, mb_stale_submit;
static uint32_t mb_hash_str(const char *s) { uint32_t h=2166136261u; if(!s)return h; while(*s){h^=(uint8_t)*s++;h*=16777619u;} return h; }
static bool mb_share_is_dup(const bm_job *j, const task_result *r) {
    uint64_t now=r->timestamp_us; uint32_t jh=mb_hash_str(j->jobid)^mb_hash_str(j->extranonce2);
    for(int i=0;i<MB_SHARE_CACHE;i++){ mb_share_fp_t *x=&mb_share_cache[i]; if(!x->valid||now<x->seen_us||now-x->seen_us>60000000ULL)continue; if(x->nonce==r->nonce&&x->version==r->rolled_version&&x->ntime==j->ntime&&x->job_hash==jh){x->seen_us=now;return true;} }
    mb_share_cache[mb_share_pos++%MB_SHARE_CACHE]=(mb_share_fp_t){r->nonce,r->rolled_version,j->ntime,jh,now,true}; return false;
}
''', "share cache")
needle = "        if (nonce_diff >= active_job->pool_diff)\n        {\n"
repl = r'''        if (nonce_diff >= active_job->pool_diff)
        {
            pthread_mutex_lock(&GLOBAL_STATE->valid_jobs_lock);
            bool mb_still_current=(GLOBAL_STATE->valid_jobs[job_id]!=0)&&(GLOBAL_STATE->ASIC_TASK_MODULE.active_jobs[job_id]!=NULL);
            pthread_mutex_unlock(&GLOBAL_STATE->valid_jobs_lock);
            if(!mb_still_current){mb_stale_submit++;ESP_LOGW(TAG,"MB_STALE before_submit job=%02x count=%u",job_id,mb_stale_submit);free(active_job->jobid);free(active_job->extranonce2);continue;}
            if(mb_share_is_dup(active_job,asic_result)){mb_share_duplicates++;ESP_LOGW(TAG,"MB_SHARE_DUP job=%s nonce=%08" PRIX32 " version=%08" PRIX32 " count=%u",active_job->jobid,asic_result->nonce,asic_result->rolled_version,mb_share_duplicates);free(active_job->jobid);free(active_job->extranonce2);continue;}
'''
t = replace_once(t, needle, repl, "share guard")
art.write_text(t)

cj = Path("main/tasks/create_jobs_task.c")
c = cj.read_text()
c = c.replace("        uint64_t start_time = esp_timer_get_time();\n        void *new_work = queue_dequeue_timeout(&GLOBAL_STATE->stratum_queue, timeout_ms);", "        int mb_dynamic_timeout = ASIC_get_asic_job_frequency_ms(GLOBAL_STATE);\n        if (mb_dynamic_timeout > 0 && mb_dynamic_timeout != timeout_ms) timeout_ms = mb_dynamic_timeout;\n        uint64_t start_time = esp_timer_get_time();\n        void *new_work = queue_dequeue_timeout(&GLOBAL_STATE->stratum_queue, timeout_ms);")
cj.write_text(c)

print("Mission Block Trick17 V3 patch applied")
