# 📡 DANH SÁCH & PHÂN BỔ SỬ DỤNG 80 CISCO MERAKI REST APIS TRONG MERAKIMIND

Tài liệu Kỹ thuật Kiến trúc Integration — MerakiMind AIOps Platform Enterprise 80 APIs

---

> [!NOTE]
> 📌 GHI CHÚ: Tài liệu này tổng hợp toàn bộ 80 Meraki Dashboard REST API Endpoints, Live Tools, Cisco Umbrella SIG Security & Self-Healing Tools được tích hợp trực tiếp trong MerakiMind. Tất cả endpoints được phân loại chi tiết theo HTTP Method, tên hàm SDK Python (api/meraki.py), và phân bổ cho 12 AI Agents chuyên biệt.

---

## 📋 I. BẢNG TỔNG QUAN PHÂN BỔ 80 MERAKI REST APIs & REMEDIATION TOOLS

| STT | HTTP Method & Endpoint Path | Tên Hàm Python (`api/meraki.py`) | Vị Trí & Thành Phần Sử Dụng | Mục Đích Kỹ Thuật |
|:---:|:---|:---|:---|:---|
| **1** | `GET /organizations` | `get_organizations()` | `pipeline.py (System Alert & Org Fetching)` | Danh sách tất cả Organizations mà API Key quản lý |
| **2** | `GET /organizations/{orgId}/networks` | `get_networks()` | `pipeline.py (Network Discovery & Scope)` | Danh sách các Mạng (Networks) thuộc từng Org |
| **3** | `GET /organizations/{orgId}/devices/statuses` | `get_device_statuses()` | `pipeline.py (Bảng 2 Inventory & Alerting Status)` | Trạng thái thời gian thực (Online, Offline, Alerting) |
| **4** | `GET /organizations/{orgId}/assurance/alerts` | `get_assurance_alerts()` | `pipeline.py (Bảng 1 Assurance Alerts Queue)` | Danh sách cảnh báo tổng quan cấp Org |
| **5** | `GET /networks/{netId}/alerts/history` | `get_network_alerts_history()` | `pipeline.py (Alerts History Down/Up Event Pairing)` | Lịch sử sự kiện cảnh báo chi tiết (Down/Up pairing) |
| **6** | `GET /networks/{netId}/clients` | `get_network_clients()` | `telemetry.py, client_agent.py` | Danh sách máy khách đang kết nối và tác động người dùng |
| **7** | `GET /networks/{netId}/events` | `get_network_events()` | `telemetry.py, event_log.py` | Nhật ký sự kiện nguyên bản (Auth, Deauth, AD Failures) |
| **8** | `GET /devices/{serial}` | `get_device_detail()` | `telemetry.py, device_intel.py` | Thông tin phần cứng chi tiết (Model, MAC, IP, Firmware) |
| **9** | `GET /organizations/{orgId}/appliances/uplink/statuses` | `get_appliance_uplinks()` | `telemetry.py, uplink_agent.py` | Trạng thái cổng WAN vật lý (WAN1/WAN2, Gateway) |
| **10** | `GET /organizations/{orgId}/devices/uplinks/lossAndLatency` | `get_uplink_loss_latency()` | `pipeline.py (Uplink Loss & Latency Graph)` | Đo chỉ số tổn thất gói (%) và độ trễ (ms) toàn hệ thống |
| **11** | `GET /devices/{serial}/lossAndLatencyHistory` | `get_device_loss_latency()` | `telemetry.py, wan_sdwan_agent.py` | Lịch sử 30 ngày độ trễ và rớt gói (Loss & Latency Spikes) |
| **12** | `GET /devices/{serial}/switch/ports/statuses` | `get_switch_port_statuses()` | `telemetry.py, switch_port_agent.py` | Trạng thái cổng Switch (Speed 1Gbps, Duplex, PoE Watts) |
| **13** | `GET /devices/{serial}/switch/ports/statuses/packets` | `get_device_switch_ports_statuses_packets()` | `telemetry.py, switch_port_agent.py` | Số liệu đếm gói tin nâng cao (CRC Errors, Discards) |
| **14** | `POST /devices/{serial}/liveTools/ping` | `run_ping_test()` | `uplink_agent.py, ReAct Loop` | Kích hoạt Live Tool Ping từ Meraki tới IP mục tiêu |
| **15** | `POST /devices/{serial}/liveTools/cableTest` | `get_cable_test()` | `switch_port_agent.py, ReAct Loop` | Kích hoạt Live Tool Cable Test kiểm tra đứt/hở cáp Ethernet |
| **16** | `POST /devices/{serial}/liveTools/throughput` | `run_throughput_test()` | `wan_sdwan_agent.py, ReAct Loop` | Đo kiểm băng thông thực tế (Speedtest Live Tool) qua WAN |
| **17** | `POST /devices/{serial}/liveTools/arpTable` | `get_arp_table()` | `switch_port_agent.py, ReAct Loop` | Đọc bảng ARP trên thiết bị để tra cứu IP - MAC |
| **18** | `POST /devices/{serial}/reboot` | `reboot_device()` | `Remediation Engine` | Khởi động lại thiết bị từ xa để tự khắc phục lỗi |
| **19** | `POST /devices/{serial}/switch/ports/cycle` | `cycle_switch_ports()` | `Remediation Engine` | Ngắt và cấp lại nguồn PoE trên cổng Switch để reset AP/Camera |
| **20** | `POST /devices/{serial}/blinkLeds` | `blink_device_leds()` | `api/meraki.py` | Nháy đèn LED thiết bị hỗ trợ định vị phần cứng |
| **21** | `GET /devices/{serial}/wireless/status` | `get_device_wireless_rf()` | `telemetry.py, rf_wireless_agent.py` | Thông số vô tuyến RF của Access Point (Noise Floor, Power) |
| **22** | `GET /networks/{netId}/wireless/channelUtilizationHistory` | `get_network_channel_utilization()` | `telemetry.py, rf_wireless_agent.py` | Tỷ lệ nghẽn kênh vô tuyến (% Channel Utilization 2.4/5GHz) |
| **23** | `GET /networks/{netId}/wireless/connectionStats` | `get_wireless_connection_stats()` | `telemetry.py, client_agent.py` | Thống kê tỷ lệ lỗi kết nối Wi-Fi (Assoc, Auth, DHCP, DNS) |
| **24** | `GET /networks/{netId}/wireless/clients/connectionStats` | `get_wireless_client_connection_stats()` | `telemetry.py, client_agent.py` | Thống kê trải nghiệm Wi-Fi chi tiết từng Client |
| **25** | `GET /networks/{netId}/wireless/airMarshal` | `get_network_air_marshal()` | `security_airmarshal_agent.py` | Quét bảo mật vô tuyến (Rogue AP, Packet Flooding) |
| **26** | `GET /networks/{netId}/firmwareUpgrades` | `get_network_firmware_upgrades()` | `firmware_crash_agent.py` | Lịch sử nâng cấp Firmware và lỗi tương thích phiên bản |
| **27** | `GET /organizations/{orgId}/sensor/readings/latest` | `get_sensor_readings()` | `sensor_iot_agent.py` | Chỉ số cảm biến IoT Meraki MT (Nhiệt độ, Độ ẩm, Cửa mở) |
| **28** | `GET /networks/{netId}/insight/applications/health` | `get_network_insight_application_health()` | `app_qoe_agent.py, wan_sdwan_agent.py` | Đo chỉ số trải nghiệm ứng dụng Web (Insight Web App Health) |
| **29** | `GET /networks/{netId}/appliance/vpn/statuses` | `get_network_vpn_status()` | `wan_sdwan_agent.py` | Trạng thái đường hầm Auto-VPN (Site-to-Site Mesh) |
| **30** | `GET /networks/{netId}/appliance/traffic` | `get_network_l7_firewall_rules()` | `wan_sdwan_agent.py` | Phân tích lưu lượng Layer 7 và luật tường lửa |
| **31** | `GET /networks/{netId}/switch/stacks` | `get_network_switch_stacks()` | `switch_port_agent.py` | Trạng thái cụm Switch Stack (Stack members, links) |
| **32** | `GET /networks/{netId}/switch/stp` | `get_network_switch_stp()` | `switch_port_agent.py` | Sự cố Spanning Tree Protocol (STP Loops, Root Bridge) |
| **33** | `GET /networks/{netId}/topology/linkLayer` | `get_network_topology()` | `pipeline.py (Layer 2 Topology Map)` | Sơ đồ liên kết Layer 2 (Topology link layer) |
| **34** | `GET /devices/{serial}/lldpCdp` | `get_device_lldp_cdp()` | `switch_port_agent.py` | Thông tin thiết bị láng giềng qua giao thức LLDP / CDP |
| **35** | `GET /organizations/{orgId}/configurationChanges` | `get_org_config_changes()` | `audit_config_agent.py` | Audit Log truy vết thay đổi cấu hình con người |
| **36** | `GET /networks/{netId}/appliance/performance` | `get_appliance_performance()` | `wan_sdwan_agent.py` | Tải CPU / Memory / Utilization score của MX Gateway |
| **37** | `GET /networks/{netId}/appliance/security/events` | `get_appliance_security_events()` | `wan_sdwan_agent.py` | Nhật ký an ninh mạng Snort IDS/IPS & AMP Malware |
| **38** | `GET /networks/{netId}/wireless/failedConnections` | `get_wireless_failed_connections()` | `rf_wireless_agent.py` | Lý do rớt Wi-Fi (Radius, PSK, Auth, DHCP failure rates) |
| **39** | `GET /organizations/{orgId}/insight/monitoredMediaServers` | `get_insight_monitored_media_servers()` | `app_qoe_agent.py` | Chỉ số trải nghiệm cuộc gọi VoIP (Webex, Zoom, Teams MOS) |
| **40** | `GET /networks/{netId}/switch/dhcp/server/policy` | `get_switch_dhcp_server_policy()` | `switch_port_agent.py` | Phát hiện Rogue DHCP Server cắm trái phép |
| **41** | `GET /devices/{serial}/switch/routing/interfaces` | `get_switch_routing_interfaces()` | `switch_port_agent.py` | Giao diện định tuyến Layer 3 (L3 SVI) & OSPF status |
| **42** | `POST /devices/{serial}/liveTools/traceroute` | `run_traceroute_test()` | `wan_sdwan_agent.py` | Traceroute từng chặng tới IP mục tiêu |
| **43** | `POST /devices/{serial}/liveTools/dnsLookup` | `run_dns_lookup()` | `audit_config_agent.py` | Phân giải tên miền DNS trực tiếp từ Meraki |
| **44** | `POST /devices/{serial}/liveTools/packetCaptures` | `start_packet_capture()` | `switch_port_agent.py` | Bắt gói tin raw PCAP thời gian thực trên interface |
| **45** | `POST /networks/{netId}/liveTools/wakeOnLan` | `send_wake_on_lan()` | `client_agent.py` | Gửi Magic Packet Wake-on-LAN bật PC từ xa |
| **46** | `GET /networks/{netId}/appliance/security/intrusion` | `get_security_intrusion()` | `wan_sdwan_agent.py` | Cấu hình & luật an ninh Cisco Snort IDS/IPS |
| **47** | `GET /networks/{netId}/appliance/security/malware/settings` | `get_amp_malware_settings()` | `wan_sdwan_agent.py` | Trạng thái chống mã độc Cisco AMP Sandboxing |
| **48** | `GET /organizations/{orgId}/licenses/overview` | `get_org_licenses_overview()` | `audit_config_agent.py` | Giám sát hạn dùng & quota Meraki License |
| **49** | `GET /networks/{netId}/appliance/vlans` | `get_network_vlans()` | `switch_port_agent.py` | Subnet VLAN list, Gateway IPs, DHCP helper |
| **50** | `GET /networks/{netId}/switch/dhcpServerPolicy/arpInspection/trustedServers` | `get_dai_trusted_servers()` | `switch_port_agent.py` | Dynamic ARP Inspection (DAI) chống ARP Spoofing |
| **51** | `GET /devices/{serial}/switch/ports/status/historical` | `get_switch_port_history()` | `switch_port_agent.py` | Lịch sử Link Flapping cổng Switch (Up/Down) |
| **52** | `GET /networks/{netId}/wireless/ssids` | `get_network_ssids()` | `rf_wireless_agent.py` | Chi tiết cấu hình SSID (WPA3, 802.1X, Band Steering) |
| **53** | `GET /networks/{netId}/wireless/rfProfiles` | `get_wireless_rf_profiles()` | `rf_wireless_agent.py` | RF Profile (Tx Power, Min Bitrate, Band Steering) |
| **54** | `GET /networks/{netId}/wireless/bluetooth/settings` | `get_ble_settings()` | `sensor_iot_agent.py` | Bluetooth Low Energy (BLE) beaconing & tracking |
| **55** | `GET /networks/{netId}/insight/applications/{appId}/health` | `get_app_specific_health()` | `app_qoe_agent.py` | Điểm trải nghiệm từng ứng dụng SaaS (O365, SAP) |
| **56** | `GET /organizations/{orgId}/insight/monitoredMediaServers/stats` | `get_voip_jitter_stats()` | `app_qoe_agent.py` | Bóc tách chỉ số Jitter & Packet Reordering VoIP |
| **57** | `GET /organizations/{orgId}/insight/monitoredMediaServers/performance` | `get_thousandeyes_media_perf()` | `wan_sdwan_agent.py` | Cisco ThousandEyes BGP path & ISP loss |
| **58** | `POST /devices/{serial}/liveTools/mTR` | `run_multi_target_mtr()` | `wan_sdwan_agent.py` | MTR Multi-target My TraceRoute tới 5 Data Centers |
| **59** | `POST /devices/{serial}/switch/ports/{portId}/clearCounters` | `clear_switch_port_counters()` | `switch_port_agent.py` | Automated Clear CRC & Error Counters |
| **60** | `POST /networks/{netId}/wireless/ssids/{number}/reboot` | `reboot_individual_ssid()` | `rf_wireless_agent.py` | Reset module phát sóng Wi-Fi SSID riêng biệt |
| **61** | `POST /networks/{netId}/clients/{mac}/policy` | `quarantine_malicious_client()` | `security_airmarshal_agent.py` | Cô lập Client bị nhiễm Malware (Quarantine) |
| **62** | `GET /networks/{netId}/groupPolicies` | `get_network_group_policies()` | `audit_config_agent.py` | Group Policies list & Bandwidth QoS priority |
| **63** | `GET /networks/{netId}/appliance/contentFiltering` | `get_content_filtering_rules()` | `security_airmarshal_agent.py` | Luật lọc trang web độc hại Content Filtering |
| **64** | `GET /organizations/{orgId}/sensor/readings/history` | `get_sensor_reading_history()` | `sensor_iot_agent.py` | Lịch sử 7 ngày cảm biến Temp/Humidity phòng Server |
| **65** | `GET /networks/{netId}/camera/analytics/zones` | `get_camera_heatmap_zones()` | `sensor_iot_agent.py` | Camera MV Analytics Occupancy & Heatmap zones |
| **66** | `GET /organizations/{orgId}/summary/top/clients/byUsage` | `get_top_bandwidth_hogs()` | `client_agent.py` | TOP 5 máy khách ngốn băng thông cao nhất (Hogs) |
| **67** | `GET /organizations/{orgId}/summary/top/devices/byEnergy` | `get_top_devices_by_energy()` | `device_intel.py` | Energy AIOps / Mức tiêu thụ điện năng kWh |
| **68** | `GET /networks/{netId}/wireless/rfProfiles/status` | `get_cochannel_interference()` | `rf_wireless_agent.py` | Chỉ số nhiễu đồng kênh Wi-Fi Co-channel Interference % |
| **69** | `GET /networks/{netId}/appliance/ports` | `get_appliance_ports_config()` | `wan_sdwan_agent.py` | Cấu hình cổng LAN/WAN router MX & VLAN tagging |
| **70** | `POST /devices/{serial}/liveTools/cableTest/history` | `get_cable_test_history()` | `switch_port_agent.py` | Lịch sử suy hao tín hiệu & TDR Cable Faults |
| **71** | `GET /networks/{netId}/appliance/dns/customRecurser` | `get_custom_dns_recurser()` | `audit_config_agent.py` | [NEW 80] Cisco Umbrella SIG Custom DNS Recurser |
| **72** | `GET /organizations/{orgId}/brandingPolicies` | `get_org_branding_policies()` | `audit_config_agent.py` | [NEW 80] Captive Portal Branding Policies & Logos |
| **73** | `GET /networks/{netId}/appliance/sdwan/trafficShaping/rules` | `get_sdwan_traffic_shaping()` | `wan_sdwan_agent.py` | [NEW 80] SD-WAN Traffic Shaping Rules & App QoS |
| **74** | `GET /organizations/{orgId}/appliance/vpn/thirdPartyVPNPeers` | `get_third_party_vpn_peers()` | `wan_sdwan_agent.py` | [NEW 80] Multi-Cloud AWS/Azure IPsec VPN Tunnels |
| **75** | `GET /networks/{netId}/wireless/rfProfiles/assignments` | `get_rf_profile_assignments()` | `rf_wireless_agent.py` | [NEW 80] Wi-Fi 6E / Wi-Fi 7 Tri-Band 6GHz Spectrum |
| **76** | `GET /networks/{netId}/wireless/mesh/statuses` | `get_wireless_mesh_statuses()` | `rf_wireless_agent.py` | [NEW 80] Wireless Mesh Link Quality & Signal RSSI |
| **77** | `GET /devices/{serial}/switch/routing/staticRoutes` | `get_switch_static_routes()` | `switch_port_agent.py` | [NEW 80] Layer 3 Switch Static Routing Table |
| **78** | `POST /devices/{serial}/switch/ports/{portId}/powerOverEthernet` | `set_switch_port_poe()` | `switch_port_agent.py` | [NEW 80] Scheduled PoE Power On/Off per Switch Port |
| **79** | `GET /networks/{netId}/webhooks/httpServers` | `get_webhook_http_servers()` | `event_log.py` | [NEW 80] Real-time Webhooks (Telegram/Slack/ServiceNow) |
| **80** | `GET /organizations/{orgId}/webhooks/logs` | `get_webhook_delivery_logs()` | `event_log.py` | [NEW 80] Webhook Real-time Incident Delivery Logs |

