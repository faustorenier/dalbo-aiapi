import google.generativeai as genai
from typing import List, Dict, Any
from fastapi import HTTPException
import json

try:
    from .llm import call_llm
except ImportError:
    from llm import call_llm


def convert_price_to_float(price_str):
    if not price_str or not isinstance(price_str, str):
        return None
    try:
        # Remove spaces and replace comma with dot
        cleaned_price = price_str.strip().replace(".", "").replace(",", ".")
        return float(cleaned_price)
    except (ValueError, AttributeError):
        return None


def convert_quantity_to_int(quantity_str):
    if not quantity_str or not isinstance(quantity_str, str):
        return None
    try:
        # Remove spaces and convert to integer
        cleaned_quantity = quantity_str.strip()
        return int(cleaned_quantity)
    except (ValueError, AttributeError):
        return None


def normalize_product_name(product_name: str, standard_names: List[str]) -> str:
    """
    Normalize a product name by matching it with standard names.

    Args:
        product_name: The original product name
        standard_names: List of standard names to match against

    Returns:
        The normalized product name
    """
    for standard_name in standard_names:
        if standard_name.lower() in product_name.lower():
            return standard_name
    return product_name


def normalize_product_data(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a single product's data including prices, quantity and coverings.

    Args:
        product: The product dictionary to normalize

    Returns:
        The normalized product dictionary
    """
    normalized_product = product.copy()

    # Convert prices to float
    if "full_price" in normalized_product:
        normalized_product["full_price"] = convert_price_to_float(
            normalized_product["full_price"]
        )
    if "discounted_price" in normalized_product:
        normalized_product["discounted_price"] = convert_price_to_float(
            normalized_product["discounted_price"]
        )

    # Convert quantity to integer
    if "quantity" in normalized_product:
        normalized_product["quantity"] = convert_quantity_to_int(
            normalized_product["quantity"]
        )

    return normalized_product


def normalize_coverings(
    coverings: List[Dict[str, Any]], coverings_list: List[str]
) -> List[Dict[str, Any]]:
    """
    Normalize a list of coverings by filtering and standardizing their names.

    Args:
        coverings: List of covering dictionaries
        coverings_list: List of standard covering names

    Returns:
        List of normalized covering dictionaries
    """
    normalized_coverings = []

    for covering in coverings:
        if "name" not in covering:
            continue

        # Check if covering matches any standard name
        if any(
            standard_name.lower() in covering["name"].lower()
            for standard_name in coverings_list
        ):
            normalized_covering = covering.copy()
            normalized_covering["name"] = normalize_product_name(
                covering["name"], coverings_list
            )
            normalized_coverings.append(normalized_covering)

    return normalized_coverings


def process_chunk_data(
    chunk: Dict[str, Any], products_list: List[str], coverings_list: List[str], clients_list: List[Dict[str, str]]
) -> List[Dict[str, Any]]:
    """
    Process a single chunk of data, normalizing products, their coverings and client names.

    Args:
        chunk: The data chunk to process
        products_list: List of standard product names
        coverings_list: List of standard covering names
        clients_list: List of standardized client names with their IDs

    Returns:
        List of processed items
    """
    processed_items = []

    if "data" not in chunk or not isinstance(chunk["data"], list):
        return processed_items

    for item in chunk["data"]:
        if "products" not in item or not isinstance(item["products"], list):
            continue

        # Filter and normalize products
        normalized_products = []
        for product in item["products"]:
            if "name" not in product:
                continue

            # Check if product matches any standard name
            if any(
                standard_name.lower() in product["name"].lower()
                for standard_name in products_list
            ):
                normalized_product = normalize_product_data(product)
                normalized_product["name"] = normalize_product_name(
                    product["name"], products_list
                )

                # Handle coverings if present
                if "coverings" in normalized_product and isinstance(
                    normalized_product["coverings"], list
                ):
                    normalized_product["coverings"] = normalize_coverings(
                        normalized_product["coverings"], coverings_list
                    )

                normalized_products.append(normalized_product)

        if normalized_products:
            processed_item = item.copy()
            processed_item["products"] = normalized_products
            processed_items.append(processed_item)

    # Normalize client names for this chunk
    if processed_items:
        prompt = f"""
        You are an assistant specialized in normalizing client names. Your task is to match and replace client names with their standardized versions from a reference list.

        REFERENCE LIST:
        {json.dumps(clients_list, indent=2)}

        RULES:
        1. Match the input client name with the most similar name in the reference list
        2. If a match is found, replace the name with the standardized version and include its ID
        3. If no match is found, keep the original name
        4. Preserve all other fields in the input data
        5. Return the data in the same format as the input

        INPUT DATA:
        {json.dumps(processed_items, indent=2)}

        Return the normalized data in JSON format.
        """

        try:
            processed_items = json.loads(call_llm(prompt))
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error during client names normalization in chunk: {str(e)}"
            )

    return processed_items


def merge_items_by_invoice(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge items that share the same invoice number.

    Args:
        items: List of items to merge

    Returns:
        List of merged items
    """
    invoice_dict = {}

    for item in items:
        invoice_number = item.get("invoice_number")
        if not invoice_number:
            continue

        if invoice_number in invoice_dict:
            # Merge products with existing item
            invoice_dict[invoice_number]["products"].extend(item["products"])
        else:
            # Add new item to dictionary
            invoice_dict[invoice_number] = item.copy()

    return list(invoice_dict.values())


def normalize_results(
    result: Dict[str, Any],
    products_list: List[str],
    coverings_list: List[str],
    clients_list: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """
    Normalize and process the raw data from the result, handling products and coverings.

    Args:
        result: The raw result data
        products_list: List of standard product names
        coverings_list: List of standard covering names
        clients_list: List of standard client names with their IDs

    Returns:
        List of normalized and merged items
    """
    normalized_result = result.copy()
    processed_items = []

    # Process each chunk in the raw data
    for chunk in normalized_result["raw_data"]["chunks"]:
        processed_items.extend(process_chunk_data(chunk, products_list, coverings_list, clients_list))

    # Merge items with the same invoice number
    final_result = merge_items_by_invoice(processed_items)

    return final_result
