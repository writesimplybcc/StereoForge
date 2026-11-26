"""H.264 MVC (Annex H) Bitstream Syntax Definitions.

Implements:
- NAL Unit Types (NAL 14 Prefix, NAL 20 Coded Slice Extension)
- MVC Subset Sequence Parameter Set (Subset SPS)
- MVC extension headers and view identifiers
"""

from dataclasses import dataclass
from typing import List, Dict, Any


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
        """Packs the 3-byte nal_unit_header_mvc_extension().

        Syntax:
        - svc_extension_flag (1 bit) = 0 (MVC)
        - non_idr_flag (1 bit)
        - priority_id (6 bits)
        - view_id (10 bits)
        - temporal_id (3 bits)
        - anchor_pic_flag (1 bit)
        - inter_view_flag (1 bit)
        - reserved_one_bit (1 bit) = 1
        """
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
