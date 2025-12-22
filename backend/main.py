from typing import List
from fastapi import FastAPI, HTTPException, Query 
from pydantic import BaseModel
from enum import Enum
import httpx 
from fastapi.middleware.cors import CORSMiddleware # CORS middleware
from cachetools import TTLCache # Caching
import time # For time.time() in TTLCache key generation, though TTLCache handles this internally

# Create a TTL cache with a max size of 1024 and a TTL of 600 seconds (10 minutes)
github_issues_cache = TTLCache(maxsize=1024, ttl=600)

class ScoredIssue(BaseModel):
    id: int
    number: int
    title: str
    user: str
    state: str
    created_at: str
    updated_at: str
    labels: List[str]
    html_url: str
    priority_score: float
    friendliness_score: float

class ScoredIssuesResponse(BaseModel):
    owner: str
    repo: str
    issues: List[ScoredIssue]

class SortBy(str, Enum):
    priority = "priority"
    friendliness = "friendliness"
    created_at = "created_at"

def calculate_priority_score(issue: dict) -> float:
    labels = {label["name"].lower() for label in issue.get("labels", [])}
    comments = issue.get("comments", 0)

    score = 0.0

    #Label-based scoring
    if "bug" in labels:
        score += 3.0
    if "critical" in labels or "high priority" in labels:
        score += 4.0
    if "enhancement" in labels or "feature" in labels:
        score += 1.0
    
    #Activity-based scoring
    score += min(comments, 10) * 0.3  # more comments -> more important

    return score

def compute_friendliness_score(issue: dict) -> float:
    labels = {label["name"].lower() for label in issue.get("labels", [])}
    body = issue.get("body", "") or ""
    comments = issue.get("comments", 0)

    score = 0.0  # Start with a base score

    #Label-based scoring
    if "good first issue" in labels or "help wanted" in labels:
        score += 3.0
    if "bug" in labels:
        score -= 1.0

    #Activity-based scoring
    if comments > 5:
        score -= 2.0  # More comments might indicate complexity
    
    #Detailed descriptions make issues more approachable and understandable
    if len(body) > 300:
        score += 1.0

    return max(score, 0.0)  # Ensure non-negative score

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", # Default for create-react-app
        "http://localhost:5173"  # Default for Vite
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

GITHUB_API_BASE = "https://api.github.com"

# Manually handle caching for the async function
async def get_github_issues_cached(owner: str, repo: str):
    """
    Fetches issues from GitHub API with caching.
    """
    cache_key = (owner, repo)
    if cache_key in github_issues_cache:
        print(f"Fetching issues for {owner}/{repo} from cache (cache hit)")
        return github_issues_cache[cache_key]

    print(f"Fetching issues from GitHub API for {owner}/{repo} (cache miss)")
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
    github_issues_cache[cache_key] = data # Store the awaited result
    return data


@app.get("/repos/{owner}/{repo}/issues", response_model=ScoredIssuesResponse)
async def list_repo_issues(
    owner: str, 
    repo: str,
    sort_by: SortBy = Query(SortBy.priority, description="Field to sort by."),
    direction: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction, either 'asc' or 'desc'."),
    limit: int = Query(20, ge=1, le=100, description="Number of issues to return."),
    offset: int = Query(0, ge=0, description="Number of issues to skip.")
    ) -> ScoredIssuesResponse:
    """
    Fetches issues for a given GitHub repository.
    Example: /repos/facebook/react/contributors
    """
    # Use the cached function to get GitHub issues
    data = await get_github_issues_cached(owner, repo)

    issues: list[ScoredIssue] = []

    for issue in data:
        if "pull_request" in issue:
            continue

        labels = [label["name"].lower() for label in issue.get("labels", [])]
        priority_score = calculate_priority_score(issue)
        friendliness_score = compute_friendliness_score(issue)

        scored_issue = ScoredIssue(
            id=issue["id"],
            number=issue["number"],
            title=issue["title"],
            user=issue["user"]["login"],
            state=issue["state"],
            created_at=issue["created_at"],
            updated_at=issue["updated_at"],
            labels=labels,
            html_url=issue["html_url"],
            priority_score=priority_score,
            friendliness_score=friendliness_score,
        )
        issues.append(scored_issue)

    # Apply sorting
    if sort_by == SortBy.priority:
        key_fn = lambda issue: issue.priority_score
    elif sort_by == SortBy.friendliness:
        key_fn = lambda issue: issue.friendliness_score
    else:
        key_fn = lambda issue: issue.created_at

    #Apply pagination
    issues = issues[offset:offset + limit]
    reverse = (direction == "desc")
    issues = sorted(issues, key=key_fn, reverse=reverse)
    return ScoredIssuesResponse(owner=owner, repo=repo, issues=issues)
        