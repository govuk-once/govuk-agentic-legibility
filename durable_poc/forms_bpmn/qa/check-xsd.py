"""Optional official BPMN 2.0 schema validation; pip install lxml, npm ci first."""

import sys
from pathlib import Path

from lxml import etree

schema_path = (
    Path(__file__).parent / "node_modules/bpmn-moddle/resources/bpmn/xsd/BPMN20.xsd"
)
schema = etree.XMLSchema(etree.parse(str(schema_path)))
if len(sys.argv) < 2:
    raise SystemExit("Usage: python check-xsd.py file.bpmn ...")
for name in sys.argv[1:]:
    schema.assertValid(etree.parse(name))
    print(f"{name}: BPMN 2.0 XSD valid")
