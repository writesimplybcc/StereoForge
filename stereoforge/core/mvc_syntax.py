"""H.264 MVC (Annex H) Bitstream Syntax Definitions.

Implements:
- NAL Unit Types (NAL 14 Prefix, NAL 15 Subset SPS, NAL 20 Coded Slice Extension)
- BitstreamWriter & BitstreamReader with Exp-Golomb ue(v), se(v), and raw bit operations
- Annex H Subset Sequence Parameter Set (Subset SPS) generator
- Annex H Prefix NAL (NAL 14) generator
- MVC extension headers and view identifiers
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional


# Standard H.264 NAL Unit Types
NAL_NON_IDR_SLICE = 1
NAL_DPA = 2
NAL_DPB = 3
NAL_DPC = 4
NAL_IDR_SLICE = 5
NAL_SEI = 6
NAL_SPS = 7
NAL_PPS = 8
NAL_AUD = 9
NAL_FILLER = 12

# Annex H MVC NAL Unit Types
NAL_PREFIX = 14          # Prefix NAL unit before base view slices
NAL_SUBSET_SPS = 15      # Subset Sequence Parameter Set
NAL_SLICE_EXT = 20       # Coded slice extension (Dependent View slices)


class BitstreamWriter:
    """Bit-level writer supporting Exp-Golomb ue(v), se(v), and raw bits u(n)."""

    def __init__(self):
        self._bytes = bytearray()
        self._current_byte = 0
        self._bit_pos = 0

    def write_bit(self, bit: int) -> None:
        self._current_byte = (self._current_byte << 1) | (1 if bit else 0)
        self._bit_pos += 1
        if self._bit_pos == 8:
            self._bytes.append(self._current_byte)
            self._current_byte = 0
            self._bit_pos = 0

    def write_bits(self, val: int, num_bits: int) -> None:
        for i in range(num_bits - 1, -1, -1):
            self.write_bit((val >> i) & 1)

    def write_ue(self, val: int) -> None:
        """Writes unsigned Exp-Golomb integer ue(v)."""
        x = val + 1
        leading_zeros = x.bit_length() - 1
        for _ in range(leading_zeros):
            self.write_bit(0)
        self.write_bits(x, leading_zeros + 1)

    def write_se(self, val: int) -> None:
        """Writes signed Exp-Golomb integer se(v)."""
        if val <= 0:
            self.write_ue(-2 * val)
        else:
            self.write_ue(2 * val - 1)

    def write_trailing_bits(self) -> None:
        """Writes rbsp_trailing_bits (1 bit followed by 0-pad to byte boundary)."""
        self.write_bit(1)
        while self._bit_pos != 0:
            self.write_bit(0)

    def get_rbsp(self) -> bytes:
        data = bytearray(self._bytes)
        if self._bit_pos > 0:
            data.append(self._current_byte << (8 - self._bit_pos))
        return bytes(data)

    def get_ebsp(self) -> bytes:
        """Applies Annex B emulation prevention bytes (0x03)."""
        rbsp = self.get_rbsp()
        ebsp = bytearray()
        zeros = 0
        for b in rbsp:
            if zeros == 2 and b in (0x00, 0x01, 0x02, 0x03):
                ebsp.append(0x03)
                zeros = 0
            ebsp.append(b)
            if b == 0x00:
                zeros += 1
            else:
                zeros = 0
        return bytes(ebsp)


class BitstreamReader:
    """Bit-level reader supporting Exp-Golomb ue(v), se(v), and raw bits u(n)."""

    def __init__(self, data: bytes):
        # Remove emulation prevention bytes
        rbsp = bytearray()
        i = 0
        n = len(data)
        while i < n:
            if i + 2 < n and data[i] == 0 and data[i + 1] == 0 and data[i + 2] == 3:
                rbsp.append(data[i])
                rbsp.append(data[i + 1])
                i += 3
            else:
                rbsp.append(data[i])
                i += 1
        self._data = bytes(rbsp)
        self._byte_pos = 0
        self._bit_pos = 0

    def read_bit(self) -> int:
        if self._byte_pos >= len(self._data):
            return 0
        byte = self._data[self._byte_pos]
        bit = (byte >> (7 - self._bit_pos)) & 1
        self._bit_pos += 1
        if self._bit_pos == 8:
            self._byte_pos += 1
            self._bit_pos = 0
        return bit

    def read_bits(self, num_bits: int) -> int:
        val = 0
        for _ in range(num_bits):
            val = (val << 1) | self.read_bit()
        return val

    def read_ue(self) -> int:
        leading_zeros = 0
        while self.read_bit() == 0 and leading_zeros < 32:
            leading_zeros += 1
        if leading_zeros == 0:
            return 0
        info = self.read_bits(leading_zeros)
        return (1 << leading_zeros) - 1 + info

    def read_se(self) -> int:
        code_num = self.read_ue()
        val = (code_num + 1) // 2
        return val if (code_num % 2 == 1) else -val


@dataclass
class MVCViewInfo:
    view_id: int               # 0 = Base view (Left), 1 = Dependent view (Right)
    is_base_view: bool = False
    inter_view_flag: bool = True
    anchor_pic_flag: bool = False  # True for IDR/Anchor frames
    priority_id: int = 0
    temporal_id: int = 0


class MVCBitstreamHeader:
    """Helper for generating 3-byte MVC NAL Unit Header Extensions (Annex H.7.3.1.1)."""

    @staticmethod
    def pack_nal_header_extension(
        view: MVCViewInfo,
        non_idr_flag: bool = True
    ) -> bytes:
        """Packs the 3-byte nal_unit_header_mvc_extension()."""
        # Byte 0: [svc_ext: 0][non_idr: 1][priority_id: 6 bits]
        b0 = ((1 if non_idr_flag else 0) << 6) | (view.priority_id & 0x3F)

        # Byte 1: view_id high 8 bits
        b1 = (view.view_id >> 2) & 0xFF

        # Byte 2: [view_id low 2 bits][temporal_id: 3 bits][anchor: 1 bit][inter_view: 1 bit][reserved: 1 bit]
        b2 = (
            ((view.view_id & 0x03) << 6)
            | ((view.temporal_id & 0x07) << 3)
            | ((1 if view.anchor_pic_flag else 0) << 2)
            | ((1 if view.inter_view_flag else 0) << 1)
            | 0x01
        )

        return bytes([b0, b1, b2])

    @staticmethod
    def unpack_nal_header_extension(data: bytes) -> MVCViewInfo:
        """Parses a 3-byte MVC NAL header extension."""
        if len(data) < 3:
            raise ValueError("MVC header extension requires 3 bytes")

        b0, b1, b2 = data[0], data[1], data[2]
        priority_id = b0 & 0x3F
        view_id = ((b1 & 0xFF) << 2) | ((b2 >> 6) & 0x03)
        temporal_id = (b2 >> 3) & 0x07
        anchor_pic_flag = bool((b2 >> 2) & 0x01)
        inter_view_flag = bool((b2 >> 1) & 0x01)

        return MVCViewInfo(
            view_id=view_id,
            is_base_view=(view_id == 0),
            inter_view_flag=inter_view_flag,
            anchor_pic_flag=anchor_pic_flag,
            priority_id=priority_id,
            temporal_id=temporal_id
        )


class MVCSubsetSPS:
    """Annex H.7.3.2.1.4: Subset Sequence Parameter Set (NAL Unit Type 15).

    Generates the compliant Subset SPS declaring stereoscopic view dependency
    (View 1 referencing View 0) for hardware 3D Blu-ray decoders and tsMuxeR.
    """

    @staticmethod
    def generate(
        width: int = 1920,
        height: int = 1080,
        sps_id: int = 0,
        level_idc: int = 41,  # Level 4.1 (Blu-ray 3D standard)
        view_id_base: int = 0,
        view_id_dep: int = 1
    ) -> bytes:
        """Synthesizes a complete Annex B Subset SPS NAL unit (including 4-byte start code)."""
        width_mbs = (width + 15) // 16
        height_mbs = (height + 15) // 16
        crop_bottom = (height_mbs * 16 - height) // 2

        w = BitstreamWriter()

        # profile_idc: Stereo High Profile (128)
        w.write_bits(128, 8)
        # constraint_set flags: constraint_set1_flag = 1
        w.write_bit(0)
        w.write_bit(1)
        w.write_bit(0)
        w.write_bit(0)
        w.write_bit(0)
        w.write_bit(0)
        w.write_bits(0, 2)    # reserved_zero_2bits
        w.write_bits(level_idc, 8)
        w.write_ue(sps_id)

        # High profile fields
        w.write_ue(1)         # chroma_format_idc (1 = 4:2:0)
        w.write_ue(0)         # bit_depth_luma_minus8 (8-bit)
        w.write_ue(0)         # bit_depth_chroma_minus8 (8-bit)
        w.write_bit(0)        # qpprime_y_zero_transform_bypass_flag
        w.write_bit(0)        # seq_scaling_matrix_present_flag

        w.write_ue(0)         # log2_max_frame_num_minus4
        w.write_ue(0)         # pic_order_cnt_type
        w.write_ue(2)         # log2_max_pic_order_cnt_lsb_minus4
        w.write_ue(4)         # max_num_ref_frames
        w.write_bit(0)        # gaps_in_frame_num_value_allowed_flag
        w.write_ue(width_mbs - 1)
        w.write_ue(height_mbs - 1)
        w.write_bit(1)        # frame_mbs_only_flag (progressive)
        w.write_bit(1)        # direct_8x8_inference_flag

        if crop_bottom > 0:
            w.write_bit(1)    # frame_cropping_flag
            w.write_ue(0)     # crop left
            w.write_ue(0)     # crop right
            w.write_ue(0)     # crop top
            w.write_ue(crop_bottom)
        else:
            w.write_bit(0)

        w.write_bit(0)        # vui_parameters_present_flag

        # seq_parameter_set_mvc_extension()
        w.write_bit(1)        # bit_equal_to_one
        w.write_ue(1)         # num_views_minus1 = 1 (2 views)
        w.write_ue(view_id_base)  # view_id[0]
        w.write_ue(view_id_dep)   # view_id[1]

        # Anchor references for view 1: references view 0
        w.write_ue(1)         # num_anchor_refs_l0[1] = 1
        w.write_ue(view_id_base)  # anchor_ref_l0[1][0] = view 0
        w.write_ue(0)         # num_anchor_refs_l1[1] = 0

        # Non-anchor references for view 1: references view 0
        w.write_ue(1)         # num_non_anchor_refs_l0[1] = 1
        w.write_ue(view_id_base)  # non_anchor_ref_l0[1][0] = view 0
        w.write_ue(0)         # num_non_anchor_refs_l1[1] = 0

        # Level values
        w.write_ue(0)         # num_level_values_signalled_minus1 = 0
        w.write_bits(level_idc, 8)
        w.write_ue(0)         # num_applicable_ops_minus1 = 0
        w.write_bits(0, 3)    # applicable_op_temporal_id = 0
        w.write_ue(1)         # applicable_op_num_target_views_minus1 = 1
        w.write_ue(view_id_base)
        w.write_ue(view_id_dep)
        w.write_ue(1)         # applicable_op_num_views_minus1 = 1

        w.write_bit(0)        # mvc_vui_parameters_present_flag
        w.write_trailing_bits()

        nal_header = bytes([(3 << 5) | NAL_SUBSET_SPS])  # nal_ref_idc = 3, nal_type = 15
        return b"\x00\x00\x00\x01" + nal_header + w.get_ebsp()


class PrefixNAL:
    """Annex H.7.3.2.12: Prefix NAL Unit (NAL Unit Type 14).

    Precedes base view slices in an MVC bitstream to signal view metadata
    (view_id = 0) to MVC-aware players.
    """

    @staticmethod
    def generate(priority_id: int = 0, temporal_id: int = 0) -> bytes:
        view_info = MVCViewInfo(
            view_id=0,
            is_base_view=True,
            inter_view_flag=False,
            anchor_pic_flag=False,
            priority_id=priority_id,
            temporal_id=temporal_id
        )
        nal_header_ext = MVCBitstreamHeader.pack_nal_header_extension(view_info, non_idr_flag=True)
        nal_byte = (2 << 5) | NAL_PREFIX

        w = BitstreamWriter()
        for b in nal_header_ext:
            w.write_bits(b, 8)
        w.write_bit(0)        # prefix_nal_unit_additional_extension_flag
        w.write_trailing_bits()

        return b"\x00\x00\x00\x01" + bytes([nal_byte]) + w.get_ebsp()