---

## 🎯 II. CHI TIẾT PHÂN BỔ 80 APIS THEO SYSTEM PIPELINE & 12 SPECIALIZED AI AGENTS

🎯 II. CHI TIẾT PHÂN BỔ 80 APIS THEO SYSTEM PIPELINE & 12 SPECIALIZED AI AGENTS

### • 0. System Pipeline & Infrastructure (Alert Data & System Inventory Fetching)
- Endpoints API sử dụng: API #1 (get_organizations), API #2 (get_networks), API #3 (get_device_statuses), API #4 (get_assurance_alerts), API #5 (get_network_alerts_history), API #10 (lossAndLatency), API #33 (linkLayer topology)
- Chức năng: server.py và pipeline.py dùng để đọc danh sách Organizations, Networks, Device Inventory Bảng 2, Assurance Alerts Queue Bảng 1, Lịch sử cảnh báo Down/Up, và sơ đồ Layer 2.

### • 1. AuditConfigAgent (Audit & Compliance Specialist)
- Endpoints API sử dụng: API #35, #43, #48, #62, #71, #72 (configurationChanges, DNS, Licenses, Group Policies, Umbrella SIG, Branding)
- Chức năng: Đối soát chỉnh sửa cấu hình con người, kiểm tra Meraki License, Group Policies và Cisco Umbrella SIG Custom DNS.

