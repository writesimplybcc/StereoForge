#include "inter_view_encoder.h"
#include "annex_h_writer.h"
#include <stdlib.h>
#include <string.h>

static inline uint32_t sad_16x16(
    const uint8_t* cur, int cur_stride,
    const uint8_t* ref, int ref_stride
) {
    uint32_t sum = 0;
    for (int y = 0; y < 16; y++) {
        const uint8_t* c = cur + y * cur_stride;
        const uint8_t* r = ref + y * ref_stride;
        for (int x = 0; x < 16; x++) {
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
        for (int mb_x = 0; mb_x < mb_w; mb_x++) {
            int x_pos = mb_x * 16;
            const uint8_t* cur_mb = right_y + y_pos * w + x_pos;

            uint32_t best_sad = 0xFFFFFFFF;
            int16_t best_dx = 0;

            // Search window: horizontal parallax dx in [-48, +4]
            int min_dx = (x_pos >= 48) ? -48 : -x_pos;
            int max_dx = (x_pos + 16 + 4 <= w) ? 4 : (w - x_pos - 16);

            for (int dx = min_dx; dx <= max_dx; dx += 2) {
                const uint8_t* ref_mb = left_recon_y + y_pos * w + (x_pos - dx);
                uint32_t s = sad_16x16(cur_mb, w, ref_mb, w);
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
    (void)left_recon_frame;
    if (max_out < 128) return -1;

    // Write Annex B Start Code
    out_buf[0] = 0x00; out_buf[1] = 0x00; out_buf[2] = 0x00; out_buf[3] = 0x01;

    // Pack NAL Unit Type 20 header + MVC Extension (4 bytes)
    int nal_ref_idc = right_frame->is_keyframe ? 3 : 2;
    annex_h_pack_nal20_header(out_buf + 4, nal_ref_idc, right_frame->is_keyframe, cfg->view_id_dep);

    // Slice RBSP payload writer
    uint8_t rbsp[2048];
    bs_writer_t bs;
    bs_init(&bs, rbsp, sizeof(rbsp));

    // slice_header()
    bs_write_ue(&bs, 0); // first_mb_in_slice = 0
    if (right_frame->is_keyframe) {
        bs_write_ue(&bs, 7); // slice_type = I-slice (7 = all I)
    } else {
        bs_write_ue(&bs, 5); // slice_type = P-slice (5 = all P)
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
    bs_write_trailing_bits(&bs);

    size_t ebsp_len = bs_flush_ebsp(&bs, out_buf + 8, max_out - 8);
    return (int)(8 + ebsp_len);
}
