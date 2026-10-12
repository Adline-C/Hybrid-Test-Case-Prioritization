/**
 * TestGraphView — Canvas force-directed knowledge graph for CHART-P rankings.
 *
 * Rendered via HTML5 Canvas (requestAnimationFrame) so particle halos stay at
 * ~60 FPS without React re-renders on every tick. Loaded as a classic script
 * so the CDN Babel dashboard can use <TestGraphView /> without a bundler.
 */
(function (global) {
  const { useRef, useEffect, useMemo } = React;

  const BG = "#0D0F12";
  const HIGH = "#FF7A00";
  const CYAN = "#00E5FF";
  const FILE_COLOR = "#F97316";
  const MODULE_COLOR = "#60a5fa";
  const CORE_COLOR = "#F1F5F9";

  function shortLabel(name) {
    if (!name) return "";
    return String(name).replace(/^.*::/, "");
  }

  function moduleOf(name) {
    if (!name) return "tests";
    return String(name).split("::")[0] || "tests";
  }

  function formatScore(score) {
    return Number(score).toFixed(1);
  }

  function buildGraphData(tests, changedFiles, commitSha, repoName, highThreshold) {
    const nodes = [];
    const links = [];
    const files = Array.isArray(changedFiles) ? changedFiles : [];
    const allTests = Array.isArray(tests) ? tests : [];
    
    // Sort tests to prioritize high score and overlap
    const sortedTests = allTests.slice().sort(function (a, b) {
      if (b.overlap !== a.overlap) return (b.overlap ? 1 : 0) - (a.overlap ? 1 : 0);
      return (b.score || 0) - (a.score || 0);
    });

    const coreId = "core";
    nodes.push({
      id: coreId,
      kind: "core",
      label: repoName || "Repository",
      sub: commitSha || "HEAD",
      r: 22,
    });

    files.forEach(function (f) {
      const id = "file:" + f;
      const parts = String(f).split("/");
      nodes.push({
        id: id,
        kind: "file",
        label: parts[parts.length - 1] || f,
        full: f,
        r: 11,
      });
      links.push({ source: coreId, target: id, kind: "core-file" });
    });

    const moduleIds = {};
    const testNodes = [];
    const testLinks = [];

    sortedTests.forEach(function (t) {
      const mod = moduleOf(t.name);
      const mid = "mod:" + mod;
      if (!moduleIds[mod]) {
        moduleIds[mod] = mid;
        nodes.push({
          id: mid,
          kind: "module",
          label: mod,
          full: mod,
          r: 13,
        });
        if (files.length === 0) {
          links.push({ source: coreId, target: mid, kind: "core-mod" });
        }
      }

      const high = (t.score || 0) >= (highThreshold !== undefined ? highThreshold : 2.25);
      const tid = "test:" + t.name;
      testNodes.push({
        id: tid,
        kind: "test",
        label: shortLabel(t.name),
        full: t.name,
        score: t.score || 0,
        overlap: !!t.overlap,
        failures: t.failures_in_last_5 || 0,
        high: high,
        r: high ? 10 : 6.5,
      });
      testLinks.push({ source: mid, target: tid, kind: "mod-test" });

      if (t.overlap && files.length) {
        files.forEach(function (f) {
          testLinks.push({ source: "file:" + f, target: mid, kind: "file-mod" });
        });
      }
    });

    // Cap total nodes to max 200 nodes
    const maxNodes = 200;
    const baseNodeCount = nodes.length;
    const availableForTests = Math.max(0, maxNodes - baseNodeCount);
    
    const isCapped = testNodes.length > availableForTests;
    const selectedTestNodes = testNodes.slice(0, availableForTests);
    const selectedTestIds = new Set(selectedTestNodes.map(function(n) { return n.id; }));

    nodes.push.apply(nodes, selectedTestNodes);

    testLinks.forEach(function (l) {
      if (l.kind === "mod-test" && !selectedTestIds.has(l.target)) return;
      links.push(l);
    });

    if (files.length && selectedTestNodes.length) {
      const linkedMods = {};
      links.forEach(function (l) {
        if (l.kind === "file-mod") linkedMods[l.target] = true;
      });
      Object.keys(moduleIds).forEach(function (mod) {
        const mid = moduleIds[mod];
        if (!linkedMods[mid]) {
          links.push({ source: coreId, target: mid, kind: "core-mod" });
        }
      });
    }

    // Deduplicate file→module edges
    const seenLink = {};
    const uniqueLinks = [];
    links.forEach(function (l) {
      const key = l.source + "->" + l.target;
      if (seenLink[key]) return;
      seenLink[key] = true;
      uniqueLinks.push(l);
    });

    return { nodes: nodes, links: uniqueLinks, isCapped: isCapped || allTests.length > 200 };
  }

  function seedPositions(nodes, w, h) {
    const cx = w / 2;
    const cy = h / 2;
    const rings = { core: 0, file: 150, module: 275, test: 410 };
    const buckets = { core: [], file: [], module: [], test: [] };
    nodes.forEach(function (n) {
      (buckets[n.kind] || buckets.test).push(n);
    });
    Object.keys(buckets).forEach(function (kind) {
      const list = buckets[kind];
      const radius = rings[kind] || 240;
      list.forEach(function (n, i) {
        if (kind === "core") {
          n.x = cx;
          n.y = cy;
        } else {
          const a = (i / Math.max(list.length, 1)) * Math.PI * 2 - Math.PI / 2;
          n.x = cx + Math.cos(a) * radius + (Math.random() - 0.5) * 18;
          n.y = cy + Math.sin(a) * radius + (Math.random() - 0.5) * 18;
        }
        n.vx = 0;
        n.vy = 0;
        if (n.kind === "test" && n.high) {
          n.particles = Array.from({ length: 11 }, function (_, p) {
            return {
              angle: (p / 11) * Math.PI * 2,
              r: n.r + 7 + (p % 3) * 3,
              speed: 0.018 + (p % 5) * 0.004,
              size: 1.1 + (p % 3) * 0.45,
              phase: p * 0.7,
            };
          });
        }
      });
    });
  }

  function stepForces(nodes, links, w, h, alpha) {
    const cx = w / 2;
    const cy = h / 2;
    const n = nodes.length;
    // Charge (capped n² — typical suites stay well under 200 nodes)
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const a = nodes[i];
        const b = nodes[j];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let dist2 = dx * dx + dy * dy || 0.01;
        const dist = Math.sqrt(dist2);
        const minDist = a.r + b.r + 24;
        let force = (-420 * alpha) / dist2;
        if (dist < minDist) force -= ((minDist - dist) * 0.14);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        if (a.kind !== "core") { a.vx += fx; a.vy += fy; }
        if (b.kind !== "core") { b.vx -= fx; b.vy -= fy; }
      }
    }

    const rest = { "core-file": 175, "core-mod": 285, "file-mod": 180, "mod-test": 125 };
    for (let k = 0; k < links.length; k++) {
      const l = links[k];
      const a = l.src;
      const b = l.tgt;
      let dx = b.x - a.x;
      let dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const target = rest[l.kind] || 80;
      const f = (dist - target) * 0.012 * alpha;
      const fx = (dx / dist) * f;
      const fy = (dy / dist) * f;
      if (a.kind !== "core") { a.vx += fx; a.vy += fy; }
      if (b.kind !== "core") { b.vx -= fx; b.vy -= fy; }
    }

    for (let i = 0; i < n; i++) {
      const node = nodes[i];
      if (node.kind === "core" || node.pinned) {
        node.x = node.kind === "core" ? cx : node.x;
        node.y = node.kind === "core" ? cy : node.y;
        node.vx = 0;
        node.vy = 0;
        continue;
      }
      // Keep each type in a comfortable radial band, so tests fan out from the
      // fixed repository core instead of collapsing into the middle.
      const dx = node.x - cx;
      const dy = node.y - cy;
      const distance = Math.sqrt(dx * dx + dy * dy) || 1;
      const ring = node.kind === "file" ? 150 : node.kind === "module" ? 275 : 410;
      const radialForce = (distance - ring) * 0.0035 * alpha;
      node.vx -= (dx / distance) * radialForce;
      node.vy -= (dy / distance) * radialForce;
      node.vx *= 0.86;
      node.vy *= 0.86;
      node.x += node.vx;
      node.y += node.vy;
      node.x = Math.max(node.r + 8, Math.min(w - node.r - 8, node.x));
      node.y = Math.max(node.r + 8, Math.min(h - node.r - 8, node.y));
    }
  }

  function nodeColor(node) {
    if (node.kind === "core") return CORE_COLOR;
    if (node.kind === "file") return FILE_COLOR;
    if (node.kind === "module") return MODULE_COLOR;
    return node.high ? HIGH : CYAN;
  }

  function drawBezier(ctx, a, b, kind) {
    const mx = (a.x + b.x) / 2;
    const my = (a.y + b.y) / 2;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len = Math.sqrt(dx * dx + dy * dy) || 1;
    const bend = Math.min(42, len * 0.22);
    const cxp = mx - (dy / len) * bend;
    const cyp = my + (dx / len) * bend;
    const highLink = a.high || b.high;
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.quadraticCurveTo(cxp, cyp, b.x, b.y);
    ctx.strokeStyle = highLink ? "rgba(255,122,0,0.28)" : "rgba(0,229,255,0.18)";
    if (kind === "file-mod") ctx.strokeStyle = "rgba(249,115,22,0.32)";
    ctx.lineWidth = highLink ? 1.6 : 1.05;
    ctx.stroke();
  }

  function drawNode(ctx, node, t, active) {
    const color = nodeColor(node);
    if (node.kind === "test" && node.high && node.particles) {
      for (let i = 0; i < node.particles.length; i++) {
        const p = node.particles[i];
        p.angle += p.speed;
        const pr = p.r + Math.sin(t * 0.004 + p.phase) * 2.2;
        const px = node.x + Math.cos(p.angle) * pr;
        const py = node.y + Math.sin(p.angle) * pr;
        ctx.beginPath();
        ctx.fillStyle = "rgba(255,122,0," + (0.35 + 0.35 * Math.sin(t * 0.006 + p.phase)) + ")";
        ctx.shadowColor = HIGH;
        ctx.shadowBlur = 10;
        ctx.arc(px, py, p.size, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.shadowBlur = 0;
    }

    const g = ctx.createRadialGradient(node.x, node.y, 1, node.x, node.y, node.r * 3.2);
    g.addColorStop(0, color);
    g.addColorStop(0.35, color + "99");
    g.addColorStop(1, "rgba(13,15,18,0)");
    ctx.beginPath();
    ctx.fillStyle = g;
    ctx.arc(node.x, node.y, node.r * 3.2, 0, Math.PI * 2);
    ctx.fill();

    ctx.beginPath();
    ctx.shadowColor = color;
    ctx.shadowBlur = active ? 32 : node.kind === "test" && node.high ? 28 : node.kind === "test" ? 14 : node.kind === "core" ? 22 : 16;
    ctx.fillStyle = color;
    ctx.arc(node.x, node.y, node.r, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;

    ctx.beginPath();
    ctx.fillStyle = "rgba(13,15,18,0.55)";
    ctx.arc(node.x, node.y, Math.max(2, node.r * 0.38), 0, Math.PI * 2);
    ctx.fill();

    // Names are intentionally contextual: displaying every test name turns a
    // large suite into an unreadable cloud.
    if (active) {
      ctx.font = node.kind === "core" ? "600 11px Inter, system-ui, sans-serif"
        : node.kind === "test" ? "500 10px JetBrains Mono, monospace"
        : "500 10px Inter, system-ui, sans-serif";
      ctx.fillStyle = "rgba(241,245,249,0.96)";
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      const text = node.label;
      const clipped = text.length > 28 ? text.slice(0, 26) + "…" : text;
      ctx.fillText(clipped, node.x, node.y + node.r + 5);
      if (node.kind === "core" && node.sub) {
        ctx.font = "500 10px JetBrains Mono, monospace";
        ctx.fillStyle = HIGH;
        ctx.fillText(node.sub, node.x, node.y + node.r + 18);
      }
    }
  }

  function hitTest(nodes, x, y) {
    let best = null;
    let bestD = 18;
    for (let i = 0; i < nodes.length; i++) {
      const n = nodes[i];
      const dx = n.x - x;
      const dy = n.y - y;
      const d = Math.sqrt(dx * dx + dy * dy);
      if (d < n.r + 8 && d < bestD + n.r) {
        best = n;
        bestD = d;
      }
    }
    return best;
  }

  function TestGraphView(props) {
    const tests = props.tests;
    const changedFiles = props.changedFiles;
    const commitSha = props.commitSha;
    const repoName = props.repoName;
    const wc = props.wc !== undefined ? props.wc : 2.0;
    const wh = props.wh !== undefined ? props.wh : 1.0;
    const highThreshold = (wc + wh) * 0.75;
    const cooldownTicks = props.cooldownTicks !== undefined ? props.cooldownTicks : 100;
    const onEngineStop = props.onEngineStop || function () {};

    const wrapRef = useRef(null);
    const canvasRef = useRef(null);
    const tooltipRef = useRef(null);
    const graph = useMemo(
      function () {
        return buildGraphData(tests, changedFiles, commitSha, repoName, highThreshold);
      },
      [tests, changedFiles, commitSha, repoName, highThreshold]
    );

    useEffect(function () {
      const canvas = canvasRef.current;
      const wrap = wrapRef.current;
      if (!canvas || !wrap) return;

      const ctx = canvas.getContext("2d", { alpha: false });
      const nodes = graph.nodes.map(function (n) { return Object.assign({}, n); });
      const byId = {};
      nodes.forEach(function (n) { byId[n.id] = n; });
      const links = graph.links
        .map(function (l) {
          return { kind: l.kind, src: byId[l.source], tgt: byId[l.target] };
        })
        .filter(function (l) { return l.src && l.tgt; });

      let w = 0;
      let h = 0;
      let raf = 0;
      let alpha = 1;
      let running = true;
      let hovered = null;
      let selected = null;
      let dragging = null;
      let t0 = performance.now();
      let tickCount = 0;

      function queueFrame() {
        if (!raf && running) raf = requestAnimationFrame(frame);
      }

      function resize() {
        const rect = wrap.getBoundingClientRect();
        w = Math.max(320, rect.width);
        h = Math.max(420, rect.height);
        const dpr = Math.min(window.devicePixelRatio || 1, 1.5); // capped at 1.5 for smooth 60fps rendering
        canvas.width = Math.floor(w * dpr);
        canvas.height = Math.floor(h * dpr);
        canvas.style.width = w + "px";
        canvas.style.height = h + "px";
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        queueFrame();
      }

      resize();
      seedPositions(nodes, w, h);

      const tooltip = tooltipRef.current;

      function setTooltip(node, clientX, clientY) {
        if (!tooltip) return;
        if (!node) {
          tooltip.style.display = "none";
          return;
        }
        let html = "<div class='tt-k'>" + node.kind.toUpperCase() + "</div>";
        html += "<div class='tt-name'>" + (node.full || node.label) + "</div>";
        if (node.kind === "test") {
          html += "<div class='tt-row'>CHART-P Score <b>" + formatScore(node.score) + "</b></div>";
          html += "<div class='tt-row'>Changed File <b>" + (node.overlap ? "YES" : "no") + "</b></div>";
          html += "<div class='tt-row'>Historical Fails <b>" + node.failures + "</b></div>";
        } else if (node.kind === "core") {
          html += "<div class='tt-row'>Commit <b>" + (node.sub || "HEAD") + "</b></div>";
        }
        tooltip.innerHTML = html;
        tooltip.style.display = "block";
        const rect = wrap.getBoundingClientRect();
        tooltip.style.left = Math.min(rect.width - 240, Math.max(8, clientX - rect.left + 14)) + "px";
        tooltip.style.top = Math.min(rect.height - 120, Math.max(8, clientY - rect.top + 14)) + "px";
      }

      function pointerPos(ev) {
        const rect = canvas.getBoundingClientRect();
        return { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
      }

      function onMove(ev) {
        const p = pointerPos(ev);
        if (dragging) {
          dragging.x = p.x;
          dragging.y = p.y;
          dragging.vx = 0;
          dragging.vy = 0;
          alpha = Math.max(alpha, 0.35);
          tickCount = 0; // resume physics on dragging
          setTooltip(dragging, ev.clientX, ev.clientY);
          queueFrame();
          return;
        }
        const hit = hitTest(nodes, p.x, p.y);
        hovered = hit;
        canvas.style.cursor = hit ? "pointer" : "grab";
        setTooltip(hit, ev.clientX, ev.clientY);
        queueFrame();
      }

      function onDown(ev) {
        const p = pointerPos(ev);
        const hit = hitTest(nodes, p.x, p.y);
        if (hit && hit.kind !== "core") {
          dragging = hit;
          hit.pinned = true;
          canvas.style.cursor = "grabbing";
          alpha = Math.max(alpha, 0.35);
          tickCount = 0; // resume physics
          queueFrame();
        }
      }

      function onClick(ev) {
        const p = pointerPos(ev);
        selected = hitTest(nodes, p.x, p.y);
        setTooltip(selected, ev.clientX, ev.clientY);
        queueFrame();
      }

      function onUp() {
        if (dragging) dragging.pinned = false;
        dragging = null;
      }

      function frame(now) {
        if (!running) return;
        raf = 0;
        const dt = Math.min(32, now - t0);
        t0 = now;
        if (document.hidden) {
          queueFrame();
          return;
        }
        
        // Capped physics updates
        if (tickCount < cooldownTicks) {
          alpha += (0.04 - alpha) * 0.02;
          stepForces(nodes, links, w, h, alpha);
          tickCount++;
          if (tickCount === cooldownTicks) {
            onEngineStop();
          }
        }

        ctx.fillStyle = BG;
        ctx.fillRect(0, 0, w, h);

        const vg = ctx.createRadialGradient(w / 2, h / 2, 20, w / 2, h / 2, Math.max(w, h) * 0.55);
        vg.addColorStop(0, "rgba(255,122,0,0.05)");
        vg.addColorStop(1, "rgba(13,15,18,0)");
        ctx.fillStyle = vg;
        ctx.fillRect(0, 0, w, h);

        ctx.lineCap = "round";
        for (let i = 0; i < links.length; i++) {
          drawBezier(ctx, links[i].src, links[i].tgt, links[i].kind);
        }
        for (let i = 0; i < nodes.length; i++) {
          drawNode(ctx, nodes[i], now, hovered === nodes[i] || selected === nodes[i]);
        }
        // Once the layout settles, leave the canvas idle. Pointer events queue
        // a single redraw for labels/tooltips, and dragging resumes simulation.
        if (tickCount < cooldownTicks) queueFrame();
        void dt;
      }

      const ro = new ResizeObserver(function () { resize(); });
      ro.observe(wrap);
      canvas.addEventListener("mousemove", onMove);
      canvas.addEventListener("mousedown", onDown);
      canvas.addEventListener("click", onClick);
      window.addEventListener("mouseup", onUp);
      canvas.addEventListener("mouseleave", function () {
        hovered = null;
        setTooltip(null);
        queueFrame();
      });

      queueFrame();

      return function () {
        running = false;
        cancelAnimationFrame(raf);
        ro.disconnect();
        canvas.removeEventListener("mousemove", onMove);
        canvas.removeEventListener("mousedown", onDown);
        canvas.removeEventListener("click", onClick);
        window.removeEventListener("mouseup", onUp);
      };
    }, [graph]);

    const highCount = (tests || []).filter(function (t) { return t.score >= highThreshold; }).length;

    return React.createElement(
      "div",
      { className: "graph-card card" },
      React.createElement(
        "div",
        { className: "card-header" },
        React.createElement("span", { className: "card-title" }, "Force-Directed Knowledge Graph"),
        React.createElement(
          "span",
          { className: "card-meta" },
          (repoName || "Repository") + " · " + (commitSha || "HEAD") + " · " + highCount + " high-priority"
        )
      ),
      graph.isCapped && React.createElement(
        "div",
        { style: { padding: "0.5rem 1rem", fontSize: "0.78rem", color: "var(--amber)", backgroundColor: "rgba(255, 122, 0, 0.08)", borderBottom: "1px solid rgba(255, 122, 0, 0.15)", fontWeight: "500" } },
        "⚠️ Graph capped at top 200 high-risk nodes for rendering performance."
      ),
      React.createElement(
        "div",
        { className: "graph-shell", ref: wrapRef },
        React.createElement("canvas", { className: "graph-canvas", ref: canvasRef }),
        React.createElement("div", { className: "graph-tooltip", ref: tooltipRef }),
        React.createElement(
          "div",
          { className: "graph-legend" },
          React.createElement("span", { className: "lg lg-core" }, "Commit core"),
          React.createElement("span", { className: "lg lg-file" }, "Changed files"),
          React.createElement("span", { className: "lg lg-mod" }, "Test modules"),
          React.createElement("span", { className: "lg lg-high" }, "High ≥ " + highThreshold.toFixed(2)),
          React.createElement("span", { className: "lg lg-cyan" }, "Medium / Low")
        )
      )
    );
  }

  global.TestGraphView = TestGraphView;
})(window);
