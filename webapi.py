from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi import Request
import requests
from io import BufferedReader, BytesIO
from starlette.middleware.trustedhost import TrustedHostMiddleware
import asyncio
from contextlib import asynccontextmanager
from typing import Optional
import base64
import xmltodict
import grpc
import dbservice_pb2
import dbservice_pb2_grpc
from dbservice_pb2 import EmptyData
import uvicorn

@asynccontextmanager
async def lifespan(app: FastAPI):
    global unfinished_tasks

    unfinished_tasks = []

    task = asyncio.create_task(periodic_task())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        for task_id in unfinished_tasks:
            print(f"Finalizing task {task_id} during shutdown.")
            try:
                stub.Finalize(dbservice_pb2.FinalizeRequest(error=True))
            except grpc.RpcError as e:
                print(f"Failed to finalize task {task_id}. Database will have inconsistent state!")

app = FastAPI(lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")


# ============================================================================ #
# Periodic task

async def periodic_task_content():
    global stub, unfinished_tasks

    try:

        # pull from queue
        response = stub.Pull(EmptyData())
        if response.status == dbservice_pb2.QueueStatus.PROCESSING:
            print(f"Periodic task: still processing {response.id}")
            return
        if response.status == dbservice_pb2.QueueStatus.EMPTY:
            print("Periodic task: queue is empty")
            return
        print(f"Periodic task: start processing {response.ready.id}")
        unfinished_tasks.append(response.ready.id)

        img_bytes = response.ready.item.input
        
        # get_caption
        caption = await asyncio.to_thread(get_caption, img_bytes)
        print(f"Caption: {caption}")
        if caption == None:
            stub.Finalize(dbservice_pb2.FinalizeRequest(error=True))
            return

        # get_ai_image
        img_bytes = await asyncio.to_thread(get_ai_image, caption)
        print("Got AI image.")
        if img_bytes == None:
            stub.Finalize(dbservice_pb2.FinalizeRequest(error=True))
            return
        
        # finalize
        stub.Finalize(dbservice_pb2.FinalizeRequest(error=False, img_bytes=img_bytes))
        unfinished_tasks.remove(response.ready.id)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.UNAVAILABLE:
            print("The gRPC server is unavailable. Check if it's running and accessible.")
        else:
            print(f"gRPC error: {e}")
            print(f"Details: {e.details()}")
            print(f"Status Code: {e.code()}")
    

async def periodic_task():
    while True:
        await asyncio.sleep(10)
        asyncio.create_task(periodic_task_content())


# ============================================================================ #
# Endpoints

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    global stub
    img_bytes = await file.read()
    result = stub.Add(dbservice_pb2.AddRequest(img_bytes=img_bytes))
    return {"status": "success", "id": result.id}


@app.get("/query")
async def query_id(id: str):
    global stub
    result = stub.Check(dbservice_pb2.CheckRequest(id=id))
    if result.HasField("exist"):
        
        if result.exist.state == dbservice_pb2.State.PENDING1:
            return {"status": "success", "state": "pending_1", "position": result.exist.position}
        
        if result.exist.state == dbservice_pb2.State.PENDING2:
            return {"status": "success", "state": "pending_2"}
        
        if result.exist.state == dbservice_pb2.State.FAILED:
            return {"status": "success", "state": "failed"}
        
        img_str = base64.b64encode(result.exist.item.output).decode('utf-8')
        return {"status": "success", "state": "success", "response": img_str}

    return {"status": "success", "state": "not_in_system"}

# ============================================================================ #
# External service calls

def get_ai_image(caption) -> Optional[bytes]:
    url = "http://127.0.0.1:5001/generate_image"

    xml_body = f"""
    <request>
        <prompt>{caption}</prompt>
    </request>
    """

    headers = {'Content-Type': 'application/xml'}
    response = requests.post(url, data=xml_body, headers=headers)
    if response.status_code == 200:
        response_dict = xmltodict.parse(response.text)
        img_base64 = response_dict.get("response", {}).get("image")
        img_bytes = base64.b64decode(img_base64)
        return img_bytes

    print(f"Error {response.status_code} in get_ai_image: {response.text}")
    return None


def get_caption(img_bytes: bytes) -> Optional[str]:
    image = BufferedReader(BytesIO(img_bytes))

    endpoint = 'https://dist-sys-computer-vision-instance.cognitiveservices.azure.com/'
    subscription_key = '5REeuCbDHvCoEB1NLvJehfw2zqH9w2IvsqIevSuX0mjPKbY4I0ygJQQJ99AKACi5YpzXJ3w3AAAFACOGFzYM'
    url = endpoint + '/vision/v3.2/describe'

    headers = {
        'Ocp-Apim-Subscription-Key': subscription_key,
        'Content-Type': 'application/octet-stream'
    }
    response = requests.post(url, headers=headers, data=image)

    if response.status_code == 200:
        analysis = response.json()
        caption = analysis['description']['captions'][0]['text']
        return caption
    
    print(f"Error {response.status_code} in get_caption: {response.text}")
    return None

# ============================================================================ #

if __name__ == "__main__":
    global stub
    global templates

    # gRPC dbservice
    channel = grpc.insecure_channel('localhost:5002')
    stub = dbservice_pb2_grpc.DBServiceStub(channel)

    # app setup
    templates = Jinja2Templates(directory="templates")
    uvicorn.run(app, host="127.0.0.1", port=5000)
