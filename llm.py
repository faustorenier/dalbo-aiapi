import os
import google.generativeai as genai
from fastapi import HTTPException


MODEL_NAME = "gemini-2.0-flash"  # Google's Gemini model to use


def call_llm(prompt: str) -> str:
    """
    Call Google's Gemini API with the given prompt and return the response.

    Args:
        prompt (str): The prompt to send to Gemini API

    Returns:
        str: The JSON response from Gemini API

    Raises:
        HTTPException: If API key is missing or if there's an error during the API call
    """
    google_api_key = os.getenv("GOOGLE_API_KEY")

    if not google_api_key:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_API_KEY not found in environment variables. Please set it in your .env file.",
        )

    genai.configure(api_key=google_api_key)
    model = genai.GenerativeModel(MODEL_NAME)

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json"
            ),
            stream=False,
        )

        if response.prompt_feedback.block_reason:
            raise HTTPException(
                status_code=500,
                detail=f"Request was blocked: {response.prompt_feedback.block_reason}",
            )

        return response.text

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error during Gemini API call: {str(e)}"
        )