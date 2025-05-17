# load prompts
try:
    from .prompts.le_comfort import le_comfort_main_prompt
except ImportError:
    from prompts.le_comfort import le_comfort_main_prompt

# load lists
try:
    from .lists.le_comfort import le_comfort_products_list, le_comfort_coverings_list, le_comfort_clients_list
except ImportError:
    from lists.le_comfort import le_comfort_products_list, le_comfort_coverings_list, le_comfort_clients_list


COMPANIES_INFO = {
    "86e676e3-4cc0-4725-b12c-358d3b4b3e43": {
        "NAME": "Le Comfort",
        "MAIN_PROMPT": le_comfort_main_prompt,
        "PRODUCTS_LIST": le_comfort_products_list,
        "COVERINGS_LIST": le_comfort_coverings_list,
        "CLIENTS_LIST": le_comfort_clients_list,
    },
}