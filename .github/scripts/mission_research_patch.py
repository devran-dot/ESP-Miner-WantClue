from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, got {count}")
    return text.replace(old, new, 1)


bm = Path("components/asic/bm1370.c")
s = bm.read_text()
s = replace_once(s, '#include "esp_log.h"\n', '#include "esp_log.h"\n#include "esp_timer.h"\n', "esp_timer include")

insert = '''static int address_interval;

#ifndef MISSION_HCN_PERCENT
#define MISSION_HCN_PERCENT 0.95
#endif
#ifndef MISSION_RAW_NONCE_RANGE
#define MISSION_RAW_NONCE_RANGE 0
#endif

#define MISSION_DUP_RING_SIZE 64
#define MISSION_DUP_WINDOW_US 30000000ULL

typedef struct {
    uint8_t valid;
    uint8_t job_id;
    uint32_t nonce;
    uint32_t rolled_version;
    uint64_t timestamp_us;
} mission_result_fingerprint_t;

static mission_result_fingerprint_t mission_dup_ring[MISSION_DUP_RING_SIZE];
static uint32_t mission_dup_ring_pos;
static uint32_t mission_results_total;
static uint32_t mission_results_unique;
static uint32_t mission_results_duplicate;
static uint32_t mission_invalid_jobs;
static uint32_t mission_jobs_sent;
static uint32_t mission_jobs_replaced;
static uint32_t mission_repeated_payloads;
static uint64_t mission_last_job_us;
static uint32_t mission_version_or;
static uint16_t mission_version_min = 0xffff;
static uint16_t mission_version_max;
static uint32_t mission_core_hits[128];
static uint32_t mission_small_core_hits[16];
static BM1370_job mission_last_job_payload;
static bool mission_last_job_payload_valid;

static bool mission_is_duplicate(uint8_t job_id, uint32_t nonce, uint32_t rolled_version, uint64_t now_us)
{
    for (uint32_t i = 0; i < MISSION_DUP_RING_SIZE; i++) {
        mission_result_fingerprint_t *fp = &mission_dup_ring[i];
        if (!fp->valid) continue;
        if (now_us >= fp->timestamp_us && now_us - fp->timestamp_us > MISSION_DUP_WINDOW_US) continue;
        if (fp->job_id == job_id && fp->nonce == nonce && fp->rolled_version == rolled_version) {
            fp->timestamp_us = now_us;
            return true;
        }
    }

    mission_result_fingerprint_t *dst = &mission_dup_ring[mission_dup_ring_pos++ % MISSION_DUP_RING_SIZE];
    dst->valid = 1;
    dst->job_id = job_id;
    dst->nonce = nonce;
    dst->rolled_version = rolled_version;
    dst->timestamp_us = now_us;
    return false;
}

static void mission_log_result_summary(void)
{
    uint32_t best_core = 0, best_core_hits = 0;
    uint32_t best_small = 0, best_small_hits = 0;
    for (uint32_t i = 0; i < 128; i++) {
        if (mission_core_hits[i] > best_core_hits) {
            best_core_hits = mission_core_hits[i];
            best_core = i;
        }
    }
    for (uint32_t i = 0; i < 16; i++) {
        if (mission_small_core_hits[i] > best_small_hits) {
            best_small_hits = mission_small_core_hits[i];
            best_small = i;
        }
    }
    ESP_LOGI(TAG,
             "MB_DIAG result total=%u unique=%u dup=%u invalid_job=%u ver_or=%04x ver_min=%04x ver_max=%04x top_core=%u/%u top_small=%u/%u",
             mission_results_total, mission_results_unique, mission_results_duplicate, mission_invalid_jobs,
             mission_version_or & 0xffff, mission_version_min, mission_version_max,
             best_core, best_core_hits, best_small, best_small_hits);
}
'''
s = replace_once(s, "static int address_interval;\n", insert, "diagnostic block")

old = '''void BM1370_set_version_mask(uint32_t version_mask) 
{
    int versions_to_roll = version_mask >> 13;
    uint8_t version_byte0 = (versions_to_roll >> 8);
    uint8_t version_byte1 = (versions_to_roll & 0xFF); 
    uint8_t version_cmd[] = {0x00, 0xA4, 0x90, 0x00, version_byte0, version_byte1};
    _send_BM1370(TYPE_CMD | GROUP_ALL | CMD_WRITE, version_cmd, 6, BM1370_SERIALTX_DEBUG);
}
'''
new = '''void BM1370_set_version_mask(uint32_t version_mask) 
{
    int versions_to_roll = version_mask >> 13;
    uint8_t version_byte0 = (versions_to_roll >> 8);
    uint8_t version_byte1 = (versions_to_roll & 0xFF); 
    uint8_t version_cmd[] = {0x00, 0xA4, 0x90, 0x00, version_byte0, version_byte1};
    ESP_LOGI(TAG, "MB_DIAG version_mask pool=0x%08lx reg_A4=0x9000%02x%02x",
             (unsigned long)version_mask, version_byte0, version_byte1);
    _send_BM1370(TYPE_CMD | GROUP_ALL | CMD_WRITE, version_cmd, 6, BM1370_SERIALTX_DEBUG);
}
'''
s = replace_once(s, old, new, "version mask")

