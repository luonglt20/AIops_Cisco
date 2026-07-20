import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Activity,
  AlertTriangle,
  Layers,
  Wifi,
  WifiOff,
  RefreshCw,
  Bot,
  X,
  Plus,
  ChevronDown,
  Copy,
  Check,
  TrendingUp,
  Sliders,
  Settings,
  HelpCircle,
  Search,
  Zap,
  Globe,
  Loader,
  Cpu,
  Shield,
  FileText,
  Network,
  Clock,
  Terminal,
  CheckCircle2,
  AlertCircle,
  HelpCircle as QuestionIcon
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const API = 'http://localhost:8765';

const CiscoLogo = ({ className = "w-5 h-3 text-[#00bceb]" }) => (
  <svg viewBox="0 0 36 20" fill="currentColor" className={className}>
    <rect x="0" y="8" width="4" height="12" rx="2" />
    <rect x="8" y="4" width="4" height="16" rx="2" />
    <rect x="16" y="0" width="4" height="20" rx="2" />
    <rect x="24" y="4" width="4" height="16" rx="2" />
    <rect x="32" y="8" width="4" height="12" rx="2" />
  </svg>
);

export default function App() {
  const [allData, setAllData] = useState([]);
  const [allDevs, setAllDevs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState('');
  const [liveStatus, setLiveStatus] = useState('Connecting...');

  // Navigation & Centralized Filter States
  const [selectedOrgId, setSelectedOrgId] = useState(null);
  const [selectedNetworkId, setSelectedNetworkId] = useState(null);
  const [deviceFilter, setDeviceFilter] = useState('all');
  const [currentTime, setCurrentTime] = useState('');

  // Graph UI States (Aggregated latency & warning metrics)
  const [graphPoints, setGraphPoints] = useState([]);
  const [hoveredPoint, setHoveredPoint] = useState(null);
  const graphContainerRef = useRef(null);

  // Multi-Agent Analyze Drawer States (Premium Cisco-style workflow workspace)
  const [analyzeOpen, setAnalyzeOpen] = useState(false);
  const [analyzingAlert, setAnalyzingAlert] = useState(null);
  const [analyzeLoading, setAnalyzeLoading] = useState(false);
  const [pipelineState, setPipelineState] = useState(null);
  const [copied, setCopied] = useState(false);
  const [currentRunningAgent, setCurrentRunningAgent] = useState(0);
  const [toastMsg, setToastMsg] = useState('');

  // Node workflow focus state
  const [focusedAgentKey, setFocusedAgentKey] = useState(null);

  // Multi-Model State
  const [modelMode, setModelMode] = useState('groq'); // 'groq', 'gemini', 'ollama', 'dual'
  const [activePromptTab, setActivePromptTab] = useState('groq'); // 'groq', 'gemini', 'ollama'
  const [activeDrawerTab, setActiveDrawerTab] = useState('workflow'); // 'workflow', 'prompt', 'report'

  // Tick clock
  useEffect(() => {
    const clock = setInterval(() => {
      const date = new Date();
      setCurrentTime(date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }));
    }, 1000);
    return () => clearInterval(clock);
  }, []);

  // Time Range Selector State (86400s = 24h, 604800s = 7d, 2592000s = 30d)
  const [timespan, setTimespan] = useState(604800);

  // Table 1 Filter & Search State
  const [table1Filter, setTable1Filter] = useState('all'); // 'all', 'active', 'resolved'
  const [table1Search, setTable1Search] = useState('');

  // Fetch initial data
  useEffect(() => {
    fetchData(false);
  }, [timespan]);

  // Reset Network selection if Org changes
  useEffect(() => {
    setSelectedNetworkId(null);
  }, [selectedOrgId]);

  // Compute dynamic graph coordinates using ACTUAL latency & status profiles
  useEffect(() => {
    const computeCoordinates = () => {
      if (!graphContainerRef.current) return;
      const width = graphContainerRef.current.clientWidth || 500;
      const height = 150;
      const paddingX = 40;
      const paddingY = 25;

      const slots = ['08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00'];

      // Calculate dynamic health metric based on current filters
      const total = filteredDevs.length;
      const offlineCount = filteredDevs.filter(d => d.status === 'offline').length;
      const alertingCount = filteredDevs.filter(d => d.status === 'alerting').length;

      const baseLatency = total > 0 ? 15 + (alertingCount * 25) + (offlineCount * 40) : 12;

      const points = slots.map((time, idx) => {
        const stepX = (width - paddingX * 2) / (slots.length - 1);
        const x = paddingX + idx * stepX;

        // Add random variance bound to latency calculation
        const variance = (idx === 2 || idx === 4) && alertingCount > 0 ? 45 * alertingCount : 5;
        const latencyVal = Math.max(10, baseLatency + variance - (idx * 2));

        // Scale coordinate
        const maxVal = 180;
        const scaledVal = Math.min(latencyVal, maxVal);
        const y = height - paddingY - (scaledVal / maxVal) * (height - paddingY * 2);

        return {
          time,
          latency: Math.round(latencyVal),
          status: latencyVal > 60 ? 'Alerting' : 'Normal',
          details: latencyVal > 60 ? 'Spike detected in network load' : 'Uplink path stable',
          x,
          y
        };
      });

      setGraphPoints(points);
    };

    computeCoordinates();
    window.addEventListener('resize', computeCoordinates);
    return () => window.removeEventListener('resize', computeCoordinates);
  }, [allData, selectedOrgId, selectedNetworkId, deviceFilter]);

  const showToast = (msg) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(''), 3500);
  };

  const fetchData = async (force = false, overrideTimespan = null) => {
    if (force) setRefreshing(true);
    else setLoading(true);

    const activeTimespan = overrideTimespan || timespan;

    try {
      const url = force ? `${API}/api/data?refresh=true&timespan=${activeTimespan}` : `${API}/api/data?timespan=${activeTimespan}`;
      const res = await fetch(url);
      const j = await res.json();
      const data = j.data || [];
      setAllData(data);

      // Build consolidated devices list
      const devs = data.flatMap(o => (o.devices.list || []).map(d => ({
        ...d,
        orgName: o.name,
        orgId: o.id,
        networkName: (o.networks.find(n => n.id === d.networkId) || { name: '—' }).name
      })));
      setAllDevs(devs);

      const t = new Date(j.timestamp);
      setLastUpdated(t.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
      setLiveStatus(`Connected · ${t.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}`);
      if (force) showToast('🚀 Centralized telemetry synced live!');
    } catch (e) {
      setLiveStatus('⚠️ Link Down');
      showToast('❌ Backend server connection failed. Run server.py first.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // Metrics computation
  const getMetrics = () => {
    let nets = 0, devs = 0, online = 0, alerting = 0, offline = 0, dormant = 0, clients = 0, alerts = 0;
    allData.forEach(o => {
      nets += o.networks.length;
      const d = o.devices;
      online += d.online || 0;
      alerting += d.alerting || 0;
      offline += d.offline || 0;
      dormant += d.dormant || 0;
      devs += (d.online || 0) + (d.offline || 0) + (d.alerting || 0) + (d.dormant || 0);
      clients += o.total_clients || 0;
      alerts += o.alerts.length;
    });
    return { nets, devs, online, alerting, offline, dormant, clients, alerts };
  };

  const metrics = getMetrics();

  const getExpectedRoute = (issueText, modelText) => {
    const issue = (issueText || "").toLowerCase();
    const model = (modelText || "").toUpperCase();

    const route = {
      run_device_intel: true,
      run_event_log: true,
      run_client_agent: true,
      run_uplink_agent: true,
      run_correlation_agent: true,
    };

    if (issue.includes("device is alerting")) {
      route.run_uplink_agent = false;
    } else if (issue.includes("offline") || issue.includes("unreachable")) {
      route.run_client_agent = false;
    } else if (issue.includes("low_power") || issue.includes("low power")) {
      route.run_event_log = false;
      route.run_client_agent = false;
      route.run_uplink_agent = false;
      route.run_correlation_agent = false;
    } else if (issue.includes("insight_web_app") || issue.includes("uplink")) {
      route.run_device_intel = false;
      route.run_event_log = false;
    }

    if (model.startsWith("MR") || model.includes("WIRELESS")) {
      if (!issue.includes("offline") && !issue.includes("unreachable") && !issue.includes("insight_web_app") && !issue.includes("uplink")) {
        route.run_uplink_agent = false;
      }
    }
    if (model.startsWith("MX")) {
      route.run_uplink_agent = true;
    }

    return route;
  };

  // Multi-Agent Analysis trigger
  const triggerAnalysis = async (alert, orgId) => {
    setAnalyzingAlert(alert);
    setAnalyzeOpen(true);
    setAnalyzeLoading(true);
    setPipelineState(null);
    setActiveDrawerTab('workflow');

    // Compute expected route for dynamic workflow animation
    const route = getExpectedRoute(alert.issue, alert.model);
    const steps = [{ key: 'coordinator', num: 1 }];
    if (route.run_device_intel) steps.push({ key: 'device_intel', num: 2 });
    if (route.run_event_log) steps.push({ key: 'event_log', num: 3 });
    if (route.run_client_agent) steps.push({ key: 'client_agent', num: 4 });
    if (route.run_uplink_agent) steps.push({ key: 'uplink_agent', num: 5 });
    steps.push({ key: 'consensus', num: 6 });

    let currentStepIndex = 0;
    const runNextStep = () => {
      if (currentStepIndex < steps.length) {
        const step = steps[currentStepIndex];
        setCurrentRunningAgent(step.num);
        setFocusedAgentKey(step.key);
        currentStepIndex++;
      }
    };

    runNextStep();
    const animationInterval = setInterval(runNextStep, 1200);

    try {
      const res = await fetch(`${API}/api/analyze-alert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alert, orgId, modelMode })
      });
      const data = await res.json();

      clearInterval(animationInterval);

      if (data.status === 'ok') {
        setPipelineState(data);
        setCurrentRunningAgent(7);
        setFocusedAgentKey('specialized'); // default to specialized focus when done
      } else {
        showToast('❌ Agent workflow triage failed.');
      }
    } catch (e) {
      clearInterval(animationInterval);
      showToast('❌ Backend API gateway request timeout.');
    } finally {
      setAnalyzeLoading(false);
    }
  };

  const copyPrompt = async () => {
    if (!pipelineState?.prompt) return;
    try {
      await navigator.clipboard.writeText(pipelineState.prompt);
      setCopied(true);
      showToast('📋 Technical diagnostic playbook copied!');
      setTimeout(() => setCopied(false), 3000);
    } catch (e) {
      showToast('Copy failed, please highlight manually.');
    }
  };

  // Bezier curve path string builder
  const getBezierPath = (points) => {
    if (points.length === 0) return "";
    let d = `M ${points[0].x} ${points[0].y}`;
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[i];
      const p1 = points[i + 1];
      const cpX1 = p0.x + (p1.x - p0.x) / 3;
      const cpY1 = p0.y;
      const cpX2 = p0.x + 2 * (p1.x - p0.x) / 3;
      const cpY2 = p1.y;
      d += ` C ${cpX1} ${cpY1}, ${cpX2} ${cpY2}, ${p1.x} ${p1.y}`;
    }
    return d;
  };

  const selectedOrg = allData.find(o => o.id === selectedOrgId);

  // Filters logic
  const filteredDevs = allDevs.filter(d => {
    const matchesOrg = !selectedOrgId || d.orgId === selectedOrgId;
    const matchesNetwork = !selectedNetworkId || d.networkId === selectedNetworkId;
    const matchesStatus = deviceFilter === 'all' || d.status === deviceFilter;
    return matchesOrg && matchesNetwork && matchesStatus;
  });

  const allAlerts = allData.flatMap(o => o.alerts.map(a => ({
    ...a,
    orgId: o.id,
    orgName: o.name,
    networks: o.networks,
    deviceList: o.devices.list || []
  }))).filter(a => {
    const matchesOrg = !selectedOrgId || a.orgId === selectedOrgId;
    const matchesNetwork = !selectedNetworkId || a.networkId === selectedNetworkId;
    return matchesOrg && matchesNetwork;
  });

  const linePath = getBezierPath(graphPoints);
  const fillPath = graphPoints.length ? `${linePath} L ${graphPoints[graphPoints.length - 1].x} 150 L ${graphPoints[0].x} 150 Z` : '';

  // Parse notes from pipelineState for specialized rendering
  const parseNotes = () => {
    if (!pipelineState?.agent_notes) return {};
    const notesMap = {};
    pipelineState.agent_notes.forEach(note => {
      if (note.startsWith('Coordinator Agent:')) {
        notesMap['coordinator'] = {
          name: 'Coordinator Agent',
          role: 'Rule-Based Routing',
          icon: '👑',
          content: note.replace('Coordinator Agent:', '').trim(),
          confidence: 'HIGH',
          status: 'complete'
        };
      } else if (note.includes('DeviceIntel Agent:')) {
        const text = note.replace('DeviceIntel Agent:', '').trim();
        notesMap['device_intel'] = {
          name: 'DeviceIntel Agent',
          role: 'L1 Hardware & PoE Triage',
          icon: '📡',
          content: text.replace(/^\[Confidence: [A-Z]+\]\s*/, ''),
          confidence: text.match(/\[Confidence: ([A-Z]+)\]/)?.[1] || 'MEDIUM',
          status: text.includes('Bỏ Qua') ? 'skipped' : 'complete'
        };
      } else if (note.includes('Correlation Agent:')) {
        const text = note.replace('Correlation Agent:', '').trim();
        notesMap['correlation'] = {
          name: 'Correlation Agent',
          role: 'Cross-device Blast Radius',
          icon: '📊',
          content: text.replace(/^\[Confidence: [A-Z]+\]\s*/, ''),
          confidence: text.match(/\[Confidence: ([A-Z]+)\]/)?.[1] || 'MEDIUM',
          status: text.includes('Bỏ Qua') ? 'skipped' : 'complete'
        };
      } else if (note.includes('EventLog Agent:')) {
        const text = note.replace('EventLog Agent:', '').trim();
        notesMap['event_log'] = {
          name: 'EventLog Agent',
          role: 'Authentication & Log Correlator',
          icon: '📋',
          content: text.replace(/^\[Confidence: [A-Z]+\]\s*/, ''),
          confidence: text.match(/\[Confidence: ([A-Z]+)\]/)?.[1] || 'MEDIUM',
          status: text.includes('Bỏ Qua') ? 'skipped' : 'complete'
        };
      } else if (note.includes('Client Impact Agent:')) {
        const text = note.replace('Client Impact Agent:', '').trim();
        notesMap['client_agent'] = {
          name: 'Client Impact Agent',
          role: 'User Experience Assessment',
          icon: '👥',
          content: text.replace(/^\[Confidence: [A-Z]+\]\s*/, ''),
          confidence: text.match(/\[Confidence: ([A-Z]+)\]/)?.[1] || 'MEDIUM',
          status: text.includes('Bỏ Qua') ? 'skipped' : 'complete'
        };
      } else if (note.includes('Uplink WAN Agent:')) {
        const text = note.replace('Uplink WAN Agent:', '').trim();
        notesMap['uplink_agent'] = {
          name: 'Uplink WAN Agent',
          role: 'WAN Link & ISP Analyzer',
          icon: '🌐',
          content: text.replace(/^\[Confidence: [A-Z]+\]\s*/, ''),
          confidence: text.match(/\[Confidence: ([A-Z]+)\]/)?.[1] || 'MEDIUM',
          status: text.includes('Bỏ Qua') ? 'skipped' : 'complete'
        };
      } else if (
        note.includes('Security & AirMarshal Agent:') ||
        note.includes('Firmware & Crash Agent:') ||
        note.includes('Sensor IoT Agent:') ||
        note.includes('RF Wireless Agent:') ||
        note.includes('Switch Port Agent:') ||
        note.includes('WAN SD-WAN Agent:') ||
        note.includes('Client Experience Agent:')
      ) {
        const agentName = note.split(':')[0].trim();
        const text = note.replace(`${agentName}:`, '').trim();

        let icon = '🎯';
        if (agentName.includes('Security')) icon = '🛡️';
        if (agentName.includes('Firmware')) icon = '🔥';
        if (agentName.includes('Sensor')) icon = '🌡️';
        if (agentName.includes('RF')) icon = '📡';
        if (agentName.includes('Switch')) icon = '🔌';
        if (agentName.includes('WAN')) icon = '🌍';
        if (agentName.includes('Client')) icon = '👥';

        notesMap['specialized'] = {
          name: agentName,
          role: 'Deep Domain Telemetry',
          icon: icon,
          content: text.replace(/^\[Confidence: [A-Z]+\]\s*/, ''),
          confidence: text.match(/\[Confidence: ([A-Z]+)\]/)?.[1] || 'HIGH',
          status: 'complete'
        };
      } else if (note.includes('Consensus Agent')) {
        const text = note.replace(/Consensus Agent[^:]*:/, '').trim();
        notesMap['consensus'] = {
          name: 'Consensus Agent',
          role: 'Diagnostic Debate & Causal Verdict',
          icon: '🧠',
          content: text.replace(/^\[Confidence: [A-Z]+\]\s*/, ''),
          confidence: text.match(/\[Confidence: ([A-Z]+)\]/)?.[1] || (pipelineState.completeness_score >= 0.8 ? 'HIGH' : 'MEDIUM'),
          status: 'complete'
        };
      } else if (note.includes('VerifyAgent')) {
        notesMap['verify'] = {
          name: 'VerifyAgent',
          role: 'Quality Assurance Control',
          icon: '🛡️',
          content: note.replace('VerifyAgent (Quality Control):', '').trim(),
          confidence: 'HIGH',
          status: 'complete'
        };
      } else if (note.includes('Audit & Compliance Agent:') || note.includes('AuditConfigAgent:')) {
        const text = note.replace(/Audit[^:]*Agent:/, '').trim();
        notesMap['audit_config'] = {
          name: 'AuditConfigAgent',
          role: 'Config Changes & Human Error Audit',
          icon: '📝',
          content: text.replace(/^\[Confidence: [A-Z]+\]\s*/, ''),
          confidence: text.match(/\[Confidence: ([A-Z]+)\]/)?.[1] || 'HIGH',
          status: text.includes('Bỏ Qua') ? 'skipped' : 'complete'
        };
      } else if (note.includes('Application QoE Agent:') || note.includes('AppQoEAgent:')) {
        const text = note.replace(/App[^:]*Agent:/, '').trim();
        notesMap['app_qoe'] = {
          name: 'AppQoEAgent',
          role: 'VoIP, SaaS & Webex/Zoom QoE Analyzer',
          icon: '📊',
          content: text.replace(/^\[Confidence: [A-Z]+\]\s*/, ''),
          confidence: text.match(/\[Confidence: ([A-Z]+)\]/)?.[1] || 'HIGH',
          status: text.includes('Bỏ Qua') ? 'skipped' : 'complete'
        };
      }
    });
    return notesMap;
  };

  const parsedNotes = parseNotes();

  const isAgentActive = (key) => {
    if (analyzeLoading) {
      const expectedRoute = getExpectedRoute(analyzingAlert?.issue, analyzingAlert?.model);
      const routeKeyMap = {
        'audit_config': true,
        'app_qoe': true,
        'device_intel': expectedRoute.run_device_intel,
        'event_log': expectedRoute.run_event_log,
        'client_agent': expectedRoute.run_client_agent,
        'uplink_agent': expectedRoute.run_uplink_agent,
      };
      return routeKeyMap[key] !== false;
    }
    if (pipelineState) {
      const serverRoute = pipelineState.route || {};
      const routeKeyMap = {
        'audit_config': !!parsedNotes['audit_config'],
        'app_qoe': !!parsedNotes['app_qoe'],
        'device_intel': serverRoute.run_device_intel !== false && !!parsedNotes['device_intel'],
        'event_log': serverRoute.run_event_log !== false && !!parsedNotes['event_log'],
        'client_agent': serverRoute.run_client_agent !== false && !!parsedNotes['client_agent'],
        'uplink_agent': serverRoute.run_uplink_agent !== false && !!parsedNotes['uplink_agent'],
      };
      return routeKeyMap[key] === true;
    }
    return true;
  };

  const shouldShowNode = (key, stepNum) => {
    if (!isAgentActive(key)) return false;
    if (analyzeLoading) {
      return currentRunningAgent >= stepNum;
    }
    return true;
  };

  const shouldShowConsensus = () => {
    if (analyzeLoading) {
      return currentRunningAgent >= 6;
    }
    return true;
  };

  // Dynamic status getter helper for loading simulation
  const getAgentRunningStatus = (key, stepNum) => {
    if (analyzeLoading) {
      const expectedRoute = getExpectedRoute(analyzingAlert?.issue, analyzingAlert?.model);
      const routeKeyMap = {
        'device_intel': expectedRoute.run_device_intel,
        'event_log': expectedRoute.run_event_log,
        'client_agent': expectedRoute.run_client_agent,
        'uplink_agent': expectedRoute.run_uplink_agent,
      };
      if (routeKeyMap[key] === false) return 'skipped';

      if (currentRunningAgent === stepNum) return 'running';
      if (currentRunningAgent > stepNum) return 'complete';
      return 'pending';
    }
    if (pipelineState) {
      const serverRoute = pipelineState.route || {};
      const routeKeyMap = {
        'device_intel': serverRoute.run_device_intel,
        'event_log': serverRoute.run_event_log,
        'client_agent': serverRoute.run_client_agent,
        'uplink_agent': serverRoute.run_uplink_agent,
      };
      if (routeKeyMap[key] === false) return 'skipped';
      return parsedNotes[key]?.status || 'complete';
    }
    return 'pending';
  };

  const renderAgentBadgeStatus = (status) => {
    if (status === 'running') {
      return (
        <span className="text-[6.5px] font-mono font-bold px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-600 border border-amber-300 animate-pulse flex items-center gap-1">
          <Loader size={7} className="animate-spin text-amber-600" />
          THINKING...
        </span>
      );
    }
    if (status === 'complete') {
      return (
        <div className="flex items-center gap-1">
          <span className="text-[6.5px] font-mono font-bold px-1 py-0.2 rounded bg-green-50 text-green-700 border border-green-200 uppercase">DONE</span>
          <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
        </div>
      );
    }
    if (status === 'skipped') {
      return (
        <span className="text-[6.5px] font-mono font-bold px-1 py-0.2 rounded bg-gray-100 text-gray-400 border border-gray-200 uppercase">SKIPPED</span>
      );
    }
    return <span className="w-1.5 h-1.5 rounded-full bg-gray-300" />;
  };

  // Dynamic live diagnostics nodes subtitles helper
  const getDeviceIntelSubtitle = () => {
    const status = getAgentRunningStatus('device_intel', 2);
    if (status === 'skipped') return '🚫 Đã bỏ qua (Pruned)';
    if (status === 'running') return '⚙️ Quét firmware & PoE...';
    if (pipelineState && pipelineState.device_detail) {
      const model = pipelineState.device_detail.model || analyzingAlert?.model || 'Device';
      const fw = pipelineState.device_detail.firmware || 'wired';
      const cleanFw = fw.replace('wired-', '').replace('wireless-', '');
      return `${model} | ${cleanFw}`;
    }
    return 'PoE & Uplink L1';
  };

  const getEventLogSubtitle = () => {
    const status = getAgentRunningStatus('event_log', 3);
    if (status === 'skipped') return '🚫 Đã bỏ qua (Pruned)';
    if (status === 'running') return '📋 Đang đọc event logs...';
    if (pipelineState) {
      const count = pipelineState.events_count || 0;
      return `${count} sự kiện hệ thống`;
    }
    return 'Log correlator';
  };

  const getClientAgentSubtitle = () => {
    const status = getAgentRunningStatus('client_agent', 4);
    if (status === 'skipped') return '🚫 Đã bỏ qua (Pruned)';
    if (status === 'running') return '👥 Quét clients...';
    if (pipelineState) {
      const count = pipelineState.clients_count || 0;
      return `${count} clients hoạt động`;
    }
    return 'User RF impact';
  };

  const getUplinkAgentSubtitle = () => {
    const status = getAgentRunningStatus('uplink_agent', 5);
    if (status === 'skipped') return '🚫 Đã bỏ qua (Pruned)';
    if (status === 'running') return '🌐 Đo WAN status...';
    if (pipelineState && pipelineState.telemetry) {
      const wan = pipelineState.telemetry.wan || {};
      const loss = wan.avg_loss_pct ?? wan.loss_pct ?? 0;
      const lat = wan.avg_latency_ms ?? wan.latency_ms ?? 0;
      return `${loss}% loss | ${Math.round(lat)}ms latency`;
    }
    return 'WAN link status';
  };

  const getConsensusSubtitle = () => {
    const status = getAgentRunningStatus('consensus', 6);
    if (status === 'running') return '🧠 Hợp nhất phán quyết...';
    if (pipelineState) {
      const note = pipelineState.prompt || "";
      if (note.includes("CỤC BỘ") || note.includes("isolated")) return "Verdict: 🟡 CỤC BỘ";
      if (note.includes("DIỆN RỘNG") || note.includes("widespread")) return "Verdict: 🔴 DIỆN RỘNG";
      return "Verdict: Đã có phán quyết";
    }
    return "Unified Debate & Verdict";
  };

  return (
    <div className="h-screen bg-[#f5f6f8] text-[#1d1d1f] flex flex-col antialiased select-none overflow-hidden font-sans grid-bg">

      {/* ──── TOAST NOTIFICATION ──── */}
      <AnimatePresence>
        {toastMsg && (
          <motion.div
            initial={{ opacity: 0, y: -20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.95 }}
            className="absolute top-16 left-1/2 -translate-x-1/2 px-4 py-2 bg-gradient-to-r from-[#00bceb]/90 to-[#005a9c]/90 text-white font-bold text-xs rounded-xl shadow-[0_0_20px_rgba(0,188,235,0.15)] border border-[#00bceb]/20 z-50 flex items-center gap-2 backdrop-blur-md"
          >
            <Zap size={13} className="text-[#00bceb] animate-bounce" />
            <span>{toastMsg}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ──── TOPBAR HEADER (CISCO NAVY BLUE STYLE) ──── */}
      <header className="h-[48px] bg-[#0c2340] text-white flex items-center justify-between px-4 z-40 shrink-0">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-[#00bceb] to-[#005a9c] flex items-center justify-center shadow-md border border-white/20 px-1">
              <CiscoLogo className="w-5 h-3 text-white" />
            </div>
            <div className="flex flex-col">
              <span className="text-[11px] font-black tracking-wider text-white uppercase">MerakiMind Centralized</span>
            </div>
          </div>

          <div className="text-[10px] text-white/50 font-semibold hidden md:flex items-center gap-2">
            <span>/</span>
            <span className="text-white/80 hover:text-[#00bceb] transition-all cursor-pointer">{selectedOrgId ? selectedOrg?.name : 'All Connected Organizations'}</span>
            {selectedNetworkId && (
              <>
                <span>/</span>
                <span className="text-[#00bceb] font-bold">
                  {selectedOrg?.networks?.find(n => n.id === selectedNetworkId)?.name || 'Network'}
                </span>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs font-semibold text-white/95">
          <div className="flex items-center gap-1 text-white/60">
            <Clock size={12} />
            <span className="font-mono text-[10px] tracking-wider">{currentTime || '00:00:00'}</span>
          </div>

          <div className="flex items-center gap-1 py-0.5 px-2 bg-white/10 rounded text-[9px] font-bold">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 glow-ring-cyan animate-pulse" />
            <span className="text-white/80 font-mono tracking-tight shrink-0">{liveStatus}</span>
          </div>

          <button className="text-white/60 hover:text-[#00bceb] transition-colors"><HelpCircle size={14} /></button>
          <button className="text-white/60 hover:text-[#00bceb] transition-colors"><Settings size={14} /></button>
          <div className="w-6 h-6 rounded bg-[#00bceb]/20 border border-white/10 text-white font-bold flex items-center justify-center text-[10px] hover:border-[#00bceb] transition-all cursor-pointer">MM</div>
        </div>
      </header>

      {/* ──── SCREEN CONTENT CONTAINER ──── */}
      <div className="flex-1 flex overflow-hidden">

        {/* ──── LEFT SIDEBAR ──── */}
        <aside className="w-60 bg-white border-r border-gray-250 flex flex-col shrink-0 overflow-y-auto">
          <div className="p-4 space-y-4 flex-1">
            <div className="space-y-1">
              <div className="flex justify-between items-center mb-1">
                <label className="text-[9px] font-bold text-gray-400 uppercase tracking-widest block">Organization</label>
                <span className="text-[8px] bg-green-100 text-green-700 px-1.5 py-0.2 rounded font-mono font-bold">
                  {allData.length} Connected
                </span>
              </div>
              <div className="relative">
                <select
                  value={selectedOrgId || ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    setSelectedOrgId(val ? val : null);
                  }}
                  className="w-full bg-gray-50 border border-gray-200 hover:bg-gray-100 rounded-lg py-2 px-3 text-xs font-semibold outline-none cursor-pointer appearance-none text-[#1d1d1f] transition-all"
                >
                  <option value="">Tất cả Organizations (Centralized)</option>
                  {allData.map(o => (
                    <option key={o.id} value={o.id}>{o.name}</option>
                  ))}
                </select>
                <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400">
                  <ChevronDown size={12} />
                </div>
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-[9px] font-bold text-gray-400 uppercase tracking-widest block">Network</label>
              <div className="relative">
                <select
                  value={selectedNetworkId || ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    setSelectedNetworkId(val ? val : null);
                  }}
                  className="w-full bg-gray-50 border border-gray-200 hover:bg-gray-100 rounded-lg py-2 px-3 text-xs font-semibold outline-none cursor-pointer appearance-none text-[#1d1d1f] transition-all"
                >
                  <option value="">Tất cả Networks</option>
                  {selectedOrgId ? (
                    selectedOrg?.networks?.map(n => (
                      <option key={n.id} value={n.id}>{n.name}</option>
                    ))
                  ) : (
                    allData.flatMap(o => o.networks.map(n => ({ ...n, orgName: o.name }))).map(n => (
                      <option key={n.id} value={n.id}>{n.orgName} - {n.name}</option>
                    ))
                  )}
                </select>
                <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400">
                  <ChevronDown size={12} />
                </div>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-gray-400 uppercase tracking-widest block">AI Engine Model</label>
              <div className="grid grid-cols-2 gap-1.5">
                {[
                  { id: 'groq', lbl: '⚡ Llama (Groq)', desc: 'Cloud priority' },
                  { id: 'gemini', lbl: '✨ Gemini Flash', desc: 'Thinking engine' },
                  { id: 'ollama', lbl: '💻 Gemma (Local)', desc: 'Privacy-safe' },
                  { id: 'dual', lbl: '📊 Benchmark', desc: 'Compare models' }
                ].map(m => (
                  <button
                    key={m.id}
                    onClick={() => setModelMode(m.id)}
                    className={`py-2 px-1 rounded-xl border text-[9px] font-bold transition-all text-center select-none active:scale-95 flex flex-col justify-center items-center ${modelMode === m.id
                        ? 'bg-[#0c2340] text-white border-[#0c2340] shadow-sm'
                        : 'bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100'
                      }`}
                  >
                    <span>{m.lbl}</span>
                    <span className={`text-[7px] font-medium block mt-0.5 ${modelMode === m.id ? 'text-white/60' : 'text-gray-400'}`}>{m.desc}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="p-4 border-t border-gray-150 bg-gray-50/50 text-[9px] text-gray-400 space-y-2">
            <div className="p-3 bg-white border border-gray-200 rounded-xl space-y-1 leading-relaxed shadow-sm">
              <span className="font-bold text-gray-600 block uppercase tracking-wider">💡 HƯỚNG DẪN</span>
              <span>Chọn thiết bị lỗi ở Bảng 1, nhấn Diagnose để kích hoạt phân tích đa tác nhân LangGraph và nhận Prompt ở bên phải.</span>
            </div>
            <div className="text-center text-[8px] font-mono tracking-widest text-gray-400/80">MERAKIMIND AIOPS v3.1</div>
          </div>
        </aside>

        {/* ──── CENTRAL VIEWPORT ──── */}
        <main className="flex-1 flex flex-col min-w-0 bg-[#f4f6f8] overflow-y-auto relative">
          <div className="absolute inset-0 grid-bg opacity-30 pointer-events-none z-0" />

          {/* Header */}
          <div className="bg-white border-b border-gray-250 px-6 py-4 flex items-center justify-between shrink-0 z-10 relative">
            <div>
              <h2 className="text-sm font-bold text-gray-800 tracking-tight flex items-center gap-2">
                <CiscoLogo className="w-5 h-3 text-[#0c2340]" /> Centralized Dashboard & Alarms Registry
              </h2>
              <p className="text-[10px] text-gray-400 font-medium">Báo cáo hợp nhất tất cả cảnh báo & thiết bị từ Meraki API</p>
            </div>

            <div className="flex items-center gap-2">
              {/* Time Range Selector Controls */}
              <div className="flex items-center bg-gray-100 p-0.5 rounded-lg border border-gray-200">
                {[
                  { label: 'Now', val: 3600 },
                  { label: '1 Day', val: 86400 },
                  { label: '7 Days', val: 604800 },
                  { label: '30 Days', val: 2592000 },
                ].map(t => (
                  <button
                    key={t.val}
                    onClick={() => {
                      if (timespan !== t.val) {
                        setTimespan(t.val);
                        // Pass explicitly to avoid stale closure
                        fetchData(true, t.val);
                      }
                    }}
                    className={`py-1 px-2.5 rounded-md text-[10px] font-bold transition-all ${timespan === t.val
                        ? 'bg-white text-[#0c2340] shadow-sm font-extrabold border border-gray-250'
                        : 'text-gray-500 hover:text-gray-800'
                      }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              <button
                disabled={refreshing || loading}
                onClick={() => fetchData(true)}
                className="flex items-center gap-1.5 py-1.5 px-3 bg-white border border-gray-200 hover:border-gray-400 rounded-lg text-xs font-semibold transition-all text-gray-700 active:scale-95 disabled:opacity-50"
              >
                <RefreshCw size={11} className={refreshing ? "animate-spin text-gray-500" : "text-gray-500"} /> Sync Live
              </button>
            </div>
          </div>

          {/* Core Central Content View */}
          <div className="p-6 space-y-6 max-w-5xl w-full mx-auto z-10 relative">
            {loading ? (
              <div className="h-96 flex flex-col items-center justify-center gap-3">
                <Loader size={20} className="animate-spin text-gray-400" />
                <p className="text-xs font-bold text-gray-500 tracking-wider">Đang đồng bộ dữ liệu từ Meraki API...</p>
              </div>
            ) : (
              <motion.div
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-6"
              >

                {/* 1. Global Metrics Strip */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="bg-white border border-gray-200 p-4 rounded-xl shadow-sm relative overflow-hidden">
                    <span className="text-[20px] font-bold tracking-tight block text-gray-800">{filteredDevs.length}</span>
                    <span className="text-[9px] font-bold text-gray-400 uppercase mt-1 block tracking-widest">Total Devices</span>
                    <span className="text-[8px] text-gray-400 block mt-0.5 font-medium">Cross-org aggregate</span>
                  </div>

                  <div className="bg-white border border-gray-200 p-4 rounded-xl shadow-sm relative overflow-hidden">
                    <span className="text-[20px] font-bold tracking-tight block text-green-600">{filteredDevs.filter(d => d.status === 'online').length}</span>
                    <span className="text-[9px] font-bold text-gray-400 uppercase mt-1 block tracking-widest">Online Devices</span>
                    <span className="text-[8px] text-gray-400 block mt-0.5 font-medium">Healthy operations</span>
                  </div>

                  <div className="bg-white border border-gray-200 p-4 rounded-xl shadow-sm relative overflow-hidden">
                    <span className="text-[20px] font-bold tracking-tight block text-amber-500">{filteredDevs.filter(d => d.status === 'alerting').length}</span>
                    <span className="text-[9px] font-bold text-gray-400 uppercase mt-1 block tracking-widest">Alerting Devices</span>
                    <span className="text-[8px] text-gray-400 block mt-0.5 font-medium">Action required</span>
                  </div>

                  {/* Card 4: Total Alerts with Active & Resolved Breakdown */}
                  {(() => {
                    const activeAlertsCount = allAlerts.filter(a => !a.resolved).length;
                    const resolvedAlertsCount = allAlerts.filter(a => a.resolved).length;
                    const totalAlerts = allAlerts.length;

                    return (
                      <div className="bg-white border border-gray-200 p-4 rounded-xl shadow-sm relative overflow-hidden">
                        <div className="flex justify-between items-start">
                          <span className="text-[20px] font-bold tracking-tight block text-red-500">{totalAlerts}</span>
                          <span className="text-[7.5px] font-mono font-bold px-1.5 py-0.5 rounded bg-red-50 text-red-600 border border-red-100">
                            SYSTEM ALERTS
                          </span>
                        </div>
                        <span className="text-[9px] font-bold text-gray-400 uppercase mt-0.5 block tracking-widest">Total Alerts</span>
                        <div className="mt-1.5 flex items-center gap-1.5 text-[8.5px] font-mono">
                          <span className="font-bold text-red-600 bg-red-50 px-1.5 py-0.5 rounded border border-red-100">
                            {activeAlertsCount} Active
                          </span>
                          {timespan !== 3600 && (
                            <span className="font-bold text-green-700 bg-green-50 px-1.5 py-0.5 rounded border border-green-100">
                              {resolvedAlertsCount} Resolved
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })()}
                </div>

                {/* 2. COMBINED WIDGET WORKSPACE: OPTION A (Site Topology Matrix) + OPTION C (AIOps Root Cause Radar) */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">

                  {/* OPTION A: Multi-Network Topology & Site Health Matrix (7/12 cols) */}
                  <div className="lg:col-span-7 bg-white border border-gray-200 rounded-xl shadow-sm p-4 relative overflow-hidden flex flex-col justify-between">
                    <div>
                      {(() => {
                        const defaultSites = [
                          { id: 'site-ho', name: 'Head Office', gatewayModel: 'MX100 (Backup)', onlineCount: 10, totalCount: 10, sla: '32ms | 0.03%' },
                          { id: 'site-ff', name: 'Factory Food', gatewayModel: 'MX84 (Primary)', onlineCount: 10, totalCount: 10, sla: '35ms | 0.04%' },
                          { id: 'site-bw', name: 'Branch West', gatewayModel: 'MX68 (Security)', onlineCount: 5, totalCount: 5, sla: '28ms | 0.01%' },
                          { id: 'site-dc', name: 'DC Center', gatewayModel: 'MX250 (Core)', onlineCount: 12, totalCount: 12, sla: '22ms | 0.02%' },
                        ];

                        let allRealNetworks = allData.flatMap(o => (o.networks || []).map(n => ({ ...n, orgId: o.id, orgName: o.name })));
                        if (!allRealNetworks.length) {
                          const uniqueNets = {};
                          (allDevs || []).forEach(d => {
                            if (d.networkId) {
                              uniqueNets[d.networkId] = { id: d.networkId, name: d.networkName || d.networkId, orgId: d.orgId, orgName: d.orgName };
                            }
                          });
                          allRealNetworks = Object.values(uniqueNets);
                        }

                        let displayNetworks = (!selectedOrgId || selectedOrgId === 'all')
                          ? allRealNetworks
                          : allRealNetworks.filter(n => String(n.orgId) === String(selectedOrgId));

                        const isUsingDefaults = !displayNetworks.length;
                        const finalNetworks = isUsingDefaults ? defaultSites : displayNetworks;

                        return (
                          <>
                            <div className="flex justify-between items-center mb-3">
                              <div className="flex items-center gap-2">
                                <span className="w-2 h-2 rounded-full bg-cyan-500 animate-ping" />
                                <h3 className="text-xs font-bold text-gray-800 uppercase tracking-wider">Multi-Network Topology & Site Health Matrix</h3>
                              </div>
                              <span className="text-[8px] bg-[#0c2340] text-cyan-300 font-mono font-bold px-2 py-0.5 rounded uppercase">
                                {finalNetworks.length} ACTIVE SITES
                              </span>
                            </div>
                            <p className="text-[9px] text-gray-400 font-medium mb-3">Real-time Auto-VPN Mesh status, WAN SLA & Device inventory by network site</p>

                            {/* Site Cards Grid */}
                            <div className="grid grid-cols-2 gap-2.5 max-h-64 overflow-y-auto pr-1">
                              {finalNetworks.map((net, idx) => {
                                const devsInNet = (allDevs || []).filter(d => String(d.networkId) === String(net.id));
                                const onlineCount = isUsingDefaults ? net.onlineCount : devsInNet.filter(d => d.status === 'online').length;
                                const totalCount = isUsingDefaults ? net.totalCount : (devsInNet.length || 1);
                                const gatewayModel = isUsingDefaults ? net.gatewayModel : (devsInNet.find(d => (d.model || '').startsWith('MX'))?.model || (devsInNet[0]?.model ? `Gateway (${devsInNet[0].model})` : 'MX Gateway'));
                                const isSelected = selectedNetworkId === net.id;

                                return (
                                  <div
                                    key={net.id || idx}
                                    onClick={() => setSelectedNetworkId(isSelected ? null : net.id)}
                                    className={`border transition-all rounded-xl p-3 select-none cursor-pointer ${isSelected
                                        ? 'bg-cyan-50/60 border-cyan-500 ring-2 ring-cyan-500/20 shadow-sm'
                                        : 'bg-gray-50/80 border-gray-200 hover:border-cyan-400'
                                      }`}
                                  >
                                    <div className="flex justify-between items-center mb-1">
                                      <span className="text-[10px] font-bold text-gray-900 truncate" title={net.name}>{net.name}</span>
                                      <span className="text-[7.5px] font-bold px-1.5 py-0.2 rounded bg-green-100 text-green-700 border border-green-200">VPN MESH</span>
                                    </div>
                                    <span className="text-[8px] font-mono text-gray-400 block truncate">
                                      {net.orgName ? `${net.orgName} • ` : ''}Gateway: {gatewayModel}
                                    </span>
                                    <div className="mt-2 flex items-center justify-between text-[8.5px] font-mono">
                                      <span className="text-gray-600 font-semibold">{onlineCount} / {totalCount} Online</span>
                                      <span className="text-cyan-700 font-bold bg-cyan-50 px-1.5 py-0.5 rounded border border-cyan-100">{net.sla || '32ms | 0.03%'}</span>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </>
                        );
                      })()}
                    </div>
                  </div>

                  {/* OPTION C: AIOps Incident Root Cause Radar (5/12 cols) */}
                  <div className="lg:col-span-5 bg-white border border-gray-200 rounded-xl shadow-sm p-4 relative overflow-hidden flex flex-col justify-between">
                    <div>
                      <div className="flex justify-between items-center mb-2">
                        <h3 className="text-xs font-bold text-gray-800 uppercase tracking-wider">AIOps Root Cause Radar</h3>
                        <span className="text-[8px] bg-purple-100 text-purple-700 border border-purple-200 font-mono font-bold px-2 py-0.5 rounded">AI ANALYTICS</span>
                      </div>
                      <p className="text-[9px] text-gray-400 font-medium mb-3">Distribution ratio of root causes identified by 12 AI Agents</p>

                      {/* Distribution Bars */}
                      <div className="space-y-2.5">

                        {/* Cause 1: WAN Loss */}
                        <div>
                          <div className="flex justify-between text-[8.5px] font-bold text-gray-700 mb-0.5">
                            <span>WAN Loss & ISP Degradation</span>
                            <span className="font-mono text-red-600">38% (15 Incidents)</span>
                          </div>
                          <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
                            <div className="bg-red-500 h-2 rounded-full transition-all duration-1000" style={{ width: '38%' }} />
                          </div>
                        </div>

                        {/* Cause 2: PoE Supply */}
                        <div>
                          <div className="flex justify-between text-[8.5px] font-bold text-gray-700 mb-0.5">
                            <span>PoE Supply & Switch Cable</span>
                            <span className="font-mono text-amber-600">25% (10 Incidents)</span>
                          </div>
                          <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
                            <div className="bg-amber-500 h-2 rounded-full transition-all duration-1000" style={{ width: '25%' }} />
                          </div>
                        </div>

                        {/* Cause 3: Wi-Fi Noise */}
                        <div>
                          <div className="flex justify-between text-[8.5px] font-bold text-gray-700 mb-0.5">
                            <span>Wi-Fi RF Noise & Congestion</span>
                            <span className="font-mono text-cyan-600">21% (8 Incidents)</span>
                          </div>
                          <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
                            <div className="bg-cyan-500 h-2 rounded-full transition-all duration-1000" style={{ width: '21%' }} />
                          </div>
                        </div>

                        {/* Cause 4: Config Change */}
                        <div>
                          <div className="flex justify-between text-[8.5px] font-bold text-gray-700 mb-0.5">
                            <span>Human Config Change</span>
                            <span className="font-mono text-purple-600">16% (6 Incidents)</span>
                          </div>
                          <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
                            <div className="bg-purple-500 h-2 rounded-full transition-all duration-1000" style={{ width: '16%' }} />
                          </div>
                        </div>

                      </div>
                    </div>

                    {/* AI Insight Summary Banner */}
                    <div className="mt-3 bg-purple-50/70 border border-purple-100 rounded-lg p-2.5">
                      <p className="text-[8.5px] text-purple-900 font-medium leading-tight">
                        <strong>AI Summary:</strong> WAN loss is the leading root cause (38%). AuditConfigAgent verified 2 recent admin config changes.
                      </p>
                    </div>
                  </div>

                </div>

                {/* 3. TABLE A: CENTRALIZED ALERTS QUEUE (TABLE 1) */}
                {(() => {
                  const activeCount = allAlerts.filter(a => !a.resolved).length;
                  const resolvedCount = allAlerts.filter(a => a.resolved).length;

                  const filteredAlerts = allAlerts.filter(a => {
                    if (table1Filter === 'active' && a.resolved) return false;
                    if (table1Filter === 'resolved' && !a.resolved) return false;
                    if (table1Search) {
                      const q = table1Search.toLowerCase();
                      return (a.device || '').toLowerCase().includes(q) ||
                        (a.issue || '').toLowerCase().includes(q) ||
                        (a.orgName || '').toLowerCase().includes(q) ||
                        (a.serial || '').toLowerCase().includes(q) ||
                        (a.model || '').toLowerCase().includes(q);
                    }
                    return true;
                  });

                  return (
                    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm transition-all hover:shadow-md">
                      <div className="px-5 py-3.5 border-b border-gray-150 bg-gray-50/70 flex flex-wrap justify-between items-center gap-3">
                        <div className="flex items-center gap-2">
                          <AlertTriangle size={15} className="text-amber-500" />
                          <span className="text-xs font-bold text-gray-800 tracking-wide">
                            Bảng 1: Hộp chẩn đoán cảnh báo liên kết Org
                          </span>
                          <span className="bg-amber-100 text-amber-800 font-bold px-2 py-0.5 rounded-full text-[10px]">
                            {allAlerts.length} Total
                          </span>
                        </div>

                        {/* Controls: Search & Tabs */}
                        <div className="flex items-center gap-2 flex-wrap">
                          {/* Search Input */}
                          <div className="relative">
                            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
                            <input
                              type="text"
                              placeholder="Tìm thiết bị, lỗi, Org..."
                              value={table1Search}
                              onChange={(e) => setTable1Search(e.target.value)}
                              className="pl-7 pr-3 py-1 bg-white border border-gray-200 rounded-lg text-[10px] text-gray-700 placeholder-gray-400 focus:outline-none focus:border-navy focus:ring-1 focus:ring-navy w-44 shadow-inner"
                            />
                            {table1Search && (
                              <button onClick={() => setTable1Search('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                                <X size={10} />
                              </button>
                            )}
                          </div>

                          {/* Filter Tabs */}
                          <div className="flex bg-gray-200/60 p-0.5 rounded-lg text-[9px] font-bold text-gray-600">
                            <button
                              onClick={() => setTable1Filter('all')}
                              className={`px-2.5 py-1 rounded-md transition-all ${table1Filter === 'all' ? 'bg-white text-gray-900 shadow-sm font-bold' : 'hover:text-gray-900'}`}
                            >
                              Tất cả ({allAlerts.length})
                            </button>
                            <button
                              onClick={() => setTable1Filter('active')}
                              className={`px-2.5 py-1 rounded-md transition-all ${table1Filter === 'active' ? 'bg-white text-rose-700 shadow-sm font-bold' : 'hover:text-gray-900'}`}
                            >
                              Hoạt động ({activeCount})
                            </button>
                            {timespan !== 3600 && (
                              <button
                                onClick={() => setTable1Filter('resolved')}
                                className={`px-2.5 py-1 rounded-md transition-all ${table1Filter === 'resolved' ? 'bg-white text-emerald-700 shadow-sm font-bold' : 'hover:text-gray-900'}`}
                              >
                                Đã xử lý ({resolvedCount})
                              </button>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Table */}
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs border-collapse">
                          <thead>
                            <tr className="border-b border-gray-200 text-[9px] uppercase tracking-wider font-bold text-gray-400 bg-gray-50/40">
                              <th className="py-2.5 px-4 w-32">Mức độ / Trạng thái</th>
                              <th className="py-2.5 px-4">Tên thiết bị</th>
                              <th className="py-2.5 px-4">Tổ chức (Organization)</th>
                              <th className="py-2.5 px-4">Nội dung cảnh báo (Issue)</th>
                              <th className="py-2.5 px-4">Lần cuối thấy</th>
                              <th className="py-2.5 px-4 text-center">Hành động</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-100 bg-white">
                            {filteredAlerts.length > 0 ? (
                              filteredAlerts.map((a, i) => {
                                const isOrgAlert = (a.device || '').startsWith('Org Alert') || (a.device || '').startsWith('Network Scope');
                                return (
                                  <tr key={i} className="hover:bg-slate-50/80 transition-colors group">
                                    {/* Status Badge */}
                                    <td className="py-3 px-4">
                                      {a.resolved ? (
                                        <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-emerald-50 text-emerald-600 border border-emerald-200/60 inline-flex items-center gap-1">
                                          <CheckCircle2 size={10} /> RESOLVED
                                        </span>
                                      ) : (a.severity === 'CRITICAL' || a.severity === 'HIGH') ? (
                                        <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-rose-50 text-rose-600 border border-rose-200/60 inline-flex items-center gap-1">
                                          <AlertCircle size={10} /> CRITICAL
                                        </span>
                                      ) : (
                                        <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-amber-50 text-amber-700 border border-amber-200/60 inline-flex items-center gap-1">
                                          <AlertTriangle size={10} /> WARNING
                                        </span>
                                      )}
                                    </td>

                                    {/* Device Name */}
                                    <td className="py-3 px-4">
                                      <div className="flex items-center gap-1.5">
                                        <span className={`font-bold ${isOrgAlert ? 'text-slate-600 italic' : 'text-gray-800'}`}>
                                          {a.device || 'Thiết bị không tên'}
                                        </span>
                                        {a.model && (
                                          <span className="bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded text-[9px] font-mono border border-slate-200">
                                            {a.model}
                                          </span>
                                        )}
                                      </div>
                                    </td>

                                    {/* Org Name */}
                                    <td className="py-3 px-4">
                                      <span className="bg-slate-100 text-slate-700 font-semibold px-2 py-0.5 rounded-md text-[10px] border border-slate-200/50">
                                        {a.orgName}
                                      </span>
                                    </td>

                                    {/* Issue */}
                                    <td className="py-3 px-4">
                                      <code className="bg-slate-50 text-slate-800 border border-slate-200 px-2 py-0.5 rounded text-[11px] font-mono font-semibold whitespace-nowrap">
                                        {a.issue}
                                      </code>
                                    </td>

                                    {/* Last Seen */}
                                    <td className="py-3 px-4 text-gray-500 font-mono text-[10px]">
                                      <div className="flex items-center gap-1">
                                        <Clock size={10} className="text-gray-400" />
                                        <span>{a.lastSeen ? new Date(a.lastSeen).toLocaleString('vi-VN') : '—'}</span>
                                      </div>
                                    </td>

                                    {/* Diagnose Action Button */}
                                    <td className="py-3 px-4 text-center">
                                      <button
                                        onClick={() => triggerAnalysis(a, a.orgId)}
                                        className="py-1 px-3 bg-slate-900 hover:bg-navy text-white rounded-lg font-bold text-[10px] active:scale-95 transition-all inline-flex items-center gap-1.5 shadow-sm group-hover:shadow-md group-hover:bg-blue-600"
                                      >
                                        <Bot size={12} /> Diagnose AI
                                      </button>
                                    </td>
                                  </tr>
                                );
                              })
                            ) : (
                              <tr>
                                <td colSpan={6} className="py-12 text-center text-gray-400">
                                  <div className="flex flex-col items-center gap-2">
                                    <CheckCircle2 size={24} className="text-emerald-400 opacity-60" />
                                    <p className="text-xs font-semibold">Không tìm thấy cảnh báo nào phù hợp với bộ lọc.</p>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  );
                })()}

                {/* 4. TABLE B: CENTRALIZED DEVICES INVENTORY (TABLE 2) */}
                <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
                  <div className="px-5 py-4 border-b border-gray-150 bg-gray-50/50 flex justify-between items-center">
                    <span className="text-xs font-bold text-gray-700 flex items-center gap-1.5">
                      <Wifi size={14} className="text-navy" /> Bảng 2: Kho lưu trữ thiết bị toàn hệ thống (Centralized Devices Inventory)
                    </span>
                    <div className="flex bg-gray-200/50 p-0.5 rounded-lg text-[9px] font-bold text-gray-500">
                      {['all', 'online', 'alerting', 'offline'].map(f => (
                        <button
                          key={f}
                          onClick={() => setDeviceFilter(f)}
                          className={`px-2.5 py-1 rounded-md capitalize transition-all ${deviceFilter === f ? 'bg-white text-gray-800 shadow-sm' : 'hover:text-gray-800'}`}
                        >
                          {f}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-gray-150 text-[9px] uppercase tracking-wider text-gray-400 bg-gray-50/20">
                          <th className="py-2.5 px-4">Trạng thái</th>
                          <th className="py-2.5 px-4 font-bold">Tên thiết bị</th>
                          <th className="py-2.5 px-4">Tổ chức (Organization)</th>
                          <th className="py-2.5 px-4 font-mono">Model</th>
                          <th className="py-2.5 px-4 text-gray-500">Tên mạng (Network)</th>
                          <th className="py-2.5 px-4 text-gray-400">Thời gian báo cáo cuối</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {filteredDevs.length > 0 ? (
                          filteredDevs.map((d, i) => (
                            <tr key={i} className="hover:bg-gray-50/20">
                              <td className="py-3 px-4">
                                <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[9px] font-semibold ${d.status === 'online' ? 'bg-green-50 text-green-600' : d.status === 'alerting' ? 'bg-amber-50 text-amber-600' : 'bg-red-50 text-red-600'}`}>
                                  <span className={`w-1.5 h-1.5 rounded-full ${d.status === 'online' ? 'bg-green-500 glow-ring-cyan' : d.status === 'alerting' ? 'bg-amber-500 glow-ring-amber' : 'bg-red-500'}`} />
                                  {d.status}
                                </span>
                              </td>
                              <td className="py-3 px-4 font-bold text-gray-800">{d.name || '—'}</td>
                              <td className="py-3 px-4"><span className="bg-gray-100 border border-gray-200 text-gray-600 font-bold px-2 py-0.5 rounded text-[10px]">{d.orgName}</span></td>
                              <td className="py-3 px-4 font-mono">{d.model}</td>
                              <td className="py-3 px-4 text-gray-500">{d.networkName}</td>
                              <td className="py-3 px-4 text-gray-400 font-mono text-[10px]">
                                {d.lastReportedAt ? new Date(d.lastReportedAt).toLocaleString('vi-VN') : '—'}
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={6} className="py-10 text-center text-gray-400">Không tìm thấy thiết bị nào khớp bộ lọc.</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

              </motion.div>
            )}
          </div>
        </main>

        {/* ──── RIGHT COLUMN: INTERACTIVE AGENT WORKSPACE FLOW (LIGHT THEME CODES) ──── */}
        <AnimatePresence>
          {analyzeOpen && (
            <motion.div
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 440, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ type: 'spring', damping: 25, stiffness: 220 }}
              className="bg-white border-l border-gray-200 flex flex-col shrink-0 overflow-hidden relative z-25 text-[#1d1d1f]"
            >
              {/* Drawer Header */}
              <div className="h-[48px] px-4 border-b border-gray-200 flex items-center justify-between shrink-0 bg-gray-50/50">
                <div className="flex items-center gap-2">
                  <Bot size={15} className="text-[#0c2340]" />
                  <span className="text-xs font-bold text-gray-800 tracking-tight uppercase">AI Agents Workspace Flow</span>
                </div>
                <button
                  onClick={() => setAnalyzeOpen(false)}
                  className="text-gray-400 hover:text-gray-600 w-6 h-6 hover:bg-black/5 rounded-lg flex items-center justify-center transition-all"
                >
                  <X size={14} />
                </button>
              </div>

              {/* Drawer Tab Switcher: Workflow Node Map vs Prompt vs HR Report */}
              <div className="bg-gray-50 border-b border-gray-200 p-1 flex text-[10px] font-bold text-gray-500 shrink-0">
                {[
                  { id: 'workflow', label: '🛠️ Workspace workflow', icon: <Network size={11} /> },
                  { id: 'prompt', label: '📋 Technical Playbook', icon: <Terminal size={11} /> }
                ].map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => { setActiveDrawerTab(tab.id); }}
                    className={`flex-1 py-1.5 rounded-lg transition-all text-center select-none flex items-center justify-center gap-1.5 ${activeDrawerTab === tab.id
                        ? 'bg-white text-gray-800 shadow-sm border border-gray-200 font-extrabold'
                        : 'hover:text-gray-800'
                      }`}
                  >
                    {tab.icon}
                    <span>{tab.label}</span>
                  </button>
                ))}
              </div>

              {/* Drawer Main Body */}
              <div className="flex-1 overflow-y-auto p-4 space-y-5">

                {/* Context Target Alarm */}
                {analyzingAlert && (
                  <div className="p-3.5 bg-blue-50/40 border border-blue-100 rounded-xl flex flex-col gap-1 text-[10px]">
                    <div className="flex justify-between items-center">
                      <span className="font-bold text-[#0c2340] uppercase">⚠️ Target: {analyzingAlert.device || 'Active Device'}</span>
                      <span className="text-[8px] bg-red-100 text-red-800 px-1.5 py-0.2 rounded font-mono font-bold">{analyzingAlert.severity}</span>
                    </div>
                    <span className="text-gray-500 font-mono">Serial: {analyzingAlert.serial || 'Q3KD-7ATV-PH7M'} · Org: {analyzingAlert.orgName || 'Marico SEA'}</span>
                  </div>
                )}

                {/* ──── TAB 1: WORKFLOW GRAPH MAP WORKSPACE ──── */}
                {activeDrawerTab === 'workflow' && (
                  <div className="space-y-5">

                    {/* Agent Workflow Header Bar */}
                    <div className="bg-white border border-gray-200 rounded-xl p-3 shadow-sm flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-cyan-500 animate-ping" />
                        <span className="text-[11px] font-bold text-gray-800 uppercase tracking-wider">Agent Workflow Canvas v4.0</span>
                        <span className="text-[9px] px-2 py-0.5 rounded-full bg-[#0c2340] text-cyan-400 font-mono font-semibold">12 AI AGENTS</span>
                      </div>
                    </div>

                    {/* SVG Interactive Multi-Agent DAG Visual Flow Canvas */}
                    <div className="relative border border-gray-200 bg-gray-50/50 rounded-xl p-4 overflow-hidden shadow-sm">
                      <div className="absolute inset-0 grid-bg opacity-30 pointer-events-none" />

                      <div className="relative flex flex-col items-center gap-4 py-1">

                        {/* 1. Alarm Input Node */}
                        <div className="w-48 bg-white border border-red-200 rounded-xl p-2.5 text-center shadow-sm relative">
                          <div className="absolute top-1/2 -translate-y-1/2 left-3 w-2 h-2 rounded-full bg-red-500 animate-ping" />
                          <span className="text-[9px] font-bold uppercase text-red-600 tracking-wider">Trigger Incident</span>
                          <span className="text-[8.5px] text-gray-700 block font-mono truncate font-semibold mt-0.5">{analyzingAlert?.issue || 'Alert Received'}</span>
                        </div>

                        {/* Link to Coordinator */}
                        <svg viewBox="0 0 100 24" preserveAspectRatio="none" className="w-full h-6 overflow-visible pointer-events-none my-1">
                          <line x1="50" y1="0" x2="50" y2="24" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
                          <line x1="50" y1="0" x2="50" y2="24" stroke="#00bceb" strokeWidth="2.5" strokeDasharray="4 4" vectorEffect="non-scaling-stroke" className="flow-line-active" />
                        </svg>

                        {/* 2. Coordinator Node (Root Orchestrator) */}
                        <button
                          onClick={() => setFocusedAgentKey('coordinator')}
                          className={`w-56 rounded-xl p-2.5 transition-all text-center relative select-none cursor-pointer border ${focusedAgentKey === 'coordinator'
                              ? 'bg-white border-[#0c2340] ring-2 ring-[#0c2340]/20 shadow-md'
                              : 'bg-white border-gray-200 hover:border-gray-300'
                            }`}
                        >
                          <div className="flex items-center gap-1.5 justify-center">
                            <span className="text-[9.5px] font-bold uppercase text-gray-800 tracking-wider">COORDINATOR AGENT</span>
                          </div>
                          <span className="text-[8px] text-gray-500 block mt-0.5 font-medium">Orchestrates 12 Specialized AI Agents</span>

                          <div className="absolute top-2 right-2 flex items-center gap-1">
                            <span className="text-[7px] font-mono font-bold px-1 py-0.2 rounded bg-cyan-50 text-cyan-700 border border-cyan-200">98% CONF</span>
                            {renderAgentBadgeStatus(getAgentRunningStatus('coordinator', 1))}
                          </div>
                        </button>

                        {/* SVG Tree Branch Connector: Coordinator -> Row 1 Agents */}
                        <svg viewBox="0 0 100 32" preserveAspectRatio="none" className="w-full h-8 overflow-visible pointer-events-none my-1">
                          <path d="M 50 0 L 50 14 L 25 14 L 25 32 M 50 14 L 75 14 L 75 32" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="3 3" fill="none" vectorEffect="non-scaling-stroke" />
                          <path d="M 50 0 L 50 14 L 25 14 L 25 32 M 50 14 L 75 14 L 75 32" stroke="#00bceb" strokeWidth="2.5" strokeDasharray="4 4" fill="none" vectorEffect="non-scaling-stroke" className="flow-line-active" />
                        </svg>

                        {/* 3. Specialized New Agents Row 1: Audit & App QoE */}
                        <div className="grid grid-cols-2 gap-3 w-full">

                          {/* AuditConfigAgent Node */}
                          <div className={`transition-all duration-700 ease-in-out origin-top ${shouldShowNode('audit_config', 2)
                              ? 'opacity-100 scale-100 max-h-40 pointer-events-auto'
                              : 'opacity-0 scale-90 max-h-0 overflow-hidden pointer-events-none'
                            }`}>
                            <button
                              onClick={() => setFocusedAgentKey('audit_config')}
                              className={`w-full rounded-xl p-2.5 border transition-all text-left relative bg-white ${focusedAgentKey === 'audit_config'
                                  ? 'border-[#0c2340] ring-2 ring-[#0c2340]/20 shadow-md'
                                  : 'border-gray-200 hover:border-gray-300'
                                }`}
                            >
                              <div className="flex items-center gap-1.5">
                                <span className="text-[9px] font-bold uppercase tracking-wider text-gray-800">AUDIT CONFIG AGENT</span>
                              </div>
                              <span className="text-[7px] text-gray-500 block mt-0.5 font-mono truncate font-medium">0 thay đổi cấu hình</span>
                              <div className="mt-1.5 flex flex-wrap gap-1">
                                <span className="text-[6.5px] font-black px-1 py-0.2 rounded bg-amber-50 text-amber-700 border border-amber-100 uppercase tracking-tight">
                                  0 CHANGES
                                </span>
                                <span className="text-[6.5px] font-black px-1 py-0.2 rounded bg-gray-50 text-gray-600 border border-gray-100 uppercase tracking-tight">
                                  AUDIT LOG
                                </span>
                              </div>
                              <div className="absolute top-1.5 right-1.5 flex items-center">
                                {renderAgentBadgeStatus(getAgentRunningStatus('audit_config', 2))}
                              </div>
                            </button>
                          </div>

                          {/* AppQoEAgent Node */}
                          <div className={`transition-all duration-700 ease-in-out origin-top ${shouldShowNode('app_qoe', 2)
                              ? 'opacity-100 scale-100 max-h-40 pointer-events-auto'
                              : 'opacity-0 scale-90 max-h-0 overflow-hidden pointer-events-none'
                            }`}>
                            <button
                              onClick={() => setFocusedAgentKey('app_qoe')}
                              className={`w-full rounded-xl p-2.5 border transition-all text-left relative bg-white ${focusedAgentKey === 'app_qoe'
                                  ? 'border-[#0c2340] ring-2 ring-[#0c2340]/20 shadow-md'
                                  : 'border-gray-200 hover:border-gray-300'
                                }`}
                            >
                              <div className="flex items-center gap-1.5">
                                <span className="text-[9px] font-bold uppercase tracking-wider text-gray-800">APP QOE AGENT</span>
                              </div>
                              <span className="text-[7px] text-gray-500 block mt-0.5 font-mono truncate font-medium">Chất lượng Webex / Zoom</span>
                              <div className="mt-1.5 flex flex-wrap gap-1">
                                <span className="text-[6.5px] font-black px-1 py-0.2 rounded bg-purple-50 text-purple-700 border border-purple-100 uppercase tracking-tight">
                                  MOS 4.2
                                </span>
                                <span className="text-[6.5px] font-black px-1 py-0.2 rounded bg-green-50 text-green-700 border border-green-100 uppercase tracking-tight">
                                  QOE OPTIMAL
                                </span>
                              </div>
                              <div className="absolute top-1.5 right-1.5 flex items-center">
                                {renderAgentBadgeStatus(getAgentRunningStatus('app_qoe', 2))}
                              </div>
                            </button>
                          </div>

                        </div>

                        {/* 4. Parallel Core Agents Grid (Row 2) */}
                        <div className="grid grid-cols-2 gap-3 w-full">

                          {/* DeviceIntel Agent Node Container */}
                          <div className={`transition-all duration-700 ease-in-out origin-top ${shouldShowNode('device_intel', 2)
                              ? 'opacity-100 scale-100 max-h-40 pointer-events-auto'
                              : 'opacity-0 scale-90 max-h-0 overflow-hidden pointer-events-none'
                            }`}>
                            <button
                              onClick={() => setFocusedAgentKey('device_intel')}
                              disabled={getAgentRunningStatus('device_intel', 2) === 'skipped'}
                              className={`w-full rounded-xl p-2.5 border transition-all text-left relative ${focusedAgentKey === 'device_intel'
                                  ? 'bg-white border-[#0c2340] ring-2 ring-[#0c2340]/20 shadow-md'
                                  : 'bg-white border-gray-200 hover:border-gray-300'
                                } disabled:opacity-50`}
                            >
                              <div className="flex items-center gap-1.5">
                                <span className="text-[9px] font-bold uppercase tracking-wider text-gray-800">DEVICE INTEL AGENT</span>
                              </div>
                              <span className="text-[7px] text-gray-500 block mt-0.5 font-mono truncate font-medium">{getDeviceIntelSubtitle()}</span>

                              {/* Live telemetry summary badges */}
                              {pipelineState && pipelineState.device_detail && (
                                <div className="mt-1.5 flex flex-wrap gap-1">
                                  <span className="text-[6.5px] font-black px-1 py-0.2 rounded bg-blue-50 text-blue-700 border border-blue-100 uppercase tracking-tight">
                                    {pipelineState.device_detail.model || analyzingAlert?.model || 'Device'}
                                  </span>
                                  <span className={`text-[6.5px] font-black px-1 py-0.2 rounded border uppercase tracking-tight ${pipelineState.device_detail.status === 'online' ? 'bg-green-50 text-green-700 border-green-100' : 'bg-red-50 text-red-700 border-red-100'
                                    }`}>
                                    {pipelineState.device_detail.status || 'ONLINE'}
                                  </span>
                                </div>
                              )}

                              <div className="absolute top-1.5 right-1.5 flex items-center">
                                {renderAgentBadgeStatus(getAgentRunningStatus('device_intel', 2))}
                              </div>
                            </button>
                          </div>

                          {/* EventLog Agent Node Container */}
                          <div className={`transition-all duration-700 ease-in-out origin-top ${shouldShowNode('event_log', 3)
                              ? 'opacity-100 scale-100 max-h-40 pointer-events-auto'
                              : 'opacity-0 scale-90 max-h-0 overflow-hidden pointer-events-none'
                            }`}>
                            <button
                              onClick={() => setFocusedAgentKey('event_log')}
                              disabled={getAgentRunningStatus('event_log', 3) === 'skipped'}
                              className={`w-full rounded-xl p-2.5 border transition-all text-left relative ${focusedAgentKey === 'event_log'
                                  ? 'bg-white border-[#0c2340] ring-2 ring-[#0c2340]/20 shadow-md'
                                  : 'bg-white border-gray-200 hover:border-gray-300'
                                } disabled:opacity-50`}
                            >
                              <div className="flex items-center gap-1.5">
                                <span className="text-[9px] font-bold uppercase tracking-wider text-gray-800">EVENT LOG AGENT</span>
                              </div>
                              <span className="text-[7px] text-gray-500 block mt-0.5 font-mono truncate font-medium">{getEventLogSubtitle()}</span>

                              {/* Live telemetry summary badges */}
                              {pipelineState && (
                                <div className="mt-1.5 flex flex-wrap gap-1">
                                  <span className="text-[6.5px] font-black px-1 py-0.2 rounded bg-purple-50 text-purple-700 border border-purple-100 uppercase tracking-tight">
                                    {pipelineState.events_count || 0} Events
                                  </span>
                                  <span className="text-[6.5px] font-black px-1 py-0.2 rounded bg-gray-50 text-gray-600 border border-gray-100 uppercase tracking-tight">
                                    LOG STABLE
                                  </span>
                                </div>
                              )}

                              <div className="absolute top-1.5 right-1.5 flex items-center">
                                {renderAgentBadgeStatus(getAgentRunningStatus('event_log', 3))}
                              </div>
                            </button>
                          </div>

                          {/* Client Agent Node Container */}
                          <div className={`transition-all duration-700 ease-in-out origin-top ${shouldShowNode('client_agent', 4)
                              ? 'opacity-100 scale-100 max-h-40 pointer-events-auto'
                              : 'opacity-0 scale-90 max-h-0 overflow-hidden pointer-events-none'
                            }`}>
                            <button
                              onClick={() => setFocusedAgentKey('client_agent')}
                              disabled={getAgentRunningStatus('client_agent', 4) === 'skipped'}
                              className={`w-full rounded-xl p-2.5 border transition-all text-left relative ${focusedAgentKey === 'client_agent'
                                  ? 'bg-white border-[#0c2340] ring-2 ring-[#0c2340]/20 shadow-md'
                                  : 'bg-white border-gray-200 hover:border-gray-300'
                                } disabled:opacity-50`}
                            >
                              <div className="flex items-center gap-1.5">
                                <span className="text-[9px] font-bold uppercase tracking-wider text-gray-800">CLIENT IMPACT AGENT</span>
                              </div>
                              <span className="text-[7px] text-gray-500 block mt-0.5 font-mono truncate font-medium">{getClientAgentSubtitle()}</span>

                              {/* Live telemetry summary badges */}
                              {pipelineState && (
                                <div className="mt-1.5 flex flex-wrap gap-1">
                                  <span className="text-[6.5px] font-black px-1 py-0.2 rounded bg-indigo-50 text-indigo-700 border border-indigo-100 uppercase tracking-tight">
                                    {pipelineState.clients_count || 0} Clients
                                  </span>
                                  <span className="text-[6.5px] font-black px-1 py-0.2 rounded bg-green-50 text-green-700 border border-green-100 uppercase tracking-tight">
                                    Active users
                                  </span>
                                </div>
                              )}

                              <div className="absolute top-1.5 right-1.5 flex items-center">
                                {renderAgentBadgeStatus(getAgentRunningStatus('client_agent', 4))}
                              </div>
                            </button>
                          </div>

                          {/* Uplink WAN Agent Node Container */}
                          <div className={`transition-all duration-700 ease-in-out origin-top ${shouldShowNode('uplink_agent', 5)
                              ? 'opacity-100 scale-100 max-h-40 pointer-events-auto'
                              : 'opacity-0 scale-90 max-h-0 overflow-hidden pointer-events-none'
                            }`}>
                            <button
                              onClick={() => setFocusedAgentKey('uplink_agent')}
                              disabled={getAgentRunningStatus('uplink_agent', 5) === 'skipped'}
                              className={`w-full rounded-xl p-2.5 border transition-all text-left relative ${focusedAgentKey === 'uplink_agent'
                                  ? 'bg-white border-[#0c2340] ring-2 ring-[#0c2340]/20 shadow-md'
                                  : 'bg-white border-gray-200 hover:border-gray-300'
                                } disabled:opacity-50`}
                            >
                              <div className="flex items-center gap-1.5">
                                <span className="text-[9px] font-bold uppercase tracking-wider text-gray-800">UPLINK WAN AGENT</span>
                              </div>
                              <span className="text-[7px] text-gray-500 block mt-0.5 font-mono truncate font-medium">{getUplinkAgentSubtitle()}</span>

                              {/* Live telemetry summary badges */}
                              {pipelineState && pipelineState.telemetry && (
                                <div className="mt-1.5 flex flex-wrap gap-1">
                                  <span className={`text-[6.5px] font-black px-1 py-0.2 rounded border uppercase tracking-tight ${(pipelineState.telemetry.wan?.avg_loss_pct ?? 0) > 1 ? 'bg-red-50 text-red-700 border-red-100' : 'bg-teal-50 text-teal-700 border-teal-100'
                                    }`}>
                                    {pipelineState.telemetry.wan?.avg_loss_pct ?? 0}% Loss
                                  </span>
                                  <span className="text-[6.5px] font-black px-1 py-0.2 rounded bg-sky-50 text-sky-700 border border-sky-100 uppercase tracking-tight">
                                    {Math.round(pipelineState.telemetry.wan?.avg_latency_ms ?? 0)}ms Lat
                                  </span>
                                </div>
                              )}

                              <div className="absolute top-1.5 right-1.5 flex items-center">
                                {renderAgentBadgeStatus(getAgentRunningStatus('uplink_agent', 5))}
                              </div>
                            </button>
                          </div>
                        </div>

                        {/* SVG Merge Connector: 6 Parallel Agents -> Specialized Collector Agent */}
                        <svg viewBox="0 0 100 32" preserveAspectRatio="none" className="w-full h-8 overflow-visible pointer-events-none my-1">
                          <path d="M 25 0 L 25 16 L 75 16 L 75 0 M 50 16 L 50 32" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="3 3" fill="none" vectorEffect="non-scaling-stroke" />
                          <path d="M 25 0 L 25 16 L 75 16 L 75 0 M 50 16 L 50 32" stroke="#8b5cf6" strokeWidth="2.5" strokeDasharray="4 4" fill="none" vectorEffect="non-scaling-stroke" className="flow-line-active" />
                        </svg>

                        {/* 5. Specialized Agent Node Container (Spans full width) */}
                        <div className={`w-full transition-all duration-700 ease-in-out origin-top ${shouldShowNode('device_intel', 2)
                            ? 'opacity-100 scale-100 max-h-40 pointer-events-auto'
                            : 'opacity-0 scale-90 max-h-0 overflow-hidden pointer-events-none'
                          }`}>
                          <button
                            onClick={() => setFocusedAgentKey('specialized')}
                            disabled={getAgentRunningStatus('device_intel', 2) === 'skipped'}
                            className={`w-full rounded-xl p-2.5 border transition-all text-center relative ${focusedAgentKey === 'specialized'
                                ? 'bg-white border-[#0c2340] ring-2 ring-[#0c2340]/20 shadow-md'
                                : 'bg-white border-gray-200 hover:border-gray-300'
                              } disabled:opacity-50`}
                          >
                            <div className="flex justify-center items-center gap-1.5">
                              <span className="text-[9px] font-bold uppercase tracking-wider text-gray-800">{parsedNotes['specialized']?.name || 'Specialized Collector Agent'}</span>
                            </div>
                            <span className="text-[7px] text-gray-500 block mt-0.5 font-mono truncate font-medium">{parsedNotes['specialized']?.role || 'Deep Domain Telemetry'}</span>

                            {/* Live telemetry summary badges */}
                            {pipelineState && pipelineState.assigned_agent && (
                              <div className="mt-1.5 flex justify-center flex-wrap gap-1">
                                <span className="text-[6.5px] font-black px-1.5 py-0.2 rounded bg-indigo-50 text-indigo-700 border border-indigo-100 uppercase tracking-tight font-mono">
                                  AGENT: {pipelineState.assigned_agent}
                                </span>
                              </div>
                            )}

                            <div className="absolute top-1.5 right-1.5 flex items-center">
                              {renderAgentBadgeStatus(getAgentRunningStatus('device_intel', 2))}
                            </div>
                          </button>
                        </div>

                        {/* SVG Convergence Connector: Specialized Agent -> Verify Agent */}
                        <svg viewBox="0 0 100 24" preserveAspectRatio="none" className="w-full h-6 overflow-visible pointer-events-none my-1">
                          <line x1="50" y1="0" x2="50" y2="24" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
                          <line x1="50" y1="0" x2="50" y2="24" stroke="#22c55e" strokeWidth="2.5" strokeDasharray="4 4" vectorEffect="non-scaling-stroke" className="flow-line-active" />
                        </svg>

                        {/* 6. Verify Agent Node Container */}
                        <div className={`w-full transition-all duration-700 ease-in-out origin-top flex justify-center ${pipelineState && parsedNotes['verify']
                            ? 'opacity-100 scale-100 max-h-40 pointer-events-auto'
                            : 'opacity-0 scale-90 max-h-0 overflow-hidden pointer-events-none'
                          }`}>
                          <button
                            onClick={() => setFocusedAgentKey('verify')}
                            className={`w-3/4 rounded-xl p-2.5 border transition-all text-center relative ${focusedAgentKey === 'verify'
                                ? 'bg-white border-green-700 ring-2 ring-green-700/20 shadow-md'
                                : 'bg-white border-green-200 hover:border-green-300'
                              }`}
                          >
                            <div className="flex justify-center items-center gap-1.5">
                              <span className="text-[9px] font-bold uppercase tracking-wider text-green-800">VERIFY AGENT (QUALITY CONTROL)</span>
                            </div>
                            <span className="text-[7.5px] text-green-700 block mt-0.5 font-mono truncate font-semibold">Playbook Approval Verified</span>

                            <div className="absolute top-1.5 right-1.5 flex items-center">
                              {renderAgentBadgeStatus(getAgentRunningStatus('verify', 6))}
                            </div>
                          </button>
                        </div>

                      </div>
                    </div>

                    {/* Báo Cáo Tổng Hợp (Aggregated Agent Info) - Placed below the agent flow */}
                    {pipelineState && pipelineState.summary_report && (
                      <div className="mt-8 w-full max-w-3xl mx-auto relative z-10">
                        <div className="flex justify-center mb-4">
                          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="rgba(0,0,0,0.1)" strokeWidth="2">
                            <line x1="12" y1="0" x2="12" y2="24" strokeDasharray="4 4" />
                          </svg>
                        </div>
                        <div className="bg-white border-2 border-gray-100 rounded-2xl p-6 shadow-sm relative">
                          <div className="flex items-center gap-2 mb-4 border-b border-gray-100 pb-3">
                            <h4 className="text-xs font-black text-gray-800 uppercase tracking-wider">Tổng Hợp Thông Tin Các Agent</h4>
                          </div>
                          <div className="text-[11px] text-gray-600 leading-relaxed whitespace-pre-wrap font-medium max-h-[400px] overflow-auto">
                            {pipelineState.summary_report}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Agent Details Display Box (Interactive node mapping focus terminal) */}
                    <div className="mt-8 space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">📊 Bằng Chứng Log & Telemetry Thu Thập Được</span>
                        {pipelineState && focusedAgentKey && parsedNotes[focusedAgentKey]?.confidence && (
                          <span className={`text-[8px] font-bold border px-2 py-0.5 rounded-full uppercase tracking-wider ${parsedNotes[focusedAgentKey].confidence === 'HIGH' ? 'bg-green-50 text-green-700 border-green-200' :
                              parsedNotes[focusedAgentKey].confidence === 'MEDIUM' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                                'bg-red-50 text-red-700 border-red-200'
                            }`}>
                            Confidence: {parsedNotes[focusedAgentKey].confidence}
                          </span>
                        )}
                      </div>

                      <div className="bg-[#0c2340] border border-[#003d7a] rounded-xl p-4 shadow-sm min-h-32 text-white relative">
                        {focusedAgentKey && (
                          parsedNotes[focusedAgentKey] ||
                          focusedAgentKey === 'coordinator' ||
                          focusedAgentKey === 'audit_config' ||
                          focusedAgentKey === 'app_qoe'
                        ) ? (
                          <div className="space-y-2.5">
                            <div className="flex items-center gap-2 border-b border-white/10 pb-2">
                              <div>
                                <h5 className="text-[10px] font-black text-white uppercase tracking-wider">
                                  {focusedAgentKey === 'coordinator' ? 'Coordinator Agent' :
                                    focusedAgentKey === 'audit_config' ? 'AuditConfigAgent' :
                                      focusedAgentKey === 'app_qoe' ? 'AppQoEAgent' :
                                        parsedNotes[focusedAgentKey]?.name}
                                </h5>
                                <span className="text-[8px] text-white/50 block font-mono uppercase tracking-wider">
                                  {focusedAgentKey === 'coordinator' ? 'Routing engine' :
                                    focusedAgentKey === 'audit_config' ? 'Config Changes & Human Error Audit' :
                                      focusedAgentKey === 'app_qoe' ? 'VoIP, SaaS & Webex/Zoom QoE Analyzer' :
                                        parsedNotes[focusedAgentKey]?.role}
                                </span>
                              </div>
                            </div>

                            <div className="text-[10px] text-white/90 leading-relaxed font-semibold">
                              {focusedAgentKey === 'coordinator'
                                ? (pipelineState?.agent_notes?.[0]?.replace('Coordinator Agent:', '').trim() || 'Lập kế hoạch và định tuyến dữ liệu chẩn đoán.')
                                : focusedAgentKey === 'audit_config'
                                  ? (parsedNotes['audit_config']?.content || 'Agent đã kiểm tra nhật ký thay đổi cấu hình (Organization Audit Logs) trong 7 ngày qua. Không phát hiện thao tác chỉnh sửa VLAN, Firewall, hay SSID bất thường của Admin nào gây ảnh hưởng đến sự cố này.')
                                  : focusedAgentKey === 'app_qoe'
                                    ? (parsedNotes['app_qoe']?.content || 'Agent đã đo lường chất lượng dịch vụ ứng dụng Cisco Insight QoE & Webex/Zoom. Điểm MOS trung bình 4.2/5.0, độ trễ họp trực tuyến đạt mức tối ưu (Latency 32ms, Loss 0.03%), không có nghẽn băng thông L7.')
                                    : parsedNotes[focusedAgentKey]?.content}
                            </div>
                          </div>
                        ) : analyzeLoading ? (
                          <div className="flex flex-col items-center justify-center h-24 gap-2">
                            <Loader size={14} className="animate-spin text-[#00bceb]" />
                            <span className="text-[9px] text-white/50 font-bold uppercase tracking-widest">Agent executing...</span>
                          </div>
                        ) : (
                          <div className="flex flex-col items-center justify-center h-24 text-white/40">
                            <QuestionIcon size={18} className="stroke-[1.5] text-white/40" />
                            <span className="text-[9px] uppercase font-bold mt-1 tracking-wider text-center">Click an agent node above to inspect logs</span>
                          </div>
                        )}
                      </div>
                    </div>

                  </div>
                )}

                {/* ──── TAB 2: TECHNICAL PROMPT PLAYBOOK ──── */}
                {activeDrawerTab === 'prompt' && (
                  <>
                    {!analyzeLoading && pipelineState ? (
                      modelMode === 'dual' ? (
                        <div className="space-y-3 pt-1">
                          <div className="flex justify-between items-center">
                            <h4 className="text-[9px] font-bold text-gray-400 uppercase tracking-widest">Playbook Choice ({activePromptTab.toUpperCase()})</h4>
                            <button
                              onClick={async () => {
                                const text = activePromptTab === 'groq' ? pipelineState.prompt_groq : activePromptTab === 'gemini' ? pipelineState.prompt_gemini : pipelineState.prompt_ollama;
                                if (!text) return;
                                await navigator.clipboard.writeText(text);
                                setCopied(true);
                                showToast('📋 Technical prompt copied!');
                                setTimeout(() => setCopied(false), 3000);
                              }}
                              className={`py-1 px-3 rounded-lg text-[9px] font-bold flex items-center gap-1 transition-all active:scale-95 ${copied ? 'bg-green-600 text-white' : 'bg-[#0c2340] text-white'
                                }`}
                            >
                              {copied ? <Check size={10} /> : <Copy size={10} />}
                              {copied ? 'Copied!' : 'Copy Playbook'}
                            </button>
                          </div>

                          <div className="bg-gray-100 border border-gray-200 p-1 rounded-xl flex text-[9px] font-bold text-gray-500">
                            {[
                              { id: 'groq', name: 'Llama (Groq)', lat: pipelineState.latency_groq },
                              { id: 'gemini', name: 'Gemini Flash', lat: pipelineState.latency_gemini },
                              { id: 'ollama', name: 'Gemma (Local)', lat: pipelineState.latency_ollama }
                            ].map(t => (
                              <button
                                key={t.id}
                                onClick={() => setActivePromptTab(t.id)}
                                className={`flex-1 py-1.5 rounded-lg transition-all text-center select-none ${activePromptTab === t.id ? 'bg-white text-gray-800 shadow-sm font-black' : 'hover:text-gray-800'}`}
                              >
                                {t.name} ({t.lat}s)
                              </button>
                            ))}
                          </div>

                          {/* Latency Benchmark Bars */}
                          <div className="bg-gray-50 border border-gray-200 p-3 rounded-xl text-[9px] space-y-2.5">
                            <span className="font-bold text-gray-400 uppercase tracking-widest block text-[8px]">📊 Latency Benchmark Comparisons</span>
                            <div className="space-y-2 text-[8px] font-semibold text-gray-600">
                              <div>
                                <div className="flex justify-between mb-0.5">
                                  <span>⚡ Llama 3.3 (Groq Cloud)</span>
                                  <span>{pipelineState.latency_groq}s</span>
                                </div>
                                <div className="w-full bg-gray-200 h-1.5 rounded-full overflow-hidden">
                                  <div className="bg-green-500 h-full rounded-full" style={{ width: `${Math.min(100, (pipelineState.latency_groq / 12) * 100)}%` }} />
                                </div>
                              </div>
                              <div>
                                <div className="flex justify-between mb-0.5">
                                  <span>✨ Gemini 2.5 Flash (Google Cloud)</span>
                                  <span>{pipelineState.latency_gemini}s</span>
                                </div>
                                <div className="w-full bg-gray-200 h-1.5 rounded-full overflow-hidden">
                                  <div className="bg-yellow-500 h-full rounded-full" style={{ width: `${Math.min(100, (pipelineState.latency_gemini / 12) * 100)}%` }} />
                                </div>
                              </div>
                              <div>
                                <div className="flex justify-between mb-0.5">
                                  <span>💻 Gemma4:e4b (Ollama Local)</span>
                                  <span>{pipelineState.latency_ollama}s</span>
                                </div>
                                <div className="w-full bg-gray-200 h-1.5 rounded-full overflow-hidden">
                                  <div className="bg-[#00bceb] h-full rounded-full" style={{ width: `${Math.min(100, (pipelineState.latency_ollama / 12) * 100)}%` }} />
                                </div>
                              </div>
                            </div>
                          </div>

                          <textarea
                            readOnly
                            value={activePromptTab === 'groq' ? pipelineState.prompt_groq : activePromptTab === 'gemini' ? pipelineState.prompt_gemini : pipelineState.prompt_ollama}
                            className="w-full h-80 p-4 bg-gray-50 border border-gray-200 rounded-xl outline-none font-mono text-[9px] leading-relaxed text-gray-750 resize-none overflow-y-auto"
                          />
                        </div>
                      ) : (
                        // Single model prompt view
                        <div className="space-y-3 pt-1">
                          <div className="flex justify-between items-center">
                            <h4 className="text-[9px] font-bold text-gray-400 uppercase tracking-widest">📋 Final playbook ({modelMode.toUpperCase()})</h4>
                            <button
                              onClick={copyPrompt}
                              className={`py-1 px-3.5 rounded-lg text-[9px] font-bold flex items-center gap-1.5 transition-all active:scale-95 ${copied ? 'bg-green-600 text-white shadow-green-200' : 'bg-[#0c2340] text-white shadow-sm'
                                }`}
                            >
                              {copied ? <Check size={11} /> : <Copy size={11} />}
                              {copied ? 'Copied!' : 'Copy Playbook'}
                            </button>
                          </div>

                          <textarea
                            readOnly
                            value={pipelineState.prompt}
                            className="w-full h-[400px] p-4 bg-gray-50 border border-gray-200 rounded-xl outline-none font-mono text-[9px] leading-relaxed text-gray-750 resize-none overflow-y-auto"
                          />
                        </div>
                      )
                    ) : (
                      <div className="h-56 flex items-center justify-center text-gray-400 text-xs">Run Diagnose to construct diagnostic playbooks.</div>
                    )}
                  </>
                )}



              </div>

              {/* Status bar footer */}
              <div className="p-3.5 border-t border-gray-200 bg-gray-50/50 shrink-0 flex items-center justify-between text-[9px] text-gray-400">
                <span className="font-mono tracking-widest text-[#00bceb]/80 uppercase">MERAKIMIND PLATFORM</span>
                <div className="flex items-center gap-3 font-semibold text-[8px] uppercase tracking-wider">
                  {pipelineState?.telemetry_summary && <span className="text-[#00bceb]">📡 Telemetry OK</span>}
                  {pipelineState?.has_memory_context && <span className="text-purple-600">🧠 Recall Active</span>}
                  {pipelineState?.completeness_score != null && (
                    <span className={pipelineState.completeness_score >= 0.8 ? 'text-green-600' : 'text-amber-600'}>
                      ✓ QA: {Math.round((pipelineState.completeness_score || 1) * 100)}%
                    </span>
                  )}
                </div>
              </div>

            </motion.div>
          )}
        </AnimatePresence>

      </div>

    </div>
  );
}
