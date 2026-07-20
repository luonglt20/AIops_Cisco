"""
MerakiMind — Cisco Meraki Domain Knowledge Base v2.0
Nâng cấp:
  - Thêm 15+ model specs (MR, MS, MX, MG, MT series)
  - Failure cascade patterns — chuỗi lỗi phổ biến
  - Remediation steps chi tiết theo từng alert type
  - Firmware known issues cập nhật (MR34-35, MX21, MS18)
  - Diagnostic thresholds chuẩn theo Cisco best practice
"""

# ── Firmware Known Issues ─────────────────────────────────────────────────────
FIRMWARE_KNOWN_ISSUES = {
    # MR (Wireless AP)
    "wireless-28": "Firmware cũ (MR28.x) — bug RADIUS auth loop với WPA2-Enterprise. Upgrade lên MR29+ ngay.",
    "wireless-29": "Firmware MR29.x — đã fix RADIUS loop nhưng còn issue channel switching không ổn định ở 5GHz.",
    "wireless-30": "Firmware MR30.x — ổn định, tuy nhiên có bug memory leak sau 30+ ngày uptime liên tục không restart.",
    "wireless-31": "Firmware MR31.x — có issue DFS channel fallback gây AP reboot không mong muốn trên band 5GHz.",
    "wireless-32": "Firmware MR32.x — một số AP MR46/MR56 gặp bug 802.11ax beacon storm khi >150 clients.",
    "wireless-33": "Firmware MR33.x — latest stable cho dòng MR. Fixed 802.11ax beacon bug từ MR32.",
    "wireless-34": "Firmware MR34.x — beta/RC. Có cải tiến OFDMA scheduling nhưng cần thận trọng với production.",
    "wireless-35": "Firmware MR35.x — RC candidate. WiFi 6E support cải tiến cho MR57/MR78.",
    # MS (Switch)
    "switch-15":  "Firmware MS15.x — bug STP TCN storm trên port trunk. Upgrade lên MS16+ ngay.",
    "switch-16":  "Firmware MS16.x — ổn định, fix STP bug. Có issue LLDP neighbor không cập nhật đúng.",
    "switch-17":  "Firmware MS17.x — latest stable MS series. Hỗ trợ MLAG và tính năng advanced QoS.",
    "switch-18":  "Firmware MS18.x — RC. Cải tiến stacking bandwidth và 802.3bt PoE++ support.",
    # MX (Appliance/Security)
    "appliance-18": "Firmware MX18.x — bug IPSec renegotiation gây VPN drop 5-10 phút mỗi 8 giờ.",
    "appliance-19": "Firmware MX19.x — ổn định, fix VPN renegotiation. Kiểm tra IDS/IPS signature database.",
    "appliance-20": "Firmware MX20.x — latest stable. SD-WAN policy mới với performance-based routing.",
    "appliance-21": "Firmware MX21.x — RC. ZTNA (Zero Trust Network Access) integration và advanced threat intel.",
}


def get_firmware_note(firmware: str) -> str:
    """Get known issue note for a firmware version string."""
    if not firmware:
        return ""
    fw_lower = firmware.lower()
    for prefix, note in FIRMWARE_KNOWN_ISSUES.items():
        prefix_parts = prefix.split("-")
        if len(prefix_parts) == 2 and prefix_parts[0] in fw_lower:
            # Extract major version number
            for sep in ("wireless-", "switch-", "appliance-", "mr", "ms", "mx"):
                fw_lower_clean = fw_lower.replace(sep, "")
            major_ver = fw_lower_clean.split("-")[0].split(".")[0].strip()
            if major_ver == prefix_parts[1]:
                return f"⚠️ FIRMWARE NOTE: {note}"
    return ""


