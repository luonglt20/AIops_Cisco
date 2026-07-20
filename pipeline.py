"""
MerakiMind — Pipeline Orchestrator v3
LangGraph-style multi-agent pipeline with:
- Real Telemetry Enrichment
- Full ReAct tool loops
- ChromaDB Semantic Memory
- SQLite Trend & Anomaly Detection
"""
import threading
from datetime import datetime, timezone, timedelta

from api import meraki
from api import telemetry as telemetry_collector
from api import memory as semantic_memory
from api import trend_db
from agents import device_intel, event_log, client_agent, uplink_agent, prompt_agent, coordinator, verify_agent, correlation_agent, reporting_agent, consensus_agent
from agents import rf_wireless_agent, switch_port_agent, wan_sdwan_agent, sensor_iot_agent, security_airmarshal_agent, client_experience_agent, firmware_crash_agent, audit_config_agent, app_qoe_agent


# ─── ORG DATA FETCHER ─────────────────────────────────────────────────────────

def _fetch_org_summary(org: dict, timespan: int = 604800) -> dict:
    cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=timespan)
    is_now_mode = timespan <= 3600  # Now mode (1 hour real-time active alarms)
    org_id = org["id"]
    result = {
        "id": org_id,
        "name": org["name"],
        "networks": [],
        "devices": {
            "online": 0, "offline": 0,
            "alerting": 0, "dormant": 0,
            "list": [],
        },
        "total_clients": 0,
        "alerts": [],
    }

    networks = meraki.get_networks(org_id)
    network_by_id = {n["id"]: n["name"] for n in networks}
    result["networks"] = [
        {"id": n["id"], "name": n["name"], "types": n.get("productTypes", [])}
        for n in networks
    ]

    # 1. Fetch Device Statuses & Build Device Lookup Tables
    devices = meraki.get_device_statuses(org_id)
    device_by_serial = {}
    device_by_net    = {}

    for d in devices:
        status = d.get("status", "unknown")
        result["devices"][status] = result["devices"].get(status, 0) + 1
        dev_serial = d.get("serial", "")
        dev_name   = d.get("name", "")
        net_id     = d.get("networkId", "")

        dev_dict = {
            "name":           dev_name,
            "model":          d.get("model", ""),
            "status":         status,
            "networkId":      net_id,
            "serial":         dev_serial,
            "publicIp":       d.get("publicIp", ""),
            "lastReportedAt": d.get("lastReportedAt", ""),
            "productType":    d.get("productType", ""),
            "mac":            d.get("mac", ""),
            "lanIp":          d.get("lanIp", ""),
            "gateway":        d.get("gateway", ""),
        }
        result["devices"]["list"].append(dev_dict)
        if dev_serial:
            device_by_serial[dev_serial] = dev_dict
        if net_id:
            device_by_net.setdefault(net_id, []).append(dev_dict)

    # Deduplication map to prevent duplicate / missing alerts
    alert_map = {}

    # 2. Fetch rich Assurance Alerts from Meraki API (per_page=100, timespan=timespan) & Enrich Metadata
    assurance_alerts = meraki.get_assurance_alerts(org_id, per_page=100, timespan=timespan)
    for a in assurance_alerts:
        last_seen_str = a.get("startedAt") or a.get("lastSeen") or ""
        serial   = a.get("deviceSerial") or a.get("serial", "")
        device   = a.get("deviceName") or a.get("device", "")
        model    = a.get("deviceType") or a.get("model", "")
        issue    = a.get("type") or a.get("alertType") or a.get("issue") or "Unknown Issue"
        net_id   = a.get("networkId") or (a.get("network", {}).get("id") if isinstance(a.get("network"), dict) else "")
        severity = (a.get("severity") or "HIGH").upper()
        if severity == "HIGH":
            severity = "CRITICAL"

        # 🟢 100% MERAKI GROUND TRUTH DEVICE & NETWORK RESOLVER
        if serial and serial in device_by_serial:
            dev_match = device_by_serial[serial]
            device = dev_match.get("name") or device
            model  = dev_match.get("model") or model
            net_id = dev_match.get("networkId") or net_id

        net_name = network_by_id.get(net_id, "")
        if not device:
            if net_name:
                device = f"Network: {net_name}"
            elif net_id:
                device = f"Network Scope ({net_id[:8]})"
            else:
                device = f"Org Alert ({org['name']})"

        is_resolved = True if a.get("resolvedAt") else False
        if is_resolved:
            if is_now_mode:
                continue  # Skip resolved alerts completely in "Now" mode (timespan <= 3600)
            res_at_str = a.get("resolvedAt")
            try:
                res_at = datetime.fromisoformat(res_at_str.replace("Z", "+00:00"))
                if res_at < cutoff_time:
                    continue
            except Exception:
                pass
        
        alert_id = a.get("id") or a.get("alertId")
        key = f"{alert_id or serial or device or net_id}:{issue}"
        alert_map[key] = {
            "severity":  severity,
            "device":    device,
            "model":     model,
            "serial":    serial,
            "issue":     issue,
            "networkId": net_id,
            "lastSeen":  last_seen_str,
            "resolved":  is_resolved,
        }

    # 3. Consolidate alerting, offline, and dormant device statuses into alerts queue
    for d in result["devices"]["list"]:
        status     = d.get("status", "")
        dev_serial = d.get("serial", "")
        dev_name   = d.get("name", "") or dev_serial
        
        if status in ("alerting", "offline", "dormant"):
            has_existing = any(k.startswith(f"{dev_serial}:") or k.startswith(f"{dev_name}:") for k in alert_map if dev_serial or dev_name)
            if not has_existing:
                issue_title = "unreachable" if status in ("alerting", "offline") else f"Device is {status}"
                key = f"{dev_serial or dev_name}:{issue_title}"
                sev = "CRITICAL" if status in ("alerting", "offline") else "WARNING"
                alert_map[key] = {
                    "severity":  sev,
                    "device":    dev_name,
                    "model":     d.get("model", ""),
                    "serial":    dev_serial,
                    "networkId": d.get("networkId", ""),
                    "issue":     issue_title,
                    "lastSeen":  d.get("lastReportedAt", ""),
                    "resolved":  False,
                }

    # 4. Consolidate historical network event anomalies based on timespan (24h, 7d, 30d)
    for net in networks:
        net_id   = net["id"]
        net_name = net["name"]
        product_types = net.get("types", [])
        pt = product_types[0] if product_types else "wireless"
        events   = meraki.get_network_events(net_id, per_page=20, timespan=timespan, product_type=pt)
        
        for ev in events:
            ev_type  = ev.get("type", "")
            ev_desc  = ev.get("description") or ev_type
            ev_time  = ev.get("occurredAt") or ev.get("timestamp", "")
            dev_name = ev.get("deviceName") or f"Network: {net_name}"
            
            # Filter anomaly event keywords
            anomaly_keywords = ("fail", "error", "down", "disconnect", "flap", "rogue", "nak", "unreachable", "loss", "degraded", "denied")
            if any(kw in ev_type.lower() or kw in ev_desc.lower() for kw in anomaly_keywords):
                key = f"{dev_name}:{ev_type}"
                if key not in alert_map:
                    is_crit = any(kw in ev_type.lower() or kw in ev_desc.lower() for kw in ("unreachable", "offline", "down", "fail"))
                    alert_map[key] = {
                        "severity":  "CRITICAL" if is_crit else "WARNING",
                        "device":    dev_name,
                        "model":     ev.get("deviceModel", ""),
                        "serial":    ev.get("deviceSerial", ""),
                        "networkId": net_id,
                        "issue":     f"Event: {ev_desc[:60]}",
                        "lastSeen":  ev_time,
                        "resolved":  False,
                    }

    # 5. Fetch Network Alerts History (Down/Up events)
    for net in networks:
        net_id = net["id"]
        history = meraki.get_network_alerts_history(net_id, per_page=100)
        
        dev_history = {}
        for h in history:
            dev_serial = h.get("device", {}).get("serial", "")
            if dev_serial:
                dev_history.setdefault(dev_serial, []).append(h)
        
        for dev_serial, evts in dev_history.items():
            pending_resolution = None
            for h in evts:
                alert_type_id = h.get("alertTypeId", "")
                alert_type = h.get("alertType", "")
                occurred_at = h.get("occurredAt", "")
                dev_name = h.get("device", {}).get("name", "") or dev_serial
                dev_model = h.get("device", {}).get("model", "")
                
                is_up = "came up" in alert_type.lower() or "started" in alert_type_id or "up" in alert_type_id.split("_")
                is_down = "went down" in alert_type.lower() or "stopped" in alert_type_id or "down" in alert_type_id.split("_")
                
                if is_up:
                    pending_resolution = occurred_at
                elif is_down:
                    if pending_resolution:
                        if is_now_mode:
                            pending_resolution = None
                            continue  # Skip resolved historical alert pairing in "Now" mode
                        try:
                            res_dt = datetime.fromisoformat(pending_resolution.replace("Z", "+00:00"))
                            if res_dt < cutoff_time:
                                pending_resolution = None
                                continue
                        except Exception:
                            pass
                            
                    if alert_type_id == "stopped_reporting":
                        issue_text = "Unreachable device"
                    elif "uplink" in alert_type_id or "uplink" in alert_type.lower() or "internet" in alert_type.lower():
                        issue_text = "Internet / Uplink Down"
                    else:
                        issue_text = alert_type

                    key = f"{dev_serial}:{alert_type_id}:{occurred_at}"
                    alert_map[key] = {
                        "severity":  "CRITICAL" if not pending_resolution else "RESOLVED",
                        "device":    dev_name,
                        "model":     dev_model,
                        "serial":    dev_serial,
                        "networkId": net_id,
                        "issue":     issue_text,
                        "lastSeen":  occurred_at,
                        "resolved":  True if pending_resolution else False,
                    }
                    pending_resolution = None
                else:
                    try:
                        occ_dt = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
                        if occ_dt < cutoff_time:
                            continue
                    except Exception:
                        pass
                        
                    key = f"{dev_serial}:{alert_type_id}:{occurred_at}"
                    alert_map[key] = {
                        "severity":  "MEDIUM",
                        "device":    dev_name,
                        "model":     dev_model,
                        "serial":    dev_serial,
                        "networkId": net_id,
                        "issue":     alert_type,
                        "lastSeen":  occurred_at,
                        "resolved":  False,
                    }

    # Client count (iterate over all networks)
    total_clients = 0
    for net in networks:
        clients = meraki.get_network_clients(net["id"], timespan=3600)
        total_clients += len(clients)
    result["total_clients"] = total_clients

    result["alerts"] = list(alert_map.values())
    return result


