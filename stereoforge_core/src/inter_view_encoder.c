#include "inter_view_encoder.h"
#include "annex_h_writer.h"
#include <stdlib.h>
#include <string.h>

static inline uint32_t sad_mb(
    const uint8_t* cur, int cur_stride,
    const uint8_t* ref, int ref_stride,
    int valid_w, int valid_h
) {
    uint32_t sum = 0;
    for (int y = 0; y < valid_h; y++) {
        const uint8_t* c = cur + y * cur_stride;
        const uint8_t* r = ref + y * ref_stride;
        for (int x = 0; x < valid_w; x++) {
            int diff = (int)c[x] - (int)r[x];
            sum += (diff < 0) ? -diff : diff;
        }
    }
    return sum;
}

int ive_estimate_disparity_frame(
    const stereoforge_mvc_config_t* cfg,
    const uint8_t* right_y,
    const uint8_t* left_recon_y,
    stereoforge_disparity_t* out_disparity
) {
    int w = cfg->width;
    int h = cfg->height;
    int mb_w = (w + 15) / 16;
    int mb_h = (h + 15) / 16;
    int mb_idx = 0;

    for (int mb_y = 0; mb_y < mb_h; mb_y++) {
        int y_pos = mb_y * 16;
        int valid_h = (y_pos + 16 <= h) ? 16 : (h - y_pos);

        for (int mb_x = 0; mb_x < mb_w; mb_x++) {
            int x_pos = mb_x * 16;
            int valid_w = (x_pos + 16 <= w) ? 16 : (w - x_pos);
            const uint8_t* cur_mb = right_y + y_pos * w + x_pos;

            uint32_t best_sad = 0xFFFFFFFF;
            int16_t best_dx = 0;

            // Search window: horizontal parallax dx in [-48, +8]
            int min_dx = -48;
            if (min_dx < -x_pos) min_dx = -x_pos;
            int max_dx = 8;
            if (max_dx > (w - valid_w - x_pos)) max_dx = w - valid_w - x_pos;

            for (int dx = min_dx; dx <= max_dx; dx += 2) {
                const uint8_t* ref_mb = left_recon_y + y_pos * w + (x_pos + dx);
                uint32_t s = sad_mb(cur_mb, w, ref_mb, w, valid_w, valid_h);
                if (s < best_sad) {
                    best_sad = s;
                    best_dx = (int16_t)dx;
                }
            }

            out_disparity[mb_idx].dx = best_dx;
            out_disparity[mb_idx].dy = 0;
            out_disparity[mb_idx].sad = best_sad;
            mb_idx++;
        }
    }
    return mb_idx;
}