# ── Diagnostic Thresholds (Cisco Meraki Best Practice) ────────────────────────
THRESHOLDS = {
    # WAN Performance
    "wan_loss_critical":    5.0,    # % packet loss → critical (affects all traffic)
    "wan_loss_warning":     1.0,    # % packet loss → warning (VoIP/video affected)
    "wan_latency_critical": 200,    # ms → critical (VoIP MOS < 3.0)
    "wan_latency_high":     150,    # ms → high (VoIP affected)
    "wan_latency_warn":     50,     # ms → elevated
    "wan_jitter_max":       30,     # ms → max acceptable jitter for VoIP
    # RF / Wireless
    "channel_util_critical": 80,    # % channel utilization → severely congested
    "channel_util_high":     70,    # % → congested
    "channel_util_warn":     40,    # % → elevated
    "noise_floor_critical":  -75,   # dBm → very bad (channel unusable)
    "noise_floor_bad":       -85,   # dBm → bad noise floor
    "rssi_critical":         -80,   # dBm → very poor signal
    "rssi_poor":             -75,   # dBm → poor signal
    "rssi_fair":             -67,   # dBm → fair
    "rssi_good":             -60,   # dBm → good
    "snr_minimum":           20,    # dB → minimum acceptable SNR
    # Clients
    "client_offline_pct":    30,    # % clients offline → network-wide issue
    "client_roam_rate_high": 10,    # roams/hour per client → excessive roaming
    # Switch
    "port_error_rate":       0.01,  # % error frames → cable/SFP issue
    "poe_budget_warn":       80,    # % of PoE budget used → near exhaustion
}