import time

_CACHE_LOCK = threading.Lock()
_ORG_DATA_CACHE = None
_LAST_FETCH_TIME = 0.0
_IS_REFRESHING = False

def fetch_all_orgs(force_refresh: bool = False, timespan: int = 604800) -> list:
    """
    Fetch all organizations in parallel with memory cache and background updates.
    Returns cached data instantly (0ms latency) if available, refreshing it asynchronously in the background.
    """
    global _ORG_DATA_CACHE, _LAST_FETCH_TIME, _IS_REFRESHING
    
    current_time = time.time()
    cache_duration = 30.0  # 30 seconds cache lifetime
    
    with _CACHE_LOCK:
        # Synchronous fetch required only on initial server boot
        if _ORG_DATA_CACHE is None:
            print("[Cache] Initial boot fetch starting...")
            _ORG_DATA_CACHE = _perform_parallel_fetch(timespan=timespan)
            _LAST_FETCH_TIME = current_time
            return _ORG_DATA_CACHE

        # Block and refresh if explicitly forced (e.g. user changes timespan filter)
        if force_refresh:
            print(f"[Cache] Forced refresh requested (timespan={timespan}). Blocking to fetch...")
            _ORG_DATA_CACHE = _perform_parallel_fetch(timespan=timespan)
            _LAST_FETCH_TIME = current_time
            return _ORG_DATA_CACHE

        # Return cached data immediately if fresh enough
        cache_age = current_time - _LAST_FETCH_TIME
        if cache_age < cache_duration:
            return _ORG_DATA_CACHE

    # Trigger background refresh if stale or forced
    if not _IS_REFRESHING:
        _IS_REFRESHING = True
        print(f"[Cache] Cache stale (age: {cache_age:.1f}s) — launching background refresh...")
        t = threading.Thread(target=_background_fetch_worker, args=(timespan,))
        t.daemon = True
        t.start()

    return _ORG_DATA_CACHE or []


