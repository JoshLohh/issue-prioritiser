from typing import List
from fastapi import FastAPI, HTTPException, Query, Request, Depends
from pydantic import BaseModel
from enum import Enum
import httpx 
import os
from fastapi.middleware.cors import CORSMiddleware
import re
from sqlalchemy.orm import Session
import datetime

from . import models, database # Import models and database
from .database import engine # Import engine to create tables

# Helper to parse GitHub's Link header for pagination
def parse_link_header(headers):
    links = {}
    if "link" in headers:
        link_header = headers["link"]
        link_parts = link_header.split(', ')
        for part in link_parts:
            match = re.match(r'<(.*)>; rel="(.*)"', part)
            if match:
                url, rel = match.groups()
                links[rel] = url
    return links

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
    total_issues: int
    issues: List[ScoredIssue]

class SortBy(str, Enum):
    priority = "priority"
    friendliness = "friendliness"
    created_at = "created_at"

def calculate_priority_score(issue: dict) -> float:
    labels = {label["name"].lower() for label in issue.get("labels", [])}
    comments = issue.get("comments", 0)
    score = 0.0
    if "bug" in labels:
        score += 3.0
    if "critical" in labels or "high priority" in labels:
        score += 4.0
    if "enhancement" in labels or "feature" in labels:
        score += 1.0
    score += min(comments, 10) * 0.3
    return score

def compute_friendliness_score(issue: dict) -> float:
    labels = {label["name"].lower() for label in issue.get("labels", [])}
    body = issue.get("body", "") or ""
    comments = issue.get("comments", 0)
    score = 0.0
    if "good first issue" in labels or "help wanted" in labels:
        score += 3.0
    if "bug" in labels:
        score -= 1.0
    if comments > 5:
        score -= 2.0
    if len(body) > 300:
        score += 1.0
    return max(score, 0.0)

app = FastAPI()

# Create database tables on startup
@app.on_event("startup")
def on_startup():
    models.Base.metadata.create_all(bind=engine)

@app.middleware("http")
async def add_cache_control_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "public, max-age=180"
    return response

# Origins for CORS
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
]

# If a frontend URL is set in the environment, add it to the origins list
FRONTEND_URL = os.environ.get("FRONTEND_URL")
if FRONTEND_URL:
    origins.append(FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

GITHUB_API_BASE = "https://api.github.com"

async def get_all_github_issues(owner: str, repo: str):
    """
    Fetches ALL issues from the GitHub repository by handling pagination.
    """
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
    all_issues = []
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues"
    is_first_request = True
    
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    async with httpx.AsyncClient(follow_redirects=True) as client:
        while url:
            if is_first_request:
                params = {"state": "open", "per_page": 100}
                is_first_request = False
            else:
                params = None

            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code == 403:
                # Distinguish between auth failure and rate limit
                if GITHUB_TOKEN:
                    detail = "GitHub API request failed: 403 Forbidden. This could be due to an invalid token or insufficient permissions."
                else:
                    detail = "GitHub API rate limit exceeded. Please set a GITHUB_TOKEN environment variable to increase your rate limit."
                raise HTTPException(status_code=403, detail=detail)

            if response.status_code == 404 and not all_issues:
                raise HTTPException(status_code=404, detail="Repository not found.")
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Error fetching issues from GitHub.")

            all_issues.extend(response.json())
            
            links = parse_link_header(response.headers)
            url = links.get("next")

    return all_issues


@app.get("/repos/{owner}/{repo}/issues", response_model=ScoredIssuesResponse)
async def list_repo_issues(
    owner: str, 
    repo: str,
    sort_by: SortBy = Query(SortBy.priority, description="Field to sort by."),
    direction: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction, either 'asc' or 'desc'."),
    limit: int = Query(25, ge=1, le=100, description="Number of issues to return."),
    offset: int = Query(0, ge=0, description="Number of issues to skip."),
    db: Session = Depends(database.get_db) 
    ) -> ScoredIssuesResponse:
    
    all_raw_issues = await get_all_github_issues(owner, repo)

    scored_issues: list[ScoredIssue] = []
    for issue_data in all_raw_issues: 
        if "pull_request" in issue_data:
            continue

        labels = [label["name"].lower() for label in issue_data.get("labels", [])]
        priority_score = calculate_priority_score(issue_data)
        friendliness_score = compute_friendliness_score(issue_data)

        # Create ScoredIssue Pydantic model
        scored_issue = ScoredIssue(
            id=issue_data["id"],
            number=issue_data["number"],
            title=issue_data["title"],
            user=issue_data["user"]["login"],
            state=issue_data["state"],
            created_at=issue_data["created_at"],
            updated_at=issue_data["updated_at"],
            labels=labels,
            html_url=issue_data["html_url"],
            priority_score=priority_score,
            friendliness_score=friendliness_score,
        )
        scored_issues.append(scored_issue)

        # Save or update issue in the database
        db_issue = db.query(models.Issue).filter(models.Issue.id == scored_issue.id).first()
        if db_issue:
            # Update existing issue
            db_issue.number = scored_issue.number
            db_issue.title = scored_issue.title
            db_issue.user = scored_issue.user
            db_issue.state = scored_issue.state
            db_issue.created_at = scored_issue.created_at
            db_issue.updated_at = scored_issue.updated_at
            db_issue.labels = scored_issue.labels
            db_issue.html_url = scored_issue.html_url
            db_issue.priority_score = scored_issue.priority_score
            db_issue.friendliness_score = scored_issue.friendliness_score
        else:
            # Create new issue
            db_issue = models.Issue(
                id=scored_issue.id,
                number=scored_issue.number,
                title=scored_issue.title,
                user=scored_issue.user,
                state=scored_issue.state,
                created_at=scored_issue.created_at,
                updated_at=scored_issue.updated_at,
                labels=scored_issue.labels,
                html_url=scored_issue.html_url,
                priority_score=scored_issue.priority_score,
                friendliness_score=scored_issue.friendliness_score,
            )
            db.add(db_issue)
    
    db.commit() 
    # Refresh the instances to ensure they reflect any changes from the database
    for issue_obj in scored_issues:
        db.refresh(db.query(models.Issue).filter(models.Issue.id == issue_obj.id).first())


    if sort_by == SortBy.priority:
        key_fn = lambda issue: issue.priority_score
    elif sort_by == SortBy.friendliness:
        key_fn = lambda issue: issue.friendliness_score
    else:
        key_fn = lambda issue: issue.created_at

    reverse = (direction == "desc")
    sorted_issues = sorted(scored_issues, key=key_fn, reverse=reverse)
    
    total_issues = len(sorted_issues)
    paginated_issues = sorted_issues[offset:offset + limit]

    return ScoredIssuesResponse(owner=owner, repo=repo, total_issues=total_issues, issues=paginated_issues)