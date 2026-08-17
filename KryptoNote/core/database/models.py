from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NodeItemDTO:
    id: int
    type: str
    title: str
    x: int
    y: int
    width: int
    height: int
    text_content: Optional[str] = None
    thumbnail: Optional[bytes] = None
    is_chunked: bool = False
    total_size: int = 0
    title_size: int = 14
    text_size: int = 10
    created_at: str = ""
    updated_at: str = ""
    media_width: int = 0
    media_height: int = 0
    media_duration: float = 0.0
    original_filename: str = ""
    media_metadata: list[dict] = field(default_factory=list)
    frame_locked: bool = False
    frame_color: str = ""
    frame_opacity: float = 0.21



@dataclass
class TagDTO:
    id: int
    name: str
    color: str

@dataclass
class ConnectionDTO:
    id: int
    start_id: int
    end_id: int