def _background_fetch_worker(timespan: int = 604800):
    global _ORG_DATA_CACHE, _LAST_FETCH_TIME, _IS_REFRESHING
    try:
        data = _perform_parallel_fetch(timespan=timespan)
        with _CACHE_LOCK:
            _ORG_DATA_CACHE = data
            _LAST_FETCH_TIME = time.time()
        print("[Cache] Background refresh completed successfully.")
    except Exception as e:
        print(f"[Cache] Background refresh error: {e}")
    finally:
        _IS_REFRESHING = False

def _perform_parallel_fetch(timespan: int = 604800) -> list:
    orgs = meraki.get_organizations()
    results = [None] * len(orgs)
    threads = []

    def _fetch(i, org):
        results[i] = _fetch_org_summary(org, timespan=timespan)

    for i, org in enumerate(orgs):
        t = threading.Thread(target=_fetch, args=(i, org))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=30)

    return [r for r in results if r is not None]



# ─── ANALYZE PIPELINE ─────────────────────────────────────────────────────────

def run_analyze_pipeline(alert_data: dict, org_data: dict, model_mode: str = None) -> dict:
    """
    Execute the Multi-Agent diagnostics:
      - Phase 0: Run Coordinator Agent to dynamically configure routing path.
      - Phase 1: Concurrently fetch data ONLY for agents enabled by the Coordinator.
      - Phase 2: Run active expert agents sequentially in a Shared Blackboard State loop.
      - Phase 3 & 4: Run PromptAgent and VerifyAgent QC validation (supports dual-model/local benchmarks).
    """
    from api.llm import set_default_provider
    mode_init = model_mode or "groq"
    set_default_provider("groq" if mode_init == "dual" else mode_init)

    state = {
        "alert":           alert_data,
        "org":             org_data,
        "device_detail":   {},
        "events":          [],
        "clients":         [],
        "uplink":          {},
        "agent_notes":     [],
        "resolved_serial": "",
        "resolved_net_id": "",
        "final_prompt":    "",
        "blackboard":      {},
        "telemetry":       {},
        "model_mode":      model_mode or "groq",
        "prompt_groq":    "",
        "prompt_gemini":  "",
        "prompt_ollama":  "",
        "latency_groq":   0.0,
        "latency_gemini": 0.0,
        "latency_ollama": 0.0,
    }

    # Phase 0: Orchestrate diagnostic strategy using Coordinator Agent
    state = coordinator.run(state)
    route = state.get("route", {})
    
    # Step 1: Sequential in-memory resolution (Agent 1 - DeviceIntel resolution step)
    state = device_intel.run(state)
    serial = state["resolved_serial"]
    net_id = state["resolved_net_id"]
    
    lock = threading.Lock()
    threads_fetch = []

    # Task A: Fetch device detail from Meraki API (firmware, tags) - Always run for context
    def task_detail():
        if serial:
            detail = meraki.get_device_detail(serial)
            if detail:
                with lock:
                    state["device_detail"].update(detail)
                    if not state["resolved_net_id"] and detail.get("networkId"):
                        state["resolved_net_id"] = detail["networkId"]
                        print(f"  → resolved net_id from API: {detail['networkId']}")
    threads_fetch.append(threading.Thread(target=task_detail, name="Fetch-DeviceDetail"))

    # Task B: Fetch Event Logs (if enabled in route)
    if route.get("run_event_log", True):
        def task_events():
            temp_state = {
                "resolved_net_id": net_id,
                "resolved_serial": serial,
                "device_detail":   state["device_detail"],
                "events":          [],
            }
            event_log.run(temp_state)
            with lock:
                state["events"] = temp_state["events"]
        threads_fetch.append(threading.Thread(target=task_events, name="Fetch-Events"))

    # Task B: Fetch clients active (if enabled in route)
    if route.get("run_client_agent", True):
        def task_clients():
            temp_state = {
                "resolved_net_id": net_id,
                "resolved_serial": serial,
                "device_detail":   state["device_detail"],
                "clients":         [],
            }
            client_agent.run(temp_state)
            with lock:
                state["clients"] = temp_state["clients"]
        threads_fetch.append(threading.Thread(target=task_clients, name="Fetch-Clients"))

    # Task C: Fetch uplink status (if enabled in route)
    if route.get("run_uplink_agent", True):
        def task_uplinks():
            temp_state = {
                "org":             state["org"],
                "resolved_net_id": net_id,
                "resolved_serial": serial,
                "device_detail":   state["device_detail"],
                "uplink":          {},
            }
            uplink_agent.run(temp_state)
            with lock:
                state["uplink"] = temp_state["uplink"]
        threads_fetch.append(threading.Thread(target=task_uplinks, name="Fetch-Uplinks"))

    # Launch active data-fetching threads
    for t in threads_fetch:
        t.start()
    for t in threads_fetch:
        t.join(timeout=20)

    # ── Telemetry Enrichment (collect real metrics before LLM analysis) ──────
    print("[Pipeline] Collecting real-time telemetry snapshot...")
    try:
        state = telemetry_collector.collect(state)
    except Exception as e:
        print(f"[Pipeline] Telemetry collection error: {e}")
        state["telemetry"] = {}

    # ── Trend DB: Inject historical incident context into Blackboard ─────────
    if serial:
        trend_ctx = trend_db.build_trend_context(serial, window_hours=24)
        if trend_ctx:
            print(f"[Pipeline] Trend context injected: {trend_ctx[:80]}...")
            state["blackboard"]["trend_history"] = trend_ctx

    # ── Semantic Memory: Retrieve similar past incidents ─────────────────────
    dev_model = state.get("device_detail", {}).get("model", alert_data.get("model", ""))
    firmware  = state.get("device_detail", {}).get("firmware", "")
    alert_type = alert_data.get("issue", "Unknown")
    try:
        similar_cases = semantic_memory.retrieve_similar(
            alert_type=alert_type,
            device_model=dev_model,
            firmware=firmware,
            org_id=org_data.get("id", ""),
            top_k=3,
        )
        memory_ctx = semantic_memory.build_memory_context(similar_cases)
        if memory_ctx:
            print(f"[Pipeline] Memory context: {len(similar_cases)} similar incidents found.")
            state["blackboard"]["semantic_memory"] = memory_ctx
    except Exception as e:
        print(f"[Pipeline] Semantic memory error: {e}")

    # Phase 2: Parallel LLM analyses using Shared Blackboard context
    llm_threads = []
    
    # 1. DeviceIntel Agent
    def run_device_intel():
        if route.get("run_device_intel", True):
            print("[Pipeline] Running DeviceIntel Agent...")
            state["notes_device_intel"] = device_intel.analyze_with_llm(state)
        else:
            state["notes_device_intel"] = "[Agent Bỏ Qua] Theo định hướng điều phối của Coordinator."
    llm_threads.append(threading.Thread(target=run_device_intel))
    
    # 2. EventLog Agent
    def run_event_log():
        if route.get("run_event_log", True):
            print("[Pipeline] Running EventLog Agent...")
            state["notes_event_log"] = event_log.analyze_with_llm(state)
        else:
            state["notes_event_log"] = "[Agent Bỏ Qua] Không được kích hoạt."
    llm_threads.append(threading.Thread(target=run_event_log))
    
    # 3. Client Impact Agent
    def run_client_agent():
        if route.get("run_client_agent", True):
            print("[Pipeline] Running Client Impact Agent...")
            state["notes_client_agent"] = client_agent.analyze_with_llm(state)
        else:
            state["notes_client_agent"] = "[Agent Bỏ Qua] Không được kích hoạt."
    llm_threads.append(threading.Thread(target=run_client_agent))
    
    # 4. Uplink WAN Agent
    def run_uplink_agent():
        if route.get("run_uplink_agent", True):
            print("[Pipeline] Running Uplink WAN Agent...")
            state["notes_uplink_agent"] = uplink_agent.analyze_with_llm(state)
        else:
            state["notes_uplink_agent"] = "[Agent Bỏ Qua] Không được kích hoạt."
    llm_threads.append(threading.Thread(target=run_uplink_agent))

    # 5. Audit & Compliance Agent
    def run_audit_config():
        if route.get("run_audit_config", True):
            print("[Pipeline] Running Audit & Compliance Agent...")
            state["notes_audit_config"] = audit_config_agent.analyze_with_llm(state)
        else:
            state["notes_audit_config"] = "[Agent Bỏ Qua] Không được kích hoạt."
    llm_threads.append(threading.Thread(target=run_audit_config))

    # 6. Application QoE Agent
    def run_app_qoe():
        if route.get("run_app_qoe", True):
            print("[Pipeline] Running Application QoE Agent...")
            state["notes_app_qoe"] = app_qoe_agent.analyze_with_llm(state)
        else:
            state["notes_app_qoe"] = "[Agent Bỏ Qua] Không được kích hoạt."
    llm_threads.append(threading.Thread(target=run_app_qoe))

    # 5. Specialized Collector Dispatch
    assigned_agent = state.get("assigned_agent", "client_experience_agent")
    def run_specialized():
        print(f"[Pipeline] Running Specialized Collector: {assigned_agent}...")
        if assigned_agent == "security_airmarshal_agent":
            state["notes_security_airmarshal_agent"] = security_airmarshal_agent.analyze_with_llm(state)
        elif assigned_agent == "firmware_crash_agent":
            state["notes_firmware_crash_agent"] = firmware_crash_agent.analyze_with_llm(state)
        elif assigned_agent == "sensor_iot_agent":
            state["notes_sensor_iot_agent"] = sensor_iot_agent.analyze_with_llm(state)
        elif assigned_agent == "rf_wireless_agent":
            state["notes_rf_wireless_agent"] = rf_wireless_agent.analyze_with_llm(state)
        elif assigned_agent == "switch_port_agent":
            state["notes_switch_port_agent"] = switch_port_agent.analyze_with_llm(state)
        elif assigned_agent == "wan_sdwan_agent":
            state["notes_wan_sdwan_agent"] = wan_sdwan_agent.analyze_with_llm(state)
        else:
            state["notes_client_experience_agent"] = client_experience_agent.analyze_with_llm(state)
    llm_threads.append(threading.Thread(target=run_specialized))
    
    # Start and wait for all LLM agents
    for t in llm_threads:
        t.start()
    for t in llm_threads:
        t.join()

    # Phase 3 & 4: LangGraph Verification Cycle / Parallel Multi-Model Benchmarking
    mode = state.get("model_mode", "groq")

    if mode == "dual":
        print("[Pipeline] 📊 Running Dual/Triple-Model Benchmarking in parallel...")
        
        # We run synthesis & verification for each provider in dedicated threads to keep it extremely fast
        def run_benchmark_provider(prov_name: str, latency_key: str, prompt_key: str):
            from api.llm import set_default_provider
            set_default_provider(prov_name)
            t_start = time.time()
            st_temp = dict(state)
            st_temp["agent_notes"] = list(state["agent_notes"])
            # Run prompt agent
            st_temp = prompt_agent.run(st_temp, provider=prov_name)
            # Run verify agent
            st_temp = verify_agent.run(st_temp)
            
            with lock:
                state[prompt_key] = st_temp.get("final_prompt", "")
                state[latency_key] = round(time.time() - t_start, 2)
                print(f"[Benchmark] Completed {prov_name} in {state[latency_key]}s")

        threads_bench = [
            threading.Thread(target=run_benchmark_provider, args=("groq", "latency_groq", "prompt_groq"), name="Bench-Groq"),
            threading.Thread(target=run_benchmark_provider, args=("gemini", "latency_gemini", "prompt_gemini"), name="Bench-Gemini"),
            threading.Thread(target=run_benchmark_provider, args=("ollama", "latency_ollama", "prompt_ollama"), name="Bench-Ollama"),
        ]

        for t in threads_bench:
            t.start()
        for t in threads_bench:
            t.join(timeout=30)

        # Set default output prompt
        state["final_prompt"] = state["prompt_groq"] or state["prompt_gemini"] or state["prompt_ollama"] or "Không tạo được prompt."
        state["verification_passed"] = True  # Benchmarking modes default pass
        loop_count = 1

    else:
        # Single Provider execution
        t_start = time.time()
        loop_count = 0
        max_loops = 3
        prev_prompt = ""
        while loop_count < max_loops:
            loop_count += 1
            print(f"[Pipeline] Graph Cycle {loop_count} ({mode}): Generating prompt...")
            state = prompt_agent.run(state, provider=mode)
            
            # Check if prompt is identical to previous cycle to avoid redundant calls
            current_prompt = state.get("final_prompt", "")
            if current_prompt and current_prompt == prev_prompt:
                print(f"[Pipeline] Prompt is identical to cycle {loop_count-1}. Breaking loop early to save latency.")
                break
            prev_prompt = current_prompt

            state = verify_agent.run(state)
            missing = state.get("missing_agents", [])
            if missing and loop_count == 1:
                print(f"[Pipeline] 🔄 Callback Re-Trigger: VerifyAgent detected missing telemetry. Re-running sub-agents: {missing}...")
                if "audit_config" in missing:
                    try: run_audit_config()
                    except Exception: pass
                if "switch_port" in missing:
                    try: run_specialized()
                    except Exception: pass
                # Re-synthesize prompt after callback fetch
                state = prompt_agent.run(state, provider=mode)

            if state.get("verification_passed"):
                print(f"[Pipeline] VerifyAgent approved prompt quality on cycle {loop_count}.")
                break
            else:
                print(f"[Pipeline] VerifyAgent REJECTED prompt on cycle {loop_count}. Reason: {state.get('verification_feedback')}")

        latency = round(time.time() - t_start, 2)
        if mode == "groq":
            state["prompt_groq"] = state["final_prompt"]
            state["latency_groq"] = latency
        elif mode == "gemini":
            state["prompt_gemini"] = state["final_prompt"]
            state["latency_gemini"] = latency
        elif mode == "ollama":
            state["prompt_ollama"] = state["final_prompt"]
            state["latency_ollama"] = latency

    # Run Reporting Agent to generate simplified HR report
    print("[Pipeline] Running Reporting Agent...")
    try:
        state = reporting_agent.run(state)
    except Exception as e:
        print(f"[Pipeline] Error running Reporting Agent: {e}")
        state["notes_reporting"] = "Không thể tạo báo cáo nhân sự tại thời điểm này."

    # ── Trend DB: Record this incident ──────────────────────────────────────
    try:
        if serial:
            trend_db.record_incident(
                serial=serial,
                device_name=alert_data.get("device", ""),
                alert_type=alert_type,
                severity=alert_data.get("severity", "MEDIUM"),
                org_id=org_data.get("id", ""),
                net_id=net_id,
                model=dev_model,
                firmware=firmware,
            )
    except Exception as e:
        print(f"[Pipeline] Trend DB record error: {e}")

    # ── Semantic Memory: Save this incident ─────────────────────────────────
    try:
        diagnosis_summary = state.get("notes_device_intel", "") + " " + state.get("notes_correlation_agent", "")
        
        # Build a meaningful resolution string from extracted AI analysis
        extracted = state.get("extracted_analysis", {})
        root_causes = extracted.get("root_causes", [])
        actions = extracted.get("actions", [])
        
        if root_causes or actions:
            res_parts = []
            if root_causes:
                res_parts.append("Nguyên nhân: " + ", ".join([f"({c[0]}) {c[1]}" for c in root_causes[:2]]))
            if actions:
                res_parts.append("Giải pháp: " + ", ".join(actions[:2]))
            actual_resolution = " | ".join(res_parts)
        else:
            actual_resolution = state.get("notes_reporting", "")[:300]
            
        semantic_memory.save_incident(
            alert_type=alert_type,
            device_model=dev_model,
            firmware=firmware,
            diagnosis=diagnosis_summary[:400],
            resolution=actual_resolution,
            serial=serial,
            org_id=org_data.get("id", ""),
        )
    except Exception as e:
        print(f"[Pipeline] Semantic memory save error: {e}")

    # Format agent notes for frontend display
    state["agent_notes"] = [
        f"Coordinator Agent: {state.get('coordination_plan')}",
        f"DeviceIntel Agent: {state.get('notes_device_intel')}",
        f"EventLog Agent: {state.get('notes_event_log', '')}",
        f"Audit & Compliance Agent: {state.get('notes_audit_config', '')}",
        f"Application QoE Agent: {state.get('notes_app_qoe', '')}",
        f"Client Impact Agent: {state.get('notes_client_agent', '')}",
        f"Uplink WAN Agent: {state.get('notes_uplink_agent', '')}",
    ]
    
    # Append any specialized agent notes if present
    spec_agents = [
        ("Security & AirMarshal Agent", "notes_security_airmarshal_agent"),
        ("Firmware & Crash Agent", "notes_firmware_crash_agent"),
        ("Sensor IoT Agent", "notes_sensor_iot_agent"),
        ("RF Wireless Agent", "notes_rf_wireless_agent"),
        ("Switch Port Agent", "notes_switch_port_agent"),
        ("WAN SD-WAN Agent", "notes_wan_sdwan_agent"),
        ("Client Experience Agent", "notes_client_experience_agent"),
    ]
    for label, key in spec_agents:
        note = state.get(key)
        if note and "Bỏ Qua" not in note and note.strip():
            state["agent_notes"].append(f"{label}: {note}")
    
    if mode == "dual":
        state["agent_notes"].append("VerifyAgent (Quality Control): 📊 Đã đối soát chất lượng song song các mô hình.")
    elif not state.get("verification_passed"):
        state["agent_notes"].append("VerifyAgent (Quality Control): ⚠️ Prompt chưa đạt chất lượng tối đa nhưng đã được phục vụ.")
    else:
        state["agent_notes"].append(f"VerifyAgent (Quality Control): ✅ Đã phê duyệt sau {loop_count} chu kỳ kiểm định.")

    return state


