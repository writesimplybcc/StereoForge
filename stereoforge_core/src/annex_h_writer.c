#include "annex_h_writer.h"
#include <string.h>

void bs_init(bs_writer_t* bs, uint8_t* buf, size_t capacity) {
    bs->buf = buf;
    bs->capacity = capacity;
    bs->byte_pos = 0;
    bs->cur_byte = 0;
    bs->bit_pos = 0;
}

void bs_write_bit(bs_writer_t* bs, int bit) {
    bs->cur_byte = (uint8_t)((bs->cur_byte << 1) | (bit ? 1 : 0));
    bs->bit_pos++;
    if (bs->bit_pos == 8) {
        if (bs->byte_pos < bs->capacity) {
            bs->buf[bs->byte_pos++] = bs->cur_byte;
        }
        bs->cur_byte = 0;
        bs->bit_pos = 0;
    }
}

void bs_write_bits(bs_writer_t* bs, uint32_t val, int num_bits) {
    for (int i = num_bits - 1; i >= 0; i--) {
        bs_write_bit(bs, (val >> i) & 1);
    }
}

void bs_write_ue(bs_writer_t* bs, uint32_t val) {
    uint32_t x = val + 1;
    int leading_zeros = 0;
    uint32_t temp = x;
    while (temp > 1) {
        temp >>= 1;
        leading_zeros++;
    }
    for (int i = 0; i < leading_zeros; i++) {
        bs_write_bit(bs, 0);
    }
    bs_write_bits(bs, x, leading_zeros + 1);
}

void bs_write_se(bs_writer_t* bs, int32_t val) {
    if (val <= 0) {
        bs_write_ue(bs, (uint32_t)(-2 * val));
    } else {
        bs_write_ue(bs, (uint32_t)(2 * val - 1));
    }
}

void bs_write_trailing_bits(bs_writer_t* bs) {
    bs_write_bit(bs, 1);
    while (bs->bit_pos != 0) {
        bs_write_bit(bs, 0);
    }
}

size_t bs_flush_ebsp(bs_writer_t* bs, uint8_t* out_ebsp, size_t max_out) {
    size_t in_len = bs->byte_pos;
    if (bs->bit_pos > 0 && in_len < bs->capacity) {
        bs->buf[in_len++] = (uint8_t)(bs->cur_byte << (8 - bs->bit_pos));
    }

    size_t out_len = 0;
    int zeros = 0;
    for (size_t i = 0; i < in_len; i++) {
        uint8_t b = bs->buf[i];
        if (zeros == 2 && (b <= 3)) {
            if (out_len < max_out) out_ebsp[out_len++] = 0x03;
            zeros = 0;
        }
        if (out_len < max_out) out_ebsp[out_len++] = b;
        if (b == 0x00) zeros++; else zeros = 0;
    }
    return out_len;
}