### • 2. AppQoEAgent (Application Quality of Experience)
- Endpoints API sử dụng: API #28, #39, #55, #56, #66 (monitoredMediaServers, App Health, VoIP Jitter, Bandwidth Hogs)
- Chức năng: Đo đạc chỉ số trải nghiệm cuộc họp trực tuyến Webex/Zoom/Teams, Jitter ms và bóc tách TOP máy khách ngốn băng thông.

### • 3. DeviceIntelAgent (Hardware & Power Specialist)
- Endpoints API sử dụng: API #8, #3, #67, #78 (device_detail, device_statuses, Energy AIOps, Scheduled PoE)
- Chức năng: Kiểm tra phần cứng L1, phiên bản Firmware, mức tiêu thụ điện năng kWh và điều khiển nguồn PoE theo lịch trình.

### • 4. EventLogAgent (Log & Auth Correlator)
- Endpoints API sử dụng: API #7, #5, #79, #80 (events, alerts_history, Webhook HTTP Servers, Delivery Logs)
- Chức năng: Rà soát nhật ký sự kiện hệ thống nguyên bản và theo dõi nhật ký gửi thông báo tức thời qua Telegram/Slack/ServiceNow Webhooks.

### • 5. ClientImpactAgent (User Experience Analyzer)
- Endpoints API sử dụng: API #6, #23, #45, #66 (clients, connectionStats, Wake-on-LAN, Bandwidth Hogs)
- Chức năng: Đánh giá quy mô ảnh hưởng người dùng, tổng số clients online, phát hiện Bandwidth Hogs và gửi Magic Packet bật PC từ xa.

