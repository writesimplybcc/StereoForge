#ifndef ANNEX_H_WRITER_H
#define ANNEX_H_WRITER_H

#include <stdint.h>
#include <stddef.h>

typedef struct {
    uint8_t* buf;
    size_t capacity;
    size_t byte_pos;
    uint8_t cur_byte;
    int bit_pos; /**< 0 to 7 */
} bs_writer_t;

void bs_init(bs_writer_t* bs, uint8_t* buf, size_t capacity);
void bs_write_bit(bs_writer_t* bs, int bit);
void bs_write_bits(bs_writer_t* bs, uint32_t val, int num_bits);
void bs_write_ue(bs_writer_t* bs, uint32_t val);
void bs_write_se(bs_writer_t* bs, int32_t val);
void bs_write_trailing_bits(bs_writer_t* bs);
size_t bs_flush_ebsp(bs_writer_t* bs, uint8_t* out_ebsp, size_t max_out);

int annex_h_write_subset_sps(
    uint8_t* out_buf,
    size_t max_len,
    int width,
    int height,
    int level_idc,
    int view_id_base,
    int view_id_dep
);

int annex_h_pack_nal20_header(
    uint8_t out_ext[4],
    int nal_ref_idc,
    int is_anchor,
    int view_id
);

int annex_h_write_prefix_nal(
    uint8_t* out_buf,
    size_t max_len,
    int view_id
);

#endif /* ANNEX_H_WRITER_H */
