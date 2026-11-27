# StereoForge Core: x264 MVC Inter-View Reference Injection Specification

> **Phase 1 Technical Architecture: True Multiview Video Coding (ITU-T H.264 Annex H)**

---

## 1. Objective
Replace simulcast Right Eye encoding with genuine **Inter-View Reference Injection** inside an x264-derived encoder engine, enabling macroblocks in the Dependent View (Right Eye) to directly reference reconstructed Base View (Left Eye) frames within `RefPicList0`.

---

## 2. Core Mechanism: Disparity-Compensated `RefPicList0` Injection

In standard x264 (2D temporal coding), `h->fref[0]` contains only preceding temporal frames:
```
RefPicList0 = [ Frame_{t-1}, Frame_{t-2}, ... ]
```

In StereoForge MVC, for every frame $t$ of View 1 (Right Eye), the reconstructed frame $t$ of View 0 (Left Eye) is injected:
```
RefPicList0 = [ Reconstructed_Base_Frame_{t}, Frame_{t-1}, ... ]
```

### 2.1. Code Modifications Required in x264:

#### A. Parameter & Picture Struct Extensions (`x264.h`)
```c
typedef struct x264_param_t {
    // Standard x264 params...
    int b_mvc;                  // 1 = Enable Annex H MVC mode
    int i_view_id;              // 0 = Base View (Left), 1 = Dependent View (Right)
    int i_view_order_index;     // 0 or 1
} x264_param_t;

typedef struct x264_picture_t {
    // Standard x264 picture fields...
    x264_picture_t *p_interview_ref; // Pointer to reconstructed Left Eye YUV plate
} x264_picture_t;
```

#### B. Reference Picture List Construction (`encoder/slicetype.c`)
In `x264_reference_build_list0()`:
```c
if (h->param.b_mvc && h->param.i_view_id == 1 && h->fref_interview) {
    // Inject reconstructed Left Eye frame into index 0 or 1 of L0
    h->fref[0][h->i_ref[0]] = h->fref_interview;
    h->fref[0][h->i_ref[0]]->b_inter_view = 1;
    h->fref[0][h->i_ref[0]]->i_view_id = 0;
    h->i_ref[0]++;
}
```

#### C. Macroblock Motion & Disparity Estimation (`encoder/me.c`)
No modification needed to the core motion estimation SIMD loops (`x264_me_search_ref`):
* x264 naturally searches all reference frames in `RefPicList0`.
* For regions of the Right Eye matching the Left Eye, the Rate-Distortion optimization (RDO / SATD) automatically selects the Left Eye reference frame whenever:
  $$\text{Cost}(\text{Disparity Vector}) < \text{Cost}(\text{Temporal Motion Vector})$$

#### D. Bitstream & NAL Generation (`encoder/set.c` & `encoder/encoder.c`)
* Emit **Subset SPS (NAL 15)** at stream initiation and before IDR anchors.
* Convert slice NAL units from Type 1 / 5 into **NAL Unit Type 20** (`NAL_SLICE_EXT`).
* Set `nal_unit_header_mvc_extension()`:
  - `view_id = 1`
  - `inter_view_flag = 1`
  - `anchor_pic_flag = (slice_type == IDR)`
* Emit **RPLM commands** (`modification_of_pic_nums_idc = 4`) signaling the inter-view reference.

---

## 3. Submodule & CMake Architecture

```text
stereoforge_core/
├── CMakeLists.txt              # Orchestrates native build & links libx264-mvc
├── include/
│   └── stereoforge_mvc.h       # Clean public C API
├── src/
│   ├── stereoforge_mvc.c       # Wrapper context & frame pipeline
│   ├── annex_h_writer.c        # Subset SPS (NAL 15) & Prefix (NAL 14) writer
│   └── inter_view_encoder.c    # Frame cache & RPLM injector
└── subprojects/
    └── x264/                   # Stripped, minimal x264-mvc core
```

---

## 4. Performance & Compression Targets

| Metric | Simulcast (Current) | True MVC (x264 Core) |
| :--- | :--- | :--- |
| **Dependent View Bitrate** | 7.5 – 12.0 Mbps | **4.5 – 7.2 Mbps (35–45% savings)** |
| **Combined Disc Bitrate** | ~35 Mbps | **~24 Mbps** |
| **Visual Quality (PSNR)** | 42.1 dB | **42.0 dB (Identical visual parity)** |
| **Player Compatibility** | 3D Blu-ray / VLC4MVC | **100% 3D Blu-ray / VLC4MVC Compliant** |