### • 6. UplinkWanAgent (WAN Link Quality Specialist)
- Endpoints API sử dụng: API #9 & #10 (uplink/statuses, lossAndLatency)
- Chức năng: Giám sát trạng thái cổng WAN1/WAN2 vật lý, tỷ lệ mất gói (%) và độ trễ ISP (ms).

### • 7. WanSdwanAgent (SD-WAN & Gateway Specialist)
- Endpoints API sử dụng: API #11, #16, #29, #36, #37, #42, #46, #47, #57, #58, #69, #73, #74 (ThousandEyes, MTR, Snort IDS/IPS, SD-WAN Traffic Shaping, AWS/Azure VPN)
- Chức năng: Chẩn đoán Auto-VPN Mesh, đo đường truyền Cisco ThousandEyes BGP path, SD-WAN Traffic Shaping rules và Cloud AWS/Azure VPN Peers.

### • 8. SwitchPortAgent (Switching Infrastructure Specialist)
- Endpoints API sử dụng: API #12, #13, #15, #17, #31, #32, #40, #41, #44, #49, #50, #51, #59, #70, #77, #78 (PCAP, Clear Counters, DAI, L3 Static Routes, PoE Control)
- Chức năng: Bắt gói tin PCAP thời gian thực, tự động Clear CRC Counters, kiểm tra cáp TDR, L3 Static Routes và điều khiển nguồn PoE.

