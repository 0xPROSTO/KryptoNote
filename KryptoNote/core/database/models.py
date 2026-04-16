from dataclasses import dataclass
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


@dataclass
class ConnectionDTO:
    id: int
    start_id: int
    end_id: int
