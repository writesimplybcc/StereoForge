#ifndef INTER_VIEW_ENCODER_H
#define INTER_VIEW_ENCODER_H

#include "stereoforge_mvc.h"

int ive_estimate_disparity_frame(
    const stereoforge_mvc_config_t* cfg,
    const uint8_t* right_y,
    const uint8_t* left_recon_y,
    stereoforge_disparity_t* out_disparity
);

int ive_encode_dependent_slice(
    const stereoforge_mvc_config_t* cfg,
    const stereoforge_frame_t* right_frame,
    const stereoforge_frame_t* left_recon_frame,
    int frame_num,
    uint8_t* out_buf,
    size_t max_out
);

#endif /* INTER_VIEW_ENCODER_H */
