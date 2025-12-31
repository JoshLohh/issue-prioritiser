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
from datetime import timedelta

from . import models, database # Import models and database
from .database import engine # Import engine to create tables

# Time limit before refreshing data
REFRESH_THRESHOLD = timedelta(hours=1)

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
    force_refresh: bool = Query(False, description="Force a refresh from the GitHub API, ignoring the cache."),
    db: Session = Depends(database.get_db) 
    ) -> ScoredIssuesResponse:

    # Caching Logic
    should_fetch_from_api = True
    if not force_refresh:
        repo_record = db.query(models.Repo).filter_by(owner=owner, name=repo).first()
        if repo_record:
            time_since_refresh = datetime.datetime.now() - repo_record.last_refreshed
            if time_since_refresh < REFRESH_THRESHOLD:
                should_fetch_from_api = False

    if should_fetch_from_api:
        # Raw issues
        all_raw_issues = await get_all_github_issues(owner, repo)

        # Put necessary issues into db
        for issue_data in all_raw_issues: 
            if "pull_request" in issue_data:
                continue
            
            db_issue = db.query(models.Issue).filter(models.Issue.id == issue_data["id"]).first()

            if not db_issue:
                # If it's a new issue, create a new record
                db_issue = models.Issue(id=issue_data["id"])
                db.add(db_issue)
            
            # Update record
            db_issue.number = issue_data["number"]
            db_issue.title = issue_data["title"]
            db_issue.user = issue_data["user"]["login"]
            db_issue.state = issue_data["state"]
            db_issue.created_at = datetime.datetime.fromisoformat(issue_data["created_at"].replace('Z', '+00:00'))
            db_issue.updated_at = datetime.datetime.fromisoformat(issue_data["updated_at"].replace('Z', '+00:00'))
            db_issue.labels = [label["name"].lower() for label in issue_data.get("labels", [])]
            db_issue.html_url = issue_data["html_url"]
            db_issue.priority_score = calculate_priority_score(issue_data)
            db_issue.friendliness_score = compute_friendliness_score(issue_data)

        # Update the repo's last_refreshed timestamp
        repo_record = db.query(models.Repo).filter_by(owner=owner, name=repo).first()
        if not repo_record:
            repo_record = models.Repo(owner=owner, name=repo)
            db.add(repo_record)
        repo_record.last_refreshed = datetime.datetime.now()
        
        db.commit()

    # Query db 
    sort_column_map = {
        "priority": models.Issue.priority_score,
        "friendliness": models.Issue.friendliness_score,
        "created_at": models.Issue.created_at,
    }
    sort_column = sort_column_map.get(sort_by, models.Issue.priority_score)

    # Apply descending or ascending order
    if direction == "desc":
        sort_expression = sort_column.desc()
    else:
        sort_expression = sort_column.asc()

    # Execute query
    query = db.query(models.Issue).order_by(sort_expression)
    total_issues = query.count()
    paginated_db_issues = query.offset(offset).limit(limit).all()

    # Convert the database models to Pydantic models for response
    scored_issues = [
        ScoredIssue(
            id=db_issue.id,
            number=db_issue.number,
            title=db_issue.title,
            user=db_issue.user,
            state=db_issue.state,
            created_at=db_issue.created_at.isoformat(),
            updated_at=db_issue.updated_at.isoformat(),
            labels=db_issue.labels,
            html_url=db_issue.html_url,
            priority_score=db_issue.priority_score,
            friendliness_score=db_issue.friendliness_score,
        ) for db_issue in paginated_db_issues
    ]
    
    return ScoredIssuesResponse(owner=owner, repo=repo, total_issues=total_issues, issues=scored_issues)