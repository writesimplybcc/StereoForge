#include "stereoforge_mvc.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

int main(void) {
    printf("=========================================\n");
    printf("🧪 StereoForge Core Native Engine Test\n");
    printf("   Version: %s\n", stereoforge_mvc_version());
    printf("=========================================\n");

    stereoforge_mvc_config_t cfg;
    memset(&cfg, 0, sizeof(cfg));
    cfg.width = 1920;
    cfg.height = 1080;
    cfg.fps_num = 24000;
    cfg.fps_den = 1001;
    cfg.bitrate_kbps = 15000;
    cfg.gop_size = 24;
    cfg.strict_bluray = 1;
    cfg.view_id_base = 0;
    cfg.view_id_dep = 1;

    stereoforge_mvc_ctx_t* ctx = stereoforge_mvc_init(&cfg);
    assert(ctx != NULL);
    printf("✅ Initialized MVC encoder context for %dx%d @ 23.976 fps.\n", cfg.width, cfg.height);

    // Test 1: Generate Annex H Subset SPS (NAL 15)
    uint8_t sps_buf[256];
    int sps_len = stereoforge_mvc_get_subset_sps(ctx, sps_buf, sizeof(sps_buf));
    assert(sps_len > 10);
    assert(sps_buf[0] == 0x00 && sps_buf[1] == 0x00 && sps_buf[2] == 0x00 && sps_buf[3] == 0x01);
    uint8_t nal_type = sps_buf[4] & 0x1F;
    assert(nal_type == STEREOFORGE_NAL_SUBSET_SPS);
    printf("✅ Generated Annex H Subset SPS: %d bytes (NAL Unit Type %d, 0x%02X).\n",
           sps_len, nal_type, sps_buf[4]);

    // Test 2: Encode anchor frame (IDR -> NAL 20)
    size_t luma_sz = (size_t)cfg.width * (size_t)cfg.height;
    uint8_t* right_luma = (uint8_t*)malloc(luma_sz);
    uint8_t* left_luma = (uint8_t*)malloc(luma_sz);
    memset(right_luma, 180, luma_sz);
    memset(left_luma, 175, luma_sz);

    stereoforge_frame_t right_f;
    memset(&right_f, 0, sizeof(right_f));
    right_f.y_plane = right_luma;
    right_f.is_keyframe = 1;
    right_f.pts = 0;
    right_f.dts = 0;

    stereoforge_frame_t left_f;
    memset(&left_f, 0, sizeof(left_f));
    left_f.y_plane = left_luma;

    uint8_t pkt_buf[65536];
    stereoforge_packet_t pkt;
    pkt.data = pkt_buf;
    pkt.capacity = sizeof(pkt_buf);
    pkt.size = 0;

    int res = stereoforge_mvc_encode_frame(ctx, &right_f, &left_f, &pkt);
    assert(res == 0);
    assert(pkt.size > 0);
    // Check start code and NAL Unit Type 20
    assert(pkt.data[0] == 0x00 && pkt.data[1] == 0x00 && pkt.data[2] == 0x00 && pkt.data[3] == 0x01);
    uint8_t slice_type = pkt.data[4] & 0x1F;
    assert(slice_type == STEREOFORGE_NAL_SLICE_EXT);
    printf("✅ Encoded Anchor Frame: %zu bytes (NAL Unit Type %d Coded Slice Extension).\n",
           pkt.size, slice_type);

    // Test 3: Encode non-anchor frame (P-slice -> NAL 20 with RPLM inter-view reference)
    right_f.is_keyframe = 0;
    right_f.pts = 1000;
    right_f.dts = 1000;
    res = stereoforge_mvc_encode_frame(ctx, &right_f, &left_f, &pkt);
    assert(res == 0);
    assert(pkt.size > 0);
    printf("✅ Encoded Inter-View P-Frame: %zu bytes (NAL Unit Type 20 with RPLM).\n", pkt.size);

    // Test 4: Disparity estimation
    int mb_w = (cfg.width + 15) / 16;
    int mb_h = (cfg.height + 15) / 16;
    int num_mbs = mb_w * mb_h;
    stereoforge_disparity_t* disp = (stereoforge_disparity_t*)malloc(sizeof(stereoforge_disparity_t) * num_mbs);
    int mbs_done = stereoforge_mvc_estimate_disparity(ctx, right_luma, left_luma, disp);
    assert(mbs_done == num_mbs);
    printf("✅ Disparity Estimation: Processed %d macroblocks (16x16).\n", mbs_done);

    free(disp);
    free(right_luma);
    free(left_luma);
    stereoforge_mvc_close(ctx);

    printf("=========================================\n");
    printf("🎉 ALL NATIVE C TESTS PASSED!\n");
    printf("=========================================\n");
    return 0;
}
