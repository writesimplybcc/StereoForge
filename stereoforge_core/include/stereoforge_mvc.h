/**
 * @file stereoforge_mvc.h
 * @brief Public C API for StereoForge True Inter-View MVC Core Engine.
 *
 * Implements Phase 1 of StereoForge Core:
 * - Annex H Multiview Video Coding (MVC) bitstream synthesis.
 * - Hardware Base View reconstruction buffer ingestion.
 * - Inter-view reference frame injection into RefPicList0.
 * - Native Subset SPS (NAL 15) and Coded Slice Extension (NAL 20) emission.
 */

#ifndef STEREOFORGE_MVC_H
#define STEREOFORGE_MVC_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32) || defined(__CYGWIN__)
    #if defined(STEREOFORGE_EXPORTS)
        #define STEREOFORGE_API __declspec(dllexport)
    #else
        #define STEREOFORGE_API __declspec(dllimport)
    #endif
#else
    #if defined(__GNUC__) && __GNUC__ >= 4
        #define STEREOFORGE_API __attribute__((visibility("default")))
    #else
        #define STEREOFORGE_API
    #endif
#endif

/** NAL Unit Types */
#define STEREOFORGE_NAL_SLICE_NON_IDR  1
#define STEREOFORGE_NAL_SLICE_IDR      5
#define STEREOFORGE_NAL_SEI            6
#define STEREOFORGE_NAL_SPS            7
#define STEREOFORGE_NAL_PPS            8
#define STEREOFORGE_NAL_PREFIX        14
#define STEREOFORGE_NAL_SUBSET_SPS    15
#define STEREOFORGE_NAL_SLICE_EXT     20

/** Configuration for MVC encoder instance */
typedef struct {
    int width;
    int height;
    int fps_num;
    int fps_den;
    int bitrate_kbps;
    int gop_size;
    int strict_bluray;     /**< 1 = Enforce Blu-ray Level 4.1 & VBV buffer limits */
    int view_id_base;      /**< Default: 0 (Left Eye) */
    int view_id_dep;       /**< Default: 1 (Right Eye) */
} stereoforge_mvc_config_t;

/** Frame input container */
typedef struct {
    const uint8_t* y_plane;
    const uint8_t* u_plane;
    const uint8_t* v_plane;
    int stride_y;
    int stride_uv;
    int64_t pts;
    int64_t dts;
    int is_keyframe;       /**< 1 if IDR/anchor frame, 0 otherwise */
} stereoforge_frame_t;

/** Output packet container */
typedef struct {
    uint8_t* data;
    size_t size;
    size_t capacity;
    int64_t pts;
    int64_t dts;
    int is_keyframe;
} stereoforge_packet_t;

/** Disparity vector */
typedef struct {
    int16_t dx;            /**< Horizontal disparity offset in pixels */
    int16_t dy;            /**< Vertical residual offset (typically ~0) */
    uint32_t sad;          /**< Sum of Absolute Differences error metric */
} stereoforge_disparity_t;

/** Opaque encoder context */
typedef struct stereoforge_mvc_ctx stereoforge_mvc_ctx_t;

/**
 * @brief Initializes the native MVC encoder instance.
 * @param cfg Encoder configuration parameters.
 * @return Pointer to opaque context, or NULL on failure.
 */
STEREOFORGE_API stereoforge_mvc_ctx_t* stereoforge_mvc_init(const stereoforge_mvc_config_t* cfg);

/**
 * @brief Generates Annex H Subset SPS (NAL Unit Type 15) bitstream header.
 * @param ctx Encoder context.
 * @param out_buf Output buffer for the NAL unit (including 4-byte start code).
 * @param max_len Maximum capacity of out_buf.
 * @return Number of bytes written, or negative error code.
 */
STEREOFORGE_API int stereoforge_mvc_get_subset_sps(
    stereoforge_mvc_ctx_t* ctx,
    uint8_t* out_buf,
    size_t max_len
);

/**
 * @brief Encodes a Dependent View (Right Eye) frame using the Left Eye as inter-view reference.
 *
 * @param ctx Encoder context.
 * @param right_frame Raw Right Eye input frame.
 * @param left_recon_frame Reconstructed Left Eye frame (from Base View decoder).
 * @param out_packet Output packet to receive Annex H NAL 20 slices.
 * @return 0 on success, negative error code on failure.
 */
STEREOFORGE_API int stereoforge_mvc_encode_frame(
    stereoforge_mvc_ctx_t* ctx,
    const stereoforge_frame_t* right_frame,
    const stereoforge_frame_t* left_recon_frame,
    stereoforge_packet_t* out_packet
);

/**
 * @brief Computes fast block-based horizontal disparity between Left and Right frames.
 *
 * @param ctx Encoder context.
 * @param right_y Luma plane of Right Eye.
 * @param left_y Luma plane of Left Eye.
 * @param out_disparity Array of disparity vectors (size: (width/16) * (height/16)).
 * @return Number of macroblocks processed, or negative on error.
 */
STEREOFORGE_API int stereoforge_mvc_estimate_disparity(
    stereoforge_mvc_ctx_t* ctx,
    const uint8_t* right_y,
    const uint8_t* left_y,
    stereoforge_disparity_t* out_disparity
);

/**
 * @brief Closes and frees the encoder context.
 * @param ctx Encoder context to destroy.
 */
STEREOFORGE_API void stereoforge_mvc_close(stereoforge_mvc_ctx_t* ctx);

/**
 * @brief Returns the version string of the stereoforge-core library.
 */
STEREOFORGE_API const char* stereoforge_mvc_version(void);

#ifdef __cplusplus
}
#endif

#endif /* STEREOFORGE_MVC_H */
