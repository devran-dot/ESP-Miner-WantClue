from pathlib import Path


def one(s, old, new, label):
    n=s.count(old)
    if n!=1: raise SystemExit(f"{label}: expected 1 got {n}")
    return s.replace(old,new,1)

bm=Path('components/asic/bm1370.c')
s=bm.read_text()
# The V3 controller is inserted before this function's definition, so declare it.
s=one(s, 'static void mb_apply_mode(mb_mode_t mode)\n{', 'void BM1370_set_hash_counting_number(uint32_t hcn);\n\nstatic void mb_apply_mode(mb_mode_t mode)\n{', 'hcn prototype')
# Avoid colliding with the V2 latency variable in BM1370_process_work.
s=one(s, '    uint64_t mb_now = result.timestamp_us;\n    uint32_t mb_nonce_host', '    uint64_t mb_v3_now = result.timestamp_us;\n    uint32_t mb_nonce_host', 'v3 now declaration')
s=one(s, '        uint64_t d = mb_now - mb_last_result_us;', '        uint64_t d = mb_v3_now - mb_last_result_us;', 'v3 interarrival')
s=one(s, '    mb_last_result_us = mb_now;', '    mb_last_result_us = mb_v3_now;', 'v3 last result')
s=one(s, '    if (mb_job_send_us[mb_slot_r] && mb_now >= mb_job_send_us[mb_slot_r]) {', '    if (mb_job_send_us[mb_slot_r] && mb_v3_now >= mb_job_send_us[mb_slot_r]) {', 'v3 latency compare')
s=one(s, '        uint32_t lat = (uint32_t)(mb_now - mb_job_send_us[mb_slot_r]);', '        uint32_t lat = (uint32_t)(mb_v3_now - mb_job_send_us[mb_slot_r]);', 'v3 latency value')
s=one(s, '    mb_wrap_observe(job_id, mb_nonce_host, rolled_version, mb_now);', '    mb_wrap_observe(job_id, mb_nonce_host, rolled_version, mb_v3_now);', 'v3 wrap timestamp')
# Automatically enter measured wrap calibration once the HCN tournament has a winner.
s=one(s,
'''        ESP_LOGI(TAG, "MB_AUTOTUNE winner=%s score=%.4f", mb_cfg(mb_tuner.best_mode)->name, mb_tuner.best_score);\n        return;''',
'''        ESP_LOGI(TAG, "MB_AUTOTUNE winner=%s score=%.4f", mb_cfg(mb_tuner.best_mode)->name, mb_tuner.best_score);\n        BM1370_mission_start_wrap_calibration();\n        return;''', 'auto wrap')
# If one held job shows no loop, cautiously lengthen the next calibration job up to 1s.
s=one(s,
'''    if (job_id != mb_wrap_job_id) {\n        mb_wrap_job_id = job_id;\n        mb_wrap_job_start_us = now;\n        mb_wrap_anchor_count = 0;\n        memset(mb_wrap_anchor, 0, sizeof(mb_wrap_anchor));\n    }''',
'''    if (job_id != mb_wrap_job_id) {\n        if (mb_wrap_job_start_us && mb_wrap_anchor_count > 0 && mb_job_interval_ms < MB_V3_CAL_MAX_INTERVAL_MS) {\n            mb_job_interval_ms += 100;\n            if (mb_job_interval_ms > MB_V3_CAL_MAX_INTERVAL_MS) mb_job_interval_ms = MB_V3_CAL_MAX_INTERVAL_MS;\n            ESP_LOGI(TAG, "MB_WRAP extend interval_ms=%d no_repeat_yet=1", mb_job_interval_ms);\n        } else if (mb_wrap_job_start_us && mb_wrap_anchor_count > 0 && mb_job_interval_ms >= MB_V3_CAL_MAX_INTERVAL_MS) {\n            mb_wrap_calibrating = false;\n            mb_job_interval_ms = MB_V3_DEFAULT_INTERVAL_MS;\n            ESP_LOGI(TAG, "MB_WRAP no_repeat_below_us=%llu fallback_interval_ms=%d",\n                     (unsigned long long)(MB_V3_CAL_MAX_INTERVAL_MS * 1000ULL), mb_job_interval_ms);\n        }\n        mb_wrap_job_id = job_id;\n        mb_wrap_job_start_us = now;\n        mb_wrap_anchor_count = 0;\n        memset(mb_wrap_anchor, 0, sizeof(mb_wrap_anchor));\n    }''', 'wrap stepping')
bm.write_text(s)

# Conservative first-stage automatic recovery: clear UART buffered state only
# after repeated framing/CRC failures. No undocumented ASIC-register writes and no
# voltage/frequency changes.
p=Path('components/asic/asic_common.c')
c=p.read_text()
c=one(c,
'''        mission_uart_preamble_errors++;\n        ESP_LOGE(TAG, "Preamble mismatch: got 0x%04x, expected 0x%04x [MB preamble=%u]", received_preamble, PREAMBLE, mission_uart_preamble_errors);''',
'''        mission_uart_preamble_errors++;\n        ESP_LOGE(TAG, "Preamble mismatch: got 0x%04x, expected 0x%04x [MB preamble=%u]", received_preamble, PREAMBLE, mission_uart_preamble_errors);\n        if ((mission_uart_preamble_errors % 8) == 0) { SERIAL_clear_buffer(); ESP_LOGW(TAG, "MB_RECOVERY uart_flush reason=preamble count=%u", mission_uart_preamble_errors); }''', 'preamble recovery')
c=one(c,
'''        mission_uart_crc_errors++;\n        ESP_LOGE(TAG, "Checksum failed on response [MB crc=%u]", mission_uart_crc_errors);''',
'''        mission_uart_crc_errors++;\n        ESP_LOGE(TAG, "Checksum failed on response [MB crc=%u]", mission_uart_crc_errors);\n        if ((mission_uart_crc_errors % 8) == 0) { SERIAL_clear_buffer(); ESP_LOGW(TAG, "MB_RECOVERY uart_flush reason=crc count=%u", mission_uart_crc_errors); }''', 'crc recovery')
p.write_text(c)
print('Mission V3 fixup applied')
