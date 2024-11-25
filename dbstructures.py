from typing import Deque, Dict, Optional
from enum import Enum
from dataclasses import dataclass

type Id = str

class State(Enum):
    Pending1 = 0
    Pending2 = 1
    Success  = 2
    Failed   = 3

class QueueStatus(Enum):
    Processing  = 0
    Empty       = 1
    Ready       = 2

@dataclass
class Item:
    input   : bytes
    output  : Optional[bytes]

@dataclass
class Database:
    pending1_ids : Deque[Id]
    pending1     : Dict[Id, Item]
    pending2_id  : Optional[Id]
    pending2     : Optional[Item]
    success      : Dict[Id, Item]
    failed       : Dict[Id, Item]