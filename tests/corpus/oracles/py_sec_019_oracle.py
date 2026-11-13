import defusedxml.ElementTree as ET
def parse_xml(s):
    return ET.fromstring(s)