# ── Alert Type Patterns + Full Remediation Steps ──────────────────────────────
ALERT_PATTERNS = {
    "device is alerting": {
        "causes": [
            "Firmware crash/instability (kiểm tra firmware version vs known bugs)",
            "PoE power supply không đủ từ upstream switch (<15.4W cho PoE, <30W cho PoE+)",
            "Overheating — AP cần thông gió (nhiệt độ >60°C gây throttle)",
            "Upstream switch port flapping (kiểm tra port error counters)",
            "RF channel congestion gây AP watchdog timeout",
            "Memory leak sau uptime dài (>30 ngày không restart)",
            "IP conflict hoặc DHCP starvation trên management VLAN",
        ],
        "api_checks": [
            "GET /devices/{serial}/lossAndLatencyHistory?ip=8.8.8.8&timespan=86400",
            "GET /devices/{serial}/wireless/radio/auto/byAccessPoint",
            "GET /networks/{netId}/wireless/connectionStats?timespan=3600",
            "GET /devices/{serial}/switch/ports/statuses (upstream switch)",
        ],
        "actions": [
            "POST /devices/{serial}/liveTools/ping — verify basic connectivity",
            "POST /devices/{serial}/liveTools/reboot — restart AP if stuck in crash loop",
            "POST /devices/upstream_serial/liveTools/cycleSwitchPorts — bounce PoE port",
        ],
        "remediation_steps": [
            "1. Kiểm tra đèn LED AP: Xanh lá = OK; Cam/Đỏ = lỗi phần cứng",
            "2. Xác minh upstream switch port: GET /devices/{switch_serial}/switch/ports/statuses — kiểm tra speed (phải là 1Gbps) và PoE power",
            "3. Nếu PoE power thấp (<25W cho MR46/MR44): upgrade switch port sang 802.3at hoặc chuyển sang switch có PoE+ budget",
            "4. Nếu port speed là 100Mbps thay vì 1Gbps: kiểm tra cáp vật lý (cat5e/cat6), bấm lại đầu RJ45",
            "5. Nếu firmware cũ: lên kế hoạch upgrade trong maintenance window",
            "6. Nếu uptime >30 ngày: schedule reboot định kỳ qua Meraki Dashboard",
        ],
    },

    "offline": {
        "causes": [
            "Physical disconnection — cáp mạng đứt hoặc port switch down",
            "PoE failure — upstream switch mất nguồn PoE cho port",
            "IP conflict — DHCP pool exhausted hoặc static IP conflict",
            "Firmware panic/crash — AP không boot được",
            "VLAN misconfiguration — management VLAN bị block",
            "Power outage tại site — mất điện cục bộ",
        ],
        "api_checks": [
            "GET /devices/{serial} — check status và lastSeen timestamp",
            "GET /networks/{netId}/events?productType=wireless&serials={serial}&timespan=3600",
            "GET /devices/upstream_serial/switch/ports/statuses",
            "GET /networks/{netId}/clients?timespan=3600 — check DHCP leases",
        ],
        "actions": [
            "POST /devices/upstream_serial/liveTools/cycleSwitchPorts — power cycle PoE port",
            "POST /devices/{serial}/liveTools/ping — verify reachability after power cycle",
            "Kiểm tra vật lý tại site: đèn LED, cáp, nguồn điện",
        ],
        "remediation_steps": [
            "1. Xác nhận lastSeen: nếu >1 giờ → khả năng mất điện hoặc mất cáp tại site",
            "2. Kiểm tra các AP khác trong cùng mạng: nếu tất cả offline → lỗi upstream (switch/power/ISP)",
            "3. Bounce PoE port trên upstream switch: POST /devices/{switch_serial}/liveTools/cycleSwitchPorts",
            "4. Nếu không lên sau power cycle: dispatch kỹ thuật viên đến site kiểm tra vật lý",
            "5. Kiểm tra DHCP pool: đảm bảo còn địa chỉ IP trống (tránh pool exhaustion)",
        ],
    },

    "unreachable": {
        "causes": [
            "Routing issue — default gateway không reachable",
            "ACL/Firewall rule blocking management traffic (TCP 443 ra Meraki cloud)",
            "VLAN trunk không đúng cấu hình — management VLAN bị pruned",
            "DNS failure — Meraki cloud FQDN không resolve được",
            "ISP blocking — port 443/UDP 7351 bị block",
        ],
        "api_checks": [
            "GET /devices/{serial}/lossAndLatencyHistory?ip=8.8.8.8&timespan=3600",
            "GET /networks/{netId}/appliance/vlans — check VLAN config",
            "GET /networks/{netId}/appliance/firewall/l3FirewallRules — check ACL",
        ],
        "actions": [
            "POST /devices/{serial}/liveTools/ping?target=8.8.8.8 — test internet reachability",
            "POST /devices/{serial}/liveTools/traceroute — trace path to Meraki cloud",
            "Kiểm tra firewall rules: đảm bảo TCP 443 và UDP 7351 được cho phép ra ngoài",
        ],
        "remediation_steps": [
            "1. Ping 8.8.8.8 từ device để xác nhận internet connectivity",
            "2. Traceroute đến dashboard.meraki.com — xác định điểm gãy trong path",
            "3. Kiểm tra management VLAN config: VLAN ID phải khớp trên switch trunk port",
            "4. Verify DNS: nslookup dashboard.meraki.com phải resolve được",
            "5. Kiểm tra firewall: allow TCP 443 outbound và UDP 7351 (AutoVPN)",
        ],
    },

    "low_power": {
        "causes": [
            "PoE budget exceeded trên upstream switch",
            "802.3af (PoE 15.4W) thay vì 802.3at (PoE+ 30W) — MR46/MR56 cần PoE+",
            "Switch port config sai PoE standard hoặc PoE disabled",
            "Cáp cat3/cat5 không đủ chuẩn dẫn điện cho PoE",
        ],
        "api_checks": [
            "GET /devices/{switch_serial}/switch/ports — check poeEnabled và powerUsageInWh",
            "GET /devices/{switch_serial}/switch/ports/statuses — xem actual power draw",
        ],
        "actions": [
            "Upgrade PoE budget: chuyển AP sang switch port có 802.3at support",
            "POST /devices/{switch_serial}/switch/ports/{portId} — force 802.3at standard",
            "Kiểm tra tổng PoE budget trên switch: đảm bảo không vượt quá rated capacity",
        ],
        "remediation_steps": [
            "1. Kiểm tra power budget: tổng wattage tất cả devices phải < 80% rated budget",
            "2. Xác nhận switch model hỗ trợ PoE+: MS225/MS350/MS355 mới có PoE+",
            "3. Thay cáp nếu cáp cũ (cat3/cat5 không đủ chuẩn cấp PoE 30W)",
            "4. Nếu PoE budget đầy: thêm switch PoE hoặc dùng injector PoE ngoài",
        ],
    },

    "insight_web_app": {
        "causes": [
            "ISP latency/packet loss trên WAN link đi quốc tế",
            "DNS resolution chậm (>100ms) làm trễ mọi request",
            "Application-level bottleneck — CDN server tắc hoặc origin slow",
            "QoS policy thiếu — traffic ứng dụng web không được ưu tiên",
            "SD-WAN failover chưa được cấu hình — không tự chuyển WAN khi suy hao",
        ],
        "api_checks": [
            "GET /organizations/{orgId}/insight/applications — app performance metrics",
            "GET /devices/{serial}/lossAndLatencyHistory?ip=8.8.8.8&timespan=3600",
            "GET /organizations/{orgId}/uplinks/statuses — all WAN uplink health",
            "GET /networks/{netId}/appliance/trafficShaping/uplinkSelection",
        ],
        "actions": [
            "Cấu hình SD-WAN Uplink Preference: ưu tiên WAN link tốt cho ứng dụng bị ảnh hưởng",
            "Kích hoạt QoS Class of Service: priority queue cho business-critical apps",
            "Cấu hình DNS Server sang 8.8.8.8/8.8.4.4 hoặc 1.1.1.1 để giảm DNS latency",
        ],
        "remediation_steps": [
            "1. Đo loss/latency WAN1 và WAN2 so sánh: GET /devices/{serial}/lossAndLatencyHistory",
            "2. Nếu WAN1 loss >2%: tạo Uplink Preference rule chuyển app sang WAN2",
            "3. Cấu hình Traffic Shaping: đặt application category priority = High",
            "4. Thử đổi DNS sang Cloudflare (1.1.1.1) — thường giảm latency 20-50ms",
            "5. Kiểm tra CDN origin: nếu server-side issue thì liên hệ ISP/vendor",
        ],
    },

    "uplink": {
        "causes": [
            "Physical WAN port degradation — cáp WAN bị lỗi hoặc đầu cắm lỏng",
            "ISP circuit issue — nhà mạng có sự cố đường truyền",
            "WAN1 failover failure — link WAN2 không tự activate khi WAN1 down",
            "BGP/routing issue với ISP (enterprise links)",
        ],
        "api_checks": [
            "GET /organizations/{orgId}/uplinks/statuses — real-time WAN status",
            "GET /devices/{serial}/lossAndLatencyHistory?ip=8.8.8.8&timespan=86400",
            "GET /networks/{netId}/appliance/uplinks/usage/byInterval",
        ],
        "actions": [
            "Verify WAN physical connections — kiểm tra đầu cáp và đèn WAN port",
            "Contact ISP với ticket — cung cấp loss/latency data làm bằng chứng",
            "Kích hoạt SD-WAN failover manual nếu WAN2 chưa tự activate",
        ],
        "remediation_steps": [
            "1. Kiểm tra đèn WAN port trên MX: phải sáng xanh (link up)",
            "2. So sánh loss/latency WAN1 vs WAN2: xác định link nào degraded",
            "3. Reboot WAN modem/CPE của ISP nếu được phép",
            "4. Gọi ISP hotline với SLA ticket — yêu cầu line test",
            "5. Nếu WAN2 có sẵn: force traffic sang WAN2 tạm thời",
        ],
    },
}


