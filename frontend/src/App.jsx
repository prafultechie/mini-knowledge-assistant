import { useEffect, useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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

  async function loadDocuments() {
    try {
      const response = await fetch(`${API_URL}/documents?page=1&page_size=20`);
      if (!response.ok) throw new Error('Could not load the document list.');
      const data = await response.json();
      setDocuments(data.items || []);
    } catch (err) {
      setNotice(err.message || 'Could not connect to the API.');
    }
  }

  useEffect(() => { loadDocuments(); }, []);

  async function askQuestion(event) {
    event.preventDefault();
    if (!question.trim()) { setError('Enter a question first.'); return; }
    setLoading(true); setError(''); setAnswer(null);
    try {
      const response = await fetch(`${API_URL}/ask`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: question.trim() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'The question could not be answered.');
      setAnswer(data);
    } catch (err) {
      setError(`${err.message || 'Request failed.'} Check that the backend is running.`);
    } finally { setLoading(false); }
  }

  async function addDocument(event) {
    event.preventDefault(); setSaving(true); setNotice('');
    try {
      const response = await fetch(`${API_URL}/documents`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title.trim(), content: content.trim() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'The article could not be saved.');
      setTitle(''); setContent(''); setNotice(`“${data.title}” was added to the knowledge base.`);
      await loadDocuments();
    } catch (err) { setNotice(err.message || 'Could not save article.'); }
    finally { setSaving(false); }
  }

  return <main className="shell">
    <header className="topbar"><div className="brand-mark">K</div><div><p className="eyebrow">INTERNAL SUPPORT</p><h1>Knowledge Assistant</h1></div><span className="status"><i /> Local demo</span></header>
    <section className="intro"><p className="eyebrow">YOUR TEAM'S KNOWLEDGE, IN ONE PLACE</p><h2>What do you need help with?</h2><p>Ask a question in plain English. Answers are based on the articles in your knowledge base, with sources you can check.</p></section>
    <section className="panel ask-panel"><form onSubmit={askQuestion}><label htmlFor="question">Ask a question</label><textarea id="question" value={question} onChange={e => setQuestion(e.target.value)} placeholder="e.g. How long do I have to request a refund?" rows="3" maxLength="1000" /><div className="form-footer"><span>{question.length}/1000</span><button type="submit" disabled={loading}>{loading ? <><span className="spinner" /> Searching…</> : <>Ask question <span>→</span></>}</button></div></form>
      {error && <div className="alert error" role="alert">{error}</div>}
      {loading && <div className="loading-note"><span className="spinner dark" /> Looking through your knowledge base…</div>}
      {answer && <div className="answer-block" aria-live="polite"><div className="answer-heading"><span className="answer-icon">✦</span><div><h3>Answer</h3><p>Generated from the available knowledge</p></div></div><p className="answer-text">{answer.answer}</p><div className="sources-heading">Sources <span>{answer.sources.length}</span></div>{answer.sources.length ? <div className="sources-list">{answer.sources.map(source => <article className="source" key={`${source.document_id}-${source.chunk_id}`}><div className="source-symbol">↗</div><div className="source-copy"><strong>{source.title}</strong><p>{source.excerpt}{source.excerpt.length >= 280 ? '…' : ''}</p><small>Document #{source.document_id} · Relevance {(source.score * 100).toFixed(0)}%</small></div></article>)}</div> : <p className="muted">No matching source was found.</p>}</div>}
    </section>
    <div className="lower-grid"><section className="panel"><div className="section-heading"><div><p className="eyebrow">KNOWLEDGE BASE</p><h3>Articles</h3></div><span className="count">{documents.length}</span></div>{documents.length ? <ul className="document-list">{documents.map(doc => <li key={doc.document_id}><span className="doc-icon">▤</span><span><strong>{doc.title}</strong><small>Added {new Date(doc.created_at).toLocaleDateString()}</small></span></li>)}</ul> : <p className="muted">No articles yet. Add one to get started.</p>}</section>
      <section className="panel"><div className="section-heading"><div><p className="eyebrow">CONTRIBUTE</p><h3>Add an article</h3></div></div><form className="add-form" onSubmit={addDocument}><label htmlFor="title">Article title</label><input id="title" value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g. Refund Policy" maxLength="200" required /><label htmlFor="content">Article content</label><textarea id="content" value={content} onChange={e => setContent(e.target.value)} placeholder="Write the policy, FAQ, or troubleshooting steps…" rows="5" maxLength="50000" required /><button className="secondary-button" type="submit" disabled={saving}>{saving ? 'Saving article…' : 'Add to knowledge base'}</button>{notice && <p className="notice" role="status">{notice}</p>}</form></section></div>
    <footer>Mini Knowledge Assistant <span>•</span> Built for internal support teams</footer>
  </main>;
}