int annex_h_write_subset_sps(
    uint8_t* out_buf,
    size_t max_len,
    int width,
    int height,
    int level_idc,
    int view_id_base,
    int view_id_dep
) {
    if (max_len < 64) return -1;

    uint8_t raw_rbsp[256];
    bs_writer_t bs;
    bs_init(&bs, raw_rbsp, sizeof(raw_rbsp));

    int width_mbs = (width + 15) / 16;
    int height_mbs = (height + 15) / 16;
    int crop_bottom = (height_mbs * 16 - height) / 2;

    // profile_idc: Stereo High Profile (128)
    bs_write_bits(&bs, 128, 8);
    // constraint_set1_flag = 1
    bs_write_bit(&bs, 0); bs_write_bit(&bs, 1); bs_write_bit(&bs, 0);
    bs_write_bit(&bs, 0); bs_write_bit(&bs, 0); bs_write_bit(&bs, 0);
    bs_write_bits(&bs, 0, 2); // reserved_zero_2bits
    bs_write_bits(&bs, (uint32_t)level_idc, 8);
    bs_write_ue(&bs, 0); // sps_id = 0

    // High profile syntax elements
    bs_write_ue(&bs, 1); // chroma_format_idc (4:2:0)
    bs_write_ue(&bs, 0); // bit_depth_luma_minus8
    bs_write_ue(&bs, 0); // bit_depth_chroma_minus8
    bs_write_bit(&bs, 0); // qpprime_y_zero_transform_bypass_flag
    bs_write_bit(&bs, 0); // seq_scaling_matrix_present_flag

    bs_write_ue(&bs, 0); // log2_max_frame_num_minus4
    bs_write_ue(&bs, 0); // pic_order_cnt_type
    bs_write_ue(&bs, 2); // log2_max_pic_order_cnt_lsb_minus4
    bs_write_ue(&bs, 4); // max_num_ref_frames
    bs_write_bit(&bs, 0); // gaps_in_frame_num_value_allowed_flag
    bs_write_ue(&bs, (uint32_t)(width_mbs - 1));
    bs_write_ue(&bs, (uint32_t)(height_mbs - 1));
    bs_write_bit(&bs, 1); // frame_mbs_only_flag
    bs_write_bit(&bs, 1); // direct_8x8_inference_flag

    if (crop_bottom > 0) {
        bs_write_bit(&bs, 1);
        bs_write_ue(&bs, 0); bs_write_ue(&bs, 0); bs_write_ue(&bs, 0);
        bs_write_ue(&bs, (uint32_t)crop_bottom);
    } else {
        bs_write_bit(&bs, 0);
    }
    bs_write_bit(&bs, 0); // vui_parameters_present_flag

    // seq_parameter_set_mvc_extension()
    bs_write_bit(&bs, 1); // bit_equal_to_one
    bs_write_ue(&bs, 1);  // num_views_minus1 = 1 (Stereo)
    bs_write_ue(&bs, (uint32_t)view_id_base);
    bs_write_ue(&bs, (uint32_t)view_id_dep);

    // Anchor references: View 1 references View 0
    bs_write_ue(&bs, 1); // num_anchor_refs_l0[1] = 1
    bs_write_ue(&bs, (uint32_t)view_id_base);
    bs_write_ue(&bs, 0); // num_anchor_refs_l1[1] = 0

    // Non-anchor references: View 1 references View 0
    bs_write_ue(&bs, 1); // num_non_anchor_refs_l0[1] = 1
    bs_write_ue(&bs, (uint32_t)view_id_base);
    bs_write_ue(&bs, 0); // num_non_anchor_refs_l1[1] = 0

    // Level values
    bs_write_ue(&bs, 0); // num_level_values_signalled_minus1 = 0
    bs_write_bits(&bs, (uint32_t)level_idc, 8);
    bs_write_ue(&bs, 0); // num_applicable_ops_minus1 = 0
    bs_write_bits(&bs, 0, 3);
    bs_write_ue(&bs, 1);
    bs_write_ue(&bs, (uint32_t)view_id_base);
    bs_write_ue(&bs, (uint32_t)view_id_dep);
    bs_write_ue(&bs, 1);

    bs_write_bit(&bs, 0); // mvc_vui_parameters_present_flag
    bs_write_trailing_bits(&bs);

    // Write Annex B start code + NAL header (nal_ref_idc=3, nal_unit_type=15)
    out_buf[0] = 0x00; out_buf[1] = 0x00; out_buf[2] = 0x00; out_buf[3] = 0x01;
    out_buf[4] = (uint8_t)((3 << 5) | 15); // 0x6F

    size_t ebsp_len = bs_flush_ebsp(&bs, out_buf + 5, max_len - 5);
    return (int)(5 + ebsp_len);
}

int annex_h_pack_nal20_header(
    uint8_t out_ext[4],
    int nal_ref_idc,
    int is_anchor,
    int view_id
) {
    // Byte 0: [nal_ref_idc: 2 bits][nal_unit_type: 20]
    out_ext[0] = (uint8_t)(((nal_ref_idc & 0x03) << 5) | 20);

    // MVC NAL Extension Header (3 bytes):
    // Byte 1: [svc_ext: 0][non_idr: 1 bit][priority_id: 6 bits]
    int non_idr_flag = is_anchor ? 0 : 1;
    out_ext[1] = (uint8_t)((non_idr_flag << 6) | 0x00);

    // Byte 2: view_id high 8 bits
    out_ext[2] = (uint8_t)((view_id >> 2) & 0xFF);

    // Byte 3: [view_id low 2 bits][temporal_id: 3 bits][anchor: 1 bit][inter_view: 1 bit][reserved: 1]
    int anchor_pic_flag = is_anchor ? 1 : 0;
    int inter_view_flag = 1; // Always True for dependent stereoscopic view
    out_ext[3] = (uint8_t)(
        ((view_id & 0x03) << 6)
        | (0 << 3)
        | (anchor_pic_flag << 2)
        | (inter_view_flag << 1)
        | 0x01
    );

    return 4;
}