def get_alert_context(alert_type: str) -> dict:
    """Get full diagnostic context for an alert type."""
    alert_lower = (alert_type or "").lower()
    for pattern, context in ALERT_PATTERNS.items():
        if pattern in alert_lower:
            return context
    return {
        "causes": ["Kiểm tra device status và event logs để xác định nguyên nhân"],
        "api_checks": [
            "GET /devices/{serial} — check device status",
            "GET /networks/{netId}/events — review recent events",
        ],
        "actions": ["POST /devices/{serial}/liveTools/ping — verify connectivity"],
        "remediation_steps": [
            "1. Kiểm tra trạng thái thiết bị trong Meraki Dashboard",
            "2. Review event logs 24h gần nhất",
            "3. Ping test từ Dashboard để xác nhận reachability",
        ],
    }


# ── Failure Cascade Patterns ──────────────────────────────────────────────────
FAILURE_CASCADES = {
    "poe_starvation": {
        "name": "PoE Starvation Cascade",
        "trigger": "Switch PoE budget exceeded hoặc port config sai",
        "chain": [
            "Switch PoE port cấp không đủ wattage (ví dụ 13W thay vì 25.5W cho MR46)",
            "→ AP khởi động trong Low Power Mode: tắt 1 radio (thường 5GHz)",
            "→ AP watchdog detect thiếu resource → reboot liên tục mỗi 4-8 phút",
            "→ Clients bị ngắt kết nối theo chu kỳ — không thể roam sang AP khác",
            "→ User experience: WiFi 'chập chờn', không kết nối được lâu dài",
        ],
        "signature": "AP reboot theo chu kỳ đều đặn + port speed bình thường + chỉ 1 AP bị ảnh hưởng",
        "quick_fix": "Bounce PoE port + verify power class sau khi AP restart",
    },

    "upstream_switch_reboot": {
        "name": "Upstream Switch Reboot Cascade",
        "trigger": "Switch bị reboot (firmware upgrade, power fluctuation, STP reconvergence)",
        "chain": [
            "Upstream switch reboot hoặc mất nguồn (>5 giây)",
            "→ Tất cả AP kết nối vào switch mất PoE đồng loạt",
            "→ AP reboot → clients rớt WiFi hàng loạt trong 60-90 giây",
            "→ Switch recover → AP negotiate lại PoE → boot lên → clients reconnect",
            "→ Đột biến DHCP requests: nhiều clients xin IP cùng lúc → DHCP pool stress",
        ],
        "signature": "Nhiều AP cùng offline/online đúng 1 thời điểm + cùng network/switch",
        "quick_fix": "Kiểm tra switch event log để xác nhận thời điểm reboot",
    },

    "wan_failover_miss": {
        "name": "WAN Failover Miss Cascade",
        "trigger": "WAN1 down nhưng WAN2 không tự failover",
        "chain": [
            "WAN1 link down hoặc packet loss >5%",
            "→ SD-WAN health check fail (ping 8.8.8.8 timeout)",
            "→ MX detect WAN1 unhealthy → trigger failover sang WAN2",
            "→ Nếu WAN2 health check cũng fail: MX stuck trong failover loop",
            "→ Internet down hoàn toàn dù WAN2 vật lý vẫn connected",
            "→ Meraki cloud mất kết nối: tất cả management features offline",
        ],
        "signature": "MX alerting + WAN1 down + WAN2 không activate + mất internet",
        "quick_fix": "Check WAN2 health check IP config, verify WAN2 physical connection",
    },

    "dhcp_starvation": {
        "name": "DHCP Starvation Cascade",
        "trigger": "DHCP pool exhausted hoặc rogue DHCP server",
        "chain": [
            "DHCP pool hết địa chỉ IP hoặc có rogue DHCP server trên mạng",
            "→ Clients mới không nhận được IP (DHCP DISCOVER không được trả lời)",
            "→ Clients dùng APIPA (169.254.x.x) → không thể kết nối internet",
            "→ Clients cũ giữ lease cũ: vẫn có mạng tạm thời",
            "→ Sau khi lease expire: toàn bộ clients mất kết nối đồng loạt",
        ],
        "signature": "Clients có IP 169.254.x.x + event log có 'dhcp lease' errors + tăng đột biến client count",
        "quick_fix": "Mở rộng DHCP pool hoặc giảm lease time",
    },

    "rf_congestion": {
        "name": "RF Channel Congestion Cascade",
        "trigger": "Channel utilization cao + nhiều nguồn nhiễu RF",
        "chain": [
            "Channel utilization >70% (nhiều APs/clients trên cùng channel)",
            "→ CSMA/CA collision rate tăng → throughput giảm 40-60%",
            "→ Clients retry packets liên tục → latency tăng lên 200-500ms",
            "→ Video/VoIP quality drops: buffer overflow, jitter spike",
            "→ Weak clients (xa AP) chiếm nhiều airtime → 'hidden node' problem",
        ],
        "signature": "Channel util >70% + nhiều clients + throughput thấp dù RSSI OK",
        "quick_fix": "Bật Auto RF + giảm TX power + kích hoạt Band Steering sang 5GHz",
    },
}


