import requests
from flask import current_app

_BASE_URL = "https://natinfo.app/api/natinfs/search/"


def search_natinf(query, limit=50):
    """
    Search for NATINF codes matching the query.
    Proxies natinfo.app to avoid CORS issues.
    """
    if not query or len(query.strip()) < 2:
        return []

    try:
        response = requests.get(
            _BASE_URL,
            params={"q": query.strip()},
            headers={"Accept": "application/json"},
            timeout=15,
        )
        response.raise_for_status()

        results = response.json().get("results", [])
        return [
            {
                "code": item.get("numero_natinf"),
                "label": item.get("qualification_infraction", ""),
                "description": item.get("sanctions_encourues", ""),
                "articles": item.get("definie_par", ""),
            }
            for item in results[:limit]
        ]

    except requests.exceptions.Timeout:
        current_app.logger.error(
            f"Timeout when searching NATINF for query: {query}"
        )
        raise Exception("La recherche de NATINF a expiré. Veuillez réessayer.")
    except requests.exceptions.RequestException as e:
        current_app.logger.error(
            f"Error searching NATINF for query '{query}': {str(e)}"
        )
        raise Exception(
            "Erreur lors de la recherche de NATINF. Veuillez réessayer."
        )
