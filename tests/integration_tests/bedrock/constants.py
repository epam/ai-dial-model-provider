from pathlib import Path

from aidial_adapter_anthropic.dial.resource import Resource

# Resolved against this file, not the cwd: pytest runs from the repo root.
# tests/integration_tests/bedrock/constants.py -> tests/
_ASSETS = Path(__file__).parents[2] / "assets" / "bedrock"

BLUE_PNG_PICTURE = Resource.from_base64(
    type="image/png",
    data_base64="iVBORw0KGgoAAAANSUhEUgAAAAMAAAADCAIAAADZSiLoAAAAF0lEQVR4nGNkYPjPwMDAwMDAxAADCBYAG10BBdmz9y8AAAAASUVORK5CYII=",
)

DOG_PICTURE = Resource(
    type="image/png", data=(_ASSETS / "image1.png").read_bytes()
)

DOG_PICTURE_CONTENT = ["dog"]

PDF_DOCUMENT_RESOURCE = Resource(
    type="application/pdf", data=(_ASSETS / "doc.pdf").read_bytes()
)

EXCEL_DOCUMENT_RESOURCE = Resource(
    type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    data=(_ASSETS / "table.xlsx").read_bytes(),
)

MARKDOWN_DOCUMENT_RESOURCE = Resource(
    type="text/markdown", data=(_ASSETS / "doc.md").read_bytes()
)

SAMPLE_DOCUMENT_RESOURCE = Resource.from_base64(
    type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    data_base64="iVBORw0KGgoAAAANSUhEUgAAAAMAAAADCAIAAADZSiLoAAAAF0lEQVR4nGNkYPjPwMDAwMDAxAADCBYAG10BBdmz9y8AAAAASUVORK5CYII=",
)
