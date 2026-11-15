// Page shell. Query state, URL sync and tabs are added in later steps.

export default function App() {
  return (
    <>
      <header className="app-header">
        <div className="app-header__inner">
          <h1 className="app-title">SPHEREx Sky Viewer</h1>
          <p className="app-subtitle">See how a patch of sky changes over time in infrared.</p>
        </div>
      </header>

      <main className="app-main">
        <div className="status">Choose a target to begin.</div>
      </main>

      <footer className="app-footer">
        <div className="app-footer__inner">Data: SPHEREx, via NASA/IPAC Infrared Science Archive (IRSA)</div>
      </footer>
    </>
  )
}