s = replace_once(
    s,
    "    uint32_t hcn_register_value = (uint32_t)hcn_frac;\n\n    BM1370_set_hash_counting_number(hcn_register_value);\n",
    "    uint32_t hcn_register_value = (uint32_t)hcn_frac;\n\n    ESP_LOGI(TAG, \"MB_DIAG hcn percent=%.4f freq=%.2f asics=%u cores=%u cores_up=%d asics_up=%d reg10=0x%08lx\",\n             nonce_percent, frequency, asic_count, cores, cores_up, asic_count_up,\n             (unsigned long)hcn_register_value);\n    BM1370_set_hash_counting_number(hcn_register_value);\n",
    "hcn log",
)

s = replace_once(
    s,
    "    BM1370_set_nonce_space(1.0, frequency, asic_count, cores);\n",
    "    if (MISSION_RAW_NONCE_RANGE != 0) {\n        ESP_LOGW(TAG, \"MB_DIAG RAW NONCE_RANGE enabled reg10=0x%08lx\",\n                 (unsigned long)MISSION_RAW_NONCE_RANGE);\n        BM1370_set_hash_counting_number((uint32_t)MISSION_RAW_NONCE_RANGE);\n    } else {\n        BM1370_set_nonce_space(MISSION_HCN_PERCENT, frequency, asic_count, cores);\n    }\n",
    "hcn selector",
)

s = replace_once(
    s,
    "    memcpy(&job.version, &next_bm_job->version, 4);\n\n    // Hold valid_jobs_lock",
    "    memcpy(&job.version, &next_bm_job->version, 4);\n\n    uint64_t mission_now_us = (uint64_t)esp_timer_get_time();\n    if (mission_last_job_payload_valid &&\n        memcmp(((uint8_t *)&mission_last_job_payload) + 1, ((uint8_t *)&job) + 1, sizeof(BM1370_job) - 1) == 0) {\n        mission_repeated_payloads++;\n    }\n    memcpy(&mission_last_job_payload, &job, sizeof(job));\n    mission_last_job_payload_valid = true;\n\n    // Hold valid_jobs_lock",
    "job payload instrumentation",
)

s = replace_once(
    s,
    "    if (GLOBAL_STATE->ASIC_TASK_MODULE.active_jobs[job.job_id] != NULL) {\n        free_bm_job(GLOBAL_STATE->ASIC_TASK_MODULE.active_jobs[job.job_id]);\n    }\n",
    "    if (GLOBAL_STATE->ASIC_TASK_MODULE.active_jobs[job.job_id] != NULL) {\n        mission_jobs_replaced++;\n        free_bm_job(GLOBAL_STATE->ASIC_TASK_MODULE.active_jobs[job.job_id]);\n    }\n",
    "replacement counter",
)

s = replace_once(
    s,
    "    pthread_mutex_unlock(&GLOBAL_STATE->valid_jobs_lock);\n\n    //debug sent jobs",
    "    pthread_mutex_unlock(&GLOBAL_STATE->valid_jobs_lock);\n\n    mission_jobs_sent++;\n    if ((mission_jobs_sent & 0x7f) == 0) {\n        unsigned long long gap_us = mission_last_job_us ?\n            (unsigned long long)(mission_now_us - mission_last_job_us) : 0ULL;\n        ESP_LOGI(TAG, \"MB_DIAG jobs sent=%u replaced=%u repeated_payload=%u last_gap_us=%llu\",\n                 mission_jobs_sent, mission_jobs_replaced, mission_repeated_payloads, gap_us);\n    }\n    mission_last_job_us = mission_now_us;\n\n    //debug sent jobs",
    "job summary",
)

s = replace_once(
    s,
    "        pthread_mutex_unlock(&GLOBAL_STATE->valid_jobs_lock);\n        ESP_LOGW(TAG, \"Invalid job nonce found, 0x%02X\", job_id);\n        return NULL;\n",
    "        pthread_mutex_unlock(&GLOBAL_STATE->valid_jobs_lock);\n        mission_invalid_jobs++;\n        ESP_LOGW(TAG, \"Invalid job nonce found, 0x%02X [MB invalid=%u]\", job_id, mission_invalid_jobs);\n        return NULL;\n",
    "invalid job counter",
)

