from fastapi.testclient import TestClient
from backend.main import app, calculate_priority_score, compute_friendliness_score
import respx
from httpx import Response

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["Cache-Control"] == "public, max-age=180"

def test_calculate_priority_score():
    # Test with bug and high priority labels
    issue_bug_high = {
        "labels": [{"name": "bug"}, {"name": "High Priority"}],
        "comments": 5
    }
    assert calculate_priority_score(issue_bug_high) == 3.0 + 4.0 + (5 * 0.3)

    # Test with enhancement label
    issue_enhancement = {
        "labels": [{"name": "enhancement"}],
        "comments": 2
    }
    assert calculate_priority_score(issue_enhancement) == 1.0 + (2 * 0.3)

def test_compute_friendliness_score():
    # Test with good first issue
    issue_good_first = {
        "labels": [{"name": "Good First Issue"}],
        "body": "This is a short body.",
        "comments": 1
    }
    assert compute_friendliness_score(issue_good_first) == 3.0

@respx.mock
def test_list_repo_issues_multi_page():
    """
    Tests that the backend correctly fetches all pages from the GitHub API using explicit URL mocking.
    """
    owner = "test-owner"
    repo = "test-repo"
    
    page1_request_url = f"https://api.github.com/repos/{owner}/{repo}/issues?state=open&per_page=100"
    # This is the realistic URL GitHub would provide in the 'next' Link header
    page2_request_url = f"https://api.github.com/repos/{owner}/{repo}/issues?state=open&per_page=100&page=2"

    # Mock page 1: returns a "next" link to page 2
    respx.get(page1_request_url).return_value = Response(
        200,
        json=[{"id": 1, "title": "Issue from Page 1", "user": {"login": "u"}, "state": "open", "created_at": "2023-01-01T00:00:00Z", "updated_at": "2023-01-01T00:00:00Z", "labels": [], "html_url": "u1", "comments": 0, "body": "", "number": 1}],
        headers={"link": f'<{page2_request_url}>; rel="next"'}
    )
    
    # Mock page 2: returns no "next" link
    respx.get(page2_request_url).return_value = Response(
        200,
        json=[{"id": 2, "title": "Issue from Page 2", "user": {"login": "u"}, "state": "open", "created_at": "2023-01-02T00:00:00Z", "updated_at": "2023-01-02T00:00:00Z", "labels": [], "html_url": "u2", "comments": 0, "body": "", "number": 2}]
    )

    # Request issues from our backend. It should fetch both pages.
    response = client.get(f"/repos/{owner}/{repo}/issues")
    assert response.status_code == 200
    data = response.json()

    assert respx.calls.call_count == 2
    assert len(data["issues"]) == 2
    assert data["total_issues"] == 2
    assert response.headers["Cache-Control"] == "public, max-age=180"
    
    titles = {issue["title"] for issue in data["issues"]}
    assert "Issue from Page 1" in titles
    assert "Issue from Page 2" in titles
    

@respx.mock
def test_list_repo_issues_pagination_and_sorting():
    """
    Tests that pagination and sorting are applied correctly AFTER fetching all issues.
    """
    owner = "test-owner"
    repo = "test-repo-sorted"
    
    mock_issues = [
        {"id": 1, "number": 1, "title": "Low Prio", "user": {"login": "u"}, "state": "open", "created_at": "2023-01-01T00:00:00Z", "updated_at": "2023-01-01T00:00:00Z", "labels": [], "html_url": "u1", "comments": 0, "body": ""}, # Prio: 0
        {"id": 2, "number": 2, "title": "High Prio", "user": {"login": "u"}, "state": "open", "created_at": "2023-01-02T00:00:00Z", "updated_at": "2023-01-02T00:00:00Z", "labels": [{"name": "critical"}], "html_url": "u2", "comments": 0, "body": ""}, # Prio: 4
        {"id": 3, "number": 3, "title": "Mid Prio", "user": {"login": "u"}, "state": "open", "created_at": "2023-01-03T00:00:00Z", "updated_at": "2023-01-03T00:00:00Z", "labels": [{"name": "bug"}], "html_url": "u3", "comments": 0, "body": ""} # Prio: 3
    ]
    
    respx.get(f"https://api.github.com/repos/{owner}/{repo}/issues?state=open&per_page=100").return_value = Response(200, json=mock_issues)

    # Request page 1, sorted by priority desc, with a limit of 2
    response = client.get(f"/repos/{owner}/{repo}/issues?sort_by=priority&direction=desc&limit=2&offset=0")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "public, max-age=180"
    data = response.json()
    
    # Should get the first 2 of the fully sorted list
    assert data["total_issues"] == 3
    assert len(data["issues"]) == 2
    assert data["issues"][0]["title"] == "High Prio"
    assert data["issues"][1]["title"] == "Mid Prio"

    # Request page 2
    response = client.get(f"/repos/{owner}/{repo}/issues?sort_by=priority&direction=desc&limit=2&offset=2")
    assert response.status_code == 200
    data = response.json()
    
    # Should get the last remaining issue
    assert data["total_issues"] == 3
    assert len(data["issues"]) == 1
    assert data["issues"][0]["title"] == "Low Prio"

@respx.mock
def test_github_token_is_used(monkeypatch):
    """
    Tests that the GITHUB_TOKEN environment variable is used for authorization.
    """
    monkeypatch.setenv("GITHUB_TOKEN", "test_token_123")
    
    owner = "test-owner"
    repo = "test-repo-token"
    
    # Mock the GitHub API endpoint and get the route object
    gh_mock = respx.get(f"https://api.github.com/repos/{owner}/{repo}/issues?state=open&per_page=100")
    gh_mock.return_value = Response(200, json=[])
    
    client.get(f"/repos/{owner}/{repo}/issues")
    
    assert gh_mock.call_count == 1
    request = gh_mock.calls.last.request
    assert "Authorization" in request.headers
    assert request.headers["Authorization"] == "Bearer test_token_123"

@respx.mock
def test_403_error_handling():
    """
    Tests that a 403 error from GitHub is handled correctly.
    """
    owner = "test-owner"
    repo = "test-repo-403"
    
    # Mock the GitHub API to return a 403 error
    respx.get(f"https://api.github.com/repos/{owner}/{repo}/issues?state=open&per_page=100").return_value = Response(403)
    
    response = client.get(f"/repos/{owner}/{repo}/issues")
    
    assert response.status_code == 403
    assert "rate limit exceeded" in response.json()["detail"]