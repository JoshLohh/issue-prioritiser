from fastapi.testclient import TestClient
from backend.main import app, calculate_priority_score, compute_friendliness_score
import respx
from httpx import Response

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

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

    # Test with no special labels and no comments
    issue_normal = {
        "labels": [],
        "comments": 0
    }
    assert calculate_priority_score(issue_normal) == 0.0

    # Test with many comments
    issue_many_comments = {
        "labels": [],
        "comments": 20
    }
    assert calculate_priority_score(issue_many_comments) == 0.0 + (10 * 0.3) # Max comments effect is 10 * 0.3

def test_compute_friendliness_score():
    # Test with good first issue
    issue_good_first = {
        "labels": [{"name": "Good First Issue"}],
        "body": "This is a short body.",
        "comments": 1
    }
    assert compute_friendliness_score(issue_good_first) == 3.0

    # Test with bug label and many comments
    issue_bug_many_comments = {
        "labels": [{"name": "bug"}],
        "body": "This is a short body.",
        "comments": 6
    }
    assert compute_friendliness_score(issue_bug_many_comments) == max(0.0, -1.0 - 2.0)

    # Test with long body
    issue_long_body = {
        "labels": [],
        "body": "a" * 350,
        "comments": 0
    }
    assert compute_friendliness_score(issue_long_body) == 1.0

@respx.mock
def test_list_repo_issues():
    respx.get("https://api.github.com/repos/owner/repo/issues?state=open").return_value = Response(
        200,
        json=[
            {
                "id": 1,
                "number": 1,
                "title": "Bug Report",
                "user": {"login": "user1"},
                "state": "open",
                "created_at": "2023-01-01T10:00:00Z",
                "updated_at": "2023-01-01T10:00:00Z",
                "labels": [{"name": "bug"}, {"name": "critical"}],
                "html_url": "http://example.com/issue1",
                "comments": 3,
                "body": "Short description."
            },
            {
                "id": 2,
                "number": 2,
                "title": "Feature Request",
                "user": {"login": "user2"},
                "state": "open",
                "created_at": "2023-01-02T10:00:00Z",
                "updated_at": "2023-01-02T10:00:00Z",
                "labels": [{"name": "enhancement"}],
                "html_url": "http://example.com/issue2",
                "comments": 1,
                "body": "Long description." + "a"*300
            }
        ]
    )

    response = client.get("/repos/owner/repo/issues")
    assert response.status_code == 200
    data = response.json()
    assert data["owner"] == "owner"
    assert data["repo"] == "repo"
    assert len(data["issues"]) == 2

    issue1 = data["issues"][0]
    assert issue1["id"] == 1
    assert issue1["title"] == "Bug Report"
    assert "bug" in issue1["labels"]
    assert issue1["priority_score"] == calculate_priority_score({
        "labels": [{"name": "bug"}, {"name": "critical"}],
        "comments": 3
    })
    assert issue1["friendliness_score"] == compute_friendliness_score({
        "labels": [{"name": "bug"}, {"name": "critical"}],
        "comments": 3,
        "body": "Short description."
    })
    
    issue2 = data["issues"][1]
    assert issue2["id"] == 2
    assert issue2["title"] == "Feature Request"
    assert "enhancement" in issue2["labels"]
    assert issue2["priority_score"] == calculate_priority_score({
        "labels": [{"name": "enhancement"}],
        "comments": 1
    })
    assert issue2["friendliness_score"] == compute_friendliness_score({
        "labels": [{"name": "enhancement"}],
        "comments": 1,
        "body": "Long description." + "a"*300
    })

@respx.mock
def test_list_repo_issues_not_found():
    respx.get("https://api.github.com/repos/owner/nonexistent/issues?state=open").return_value = Response(
        404,
        json={"message": "Not Found"}
    )
    response = client.get("/repos/owner/nonexistent/issues")
    assert response.status_code == 404
    assert response.json() == {"detail": "Repository not found"}