def get_failure_cascade(cascade_type: str) -> dict:
    """Get failure cascade pattern by type."""
    return FAILURE_CASCADES.get(cascade_type, {})


def get_all_cascade_signatures() -> str:
    """Build a text summary of all cascade signatures for LLM injection."""
    lines = ["📖 FAILURE CASCADE PATTERNS (tham chiếu chẩn đoán):"]
    for key, cascade in FAILURE_CASCADES.items():
        lines.append(f"\n🔗 {cascade['name']}:")
        lines.append(f"   Trigger: {cascade['trigger']}")
        lines.append(f"   Signature: {cascade['signature']}")
        lines.append(f"   Quick Fix: {cascade['quick_fix']}")
    return "\n".join(lines)


# ── Model-Specific Knowledge ──────────────────────────────────────────────────
MODEL_SPECS = {
    # ── MR (Wireless Access Points) ───────────────────────────────────────────
    "MR28": {
        "type": "AP", "band": "Wi-Fi 5 (802.11ac Wave 1)", "max_clients": 100,
        "poe_required": "PoE (802.3af, 15.4W)", "antenna": "2x2 MU-MIMO",
        "notes": "Legacy AP — EOL nhưng vẫn được support. Cân nhắc upgrade lên MR36+."
    },
    "MR30H": {
        "type": "AP (Wall Plate)", "band": "Wi-Fi 5 (802.11ac)", "max_clients": 80,
        "poe_required": "PoE (802.3af, 15.4W)", "antenna": "2x2 MIMO",
        "notes": "Wall plate AP dành cho phòng khách sạn. Built-in wired ports."
    },
    "MR36": {
        "type": "AP", "band": "Wi-Fi 6 (802.11ax)", "max_clients": 200,
        "poe_required": "PoE (802.3af, 15.4W)", "antenna": "2x2 MU-MIMO",
        "notes": "Entry-level Wi-Fi 6 — dùng PoE thường. Phù hợp văn phòng nhỏ."
    },
    "MR44": {
        "type": "AP", "band": "Wi-Fi 6 (802.11ax)", "max_clients": 300,
        "poe_required": "PoE+ (802.3at, 25.5W)", "antenna": "4x4 MU-MIMO",
        "notes": "Mid-range Wi-Fi 6. CẦN PoE+ — switch PoE thường sẽ gây reboot."
    },
    "MR46": {
        "type": "AP", "band": "Wi-Fi 6 (802.11ax)", "max_clients": 400,
        "poe_required": "PoE+ (802.3at, 25.5W)", "antenna": "4x4 MU-MIMO",
        "notes": "High-density Wi-Fi 6. CẦN PoE+ bắt buộc — PoE thường (15.4W) sẽ gây throttle/reboot."
    },
    "MR46E": {
        "type": "AP (External Antenna)", "band": "Wi-Fi 6 (802.11ax)", "max_clients": 400,
        "poe_required": "PoE+ (802.3at, 25.5W)", "antenna": "4x4 MU-MIMO (External)",
        "notes": "Outdoor variant MR46 với anten ngoài. Dùng cho coverage rộng."
    },
    "MR56": {
        "type": "AP", "band": "Wi-Fi 6E (802.11ax 6GHz)", "max_clients": 500,
        "poe_required": "PoE++ (802.3bt, 90W)", "antenna": "8x8 MU-MIMO",
        "notes": "Flagship Wi-Fi 6E. CẦN PoE++ (802.3bt 90W) — chỉ MS355/MS410 cấp đủ nguồn."
    },
    "MR57": {
        "type": "AP", "band": "Wi-Fi 6E (802.11ax 6GHz)", "max_clients": 500,
        "poe_required": "PoE++ (802.3bt, 90W)", "antenna": "4x4 Tri-band MU-MIMO",
        "notes": "Tri-band Wi-Fi 6E với 6GHz support. Cần 802.3bt như MR56."
    },
    "MR76": {
        "type": "AP (Outdoor)", "band": "Wi-Fi 6 (802.11ax)", "max_clients": 200,
        "poe_required": "PoE+ (802.3at, 25.5W)", "antenna": "2x2 MU-MIMO Outdoor",
        "notes": "IP67 outdoor AP. Chịu mưa/bụi. Cần PoE+. Dùng cho outdoor coverage."
    },
    "MR86": {
        "type": "AP (Outdoor)", "band": "Wi-Fi 6 (802.11ax)", "max_clients": 400,
        "poe_required": "PoE+ (802.3at, 25.5W)", "antenna": "4x4 MU-MIMO Outdoor",
        "notes": "High-performance outdoor AP. IP67. Dùng cho stadium/plaza/parking."
    },

    # ── MS (Switches) ─────────────────────────────────────────────────────────
    "MS120": {
        "type": "Switch", "ports": 8, "poe_budget": "67W",
        "notes": "Entry-level switch, PoE thường 802.3af. Không hỗ trợ PoE+ đủ cho MR46/MR56."
    },
    "MS125": {
        "type": "Switch", "ports": 48, "poe_budget": "370W",
        "notes": "Mid-range switch, PoE thường. Budget 370W đủ cho ~24 APs PoE thường."
    },
    "MS210": {
        "type": "Switch", "ports": 24, "poe_budget": "370W",
        "notes": "Layer 2 access switch, PoE+ support (802.3at). Phù hợp cho MR44/MR46."
    },
    "MS225": {
        "type": "Switch", "ports": 48, "poe_budget": "740W",
        "notes": "PoE+ support. Budget 740W đủ cho ~24 APs MR46 cùng lúc."
    },
    "MS250": {
        "type": "Switch (L3)", "ports": 48, "poe_budget": "370W",
        "notes": "Layer 3 switch với routing capabilities. PoE+ support."
    },
    "MS350": {
        "type": "Switch (L3 Stackable)", "ports": 48, "poe_budget": "740W",
        "notes": "Stackable switch, PoE+. Hỗ trợ MLAG và advanced QoS."
    },
    "MS355": {
        "type": "Switch (L3 Stackable PoE++)", "ports": 48, "poe_budget": "1000W",
        "notes": "PoE++ (802.3bt) support — cần thiết để cấp nguồn MR56/MR57 (90W)."
    },
    "MS390": {
        "type": "Switch (Enterprise Core)", "ports": 48, "poe_budget": "1440W",
        "notes": "Enterprise core switch, PoE++ multi-gig. Hỗ trợ 10G uplinks."
    },
    "MS410": {
        "type": "Switch (Aggregation)", "ports": 16, "poe_budget": "1440W",
        "notes": "Aggregation switch với 10G/40G uplinks. PoE++ cho high-power APs."
    },

    # ── MX (Security Appliances) ──────────────────────────────────────────────
    "MX64": {
        "type": "MX Appliance", "wan_ports": 2, "max_vpn": 25, "throughput": "250 Mbps",
        "notes": "Entry-level MX. Phù hợp văn phòng <50 users. IDS/IPS available."
    },
    "MX67": {
        "type": "MX Appliance", "wan_ports": 2, "max_vpn": 50, "throughput": "450 Mbps",
        "notes": "Small branch. Built-in LTE modem option (MX67C/MX67W)."
    },
    "MX68": {
        "type": "MX Appliance", "wan_ports": 2, "max_vpn": 50, "throughput": "450 Mbps",
        "notes": "MX68W có built-in WiFi. MX68CW có cả WiFi + cellular."
    },
    "MX84": {
        "type": "MX Appliance", "wan_ports": 2, "max_vpn": 100, "throughput": "500 Mbps",
        "notes": "Mid-size branch. Rack-mountable. 1GbE x8 LAN ports."
    },
    "MX85": {
        "type": "MX Appliance", "wan_ports": 3, "max_vpn": 100, "throughput": "750 Mbps",
        "notes": "Upgraded MX84. 3 WAN ports cho multi-WAN SD-WAN."
    },
    "MX95": {
        "type": "MX Appliance", "wan_ports": 3, "max_vpn": 250, "throughput": "2 Gbps",
        "notes": "Large branch/campus. Advanced threat protection + SD-WAN."
    },
    "MX105": {
        "type": "MX Appliance", "wan_ports": 3, "max_vpn": 500, "throughput": "1.5 Gbps",
        "notes": "Enterprise branch. Multi-gig WAN support."
    },
    "MX250": {
        "type": "MX Appliance (Data Center)", "wan_ports": 4, "max_vpn": 1000, "throughput": "4 Gbps",
        "notes": "Data center / large enterprise. HA pair support."
    },
    "MX450": {
        "type": "MX Appliance (Data Center)", "wan_ports": 4, "max_vpn": 10000, "throughput": "10 Gbps",
        "notes": "Flagship MX. Large-scale deployments với advanced SD-WAN."
    },

    # ── MG (Cellular Gateways) ────────────────────────────────────────────────
    "MG21": {
        "type": "Cellular Gateway", "wan_ports": 1, "throughput": "150 Mbps",
        "notes": "4G LTE cellular gateway. Dùng làm WAN backup hoặc primary cho remote sites."
    },
    "MG41": {
        "type": "Cellular Gateway (5G)", "wan_ports": 1, "throughput": "1 Gbps",
        "notes": "5G Sub-6 cellular gateway. Kết hợp với MX cho SD-WAN với cellular failover."
    },

    # ── MT (Sensors) ──────────────────────────────────────────────────────────
    "MT10": {
        "type": "Environmental Sensor", "sensors": ["temperature", "humidity"],
        "notes": "Temperature/humidity sensor. Alert khi nhiệt độ server room bất thường."
    },
    "MT20": {
        "type": "Environmental Sensor", "sensors": ["temperature", "humidity", "water"],
        "notes": "Full environmental sensor với water leak detection."
    },
}


