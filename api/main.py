import os
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from dotenv import load_dotenv

try:
    from .data_extracter import extract_invoice_data
except ImportError:
    from data_extracter import extract_invoice_data


app = FastAPI()


# [
#     "http://localhost:3000",  # dev frontend
#     "chrome-extension://*",  # postman
#     "https://tuodominio.com",  # prod frontend
# ]

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Load environment variables and override any existing ones
load_dotenv(override=True)


# Function to verify the API key
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if x_api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=403, detail="API key not valid")
    return x_api_key


@app.get("/")
def read_root(api_key: str = Depends(verify_api_key)):
    return {"message": "You've found the perfect place to manage your invoices 😏"}


@app.post("/invoices/upload")
async def upload_invoice(
    file: UploadFile = File(...),
    companyId: str = Form(...),
    api_key: str = Depends(verify_api_key),
):
    result = await extract_invoice_data(file, companyId)
    return result