@respx.mock
def test_list_repo_issues_github_error():
    respx.get("https://api.github.com/repos/owner/repo/issues?state=open").return_value = Response(
        500,
        json={"message": "Server Error"}
    )
    response = client.get("/repos/owner/repo/issues")
    assert response.status_code == 500
    assert response.json() == {"detail": "Error fetching issues from GitHub"}

@respx.mock
def test_list_repo_issues_sorting_priority_desc():
    mock_issues = [
        {
            "id": 1, "number": 1, "title": "A", "user": {"login": "u"}, "state": "open",
            "created_at": "2023-01-01T00:00:00Z", "updated_at": "2023-01-01T00:00:00Z",
            "labels": [{"name": "bug"}], "html_url": "url1", "comments": 0, "body": ""
        }, # priority 3.0
        {
            "id": 2, "number": 2, "title": "B", "user": {"login": "u"}, "state": "open",
            "created_at": "2023-01-02T00:00:00Z", "updated_at": "2023-01-02T00:00:00Z",
            "labels": [{"name": "critical"}], "html_url": "url2", "comments": 0, "body": ""
        }, # priority 4.0
    ]
    respx.get("https://api.github.com/repos/owner/repo/issues?state=open").return_value = Response(200, json=mock_issues)

    response = client.get("/repos/owner/repo/issues?sort_by=priority&direction=desc")
    assert response.status_code == 200
    issues = response.json()["issues"]
    assert len(issues) == 2
    assert issues[0]["id"] == 2 # Critical (4.0) should come before Bug (3.0)

@respx.mock
def test_list_repo_issues_sorting_friendliness_asc():
    mock_issues = [
        {
            "id": 1, "number": 1, "title": "A", "user": {"login": "u"}, "state": "open",
            "created_at": "2023-01-01T00:00:00Z", "updated_at": "2023-01-01T00:00:00Z",
            "labels": [{"name": "bug"}], "html_url": "url1", "comments": 0, "body": ""
        }, # friendliness max(0, -1) = 0
        {
            "id": 2, "number": 2, "title": "B", "user": {"login": "u"}, "state": "open",
            "created_at": "2023-01-02T00:00:00Z", "updated_at": "2023-01-02T00:00:00Z",
            "labels": [{"name": "good first issue"}], "html_url": "url2", "comments": 0, "body": ""
        }, # friendliness 3.0
    ]
    respx.get("https://api.github.com/repos/owner/repo/issues?state=open").return_value = Response(200, json=mock_issues)

    response = client.get("/repos/owner/repo/issues?sort_by=friendliness&direction=asc")
    assert response.status_code == 200
    issues = response.json()["issues"]
    assert len(issues) == 2
    assert issues[0]["id"] == 1 # Bug (0.0) should come before Good First Issue (3.0) when ascending

@respx.mock
def test_list_repo_issues_pagination():
    mock_issues = []
    for i in range(1, 11):
        mock_issues.append({
            "id": i, "number": i, "title": f"Issue {i}", "user": {"login": "u"}, "state": "open",
            "created_at": "2023-01-01T00:00:00Z", "updated_at": "2023-01-01T00:00:00Z",
            "labels": [], "html_url": f"url{i}", "comments": 0, "body": ""
        })
    respx.get("https://api.github.com/repos/owner/repo/issues?state=open").return_value = Response(200, json=mock_issues)

    # Test limit
    response = client.get("/repos/owner/repo/issues?limit=5")
    assert response.status_code == 200
    issues = response.json()["issues"]
    assert len(issues) == 5
    assert issues[0]["id"] == 1

    # Test offset
    response = client.get("/repos/owner/repo/issues?offset=5&limit=5")
    assert response.status_code == 200
    issues = response.json()["issues"]
    assert len(issues) == 5
    assert issues[0]["id"] == 6

    # Test offset and limit combined, going out of bounds
    response = client.get("/repos/owner/repo/issues?offset=8&limit=5")
    assert response.status_code == 200
    issues = response.json()["issues"]
    assert len(issues) == 2
    assert issues[0]["id"] == 9
    assert issues[1]["id"] == 10
