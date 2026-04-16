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


@dataclass
class ConnectionDTO:
    id: int
    start_id: int
    end_id: int
