import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api import meraki

orgs = meraki.get_organizations()
for org in orgs:
    alerts = meraki.get_assurance_alerts(org['id'], timespan=604800*4)
    for a in alerts:
        if "crc" in str(a).lower():
            print("FOUND CRC ALERT:")
            import json
            print(json.dumps(a, indent=2))


