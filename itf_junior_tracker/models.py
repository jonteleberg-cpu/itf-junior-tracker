from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class Tournament:
    name: str
    url: str
    acceptance_url: str
    category: str = ""
    date_text: str = ""
    start_date: str = ""
    end_date: str = ""

@dataclass
class Entry:
    player: str
    nation: str
    tournament: str
    category: str
    draw: str
    ranking: Optional[int]
    wtn: Optional[float]
    position: str
    info: str
    acceptance_url: str
    tournament_start: str = ""
    tournament_end: str = ""
    gender: str = ""
    player_url: str = ""

    def to_dict(self):
        return asdict(self)
