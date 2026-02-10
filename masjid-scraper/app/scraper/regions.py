"""Region definitions and helper functions for South African mosque locations."""

from typing import Dict, List, Optional


# Region code mappings to display names and URL slugs
REGIONS: Dict[str, Dict[str, str]] = {
    "jhbc": {"name": "Johannesburg Central", "slug": "johannesburg-central"},
    "jhbs": {"name": "Johannesburg South", "slug": "johannesburg-south"},
    "jhbn": {"name": "Johannesburg North", "slug": "johannesburg-north"},
    "dbn":  {"name": "Durban", "slug": "durban"},
    "pta":  {"name": "Pretoria", "slug": "pretoria"},
    "cpt":  {"name": "Cape Town", "slug": "cape-town"},
    "pe":   {"name": "Port Elizabeth", "slug": "port-elizabeth"},
    "pmb":  {"name": "Pietermaritzburg", "slug": "pietermaritzburg"},
}


def get_region_codes() -> List[str]:
    """
    Get all available region codes.
    
    Returns:
        List of region codes (e.g., ['jhbc', 'jhbs', ...])
    """
    return list(REGIONS.keys())


def get_region_name(code: str) -> Optional[str]:
    """
    Get the display name for a region code.
    
    Args:
        code: Region code (e.g., 'jhbc')
        
    Returns:
        Display name (e.g., 'Johannesburg Central') or None if not found
    """
    region = REGIONS.get(code)
    return region["name"] if region else None


def get_region_slug(code: str) -> Optional[str]:
    """
    Get the URL slug for a region code.
    
    Args:
        code: Region code (e.g., 'jhbc')
        
    Returns:
        URL slug (e.g., 'johannesburg-central') or None if not found
    """
    region = REGIONS.get(code)
    return region["slug"] if region else None


def is_valid_region(code: str) -> bool:
    """
    Check if a region code is valid.
    
    Args:
        code: Region code to validate
        
    Returns:
        True if valid, False otherwise
    """
    return code in REGIONS
