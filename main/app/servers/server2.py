from typing import Any
from mcp.server.fastmcp import FastMCP
import httpx
from bs4 import BeautifulSoup

# Initialize FastMCP server with the name "mytools"
mcp = FastMCP("doctor")

@mcp.tool()
async def disease_diagnoser(query):
    """
    Search PubMed for medical articles related to the given symptoms and diagnose the disease .
    
    Args:
        query (str): The search keywords (e.g., symptoms like 'fever headache')
    
    Returns:
        str: A summary of relevant article titles and abstracts
    """
    try:
        # Step 1: Search for PMIDs
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmax": 5,
            "retmode": "json"
        }
        
        async with httpx.AsyncClient() as client:
            search_res = await client.get(search_url, params=search_params, timeout=10.0)
            search_res.raise_for_status()
            pmids = search_res.json().get("esearchresult", {}).get("idlist", [])

            if not pmids:
                return "No articles found for your query."
            # Step 2: Fetch abstracts
            fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            fetch_params = {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml"
            }

            fetch_res = await client.get(fetch_url, params=fetch_params, timeout=10.0)
            fetch_res.raise_for_status()

        # Step 3: Parse XML response
        soup = BeautifulSoup(fetch_res.content, "lxml")
        results = []
        for article in soup.find_all("pubmedarticle"):
            title = article.find("articletitle")
            abstract = article.find("abstracttext")
            if title and abstract:
                results.append(f"📝 {title.text.strip()}\n{abstract.text.strip()}\n")

        return "\n".join(results) if results else "No abstracts found."

    except Exception as e:
        return f"Error fetching PubMed data: {e}"

if __name__ == "__main__":
    mcp.run(transport="stdio")