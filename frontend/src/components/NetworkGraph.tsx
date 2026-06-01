import ForceGraph2D from 'react-force-graph-2d'
import { useRef, useEffect, useState, useCallback, useMemo } from 'react'

interface GraphNode {
  id: string | number
  address?: string
  risk?: number
  val?: number
  group?: number
  x?: number
  y?: number
  [key: string]: unknown
}

interface GraphLink {
  source: string | number | GraphNode
  target: string | number | GraphNode
  value?: number
  [key: string]: unknown
}

interface GraphData {
  nodes: GraphNode[]
  links: GraphLink[]
}

interface Props {
  data: GraphData
  onNodeClick?: (node: GraphNode) => void
}

export function NetworkGraph({ data, onNodeClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const fgRef = useRef<any>(null)
  const [dimensions, setDimensions] = useState({ width: 600, height: 600 })

  // Use ResizeObserver for truly responsive sizing
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect
      if (width > 0 && height > 0) {
        setDimensions({ width, height })
      }
    })

    observer.observe(el)

    setDimensions({
      width: el.clientWidth || 600,
      height: el.clientHeight || 600,
    })

    return () => observer.disconnect()
  }, [])

  // Auto-center graph when data changes
  useEffect(() => {
    if (fgRef.current && data.nodes.length > 0) {
      // Give it a moment to settle before fitting to view
      setTimeout(() => {
        fgRef.current.zoomToFit(400, 50)
      }, 500)
    }
  }, [data])

  const getNodeColor = useCallback((node: GraphNode): string => {
    const risk = node.risk ?? 0
    if (risk > 80) return '#ef4444' // red   – critical
    if (risk > 50) return '#f97316' // orange – high
    if (risk > 20) return '#eab308' // yellow – medium
    return '#3b82f6'                // blue   – low
  }, [])

  const nodeCanvasObject = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = node.address ? `${node.address.slice(0, 6)}...${node.address.slice(-4)}` : String(node.id)
    const fontSize = 11 / globalScale
    ctx.font = `${fontSize}px "JetBrains Mono", "Fira Code", monospace`
    const textWidth = ctx.measureText(label).width
    const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2) as [number, number]

    const color = getNodeColor(node)
    const radius = Math.sqrt(node.val || 1) * 3

    // Draw node circle
    ctx.beginPath()
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false)
    ctx.fillStyle = color
    ctx.fill()

    // Add glow effect
    ctx.shadowColor = color
    ctx.shadowBlur = 15 / globalScale
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)'
    ctx.lineWidth = 1 / globalScale
    ctx.stroke()
    ctx.shadowBlur = 0 // reset for text

    // Draw label background for readability at high zoom
    if (globalScale > 1.5) {
      ctx.fillStyle = 'rgba(3, 7, 18, 0.6)'
      ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y + radius + 2, bckgDimensions[0], bckgDimensions[1])
      
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'
      ctx.fillText(label, node.x, node.y + radius + 2 + bckgDimensions[1] / 2)
    }
  }, [getNodeColor])

  const handleNodeClick = useCallback(
    (node: any) => {
      const graphNode = node as GraphNode
      
      // Aim at node from current distance
      if (fgRef.current) {
        fgRef.current.centerAt(node.x, node.y, 1000)
        fgRef.current.zoom(2.5, 1000)
      }

      if (onNodeClick) {
        onNodeClick(graphNode)
      }
    },
    [onNodeClick]
  )

  return (
    <div
      ref={containerRef}
      className="w-full h-full min-h-[400px] bg-gray-950 rounded-xl overflow-hidden border border-gray-800 shadow-2xl relative"
    >
      <div className="absolute top-4 left-4 z-10 flex gap-2">
         <div className="flex items-center gap-2 bg-gray-900/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-gray-800 text-[10px] font-bold uppercase tracking-wider text-gray-400">
            <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
            Live Graph
         </div>
      </div>

      {dimensions.width > 0 && (
        <ForceGraph2D
          ref={fgRef}
          graphData={data}
          width={dimensions.width}
          height={dimensions.height}
          backgroundColor="#030712"
          nodeCanvasObject={nodeCanvasObject}
          nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
            const radius = Math.sqrt(node.val || 1) * 3 + 2
            ctx.fillStyle = color
            ctx.beginPath()
            ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false)
            ctx.fill()
          }}
          linkDirectionalArrowLength={3}
          linkDirectionalArrowRelPos={1}
          linkDirectionalParticles={2}
          linkDirectionalParticleSpeed={(d: any) => d.value * 0.001 + 0.005}
          linkColor={() => 'rgba(31, 41, 55, 0.4)'}
          linkWidth={1}
          onNodeClick={handleNodeClick}
          cooldownTicks={100}
          d3AlphaDecay={0.02}
          d3VelocityDecay={0.3}
        />
      )}
    </div>
  )
}
