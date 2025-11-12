from typing import TypedDict, List, Optional


class RebrickableSetData(TypedDict):
    set_num: str  # e.g., "75192-1"
    name: str
    year: int
    theme_id: int
    num_parts: int
    set_img_url: Optional[str]
    set_url: str
    last_modified_dt: str


class RebrickableSetSearchResponse(TypedDict):
    count: int
    next: Optional[str]
    previous: Optional[str]
    results: List[RebrickableSetData]


class RebrickablePartData(TypedDict):
    id: int
    inv_part_id: int
    part: dict  # Contains part_num, name, part_cat_id, etc.
    color: dict  # Contains id, name, rgb, is_trans
    set_num: str
    quantity: int
    is_spare: bool
    element_id: Optional[str]
    num_sets: int


class RebrickableInventoryResponse(TypedDict):
    count: int
    next: Optional[str]
    previous: Optional[str]
    results: List[RebrickablePartData]


class RebrickableThemeData(TypedDict):
    id: int
    parent_id: Optional[int]
    name: str


class PartIdMapping(TypedDict):
    """Maps Rebrickable part numbers to BrickLink IDs"""

    rebrickable_part_num: str
    bricklink_part_id: Optional[str]
