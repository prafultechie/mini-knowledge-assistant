
import React, { useEffect, useState } from 'react';
import './styles.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const suggestions = [
  'What is available in my knowledge base?',
  'Summarize the main points',
  'What policies should I know about?',
];

export default function App() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [documents, setDocuments] = useState([]);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState('');
  const [activeTab, setActiveTab] = useState('assistant');
  const [apiOnline, setApiOnline] = useState(null);

  async function loadDocuments() {
    try {
      const response = await fetch(`${API_URL}/documents?page=1&page_size=20`);
      if (!response.ok) throw new Error('Could not load documents.');
      const data = await response.json();
      setDocuments(data.items || []);
      setApiOnline(true);
    } catch {
      setApiOnline(false);
      setNotice('Cannot connect to the backend. Check that FastAPI is running.');
    }
  }

  useEffect(() => {
    loadDocuments();
  }, []);

  async function askQuestion(event) {
    event.preventDefault();

    if (!question.trim()) {
      setError('Enter a question first.');
      return;
    }

    setLoading(true);
    setError('');
    setAnswer(null);

    try {
      const response = await fetch(`${API_URL}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: question.trim() }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'The question could not be answered.');
      }

      setAnswer(data);
    } catch (err) {
      setError(err.message || 'Request failed. Check that the backend is running.');
    } finally {
      setLoading(false);
    }
  }

  async function addDocument(event) {
    event.preventDefault();
    setSaving(true);
    setNotice('');

    try {
      const response = await fetch(`${API_URL}/documents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title.trim(),
          content: content.trim(),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'The article could not be saved.');
      }

      setTitle('');
      setContent('');
      setNotice(`"${data.title}" was added to your knowledge base.`);
      await loadDocuments();
      setActiveTab('documents');
    } catch (err) {
      setNotice(err.message || 'Could not save the article.');
    } finally {
      setSaving(false);
    }
  }

  function openAssistantWithQuestion(value) {
    setQuestion(value);
    setAnswer(null);
    setError('');
    setActiveTab('assistant');
  }

  function renderSources(sources = []) {
    if (!sources.length) {
      return <p className="muted">No matching sources were returned.</p>;
    }

    return (
      <div className="sources-list">
        {sources.map((source) => (
          <article
            className="source"
            key={`${source.document_id}-${source.chunk_id}`}
          >
            <div className="source-symbol">↗</div>
            <div className="source-copy">
              <strong>{source.title}</strong>
              <p>{source.excerpt}</p>
              <div className="source-meta">
                <span>Document #{source.document_id}</span>
                <span>Chunk #{source.chunk_id}</span>
                <span>
                  Relevance {Math.round((source.score || 0) * 100)}%
                </span>
              </div>
            </div>
          </article>
        ))}
      </div>
    );
  }

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <button
          className="brand"
          type="button"
          onClick={() => setActiveTab('assistant')}
        >
          <span className="brand-logo">mk<span>.</span></span>
          <span className="brand-name">
            mini<span>knowledge</span>
          </span>
        </button>

        <div className="workspace-label">WORKSPACE</div>

        <nav className="side-nav" aria-label="Main navigation">
          <button
            className={`nav-item ${activeTab === 'assistant' ? 'active' : ''}`}
            onClick={() => setActiveTab('assistant')}
          >
            <span className="nav-icon">⌘</span>
            <span>Assistant</span>
          </button>

          <button
            className={`nav-item ${activeTab === 'documents' ? 'active' : ''}`}
            onClick={() => setActiveTab('documents')}
          >
            <span className="nav-icon">▤</span>
            <span>Documents</span>
            <span className="nav-count">{documents.length}</span>
          </button>

          <button
            className={`nav-item ${activeTab === 'add' ? 'active' : ''}`}
            onClick={() => setActiveTab('add')}
          >
            <span className="nav-icon">＋</span>
            <span>Add knowledge</span>
          </button>
        </nav>

        <div className="sidebar-bottom">
          <div className="system-card">
            <div className="system-card-top">
              <span className="system-dot" />
              <span>LOCAL AI</span>
              <span className="system-live">OLLAMA</span>
            </div>

            <strong>Running locally</strong>
            <p>Documents and questions are processed by your local AI setup.</p>

            <div className="model-tags">
              <span>nomic-embed-text</span>
              <span>llama3.2:3b</span>
            </div>
          </div>

          <div className="sidebar-footer">
            <span className="avatar">MK</span>
            <div className="profile-copy">
              <strong>Knowledge workspace</strong>
              <small>Local environment</small>
            </div>
            <span className="more-icon">···</span>
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>Workspace</span>
            <span className="crumb-slash">/</span>
            <strong>
              {activeTab === 'assistant'
                ? 'Assistant'
                : activeTab === 'documents'
                  ? 'Documents'
                  : 'Add knowledge'}
            </strong>
          </div>

          <div className="topbar-right">
            <span className="connection-status">
              <i className={apiOnline === false ? 'offline' : ''} />
              {apiOnline === null
                ? 'Checking API'
                : apiOnline
                  ? 'API connected'
                  : 'API offline'}
            </span>

            <a
              className="docs-link"
              href={`${API_URL}/docs`}
              target="_blank"
              rel="noreferrer"
            >
              API docs ↗
            </a>
          </div>
        </header>

        <div className="page-content">
          {activeTab === 'assistant' && (
            <>
              <section className="welcome-section">
                <div className="page-eyebrow">
                  <span className="eyebrow-line" />
                  KNOWLEDGE WORKSPACE
                </div>

                <h1>
                  Good questions start
                  <br className="desktop-break" /> with{' '}
                  <span>good knowledge.</span>
                </h1>

                <p>
                  Ask something about your documents. Get a focused answer
                  with source excerpts you can verify.
                </p>
              </section>

              <section className="assistant-card">
                <div className="card-topline">
                  <div className="card-title-icon">✳</div>

                  <div className="card-heading">
                    <h2>Ask your knowledge base</h2>
                    <p>Search your documents using natural language</p>
                  </div>

                  <span className="private-badge">
                    <i /> Local inference
                  </span>
                </div>

                <form onSubmit={askQuestion} className="question-form">
                  <label htmlFor="question">YOUR QUESTION</label>

                  <textarea
                    id="question"
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    placeholder="Ask about a policy, process, or anything in your documents..."
                    rows={3}
                    maxLength={1000}
                  />

                  <div className="question-footer">
                    <span>{question.length}/1000 characters</span>

                    <button
                      className="primary-button"
                      type="submit"
                      disabled={loading}
                    >
                      {loading ? (
                        <>
                          <span className="spinner" /> Searching
                        </>
                      ) : (
                        <>Find answer <span>↗</span></>
                      )}
                    </button>
                  </div>
                </form>

                {!answer && !loading && (
                  <div className="suggestion-area">
                    <span className="suggestion-label">TRY ASKING</span>

                    <div className="suggestion-list">
                      {suggestions.map((item) => (
                        <button
                          key={item}
                          type="button"
                          className="suggestion-chip"
                          onClick={() => openAssistantWithQuestion(item)}
                        >
                          {item} <span>↗</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {error && (
                  <div className="alert error" role="alert">
                    <strong>Request failed</strong>
                    <p>{error}</p>
                  </div>
                )}

                {loading && (
                  <div className="loading-note">
                    <span className="spinner dark" />
                    <div>
                      <strong>Searching your knowledge base</strong>
                      <p>Retrieving relevant chunks and generating an answer locally.</p>
                    </div>
                  </div>
                )}

                {answer && (
                  <div className="answer-block" aria-live="polite">
                    <div className="answer-heading">
                      <span className="answer-icon">✳</span>
                      <div>
                        <h3>Generated answer</h3>
                        <p>Review the source excerpts below</p>
                      </div>
                      <span className="answer-status">COMPLETE</span>
                    </div>

                    <div className="answer-text">{answer.answer}</div>

                    <div className="sources-heading">
                      <div>
                        <h3>Retrieved sources</h3>
                        <p>Documents used to support this response</p>
                      </div>
                      <span>{answer.sources?.length || 0}</span>
                    </div>

                    {renderSources(answer.sources || [])}

                    <button
                      className="text-button"
                      type="button"
                      onClick={() => {
                        setAnswer(null);
                        setError('');
                      }}
                    >
                      ← Ask another question
                    </button>
                  </div>
                )}
              </section>

              <div className="workspace-stats">
                <div className="stat-card">
                  <span className="stat-icon">▤</span>
                  <div>
                    <small>KNOWLEDGE BASE</small>
                    <strong>{documents.length} articles loaded</strong>
                  </div>
                </div>

                <div className="stat-card">
                  <span className="stat-icon green">⌘</span>
                  <div>
                    <small>PROCESSING</small>
                    <strong>Local Ollama models</strong>
                  </div>
                </div>
              </div>
            </>
          )}

          {activeTab === 'documents' && (
            <section className="page-section">
              <div className="page-eyebrow">
                <span className="eyebrow-line" /> KNOWLEDGE MANAGEMENT
              </div>

              <div className="page-title-row">
                <div>
                  <h1>Your documents<span>.</span></h1>
                  <p>Browse the articles available to your assistant.</p>
                </div>

                <button
                  className="primary-button"
                  onClick={() => {
                    setNotice('');
                    setActiveTab('add');
                  }}
                >
                  ＋ Add article
                </button>
              </div>

              {notice && (
                <p className="notice" role="status">{notice}</p>
              )}

              {documents.length ? (
                <div className="document-grid">
                  {documents.map((doc) => (
                    <article className="document-card" key={doc.document_id}>
                      <div className="document-card-top">
                        <span className="document-card-icon">▤</span>
                        <span className="document-label">ARTICLE</span>
                      </div>

                      <h3>{doc.title}</h3>
                      <p>Available to search in your local knowledge base.</p>

                      <div className="document-card-footer">
                        <span>
                          {doc.created_at
                            ? new Date(doc.created_at).toLocaleDateString()
                            : 'Date unavailable'}
                        </span>

                        <button
                          className="text-button"
                          onClick={() =>
                            openAssistantWithQuestion(
                              `Summarize the article "${doc.title}".`
                            )
                          }
                        >
                          Ask about it ↗
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="empty-state">
                  <span>▤</span>
                  <h3>No documents yet</h3>
                  <p>Add an article to start building your knowledge base.</p>
                  <button
                    className="primary-button"
                    onClick={() => setActiveTab('add')}
                  >
                    Add your first article
                  </button>
                </div>
              )}
            </section>
          )}

          {activeTab === 'add' && (
            <section className="page-section">
              <div className="page-eyebrow">
                <span className="eyebrow-line" /> KNOWLEDGE MANAGEMENT
              </div>

              <div className="page-title-row">
                <div>
                  <h1>Add knowledge<span>.</span></h1>
                  <p>
                    Save an article and let Ollama create embeddings for retrieval.
                  </p>
                </div>
              </div>

              <div className="editor-card">
                <div className="editor-heading">
                  <span className="document-card-icon">＋</span>
                  <div>
                    <h2>New knowledge article</h2>
                    <p>Fields marked with * are required.</p>
                  </div>
                </div>

                <form className="add-form" onSubmit={addDocument}>
                  <label htmlFor="title">Article title *</label>
                  <input
                    id="title"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder="e.g. Refund Policy"
                    maxLength={200}
                    required
                  />

                  <div className="content-label-row">
                    <label htmlFor="content">Article content *</label>
                    <span>{content.length.toLocaleString()} / 50,000</span>
                  </div>

                  <textarea
                    id="content"
                    value={content}
                    onChange={(event) => setContent(event.target.value)}
                    placeholder="Write a policy, FAQ, product guide, or troubleshooting steps..."
                    rows={10}
                    maxLength={50000}
                    required
                  />

                  <div className="editor-note">
                    <span>✳</span>
                    <p>
                      Your content is processed using your configured local
                      Ollama embedding model.
                    </p>
                  </div>

                  <div className="editor-actions">
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => {
                        setTitle('');
                        setContent('');
                        setNotice('');
                      }}
                    >
                      Clear fields
                    </button>

                    <button
                      className="primary-button"
                      type="submit"
                      disabled={saving}
                    >
                      {saving ? (
                        <><span className="spinner" /> Saving article</>
                      ) : (
                        <>Save article <span>↗</span></>
                      )}
                    </button>
                  </div>

                  {notice && (
                    <p className="notice" role="status">{notice}</p>
                  )}
                </form>
              </div>
            </section>
          )}
        </div>

        <footer className="app-footer">
          <span>MINI KNOWLEDGE ASSISTANT</span>
          <span>Local-first · Ollama powered</span>
        </footer>
      </main>
    </div>
  );
}
