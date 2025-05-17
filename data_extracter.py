import os
import json
import google.generativeai as genai
import httpx
from fastapi import FastAPI, UploadFile, HTTPException
from dotenv import load_dotenv

from io import BytesIO
from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument

try:
    from .llm import call_llm
    from .data_formatter import normalize_results
except ImportError:
    from llm import call_llm
    from data_formatter import normalize_results

try:
    from .companies_info import COMPANIES_INFO
except ImportError:
    from companies_info import COMPANIES_INFO


# Configuration constants
PAGES_PER_CHUNK = 10  # Number of pages to process at once for better memory management

app = FastAPI()

# Load environment variables and override any existing ones
load_dotenv(override=True)


async def get_pdf_text(file: UploadFile) -> list[str]:
    """
    Extract text content from a PDF file.
    
    Args:
        file (UploadFile): The PDF file to process
        
    Returns:
        list[str]: List of strings, where each string represents the text content of a page
        
    Raises:
        HTTPException: If file is not a PDF or if text extraction fails
    """
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="Error: A valid PDF file is required"
        )

    try:
        contents = await file.read()
        pdf_file = BytesIO(contents)

        # Get total number of pages
        parser = PDFParser(pdf_file)
        document = PDFDocument(parser)
        total_pages = len(list(PDFPage.create_pages(document)))

        # Extract text from each page
        pages_text = []
        for page_num in range(total_pages):
            # LAParams can be adjusted for better text extraction quality
            text = extract_text(pdf_file, page_numbers=[page_num], laparams=LAParams())
            pages_text.append(text)

        if not pages_text or all(not text.strip() for text in pages_text):
            raise HTTPException(status_code=500, detail="Error extracting text")

        return pages_text

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error during text extraction: {str(e)}"
        )


async def fetch_clients_from_crm() -> list:
    """
    Recupera la lista dei clienti dal CRM.
    
    Returns:
        list: Lista dei clienti dal CRM
        
    Raises:
        HTTPException: Se il recupero dei dati fallisce
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{os.getenv('CRM_BASE_API')}/clients",
            headers={
                "x-crm-secret-key": os.getenv("CRM_SECRET_KEY"),
                "origin": os.getenv("CRM_ALLOWED_ORIGIN")
            }
        )
        if response.status_code == 200:
            clients_data = response.json()
            return clients_data["data"]
        else:
            raise HTTPException(status_code=response.status_code, detail="Error: Failed to fetch clients data")


async def extract_invoice_data(file: UploadFile, companyId: str) -> dict:
    """
    Process a PDF invoice and extract relevant information using Gemini AI.
    
    Args:
        file (UploadFile): The PDF invoice file
        companyId (str): The ID of the company to process the invoice for
        
    Returns:
        dict: A dictionary containing:
            - filename: Name of the processed file
            - company_info: Company details
            - raw_data: Raw extracted data from Gemini
            - normalized_data: Processed and normalized invoice data
            
    Raises:
        HTTPException: If company ID is invalid or if processing fails
    """
    if companyId is None or companyId == "" or companyId not in COMPANIES_INFO:
        raise HTTPException(
            status_code=400, detail="Error: A valid company ID is required"
        )

    # Get company-specific configuration
    company_config = COMPANIES_INFO[companyId]
    company_name = company_config["NAME"]
    main_prompt = company_config["MAIN_PROMPT"]
    products_list = company_config["PRODUCTS_LIST"]
    coverings_list = company_config["COVERINGS_LIST"]
    
    # fetch clients data from CRM
    clients_list = await fetch_clients_from_crm()

    # Extract text from PDF
    pages_text = await get_pdf_text(file)

    # Initialize result structure
    result = {
        "filename": file.filename,
        "company_info": {
            "id": companyId,
            "name": company_name,
        },
        "raw_data": {"chunks": [], "total_chunks": 0, "total_pages": 0},
        "normalized_data": {},
    }

    # Process pages in chunks to manage memory and API limits
    for i in range(0, len(pages_text), PAGES_PER_CHUNK):
        chunk = pages_text[i : i + PAGES_PER_CHUNK]
        chunk_text = "\n".join(chunk)
        current_chunk_range = f"{i+1}-{min(i+PAGES_PER_CHUNK, len(pages_text))}"

        # Prepare prompt for this chunk
        chunk_prompt = f"{main_prompt}\n\nExtract informations from the following invoices text (pages {current_chunk_range}): \n---\n{chunk_text}\n---"
        
        # Get raw invoice info from Gemini
        initial_json = call_llm(chunk_prompt)

        if not initial_json:
            raise HTTPException(
                status_code=500,
                detail=f"Error: No result (raw invoice info) from Gemini API for pages {current_chunk_range}",
            )

        try:
            chunk_result = json.loads(initial_json)
            result["raw_data"]["chunks"].append(
                {
                    "pages": current_chunk_range,
                    "data": chunk_result,
                }
            )
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error parsing JSON response for pages {current_chunk_range}: {str(e)}",
            )

    if not result["raw_data"]["chunks"]:
        raise HTTPException(
            status_code=500, detail="Error: No valid results from any chunk processing"
        )

    result["raw_data"]["total_chunks"] = len(result["raw_data"]["chunks"])
    result["raw_data"]["total_pages"] = len(pages_text)

    # Normalize the extracted data using company-specific lists
    result["normalized_data"] = normalize_results(
        result, products_list, coverings_list, clients_list
    )

    return result