s = replace_once(
    s,
    "    uint32_t rolled_version = GLOBAL_STATE->ASIC_TASK_MODULE.active_jobs[job_id]->version | version_bits;\n    pthread_mutex_unlock(&GLOBAL_STATE->valid_jobs_lock);\n\n    result.job_id = job_id;\n",
    "    uint32_t rolled_version = GLOBAL_STATE->ASIC_TASK_MODULE.active_jobs[job_id]->version | version_bits;\n    pthread_mutex_unlock(&GLOBAL_STATE->valid_jobs_lock);\n\n    mission_results_total++;\n    uint16_t rolled16 = (uint16_t)(version_bits >> 13);\n    mission_version_or |= rolled16;\n    if (rolled16 < mission_version_min) mission_version_min = rolled16;\n    if (rolled16 > mission_version_max) mission_version_max = rolled16;\n    if (core_id < 128) mission_core_hits[core_id]++;\n    if (small_core_id < 16) mission_small_core_hits[small_core_id]++;\n\n    if (mission_is_duplicate(job_id, asic_result.job.nonce, rolled_version, result.timestamp_us)) {\n        mission_results_duplicate++;\n        if (mission_results_duplicate <= 10 || (mission_results_duplicate % 100) == 0) {\n            ESP_LOGW(TAG, \"MB_DUP job=%02x nonce=%08lx ver=%08lx dup=%u\",\n                     job_id, (unsigned long)ntohl(asic_result.job.nonce),\n                     (unsigned long)rolled_version, mission_results_duplicate);\n        }\n        if ((mission_results_total & 0x7ff) == 0) mission_log_result_summary();\n        return NULL;\n    }\n    mission_results_unique++;\n    if ((mission_results_total & 0x7ff) == 0) mission_log_result_summary();\n\n    result.job_id = job_id;\n",
    "result instrumentation",
)

bm.write_text(s)

common = Path("components/asic/asic_common.c")
c = common.read_text()

c = replace_once(
    c,
    'static const char * TAG = "common";\nstatic char asic_chain_error[96];\n',
    'static const char * TAG = "common";\nstatic char asic_chain_error[96];\n\nstatic uint32_t mission_uart_valid_frames;\nstatic uint32_t mission_uart_rx_errors;\nstatic uint32_t mission_uart_timeouts;\nstatic uint32_t mission_uart_length_errors;\nstatic uint32_t mission_uart_preamble_errors;\nstatic uint32_t mission_uart_crc_errors;\n\nstatic void mission_uart_summary(void)\n{\n    uint32_t bad = mission_uart_rx_errors + mission_uart_length_errors +\n                   mission_uart_preamble_errors + mission_uart_crc_errors;\n    ESP_LOGI(TAG, "MB_UART valid=%u bad=%u rx=%u timeout=%u length=%u preamble=%u crc=%u",\n             mission_uart_valid_frames, bad, mission_uart_rx_errors, mission_uart_timeouts,\n             mission_uart_length_errors, mission_uart_preamble_errors, mission_uart_crc_errors);\n}\n',
    "uart globals",
)

c = replace_once(c, '    if (received < 0) {\n        ESP_LOGE(TAG, "UART error in serial RX");\n        return ESP_FAIL;\n    }\n', '    if (received < 0) {\n        mission_uart_rx_errors++;\n        ESP_LOGE(TAG, "UART error in serial RX [MB rx=%u]", mission_uart_rx_errors);\n        return ESP_FAIL;\n    }\n', "uart rx")
c = replace_once(c, '    if (received == 0) {\n        ESP_LOGD(TAG, "UART timeout in serial RX");\n        return ESP_FAIL;\n    }\n', '    if (received == 0) {\n        mission_uart_timeouts++;\n        ESP_LOGD(TAG, "UART timeout in serial RX [MB timeout=%u]", mission_uart_timeouts);\n        return ESP_FAIL;\n    }\n', "uart timeout")
c = replace_once(c, '    if (received != buffer_size) {\n        ESP_LOGE(TAG, "Invalid response length %i", received);\n', '    if (received != buffer_size) {\n        mission_uart_length_errors++;\n        ESP_LOGE(TAG, "Invalid response length %i [MB length=%u]", received, mission_uart_length_errors);\n', "uart length")
c = replace_once(c, '    if (received_preamble != PREAMBLE) {\n        ESP_LOGE(TAG, "Preamble mismatch: got 0x%04x, expected 0x%04x", received_preamble, PREAMBLE);\n', '    if (received_preamble != PREAMBLE) {\n        mission_uart_preamble_errors++;\n        ESP_LOGE(TAG, "Preamble mismatch: got 0x%04x, expected 0x%04x [MB preamble=%u]", received_preamble, PREAMBLE, mission_uart_preamble_errors);\n', "uart preamble")
c = replace_once(c, '    if (crc5(buffer + 2, buffer_size - 2) != 0) {\n        ESP_LOGE(TAG, "Checksum failed on response");        \n', '    if (crc5(buffer + 2, buffer_size - 2) != 0) {\n        mission_uart_crc_errors++;\n        ESP_LOGE(TAG, "Checksum failed on response [MB crc=%u]", mission_uart_crc_errors);        \n', "uart crc")
c = replace_once(c, '    return ESP_OK;\n}\n\nvoid get_difficulty_mask', '    mission_uart_valid_frames++;\n    if ((mission_uart_valid_frames & 0xfff) == 0) mission_uart_summary();\n    return ESP_OK;\n}\n\nvoid get_difficulty_mask', "uart valid")

common.write_text(c)
