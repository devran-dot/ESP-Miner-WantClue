from pathlib import Path

p=Path('components/asic/serial.c')
s=p.read_text()
s=s.replace('static const char *TAG = "serial";','static const char *TAG = "serial";\nstatic uint32_t mb_tx_calls, mb_tx_failures;\nstatic uint64_t mb_tx_bytes;')
s=s.replace('    return uart_write_bytes(UART_NUM_1, (const char *)data, len);','    mb_tx_calls++;\n    int written = uart_write_bytes(UART_NUM_1, (const char *)data, len);\n    if (written > 0) mb_tx_bytes += (uint32_t)written;\n    if (written != len) { mb_tx_failures++; ESP_LOGE(TAG, "MB_TX requested=%d written=%d calls=%u failures=%u", len, written, mb_tx_calls, mb_tx_failures); }\n    else if ((mb_tx_calls & 0x7ff) == 0) ESP_LOGI(TAG, "MB_TX calls=%u failures=%u bytes=%llu", mb_tx_calls, mb_tx_failures, (unsigned long long)mb_tx_bytes);\n    return written;')
p.write_text(s)

p=Path('components/asic/bm1370.c')
s=p.read_text()
s=s.replace('static uint32_t mission_small_core_hits[16];','static uint32_t mission_small_core_hits[16];\nstatic uint32_t mb_nonce_bins[32], mb_version_bins[32];\nstatic uint64_t mb_last_result_us, mb_result_gap_sum_us, mb_result_gap_max_us;')
s=s.replace('    mission_results_total++;\n    uint16_t rolled16 = (uint16_t)(version_bits >> 13);','    mission_results_total++;\n    uint64_t mb_now = (uint64_t)esp_timer_get_time();\n    if (mb_last_result_us && mb_now >= mb_last_result_us) { uint64_t g=mb_now-mb_last_result_us; mb_result_gap_sum_us += g; if(g>mb_result_gap_max_us) mb_result_gap_max_us=g; }\n    mb_last_result_us=mb_now;\n    mb_nonce_bins[ntohl(asic_result.job.nonce) >> 27]++;\n    uint16_t rolled16 = (uint16_t)(version_bits >> 13);\n    mb_version_bins[(rolled16 >> 11) & 31]++;')
s=s.replace('    ESP_LOGI(TAG,\n             "MB_DIAG result total=%u unique=%u dup=%u invalid_job=%u ver_or=%04x ver_min=%04x ver_max=%04x top_core=%u/%u top_small=%u/%u",','    uint32_t nb=0,vb=0; for(uint32_t i=0;i<32;i++){ if(mb_nonce_bins[i]) nb++; if(mb_version_bins[i]) vb++; }\n    uint64_t avg_gap = mission_results_total > 1 ? mb_result_gap_sum_us/(mission_results_total-1) : 0;\n    ESP_LOGI(TAG, "MB_SPACE nonce_bins=%u/32 version_bins=%u/32 result_gap_avg_max_us=%llu/%llu", nb, vb, (unsigned long long)avg_gap, (unsigned long long)mb_result_gap_max_us);\n    ESP_LOGI(TAG,\n             "MB_DIAG result total=%u unique=%u dup=%u invalid_job=%u ver_or=%04x ver_min=%04x ver_max=%04x top_core=%u/%u top_small=%u/%u",')
p.write_text(s)
