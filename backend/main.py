from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx 

class Issue(BaseModel):
    id: int
    number: int
    title: str
    user: str
    state: str
    created_at: str
    updated_at: str
    labels: List[str]
    html_url: str

class IssuesResponse(BaseModel):
    owner: str
    repo: str
    issues: List[Issue]

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "ok"}

GITHUB_API_BASE = "https://api.github.com"

@app.get("/repos/{owner}/{repo}/issues", response_model=IssuesResponse)
async def list_repo_issues(owner: str, repo: str) -> IssuesResponse:
    """
    Fetches issues for a given GitHub repository.
    Example: /repos/facebook/react/contributors
    """

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues"
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(
            url,
            params = {"state": "open"},
            headers = {"Accept": "application/vnd.github+json"},
            )

    
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Repository not found")
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Error fetching issues from GitHub")

        data = response.json()

        #simplify the fields to return to frontend
        issues = [
            {
                "id": issue["id"],
                "number": issue["number"],
                "title": issue["title"],
                "user": issue["user"]["login"],
                "state": issue["state"],
                "created_at": issue["created_at"],
                "updated_at": issue["updated_at"],
                "labels": [label["name"] for label in issue.get("labels", [])],
                "html_url": issue["html_url"],
            }
            for issue in data
            if "pull_request" not in issue  # Exclude pull requests
        ]

        return IssuesResponse(owner=owner, repo=repo, issues=issues)