int ive_encode_dependent_slice(
    const stereoforge_mvc_config_t* cfg,
    const stereoforge_frame_t* right_frame,
    const stereoforge_frame_t* left_recon_frame,
    int frame_num,
    uint8_t* out_buf,
    size_t max_out
) {
    if (max_out < 1024) return -1;

    // Write Annex B Start Code (4 bytes)
    out_buf[0] = 0x00; out_buf[1] = 0x00; out_buf[2] = 0x00; out_buf[3] = 0x01;

    // Pack NAL Unit Type 20 header + MVC Extension (4 bytes)
    int nal_ref_idc = right_frame->is_keyframe ? 3 : 2;
    annex_h_pack_nal20_header(out_buf + 4, nal_ref_idc, right_frame->is_keyframe, cfg->view_id_dep);

    // Dynamic RBSP payload buffer
    size_t rbsp_cap = max_out;
    uint8_t* rbsp = (uint8_t*)malloc(rbsp_cap);
    if (!rbsp) return -1;

    bs_writer_t bs;
    bs_init(&bs, rbsp, rbsp_cap);

    // slice_header()
    bs_write_ue(&bs, 0); // first_mb_in_slice = 0
    if (right_frame->is_keyframe) {
        bs_write_ue(&bs, 7); // slice_type = I-slice
    } else {
        bs_write_ue(&bs, 5); // slice_type = P-slice
    }
    bs_write_ue(&bs, 0); // pic_parameter_set_id = 0
    bs_write_bits(&bs, (uint32_t)(frame_num & 0x0F), 4); // frame_num (4 bits)

    if (right_frame->is_keyframe) {
        bs_write_ue(&bs, (uint32_t)(frame_num % 65536)); // idr_pic_id
    }
    // pic_order_cnt_lsb (6 bits)
    bs_write_bits(&bs, (uint32_t)((frame_num * 2) & 0x3F), 6);

    // Reference Picture List Modification (RPLM) for MVC inter-view reference
    if (!right_frame->is_keyframe) {
        bs_write_bit(&bs, 1); // ref_pic_list_modification_flag_l0 = 1
        // modification_of_pic_nums_idc = 4 (inter-view reference injection)
        bs_write_ue(&bs, 4);
        bs_write_ue(&bs, (uint32_t)cfg->view_id_base); // target view_id = 0 (Left Eye)
        bs_write_ue(&bs, 3); // end of list modification (idc = 3)
    } else {
        bs_write_bit(&bs, 0); // no list modification on anchor
    }

    // slice_qp_delta
    bs_write_se(&bs, 0);

    // =========================================================================
    // Slice Data: Macroblock disparity compensation & skip coding loop
    // =========================================================================
    int w = cfg->width;
    int h = cfg->height;
    int mb_w = (w + 15) / 16;
    int mb_h = (h + 15) / 16;
    int total_mbs = mb_w * mb_h;

    const uint8_t* r_y = right_frame->y_plane;
    const uint8_t* l_y = (left_recon_frame && left_recon_frame->y_plane) ? left_recon_frame->y_plane : r_y;

    if (!right_frame->is_keyframe && r_y && l_y) {
        // P-slice CAVLC macroblock coding with inter-view disparity vectors
        int skip_run = 0;
        int prev_dx = 0;

        for (int mb_idx = 0; mb_idx < total_mbs; mb_idx++) {
            int mb_y = mb_idx / mb_w;
            int mb_x = mb_idx % mb_w;
            int x_pos = mb_x * 16;
            int y_pos = mb_y * 16;
            int valid_w = (x_pos + 16 <= w) ? 16 : (w - x_pos);
            int valid_h = (y_pos + 16 <= h) ? 16 : (h - y_pos);

            const uint8_t* cur_mb = r_y + y_pos * w + x_pos;

            // Search best horizontal disparity against Left Eye
            uint32_t best_sad = 0xFFFFFFFF;
            int16_t best_dx = 0;
            int min_dx = -32;
            if (min_dx < -x_pos) min_dx = -x_pos;
            int max_dx = 8;
            if (max_dx > (w - valid_w - x_pos)) max_dx = w - valid_w - x_pos;

            for (int dx = min_dx; dx <= max_dx; dx += 2) {
                const uint8_t* ref_mb = l_y + y_pos * w + (x_pos + dx);
                uint32_t s = sad_mb(cur_mb, w, ref_mb, w, valid_w, valid_h);
                if (s < best_sad) {
                    best_sad = s;
                    best_dx = (int16_t)dx;
                }
            }

            // If block matches well with zero disparity shift, accumulate into skip run
            if (best_dx == 0 && best_sad < 256) {
                skip_run++;
            } else {
                // Flush any accumulated skip run
                bs_write_ue(&bs, (uint32_t)skip_run);
                skip_run = 0;

                // mb_type = 0 (P_L0_16x16)
                bs_write_ue(&bs, 0);
                // ref_idx_l0 = 0 (Left Eye reference in RefPicList0)
                bs_write_ue(&bs, 0);
                // mvd_l0 = (dx - prev_dx, dy)
                bs_write_se(&bs, (int32_t)(best_dx - prev_dx));
                bs_write_se(&bs, 0);
                prev_dx = best_dx;

                // coded_block_pattern (cbp): 0 = clean match, no residual transform needed
                bs_write_ue(&bs, 0);
            }
        }
        if (skip_run > 0) {
            bs_write_ue(&bs, (uint32_t)skip_run);
        }
    } else {
        // I-slice / Anchor frame macroblock coding
        for (int mb_idx = 0; mb_idx < total_mbs; mb_idx++) {
            // mb_type = 1 (I_16x16_0_0_0)
            bs_write_ue(&bs, 1);
            // cbp = 0
            bs_write_ue(&bs, 0);
        }
    }

    bs_write_trailing_bits(&bs);

    size_t ebsp_len = bs_flush_ebsp(&bs, out_buf + 8, max_out - 8);
    free(rbsp);
    return (int)(8 + ebsp_len);
}
