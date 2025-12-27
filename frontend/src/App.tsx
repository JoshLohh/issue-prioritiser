import { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

// Define the type for a single issue
interface Issue {
  id: number;
  number: number;
  title: string;
  user: string;
  state: string;
  created_at: string;
  updated_at: string;
  labels: string[];
  html_url: string;
  priority_score: number;
  friendliness_score: number;
}

type SortByType = 'priority' | 'friendliness' | 'created_at';
type DirectionType = 'asc' | 'desc';

const PAGE_SIZE = 20;

const range = (start: number, end: number) => {
  const length = end - start + 1;
  return Array.from({ length }, (_, idx) => idx + start);
};

function App() {
  const [owner, setOwner] = useState('');
  const [repo, setRepo] = useState('');
  const [issues, setIssues] = useState<Issue[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortByType>('priority');
  const [direction, setDirection] = useState<DirectionType>('desc');
  const [page, setPage] = useState(1);
  const [totalIssues, setTotalIssues] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  const fetchIssues = async (pageToFetch: number, forceRefresh = false) => {
    if (!owner || !repo) return;

    setLoading(true);
    setError(null);
    try {
      const offset = (pageToFetch - 1) * PAGE_SIZE;
      
      const params: { [key: string]: string | number } = {
        sort_by: sortBy,
        direction: direction,
        limit: PAGE_SIZE,
        offset: offset,
      };

      if (forceRefresh) {
        params['_'] = new Date().getTime();
      }

      const response = await axios.get(`http://localhost:8000/repos/${owner}/${repo}/issues`, { params });

      setIssues(response.data.issues);
      setTotalIssues(response.data.total_issues);
      setHasMore(offset + response.data.issues.length < response.data.total_issues);
      setPage(pageToFetch);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response) {
        setError(`Error: ${err.response.data.detail || err.message}`);
      } else {
        setError('An unexpected error occurred.');
      }
      setIssues([]); // Clear issues on error
    } finally {
      setLoading(false);
    }
  };

  // Effect for automatic refetch on sort/direction change
  useEffect(() => {
    if (owner && repo) {
      fetchIssues(1); // Reset to page 1 on sort change
    }
  }, [sortBy, direction]);

  const handleFetchClick = () => {
    fetchIssues(1);
  };
  
  const handlePreviousPage = () => {
    if (page > 1) {
      fetchIssues(page - 1);
    }
  };
  
  const handleNextPage = () => {
    if (hasMore) {
      fetchIssues(page + 1);
    }
  };

  const handleRefreshClick = () => {
    fetchIssues(page, true);
  };

  const renderPagination = () => {
    const totalPages = Math.ceil(totalIssues / PAGE_SIZE);
    if (totalPages <= 1) return null;
  
    const siblingCount = 1;
    const totalPageNumbers = siblingCount + 5;
  
    if (totalPageNumbers >= totalPages) {
      return range(1, totalPages).map(p => (
        <button key={p} onClick={() => fetchIssues(p)} className={page === p ? 'active' : ''} disabled={loading}>
          {p}
        </button>
      ));
    }
  
    const leftSiblingIndex = Math.max(page - siblingCount, 1);
    const rightSiblingIndex = Math.min(page + siblingCount, totalPages);
  
    const shouldShowLeftDots = leftSiblingIndex > 2;
    const shouldShowRightDots = rightSiblingIndex < totalPages - 2;
  
    const firstPageIndex = 1;
    const lastPageIndex = totalPages;
  
    let pages: (number | string)[] = [];
  
    if (shouldShowLeftDots) {
      pages.push(firstPageIndex, '...');
    }
  
    const middleRange = range(
      shouldShowLeftDots ? leftSiblingIndex : 1,
      shouldShowRightDots ? rightSiblingIndex : totalPages
    );
    pages = pages.concat(middleRange);
  
    if (shouldShowRightDots) {
      pages.push('...', lastPageIndex);
    }
  
    return pages.map((p, i) =>
      p === '...' ? (
        <span key={`dots-${i}`} className="pagination-dots">...</span>
      ) : (
        <button key={p} onClick={() => fetchIssues(p as number)} className={page === p ? 'active' : ''} disabled={loading}>
          {p}
        </button>
      )
    );
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>GitHub Issue Prioritizer</h1>
        <div className="repo-form">
          <input
            type="text"
            value={owner}
            onChange={(e) => setOwner(e.target.value)}
            placeholder="Owner (e.g., facebook)"
          />
          <input
            type="text"
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            placeholder="Repo (e.g., react)"
          />
          <button onClick={handleFetchClick} disabled={loading || !owner || !repo}>
            {loading ? 'Fetching...' : 'Fetch Issues'}
          </button>
        </div>
        <div className="sort-options">
          <label>
            Sort by:
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value as SortByType)}>
              <option value="priority">Priority</option>
              <option value="friendliness">Friendliness</option>
              <option value="created_at">Created Date</option>
            </select>
          </label>
          <label>
            Direction:
            <select value={direction} onChange={(e) => setDirection(e.target.value as DirectionType)}>
              <option value="desc">Descending</option>
              <option value="asc">Ascending</option>
            </select>
          </label>
          <button onClick={handleRefreshClick} disabled={loading || !owner || !repo}>
            Refresh
          </button>
        </div>
      </header>
      <main>
        {error && <p className="error-message">{error}</p>}
        {loading && <p>Loading issues...</p>}
        {!loading && !error && issues.length === 0 && (
          <p>No issues to display. Enter a repository and fetch issues.</p>
        )}
        {issues.length > 0 && (
          <div className="issues-list">
            <h2>Issues for {owner}/{repo} ({totalIssues} issues found, Page {page})</h2>
            <ul>
              {issues.map((issue) => (
                <li key={issue.id}>
                  <a href={issue.html_url} target="_blank" rel="noopener noreferrer">
                    #{issue.number}: {issue.title}
                  </a>
                  <p>
                    <strong>Priority Score:</strong> {issue.priority_score.toFixed(2)} |
                    <strong> Friendliness Score:</strong> {issue.friendliness_score.toFixed(2)}
                  </p>
                  <p>
                    Opened by <strong>{issue.user}</strong> on {new Date(issue.created_at).toLocaleDateString()}
                  </p>
                  <div className="labels">
                    {issue.labels.map((label) => (
                      <span key={label} className="label">{label}</span>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
            <div className="pagination">
              <button onClick={handlePreviousPage} disabled={page <= 1 || loading}>
                Previous
              </button>
              {renderPagination()}
              <button onClick={handleNextPage} disabled={!hasMore || loading}>
                Next
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;