from concurrent import futures
import grpc
from google.protobuf.empty_pb2 import Empty

import dbservice_pb2
import dbservice_pb2_grpc

from dblogic import *
from dbstructures import *

import atexit

class DBServiceServicer(dbservice_pb2_grpc.DBServiceServicer):
    def Add(self, request, context):
        id = add(db, request.img_bytes)
        return dbservice_pb2.AddResponse(id=id)

    def Pull(self, request, context):
        result = pull(db) # Tuple[QueueStatus, Id | Tuple[Id, Item] | None]

        if result[0] == QueueStatus.Processing:
            return dbservice_pb2.PullResponse(
                status=dbservice_pb2.QueueStatus.PROCESSING,
                id=result[1]
            )
        
        if result[0] == QueueStatus.Empty:
            return dbservice_pb2.PullResponse(
                status=dbservice_pb2.QueueStatus.EMPTY,
                empty=dbservice_pb2.EmptyData()
            )
        
        return dbservice_pb2.PullResponse(
            status=dbservice_pb2.QueueStatus.READY,
            ready=dbservice_pb2.ReadyData(
                id=result[1][0],
                item=dbservice_pb2.Item(
                    input=result[1][1].input,
                    output=result[1][1].output
                )
            )
        )

    def Finalize(self, request, context):
        if (request.error):
            finalize(db, True, None)
        else:
            finalize(db, False, request.img_bytes)

        return Empty()
    
    def Check(self, request, context):
        result = check(db, request.id) # Tuple[State, Item, int | None] | None
        
        if result == None:
            return dbservice_pb2.CheckResponse(dbservice_pb2.EmptyData())
        
        state, item, maybe_position = result
        
        if state == State.Pending1:
            return dbservice_pb2.CheckResponse(
                exist=dbservice_pb2.CheckResponseExist(
                    state=dbservice_pb2.State.PENDING1,
                    item=dbservice_pb2.Item(
                        input=item.input,
                        output=item.output
                    ),
                    position=maybe_position
                )
            )
        
        if state == State.Pending2:
            return dbservice_pb2.CheckResponse(
                exist=dbservice_pb2.CheckResponseExist(
                    state=dbservice_pb2.State.PENDING2,
                    item=dbservice_pb2.Item(
                        input=item.input,
                        output=item.output
                    )
                )
            )
    
        if state == State.Failed:
            return dbservice_pb2.CheckResponse(
                exist=dbservice_pb2.CheckResponseExist(
                    state=dbservice_pb2.State.FAILED,
                    item=dbservice_pb2.Item(
                        input=item.input,
                        output=item.output
                    )
                )
            )

        return dbservice_pb2.CheckResponse(
            exist=dbservice_pb2.CheckResponseExist(
                state=dbservice_pb2.State.SUCCESS,
                item=dbservice_pb2.Item(
                    input=item.input,
                    output=item.output
                )
            )
        )

# ------------------------------------------------------------- #

db = load_db()
def on_exit():
    global db
    save_db(db)

atexit.register(on_exit)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    dbservice_pb2_grpc.add_DBServiceServicer_to_server(DBServiceServicer(), server)
    server.add_insecure_port('[::]:5002')
    server.start()
    print("gRPC server is running on port 5002...")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("Server interrupted.")

if __name__ == '__main__':
    serve()
