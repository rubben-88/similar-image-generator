from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import Response
from io import BytesIO
from diffusers import StableDiffusionPipeline
import xmltodict
import base64
import uvicorn

app = FastAPI()

model = StableDiffusionPipeline.from_pretrained(
    "runwayml/stable-diffusion-v1-5", 
    cache_dir="./model_cache"
)
model.to("cpu")

@app.post("/generate_image", response_class=Response)
async def generate_image(request: str = Body(..., media_type="application/xml")):
    try:
        request_dict = xmltodict.parse(request)
        prompt = request_dict.get("request", {}).get("prompt")
        
        if not prompt:
            raise HTTPException(status_code=400, detail="No prompt provided")
        
        image = model(
            prompt, 
            #num_inference_steps=25, 
            #height=256, 
            #width=256
        ).images[0]
        
        img_byte_arr = BytesIO()
        image.save(img_byte_arr, format="PNG")
        img_byte_arr.seek(0)

        img_base64 = base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")
        
        response_dict = {
            "response": {
                "status": "success",
                "image": img_base64
            }
        }
        xml_response = xmltodict.unparse(response_dict, pretty=True)

        return Response(content=xml_response, media_type="application/xml")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5001)