def get_model_specs(model: str) -> dict:
    """Get hardware specs for a device model (partial match supported)."""
    if not model:
        return {}
    model_upper = model.upper()
    # Exact match first
    if model_upper in MODEL_SPECS:
        return MODEL_SPECS[model_upper]
    # Partial match (e.g. "MR46E" matches "MR46")
    for key, specs in MODEL_SPECS.items():
        if key in model_upper or model_upper.startswith(key):
            return specs
    return {}


def get_poe_requirements_text(model: str) -> str:
    """Get human-readable PoE requirement text for injection into prompts."""
    spec = get_model_specs(model)
    if not spec or not spec.get("poe_required"):
        return ""
    req = spec["poe_required"]
    notes = spec.get("notes", "")
    return f"{model} yêu cầu {req}. {notes}"


# ── Org Context Builder ───────────────────────────────────────────────────────
def build_org_context(org: dict, device_serial: str, device_model: str) -> str:
    """
    Build rich org context with:
    - Device inventory breakdown (AP/Switch/MX count)
    - Other alerting devices (correlation signal)
    - Same-model health comparison
    - Failure cascade indicator
    """
    devices = org.get("devices", {}).get("list", [])
    alerts  = org.get("alerts", [])

    if not devices:
        return ""

    # Count by type
    aps      = [d for d in devices if d.get("model", "").startswith("MR")]
    switches = [d for d in devices if d.get("model", "").startswith("MS")]
    mxs      = [d for d in devices if d.get("model", "").startswith("MX")]
    online   = [d for d in devices if d.get("status") == "online"]
    offline  = [d for d in devices if d.get("status") == "offline"]

    # Other alerting devices (correlation check)
    other_alerts = [
        a for a in alerts
        if a.get("serial") != device_serial and a.get("device", "") != ""
    ]

    # Same model comparison
    same_model_healthy  = [
        d for d in devices
        if device_model and device_model in d.get("model", "")
        and d.get("serial") != device_serial
        and d.get("status") == "online"
    ]
    same_model_alerting = [
        d for d in devices
        if device_model and device_model in d.get("model", "")
        and d.get("serial") != device_serial
        and d.get("status") != "online"
    ]

    lines = [
        f"📊 ORG CONTEXT ({org.get('name','?')}):",
        f"  Tổng thiết bị: {len(devices)} ({len(aps)} AP | {len(switches)} Switch | {len(mxs)} MX)",
        f"  Đang online: {len(online)}/{len(devices)} ({round(len(online)/max(len(devices),1)*100)}%)",
    ]

    if offline:
        lines.append(f"  Đang offline: {len(offline)} thiết bị")

    if other_alerts:
        other_names = ", ".join([a.get("device", "?") for a in other_alerts[:4]])
        lines.append(f"  ⚠️ {len(other_alerts)} thiết bị khác đang alert: {other_names}")
        if len(other_alerts) >= 3:
            lines.append(
                f"  🔴 CẢNH BÁO: {len(other_alerts)} thiết bị cùng alert → "
                f"Dấu hiệu upstream failure (switch/power/ISP). "
                f"Xem xét failure cascade: 'upstream_switch_reboot' hoặc 'wan_failover_miss'."
            )
    else:
        lines.append(f"  ✅ Chỉ thiết bị này đang alert → khả năng isolated failure")

    if same_model_healthy:
        lines.append(
            f"  {len(same_model_healthy)} thiết bị {device_model} khác đang healthy → "
            f"Loại trừ firmware bug diện rộng"
        )
    if same_model_alerting:
        alert_names = ", ".join([d.get("name", "?") for d in same_model_alerting[:3]])
        lines.append(f"  ⚠️ {len(same_model_alerting)} thiết bị {device_model} khác cũng alert: {alert_names}")
        lines.append(f"  💡 Có thể firmware bug hoặc shared power source ảnh hưởng toàn dòng {device_model}")

    return "\n".join(lines)