def build_response(state: dict, generated_at: str) -> dict:
    return {
        "status":          "ok",
        "prompt":          state["final_prompt"],
        "prompt_groq":     state.get("prompt_groq", ""),
        "prompt_gemini":   state.get("prompt_gemini", ""),
        "prompt_ollama":   state.get("prompt_ollama", ""),
        "latency_groq":    state.get("latency_groq", 0.0),
        "latency_gemini":  state.get("latency_gemini", 0.0),
        "latency_ollama":  state.get("latency_ollama", 0.0),
        "model_mode":      state.get("model_mode", "groq"),
        "agent_notes":     state["agent_notes"],
        "summary_report":  state.get("notes_reporting", ""),
        "events_count":    len(state["events"]),
        "clients_count":   len(state["clients"]),
        "has_uplink":      bool(state["uplink"]),
        "report":          state.get("notes_reporting", ""),
        "generated_at":    generated_at,
        # v3 additions
        "completeness_score": state.get("completeness_score", 1.0),
        "telemetry_summary":  telemetry_collector.summarize(state),
        "trend_alert":        state.get("blackboard", {}).get("trend_history", ""),
        "has_memory_context": bool(state.get("blackboard", {}).get("semantic_memory", "")),
        # Decoupling & live diagnostics UI support
        "route":              state.get("route", {}),
        "device_detail":      state.get("device_detail", {}),
        "telemetry":          state.get("telemetry", {}),
        "assigned_agent":     state.get("assigned_agent", ""),
    }
