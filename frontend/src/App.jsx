import { useState } from 'react'
import './App.css'
import axios from 'axios'
import GraphCanvas from './components/GraphCanvas'

function App() {
  const [collapsed, setCollapsed] = useState(false);
  const [collapsed_bttm, setCollapse2] = useState(true);
  const [collapsed_right, setCollapse3] = useState(true);
  const [view,setView] = useState("");
  const [selectedConflict, setSelectedConflict] = useState(null)
  const [selectedNode, setSelectedNode] = useState(null)
  const [sessionId,setSessionId]=useState(null)
  const [graph,setGraph] = useState(null)
  const [toolName,setTool]=useState(null)
  const [toolPaper,setToolPaper]=useState(null)
  const papers= ["paper_a","paper_b"]
  const [toolres,toolResult]=useState(null)

  const [paperA,setPaperA]=useState(null)
  const [paperB,setPaperB]=useState(null)
  const [loading,setLoading]=useState(null)

  const [reviewMap,setMap]=useState(null)
  const [reviewMeta,setMeta]=useState(null)

  const handleUpload = async () => {
    setGraph(null)
    if (!paperA || !paperB) return
    setLoading(true)

    const formData = new FormData()
    formData.append('paper_a', paperA)
    formData.append('paper_b', paperB)

    try {
      const response = await axios.post('http://localhost:8000/upload', formData)
      setSessionId(response.data.session_id)
      setGraph(response.data.graph)
    } catch (error) {
      console.error('Upload failed:', error)
    } finally {
      setLoading(false)
    }
}
  const handleReview = async () => {
    setGraph(null)
    const formData = new FormData()
    formData.append('file', reviewMap)

    try {
      const response = await axios.post('http://localhost:8000/review', formData)
      setGraph(response.data)
    } catch (error) {
      console.error('Upload failed:', error)
    }
}

  const handleTool = async () => {
    const reqinfo=  {
          "session_id": sessionId,
          "tool":toolName,
          "node_a_id":selectedConflict.source,
          "node_b_id":selectedConflict.target,
          "paper":toolPaper
        }
    try {
      const response = await axios.post('http://localhost:8000/query', 
        {
          "session_id": sessionId,
          "tool":toolName,
          "node_a_id":selectedConflict.source,
          "node_b_id":selectedConflict.target,
          "paper":toolPaper
        })
      toolResult(response.data)
      console.log(response.data)
    } catch (error) {
      console.error('Upload failed:', error)
    }
}


  const handleMeta = async () => {
    const formData = new FormData()
    formData.append('file', reviewMeta)

    try {
      const response = await axios.post('http://localhost:8000/metadata', formData)
      setSessionId(response.data.session_id)
    } catch (error) {
      console.error('Upload failed:', error)
    }
}

  const handleNodeSelect = (nodeData) => {
    setSelectedNode(nodeData)
    setCollapse2(false)
}
  const handleEdgeSelect = (edgeData) => {
    setSelectedConflict(edgeData)
    setCollapse3(false)
    setView("right")
}
  return (
    <app>
        <section id="tab"> 
          <button
            className="collapse-btn"
            onClick={() => {setCollapsed(!collapsed)}}
          >
            {collapsed ? "❯❯" : "❮❮"}
          </button>

          <button
            type="button"
            className="investigate-b"
            onClick={()=>{setView("investigate"),setCollapsed(false)}}
          >
            Investigate
          </button>

          <button
            type="button"
            className="review-b"
            onClick={()=>{setView("review"),setCollapsed(false)}}
          >
            Review
          </button>

        </section>

        
      <section id="frame">

        <section id="side" className={`${view ==="" ? "":"hidden"} ${collapsed?"collapsed":""}`}> 
          <h2>Welcome!</h2>
          <p> This app is design to analyze and illustrate conflicting papers. To <code>Investigate</code>
            conflicting two papers, click on the Investigate button and upload the papers. 
            <br></br>Alternatively, you can view a conflict map prepared by someone else by clicking <code>Review</code> and uploading a graph.
          </p> 
        </section>

        <section id="investigate" className={`${view ==="investigate" ? "show":""}${collapsed?"-collapsed":""}`}> 
          <h2>Investigate</h2>
          <p>Upload two conflicting papers to analyze:</p>

          <div style={{display:"flex", flexDirection:"column", gap:"5px",padding:"20px 10px 0px 30px"}}>
            <input
              id="papera-upload"
              type="file"
              accept=".pdf"
              style={{ display: "none" }}
              onChange={e=> setPaperA(e.target.files[0])}>

            </input>
              <label htmlFor="papera-upload" id="investigate-b">
                Paper A
              </label>
            <input
              id="paperb-upload"
              type="file"
              accept=".pdf"
              style={{ display: "none" }}
              onChange={e=> setPaperB(e.target.files[0])}
              ></input>
              <label htmlFor="paperb-upload" id="investigate-b">
                Paper B
              </label>
          </div>
          <button
            onClick={handleUpload}
            disabled={!paperA || !paperB || loading}
            style={{
              marginTop: '10px',
              padding: '8px 16px',
              background: loading ? '#374151' : '#dc2626',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: !paperA || !paperB || loading ? 'not-allowed' : 'pointer',
              opacity: !paperA || !paperB ? 0.5 : 1
            }}
          >
            {loading ? 'Analyzing... (~1m)' : 'Run Analysis'}
          </button>
        </section>

        <section id="review" className={`${view ==="review" ? "show":""}${collapsed?"-collapsed":""}`}> 
          <h2>Review</h2>
          <p>Upload a conflict map to review:</p>

          <div style={{display:"flex", flexDirection:"column", gap:"5px",padding:"20px 10px 0px 30px"}}>
            <input
              id="conflict_map-upload"
              type="file"
              accept=".json"
              style={{ display: "none" }}
              onChange={e=> setMap(e.target.files[0])}
              ></input>

            <label htmlFor="conflict_map-upload" id="investigate-b">
              Choose a conflict map
            </label>
            
            <input
              id="conflict_meta-upload"
              type="file"
              accept=".json"
              style={{ display: "none" }}
              onChange={e=> setMeta(e.target.files[0])}
              ></input>

            <label htmlFor="conflict_meta-upload" id="investigate-b">
              Choose the meta data
            </label>

            <button
              onClick={()=>{handleReview(),handleMeta()}}
              disabled={!reviewMap || loading}
              style={{
                marginTop: '10px',
                padding: '8px 16px',
                background: loading ? '#374151' : '#dc2626',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: !reviewMap || loading ? 'not-allowed' : 'pointer',
                opacity: !reviewMap ? 0.5 : 1
              }}
            >
              {'View'}
            </button>

          </div>
        </section>

        <section id="center">
            {graph ? (
              <GraphCanvas graphData={graph} onConflictSelect={handleEdgeSelect} onNodeSelect={handleNodeSelect} />
            ) : (
              <div>
                <p>Choose a mode to begin</p>
              </div>
            )}
        </section>

        {selectedConflict && (
        <section id="rightPanel" className={`${view ==="right" ? "show":""}${collapsed_right?"-collapsed":""}`}> 
            <div style={{display: "flex", flexDirection: "row", alignItems: "center", justifyContent: "space-between", width: "98%"}}>
              <h2>Conflict Info</h2>
              <button
                className="collapse-btn-rel"
                onClick={() => setView("investigate")}
              >
                {"—"}
              </button>
            </div>
            <p><strong>Sesison:</strong> {sessionId}</p>
            <p><strong>Summary:</strong> {selectedConflict.summary}</p>
            <p><strong>Type:</strong> {selectedConflict.label}</p>
            <p><strong>Reasoning of Type:</strong> {selectedConflict.type_reasoning}</p>


            <div style={{alignItems:"center", padding:"25px 100px"}}> 
              <button
                type="button"
                className="interrogate-b"
                onClick={()=>{setView("interrogate")}}
              >
                <strong>Interrogation Mode</strong>
              </button>
            </div>
            <p><strong>Past Interrogations:</strong> {JSON.stringify(selectedConflict.interrogations,null,3)}</p>
        </section>
        )}
        <section id="interrogate" className={`${view ==="interrogate" ? "show":""}`}> 
            <div style={{display: "flex", flexDirection: "row", alignItems: "center", justifyContent: "space-between", width: "98%"}}>
              <h2>Tools</h2>
              <button
                className="collapse-btn-rel"
                onClick={() => setView("right")}
              >
                {"❮"}
              </button>
            </div>
            <label>Select Paper</label>
            <select value={toolPaper} onChange={(e) => setToolPaper(e.target.value)}>
              <option value="">Select paper</option>
              {papers.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            <div style={{display: "flex", flexDirection: "row", alignItems: "center", justifyContent: "space-between", width: "98%",padding:"10px 0px"}}>
              <button
                type="button"
                className="tool-b"
                onClick={()=>setTool('STEELMAN')}
              >
                <strong>Steelman</strong>
              </button>
              <button
                type="button"
                className="tool-b"
                onClick={()=>setTool('CHALLENGE')}
              >
                <strong>Challenge</strong>
              </button>
              <button
                type="button"
                className="tool-b"
                onClick={()=>setTool('ANSWER_FOR')}
              >
                <strong>Answer For</strong>
              </button>
            </div>
            <button
              onClick={()=>{handleTool()}}
              disabled={!toolName || loading}
              style={{
                marginTop: '0px',
                padding: '8px 16px',
                background: loading ? '#374151' : '#dc2626',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: !toolName  || loading ? 'not-allowed' : 'pointer',
                opacity: !toolName   ? 0.5 : 1
              }}
            >
              {'Interrogate'}
            </button>

            {toolres && (
              <section>
                <p>{JSON.stringify(toolres.result.response, null, 2)}</p>
              </section>
            )}

        </section>
      </section>

      {selectedNode && (
        <section id="bottom" className={collapsed_bttm? "collapsed":""}> 
              <div style={{display: "flex", flexDirection: "row", alignItems: "center", justifyContent: "space-between", width: "98%"}}>
                <h2>Node Info</h2>
                <button
                  className="collapse-btn-rel"
                  onClick={() => setCollapse2(true)}
                >
                  {"—"}
                </button>
              </div>
              <p><strong>Node ID:</strong> {selectedNode.id}</p>
              <p><strong>Concept:</strong> {selectedNode.label}</p>
              <p><strong>Relevant Text for the Claim:</strong>
              <br></br><strong>1.</strong>{" ..."+selectedNode.text[0]+" ..."}
              <br></br><strong>2.</strong>{" ..."+selectedNode.text[1]+" ..."}
              <br></br><strong>3.</strong>{" ..."+selectedNode.text[2]+" ..."}
              </p>  
        </section>
      )}

    </app>
  )
}

export default App