### • 9. RfWirelessAgent (Radio Frequency Specialist)
- Endpoints API sử dụng: API #21, #22, #38, #52, #53, #60, #68, #75, #76 (RF Status, Reboot SSID, Wi-Fi 6E 6GHz, Mesh Status)
- Chức năng: Đo nhiễu nền Noise Floor, độ nghẽn kênh vô tuyến 2.4GHz/5GHz, reboot SSID riêng lẻ, Wi-Fi 6E/7 Tri-Band Profiles và Mesh status.

### • 10. SecurityAirMarshalAgent (Wireless Threat Specialist)
- Endpoints API sử dụng: API #25, #7, #61, #63 (AirMarshal, Client Quarantine, Content Filtering)
- Chức năng: Quét phát hiện Rogue AP, SSID Spoofing, tự động cô lập Client nhiễm virus (Quarantine) và Content Filtering.

### • 11. FirmwareCrashAgent (Reliability Specialist)
- Endpoints API sử dụng: API #26 & #8 (firmwareUpgrades, device_detail)
- Chức năng: Phân tích lịch sử nâng cấp Firmware, phát hiện lỗi treo reboot loop do xung đột phiên bản.

### • 12. SensorIotAgent (Environmental IoT Specialist)
- Endpoints API sử dụng: API #27, #54, #64, #65 (sensor/readings, BLE, 7-day History, MV Camera Heatmaps)
- Chức năng: Theo dõi chỉ số cảm biến Meraki MT, biểu đồ lịch sử 7 ngày, cấu hình BLE và bản đồ nhiệt Camera MV Heatmap.