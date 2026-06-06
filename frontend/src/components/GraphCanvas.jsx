import  {ReactFlow, useNodesState, useEdgesState, Background} from 'reactflow'
import 'reactflow/dist/style.css'

function getNodeStyle(type) {
  if (type === 'paper') return { background: '#6A9AA0',border: "2px solid"}
  return {}
}

function getEdgeStyle(type) {
  if (type === 'conflict') return { stroke: '#581c87', strokeWidth: 5, strokeDasharray: '10 5'}
  if (type === 'owns') return { stroke: '#6b7280', strokeWidth: 3 }
  return {}
}

function calculatePos(node, graphData) {
  if (node.type === 'paper') {
    const paperNodes = graphData.nodes.filter(n => n.type === 'paper')
    const index = paperNodes.findIndex(n => n.id === node.id)
    return { x: index * 400, y: 0 }
  }
  if (node.type === 'claim') {
    const claimNodes = graphData.nodes.filter(n =>
      n.type === 'claim' && n.paper_id === node.paper_id
    )
    const index = claimNodes.findIndex(n => n.id === node.id)
    const xBase = node.paper_id === 'paper_a' ? 0 : 400
    return { x: ((-1)**(index))*75*(index)+xBase, y: ((-1)**(index))*(index+0.75) * 150 }
  }
  return { x: 0, y: 0 }
}

function transformData(graphData) {
  const rfNodes = graphData.nodes.map((node) => ({
    id: node.id,
    style:getNodeStyle(node.type),
    type: node.type === 'paper' ? 'paperNode' : 'claimNode',
    position: calculatePos(node, graphData),
    data: {
      id: node.id,
      label: node.type === 'paper' ? node.id : node.concept,
      text: node.type === 'paper' ? '' : node.text
    },
  }))

  const rfEdges = graphData.edges.map(edge => ({
    id: `${edge.source}-${edge.target}`,
    source: edge.source,
    target: edge.target,
    label: edge.conflict_type,
    data: {
      label: edge.conflict_type,
      source: edge.source,
      target: edge.target,
      summary: edge.summary,
      type_reasoning: edge.type_reasoning,
      interrogations: edge.interrogations,
    },
    style:getEdgeStyle(edge.type),
    labelStyle: { 
    fill: 'white', 
    fontSize: 11,
    fontWeight: 'bold'
    },
    labelBgStyle: { 
    fill: '#1f2937',
    },
    labelBgPadding: [6, 4],
    labelBgBorderRadius: 4,
  }))

  return { rfNodes, rfEdges }
}

export default function GraphCanvas({ graphData, onConflictSelect, onNodeSelect }) {
  const { rfNodes, rfEdges } = transformData(graphData)
  const [nodes, setNodes, onNodesChange] = useNodesState(rfNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(rfEdges)

    const onEdgeClick = (event, edge) => { {
      console.log('node clicked:', edge.data)
      onConflictSelect(edge.data)
    }
  }
    const onNodeClick = (event, node) => { {
      console.log('node clicked:', node.data)
      onNodeSelect(node.data)
    }
  }
    return (
    <div style={{ height: '900px', width: '1000px'}}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onEdgeClick={onEdgeClick}
        onNodeClick={onNodeClick}
        fitView
      />
    </div>
  )
}
