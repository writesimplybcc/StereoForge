#include "stereoforge_mvc.h"
#include "annex_h_writer.h"
#include "inter_view_encoder.h"
#include <stdlib.h>
#include <string.h>

struct stereoforge_mvc_ctx {
    stereoforge_mvc_config_t cfg;
    int frame_count;
    uint8_t* left_recon_buffer;
    size_t luma_size;
};

STEREOFORGE_API stereoforge_mvc_ctx_t* stereoforge_mvc_init(const stereoforge_mvc_config_t* cfg) {
    if (!cfg || cfg->width <= 0 || cfg->height <= 0) {
        return NULL;
    }

    stereoforge_mvc_ctx_t* ctx = (stereoforge_mvc_ctx_t*)calloc(1, sizeof(stereoforge_mvc_ctx_t));
    if (!ctx) return NULL;

    ctx->cfg = *cfg;
    if (ctx->cfg.view_id_dep == 0) ctx->cfg.view_id_dep = 1;
    if (ctx->cfg.fps_num <= 0) ctx->cfg.fps_num = 24000;
    if (ctx->cfg.fps_den <= 0) ctx->cfg.fps_den = 1001;

    ctx->luma_size = (size_t)cfg->width * (size_t)cfg->height;
    ctx->left_recon_buffer = (uint8_t*)malloc(ctx->luma_size);
    if (!ctx->left_recon_buffer) {
        free(ctx);
        return NULL;
    }
    memset(ctx->left_recon_buffer, 128, ctx->luma_size);
    ctx->frame_count = 0;

    return ctx;
}

STEREOFORGE_API int stereoforge_mvc_get_subset_sps(
    stereoforge_mvc_ctx_t* ctx,
    uint8_t* out_buf,
    size_t max_len
) {
    if (!ctx || !out_buf) return -1;
    int level = ctx->cfg.strict_bluray ? 41 : 41;
    return annex_h_write_subset_sps(
        out_buf,
        max_len,
        ctx->cfg.width,
        ctx->cfg.height,
        level,
        ctx->cfg.view_id_base,
        ctx->cfg.view_id_dep
    );
}

STEREOFORGE_API int stereoforge_mvc_encode_frame(
    stereoforge_mvc_ctx_t* ctx,
    const stereoforge_frame_t* right_frame,
    const stereoforge_frame_t* left_recon_frame,
    stereoforge_packet_t* out_packet
) {
    if (!ctx || !right_frame || !out_packet || !out_packet->data) {
        return -1;
    }

    // Cache left reconstructed luma for inter-view reference
    if (left_recon_frame && left_recon_frame->y_plane) {
        memcpy(ctx->left_recon_buffer, left_recon_frame->y_plane, ctx->luma_size);
    }

    int bytes_written = ive_encode_dependent_slice(
        &ctx->cfg,
        right_frame,
        left_recon_frame,
        ctx->frame_count,
        out_packet->data,
        out_packet->capacity
    );

    if (bytes_written > 0) {
        out_packet->size = (size_t)bytes_written;
        out_packet->pts = right_frame->pts;
        out_packet->dts = right_frame->dts;
        out_packet->is_keyframe = right_frame->is_keyframe;
        ctx->frame_count++;
        return 0;
    }
    return -2;
}

STEREOFORGE_API int stereoforge_mvc_estimate_disparity(
    stereoforge_mvc_ctx_t* ctx,
    const uint8_t* right_y,
    const uint8_t* left_y,
    stereoforge_disparity_t* out_disparity
) {
    if (!ctx || !right_y || !left_y || !out_disparity) return -1;
    return ive_estimate_disparity_frame(&ctx->cfg, right_y, left_y, out_disparity);
}

STEREOFORGE_API void stereoforge_mvc_close(stereoforge_mvc_ctx_t* ctx) {
    if (ctx) {
        if (ctx->left_recon_buffer) {
            free(ctx->left_recon_buffer);
        }
        free(ctx);
    }
}

STEREOFORGE_API const char* stereoforge_mvc_version(void) {
    return "0.1.0-alpha";
}
