from typing import Optional
from collections import deque # append(...), ... = popleft()
from datetime import datetime
import pickle
import os
from typing import Tuple
from dbstructures import *
from datetime import datetime

def uid() -> Id:
    return datetime.now().strftime("%Y%m%d%H%M%S%f")

def load_db() -> Database:
    if os.path.exists('db.pkl'):
        with open('db.pkl', 'rb') as f:
            db = pickle.load(f)
    else:
        db = Database(
            pending1_ids = deque(),
            pending1     = {},
            pending2_id  = None,
            pending2     = None,
            success      = {},
            failed       = {}
        )
    
    print("Database loaded.")
    return db

def save_db(db: Database):
    with open('db.pkl', 'wb') as f:
        pickle.dump(db, f)

    print("Database saved.")
    return

def print_db(db: Database):
    print(f"Database content:")
    print(f"    pending1_ids : {db.pending1_ids}")
    print(f"    pending1     : size {len(db.pending1)}")
    print(f"    pending2_id  : {db.pending2_id}")
    print(f"    pending2     : none? {db.pending2_id == None}")
    print(f"    success      : {db.success.keys()}")
    print(f"    failed       : {db.failed.keys()}")

# =========================================================== #

def add(db: Database, img_bytes: bytes) -> Id:
    print(f"database --- ADD was called ({datetime.now().strftime("%m/%d/%Y, %H:%M:%S")})")

    id = uid()
    db.pending1_ids.append(id)
    db.pending1[id] = Item(
        input   = img_bytes,
        output  = None
    )
    return id


def pull(db: Database) -> Tuple[QueueStatus, Id|None|Tuple[Id, Item]]:
    print(f"database --- PULL was called ({datetime.now().strftime("%m/%d/%Y, %H:%M:%S")})")

    if db.pending2_id != None:
        return (QueueStatus.Processing, db.pending2_id)

    if len(db.pending1_ids) == 0:
        return (QueueStatus.Empty, None)
    
    id = db.pending1_ids.popleft()
    item = db.pending1.pop(id)

    db.pending2_id = id
    db.pending2 = item

    print("Database after pulling:")
    print_db(db)

    return (QueueStatus.Ready, (id, item))


def finalize(db: Database, error: bool, img_bytes: Optional[bytes]):
    print(f"database --- FINALIZE was called ({datetime.now().strftime("%m/%d/%Y, %H:%M:%S")})")

    if (not error and img_bytes == None):
        raise ValueError("img_bytes can not be None if error is False")

    id = db.pending2_id
    item = db.pending2

    if not error:
        db.success[id] = Item(
            input=item.input,
            output=img_bytes
        )
    else:
        db.failed[id] = Item(
            input=item.input,
            output=None
        )
    
    db.pending2_id = None
    db.pending2 = None
    return


def check(db: Database, id: Id) -> Optional[Tuple[State, Item, Optional[int]]]:
    print(f"database --- CHECK was called ({datetime.now().strftime("%m/%d/%Y, %H:%M:%S")})")

    print_db(db)

    if id in db.pending1_ids:
        position = db.pending1_ids.index(id)
        return (State.Pending1, db.pending1[id], position)
    
    if id == db.pending2_id:
        return (State.Pending2, db.pending2, None)
    
    if id in db.success:
        return (State.Success, db.success[id], None)
    
    if id in db.failed:
        return (State.Failed, db.failed[id], None)
    
    return None