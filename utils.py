# """Schemas, prompts, consensus, validation and output helpers."""

# from __future__ import annotations

# import json
# import re
# import unicodedata
# from collections import Counter
# from collections.abc import Iterable, Mapping, Sequence
# from datetime import datetime
# from pathlib import Path

# IDENTITY_FIELDS = ("name_english", "name_chinese", "identity_document_number")
# IDENTITY_WITH_BIRTH_FIELDS = IDENTITY_FIELDS + ("date_of_birth",)
# ADDRESS_FIELDS = ("flat", "floor", "block", "building", "street", "district", "region")
# DECLARATION_FIELDS = ("agent_name", "agent_identity_document_number", "date")
# VALID_STATES = {"filled", "blank", "uncertain"}
# VALID_REGIONS = {
#     "hong kong": "Hong Kong",
#     "kowloon": "Kowloon",
#     "new territories": "New Territories",
# }


# BASE_RULES = """You are reading one cropped section of a Hong Kong Transport Department form.
# Read only handwritten or typed entries and visibly selected checkboxes.
# Printed labels, instructions, borders and guide marks are never field values.
# Use physical field location rather than guessing from language.
# Preserve Traditional Chinese, spaces that belong inside values, and leading zeros.
# Do not translate, spell-correct, infer, or copy a value from another field.
# For each field return state="filled" only when an entry is visible,
# state="blank" only when the field is visibly empty, and state="uncertain" when
# the evidence is ambiguous. Blank and uncertain fields must have value="".
# Return exactly one valid JSON object with the requested keys and no commentary.
# """


# PROMPTS = {
#     "identity": BASE_RULES
#     + """
# Extract the two name locations and identity-document number from this crop.
# The Chinese-name location can contain Latin letters. Names may contain spaces
# and hyphens but must not absorb the vertical writing guides.
# {"name_english":{"value":"","state":"filled|blank|uncertain"},
#  "name_chinese":{"value":"","state":"filled|blank|uncertain"},
#  "identity_document_number":{"value":"","state":"filled|blank|uncertain"}}
# """,
#     "identity_with_birth": BASE_RULES
#     + """
# Extract the English name, Chinese name, identity-document number and date of
# birth from this crop. Do not read the printed honorifics as part of a name.
# {"name_english":{"value":"","state":"filled|blank|uncertain"},
#  "name_chinese":{"value":"","state":"filled|blank|uncertain"},
#  "identity_document_number":{"value":"","state":"filled|blank|uncertain"},
#  "date_of_birth":{"value":"","state":"filled|blank|uncertain"}}
# """,
#     "e_contact": BASE_RULES
#     + """
# Extract only the handwritten Hong Kong mobile number or email address entered
# in the E-CONTACT MEANS field. Return the visible entry exactly; do not treat
# the bilingual instructions as a value.
# {"e_contact":{"value":"","state":"filled|blank|uncertain"}}
# """,
#     "residential": BASE_RULES
#     + """
# Extract only the Residential Address. For region, read the visibly selected
# checkbox and return Hong Kong, Kowloon, New Territories, or an empty value.
# {"flat":{"value":"","state":"filled|blank|uncertain"},
#  "floor":{"value":"","state":"filled|blank|uncertain"},
#  "block":{"value":"","state":"filled|blank|uncertain"},
#  "building":{"value":"","state":"filled|blank|uncertain"},
#  "street":{"value":"","state":"filled|blank|uncertain"},
#  "district":{"value":"","state":"filled|blank|uncertain"},
#  "region":{"value":"","state":"filled|blank|uncertain"}}
# """,
#     "correspondence": BASE_RULES
#     + """
# Extract only the Correspondence Address and Day Time Contact Telephone Number.
# Do not repeat the residential address when this section is blank. For region,
# use only the checkbox inside this correspondence section.
# {"flat":{"value":"","state":"filled|blank|uncertain"},
#  "floor":{"value":"","state":"filled|blank|uncertain"},
#  "block":{"value":"","state":"filled|blank|uncertain"},
#  "building":{"value":"","state":"filled|blank|uncertain"},
#  "street":{"value":"","state":"filled|blank|uncertain"},
#  "district":{"value":"","state":"filled|blank|uncertain"},
#  "region":{"value":"","state":"filled|blank|uncertain"},
#  "telephone":{"value":"","state":"filled|blank|uncertain"}}
# """,
#     "declaration": BASE_RULES
#     + """
# Extract optional agent details and the handwritten date from this declaration
# crop. Do not treat signature strokes as an agent name.
# {"agent_name":{"value":"","state":"filled|blank|uncertain"},
#  "agent_identity_document_number":{"value":"","state":"filled|blank|uncertain"},
#  "date":{"value":"","state":"filled|blank|uncertain"}}
# """,
# }


# TASK_FIELDS = {
#     "identity": IDENTITY_FIELDS,
#     "identity_with_birth": IDENTITY_WITH_BIRTH_FIELDS,
#     "e_contact": ("e_contact",),
#     "residential": ADDRESS_FIELDS,
#     "correspondence": ADDRESS_FIELDS + ("telephone",),
#     "declaration": DECLARATION_FIELDS,
# }


# ENGLISH_LABELS = {
#     "form_type": "Form type",
#     "name_english": "English name",
#     "name_chinese": "Chinese-name field",
#     "identity_document_number": "Identity document number",
#     "date_of_birth": "Date of birth",
#     # "e_contact": "E-contact means",
#     "residential_address": "Residential address",
#     "correspondence_address": "Correspondence address",
#     "telephone": "Telephone",
#     "agent_name": "Agent name",
#     "agent_identity_document_number": "Agent identity document number",
#     "date": "Date",
#     "flat": "Flat/Room",
#     "floor": "Floor",
#     "block": "Block/Tower",
#     "building": "Building/Estate",
#     "street": "Street/Village",
#     "district": "District",
#     "region": "Region",
# }


# CHINESE_LABELS = {
#     "form_type": "表格類型",
#     "name_english": "英文姓名",
#     "name_chinese": "中文姓名",
#     "identity_document_number": "身份證明文件號碼",
#     "date_of_birth": "出生日期",
#     "e_contact": "電子聯絡方式",
#     "residential_address": "住址",
#     "correspondence_address": "通訊地址",
#     "telephone": "日間聯絡電話",
#     "agent_name": "代理人姓名",
#     "agent_identity_document_number": "代理人身份證明文件號碼",
#     "date": "日期",
#     "flat": "室",
#     "floor": "樓",
#     "block": "座",
#     "building": "大廈或屋苑名稱",
#     "street": "門牌號數及街道或鄉村名稱",
#     "district": "地區",
#     "region": "區域",
# }


# def parse_json_object(text: str) -> dict[str, object]:
#     """Extract the first valid JSON object from a model response."""

#     decoder = json.JSONDecoder()
#     for index, character in enumerate(text):
#         if character != "{":
#             continue
#         try:
#             value, _ = decoder.raw_decode(text[index:])
#         except json.JSONDecodeError:
#             continue
#         if isinstance(value, dict):
#             return value
#     raise ValueError("No valid JSON object found in the model response")


# def normalize_for_agreement(value: object) -> str:
#     """Normalize only for voting; the selected original spelling is retained."""

#     text = unicodedata.normalize("NFKC", str(value)).casefold().strip()
#     return re.sub(r"\s+", " ", text)


# def clean_candidate(node: object) -> dict[str, str]:
#     """Convert one model leaf into a strict ``value/state`` pair."""

#     if not isinstance(node, dict):
#         return {"value": "", "state": "uncertain"}
#     value = unicodedata.normalize("NFKC", str(node.get("value", ""))).strip()
#     state = str(node.get("state", "uncertain")).strip().lower()
#     if state not in VALID_STATES:
#         state = "uncertain"
#     if state != "filled":
#         value = ""
#     elif not value:
#         state = "uncertain"
#     return {"value": value, "state": state}


# def consensus_for_task(
#     task: str,
#     responses: Sequence[Mapping[str, object]],
#     minimum_agreement: int,
# ) -> tuple[dict[str, dict[str, str]], list[dict[str, object]]]:
#     """Select field values by agreement across independent image views.

#     A value is accepted only when at least ``minimum_agreement`` views produce
#     the same normalized value and state. Ties and low agreement become
#     ``uncertain`` and are retained in the audit instead of being guessed.
#     """

#     if task not in TASK_FIELDS:
#         raise KeyError(f"Unknown extraction task: {task}")
#     if not responses:
#         raise ValueError(f"No parsed responses supplied for task {task}")

#     fields: dict[str, dict[str, str]] = {}
#     audit: list[dict[str, object]] = []
#     required = min(max(1, minimum_agreement), len(responses))

#     for field in TASK_FIELDS[task]:
#         candidates = [clean_candidate(response.get(field)) for response in responses]
#         keys = [
#             (candidate["state"], normalize_for_agreement(candidate["value"]))
#             for candidate in candidates
#         ]
#         counts = Counter(keys)
#         winning_key, votes = counts.most_common(1)[0]
#         tied = list(counts.values()).count(votes) > 1

#         if votes >= required and not tied:
#             selected = next(
#                 candidate
#                 for candidate, key in zip(candidates, keys)
#                 if key == winning_key
#             )
#         else:
#             selected = {"value": "", "state": "uncertain"}

#         fields[field] = selected
#         if len(counts) > 1 or selected["state"] == "uncertain":
#             audit.append(
#                 {
#                     "field": f"{task}.{field}",
#                     "issue": "View disagreement or insufficient agreement",
#                     "required_votes": required,
#                     "candidates": candidates,
#                 }
#             )
#     return fields, audit


# def _is_filled(item: Mapping[str, str]) -> bool:
#     return item.get("state") == "filled" and bool(item.get("value"))


# def validate_and_combine(
#     task_results: Mapping[str, Mapping[str, Mapping[str, str]]],
#     consensus_audit: Sequence[Mapping[str, object]],
#     form_id: str = "td320",
# ) -> tuple[dict[str, object], dict[str, object]]:
#     """Combine task outputs, normalize safe formats and flag inconsistencies.

#     This function never copies a name or address into another field. Values that
#     cannot be validated remain visible and are flagged for human review.
#     """

#     review = [dict(item) for item in consensus_audit]
#     identity = dict(
#         task_results.get("identity_with_birth", task_results.get("identity", {}))
#     )
#     e_contact = dict(task_results.get("e_contact", {}))
#     residential = dict(task_results.get("residential", {}))
#     correspondence = dict(task_results.get("correspondence", {}))
#     declaration = dict(task_results.get("declaration", {}))
#     has_declaration = "declaration" in task_results

#     for field in IDENTITY_FIELDS:
#         identity.setdefault(field, {"value": "", "state": "uncertain"})
#     if "identity_with_birth" in task_results:
#         identity.setdefault("date_of_birth", {"value": "", "state": "uncertain"})
#     if "e_contact" in task_results:
#         e_contact.setdefault("e_contact", {"value": "", "state": "uncertain"})
#     for field in ADDRESS_FIELDS:
#         residential.setdefault(field, {"value": "", "state": "uncertain"})
#         correspondence.setdefault(field, {"value": "", "state": "uncertain"})
#     correspondence.setdefault("telephone", {"value": "", "state": "uncertain"})
#     if has_declaration:
#         for field in DECLARATION_FIELDS:
#             declaration.setdefault(field, {"value": "", "state": "uncertain"})

#     phone = correspondence["telephone"]
#     if _is_filled(phone):
#         phone["value"] = re.sub(r"[\s().-]", "", phone["value"])
#         if not re.fullmatch(r"\d{8}", phone["value"]):
#             review.append({"field": "telephone", "issue": "Expected eight digits"})

#     if _is_filled(e_contact.get("e_contact", {})):
#         value = e_contact["e_contact"]["value"]
#         compact_phone = re.sub(r"[\s().-]", "", value)
#         if "@" not in value and not re.fullmatch(r"\d{8}", compact_phone):
#             review.append(
#                 {
#                     "field": "e_contact",
#                     "issue": "Expected an email address or eight-digit phone number",
#                 }
#             )

#     date = declaration.get("date", {})
#     if _is_filled(date):
#         date["value"] = re.sub(r"\s*([/.-])\s*", r"\1", date["value"])
#         valid = False
#         for date_format in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
#             try:
#                 # This parses a form date, not a timezone-bearing timestamp.
#                 datetime.strptime(date["value"], date_format)  # noqa: DTZ007
#                 valid = True
#                 break
#             except ValueError:
#                 pass
#         if not valid:
#             review.append({"field": "date", "issue": "Invalid date"})

#     for section_name, section in (
#         ("residential_address", residential),
#         ("correspondence_address", correspondence),
#     ):
#         region = section["region"]
#         if _is_filled(region):
#             canonical = VALID_REGIONS.get(normalize_for_agreement(region["value"]))
#             if canonical:
#                 region["value"] = canonical
#             else:
#                 review.append(
#                     {"field": f"{section_name}.region", "issue": "Invalid region"}
#                 )

#     # Identical non-empty addresses can be real, but are unsafe to accept silently.
#     comparable = [
#         field
#         for field in ADDRESS_FIELDS
#         if _is_filled(residential[field]) or _is_filled(correspondence[field])
#     ]
#     if len(comparable) >= 3 and all(
#         _is_filled(residential[field])
#         and _is_filled(correspondence[field])
#         and normalize_for_agreement(residential[field]["value"])
#         == normalize_for_agreement(correspondence[field]["value"])
#         for field in comparable
#     ):
#         review.append(
#             {
#                 "field": "correspondence_address",
#                 "issue": "Matches residential address; verify against the image",
#             }
#         )

#     states = {
#         "form_type": "filled",
#         **{key: item["state"] for key, item in identity.items()},
#         "residential_address": {
#             key: item["state"] for key, item in residential.items()
#         },
#         "correspondence_address": {
#             key: item["state"]
#             for key, item in correspondence.items()
#             if key != "telephone"
#         },
#         "telephone": correspondence["telephone"]["state"],
#         **(
#             {"e_contact": e_contact["e_contact"]["state"]}
#             if "e_contact" in e_contact
#             else {}
#         ),
#         **{key: item["state"] for key, item in declaration.items()},
#     }
#     data: dict[str, object] = {
#         "form_type": form_id,
#         **{key: item["value"] for key, item in identity.items()},
#         "residential_address": {
#             key: item["value"] for key, item in residential.items()
#         },
#         "correspondence_address": {
#             key: item["value"]
#             for key, item in correspondence.items()
#             if key != "telephone"
#         },
#         "telephone": correspondence["telephone"]["value"],
#         **(
#             {"e_contact": e_contact["e_contact"]["value"]}
#             if "e_contact" in e_contact
#             else {}
#         ),
#         **{key: item["value"] for key, item in declaration.items()},
#     }
#     audit = {
#         "status": "needs_review" if review else "passed_automated_checks",
#         "review_items": review,
#         "field_states": states,
#     }
#     return data, audit


# def translate_keys(value: object, labels: Mapping[str, str]) -> object:
#     """Recursively translate dictionary keys while leaving values unchanged."""

#     if isinstance(value, dict):
#         return {
#             labels.get(key, key): translate_keys(item, labels)
#             for key, item in value.items()
#         }
#     return value


# def render_text(data: Mapping[str, object], labels: Mapping[str, str]) -> str:
#     """Render one human-readable flat/nested form summary."""

#     lines = []
#     for key, value in data.items():
#         label = labels.get(key, key)
#         if isinstance(value, dict):
#             lines.append(f"{label}:")
#             lines.extend(
#                 f"  {labels.get(child, child)}: {entry}"
#                 for child, entry in value.items()
#             )
#         else:
#             lines.append(f"{label}: {value}")
#     return "\n".join(lines) + "\n"


# def write_json(path: Path, value: object) -> None:
#     """Write UTF-8 JSON with stable indentation."""

#     path.parent.mkdir(parents=True, exist_ok=True)
#     path.write_text(
#         json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
#     )


# def write_outputs(
#     output_root: Path,
#     image_path: Path,
#     data: Mapping[str, object],
#     audit: Mapping[str, object],
#     raw: Mapping[str, object],
# ) -> Path:
#     """Write English/Chinese text, JSON, audit and raw evidence files."""

#     folder = output_root / image_path.stem
#     folder.mkdir(parents=True, exist_ok=True)
#     name = image_path.stem
#     (folder / f"{name}_English.txt").write_text(
#         render_text(data, ENGLISH_LABELS), encoding="utf-8"
#     )
#     (folder / f"{name}_Chinese.txt").write_text(
#         render_text(data, CHINESE_LABELS), encoding="utf-8"
#     )
#     write_json(folder / f"{name}_English.json", data)
#     write_json(folder / f"{name}_Chinese.json", translate_keys(data, CHINESE_LABELS))
#     write_json(folder / f"{name}_audit.json", audit)
#     write_json(folder / f"{name}_raw.json", raw)

#     # Fail immediately if final JSON was accidentally rendered incorrectly.
#     for language in ("English", "Chinese"):
#         json.loads((folder / f"{name}_{language}.json").read_text(encoding="utf-8"))
#     return folder


# def list_images(
#     folder: Path,
#     extensions: Iterable[str],
#     templates: Iterable[Path] = (),
# ) -> list[Path]:
#     """List supported form images, excluding every registered template."""

#     if not folder.is_dir():
#         raise FileNotFoundError(f"Input folder not found: {folder.resolve()}")
#     extension_set = {extension.lower() for extension in extensions}
#     template_paths = {
#         template.resolve() for template in templates if template.exists()
#     }
#     images = [
#         path
#         for path in folder.iterdir()
#         if path.is_file()
#         and path.suffix.lower() in extension_set
#         and path.resolve() not in template_paths
#     ]
#     return sorted(images, key=lambda path: path.name.casefold())




from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path

IDENTITY_FIELDS = ("name_english", "name_chinese", "identity_document_number")
IDENTITY_WITH_BIRTH_FIELDS = IDENTITY_FIELDS + ("date_of_birth",)
ADDRESS_FIELDS = ("flat", "floor", "block", "building", "street", "district", "region")
DECLARATION_FIELDS = ("agent_name", "agent_identity_document_number", "date")
VALID_STATES = {"filled", "blank", "uncertain"}
VALID_REGIONS = {
    "hong kong": "Hong Kong",
    "kowloon": "Kowloon",
    "new territories": "New Territories",
}

# Used only to detect the common row-shift error where a district/locality is
# returned as ``street`` while the visible District row is returned blank.
# Values are normalized with ``normalize_for_agreement`` before comparison.
KNOWN_DISTRICT_VALUES = {
    "central",
    "chai wan",
    "cheng sha wan",
    "cheung sha wan",
    "causeway bay",
    "happy valley",
    "kowloon city",
    "kwai chung",
    "kwun tong",
    "mong kok",
    "north point",
    "pok fu lam",
    "sai kung",
    "sha tin",
    "sham shui po",
    "sheung wan",
    "tai po",
    "tseung kwan o",
    "tsuen wan",
    "tuen mun",
    "wan chai",
    "wong tai sin",
    "yau ma tei",
    "yuen long",
}


BASE_RULES = """You are reading one cropped section of a Hong Kong Transport Department form.
Read only handwritten or typed entries and visibly selected checkboxes.
Printed labels, instructions, borders and guide marks are never field values.
Use physical field location rather than guessing from language.
Preserve Traditional Chinese, spaces that belong inside values, and leading zeros.
Do not translate, spell-correct, infer, or copy a value from another field.
For a Region checkbox, output only one canonical English value: Hong Kong,
Kowloon, or New Territories. Never include its printed Chinese label.
For each field return state="filled" only when an entry is visible,
state="blank" only when the field is visibly empty, and state="uncertain" when
the evidence is ambiguous. Blank and uncertain fields must have value="".
Return exactly one valid JSON object with the requested keys and no commentary.
"""


PROMPTS = {
    "identity": BASE_RULES
    + """
Extract the two name locations and identity-document number from this crop.
The Chinese-name location can contain Latin letters. Names may contain spaces
and hyphens but must not absorb the vertical writing guides.
{"name_english":{"value":"","state":"filled|blank|uncertain"},
 "name_chinese":{"value":"","state":"filled|blank|uncertain"},
 "identity_document_number":{"value":"","state":"filled|blank|uncertain"}}
""",
    "identity_with_birth": BASE_RULES
    + """
Extract the English name, Chinese name, identity-document number and date of
birth from this crop. Do not read the printed honorifics as part of a name.
Read the identity number character by character, including its leading letter
and any check digit printed in parentheses. Read date-of-birth boxes in the
printed D D / M M / Y Y Y Y order and return the result as DD/MM/YYYY.
{"name_english":{"value":"","state":"filled|blank|uncertain"},
 "name_chinese":{"value":"","state":"filled|blank|uncertain"},
 "identity_document_number":{"value":"","state":"filled|blank|uncertain"},
 "date_of_birth":{"value":"","state":"filled|blank|uncertain"}}
""",
    "e_contact": BASE_RULES
    + """
Extract only the handwritten Hong Kong mobile number or email address entered
in the E-CONTACT MEANS field. Return the visible entry exactly; do not treat
the bilingual instructions as a value.
{"e_contact":{"value":"","state":"filled|blank|uncertain"}}
""",
    "residential": BASE_RULES
    + """
Extract only the Residential Address. The printed label for each long entry
line is immediately BELOW that line. Map rows by their physical order:
1. building = the first long line, immediately above "Name of Building/Estate";
2. street = the next long line, immediately above
   "Number and Name of Street (or Village)";
3. district = the final shorter line, immediately above "District";
4. region = the visibly selected checkbox to the right of the district row.
Never move a district/locality such as POK FU LAM into street. Never move a
street such as CYBERPORT 1 into building. For region, return exactly Hong Kong,
Kowloon, New Territories, or an empty value--English only.
{"flat":{"value":"","state":"filled|blank|uncertain"},
 "floor":{"value":"","state":"filled|blank|uncertain"},
 "block":{"value":"","state":"filled|blank|uncertain"},
 "building":{"value":"","state":"filled|blank|uncertain"},
 "street":{"value":"","state":"filled|blank|uncertain"},
 "district":{"value":"","state":"filled|blank|uncertain"},
 "region":{"value":"","state":"filled|blank|uncertain"}}
""",
    "correspondence": BASE_RULES
    + """
Extract only the Correspondence Address and Day Time Contact Telephone Number.
Do not repeat the residential address when this section is blank. The printed
label for each long entry line is immediately BELOW that line. Map rows by
their physical order: building first, street second, district third, and then
the region checkbox. Use only the checkbox inside this correspondence section.
Return region in canonical English only: Hong Kong, Kowloon, New Territories,
or an empty value. Never include 香港, 九龍, or 新界 in the returned region.
{"flat":{"value":"","state":"filled|blank|uncertain"},
 "floor":{"value":"","state":"filled|blank|uncertain"},
 "block":{"value":"","state":"filled|blank|uncertain"},
 "building":{"value":"","state":"filled|blank|uncertain"},
 "street":{"value":"","state":"filled|blank|uncertain"},
 "district":{"value":"","state":"filled|blank|uncertain"},
 "region":{"value":"","state":"filled|blank|uncertain"},
 "telephone":{"value":"","state":"filled|blank|uncertain"}}
""",
    "declaration": BASE_RULES
    + """
Extract optional agent details and the handwritten date from this declaration
crop. Do not treat signature strokes as an agent name.
{"agent_name":{"value":"","state":"filled|blank|uncertain"},
 "agent_identity_document_number":{"value":"","state":"filled|blank|uncertain"},
 "date":{"value":"","state":"filled|blank|uncertain"}}
""",
}


TASK_FIELDS = {
    "identity": IDENTITY_FIELDS,
    "identity_with_birth": IDENTITY_WITH_BIRTH_FIELDS,
    "e_contact": ("e_contact",),
    "residential": ADDRESS_FIELDS,
    "correspondence": ADDRESS_FIELDS + ("telephone",),
    "declaration": DECLARATION_FIELDS,
}


ENGLISH_LABELS = {
    "form_type": "Form type",
    "name_english": "English name",
    "name_chinese": "Chinese-name field",
    "identity_document_number": "Identity document number",
    "date_of_birth": "Date of birth",
    # "e_contact": "E-contact means",
    "residential_address": "Residential address",
    "correspondence_address": "Correspondence address",
    "telephone": "Telephone",
    "agent_name": "Agent name",
    "agent_identity_document_number": "Agent identity document number",
    "date": "Date",
    "flat": "Flat/Room",
    "floor": "Floor",
    "block": "Block/Tower",
    "building": "Building/Estate",
    "street": "Street/Village",
    "district": "District",
    "region": "Region",
}


CHINESE_LABELS = {
    "form_type": "表格類型",
    "name_english": "英文姓名",
    "name_chinese": "中文姓名",
    "identity_document_number": "身份證明文件號碼",
    "date_of_birth": "出生日期",
    "e_contact": "電子聯絡方式",
    "residential_address": "住址",
    "correspondence_address": "通訊地址",
    "telephone": "日間聯絡電話",
    "agent_name": "代理人姓名",
    "agent_identity_document_number": "代理人身份證明文件號碼",
    "date": "日期",
    "flat": "室",
    "floor": "樓",
    "block": "座",
    "building": "大廈或屋苑名稱",
    "street": "門牌號數及街道或鄉村名稱",
    "district": "地區",
    "region": "區域",
}


def parse_json_object(text: str) -> dict[str, object]:
    """Extract the first valid JSON object from a model response."""

    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("No valid JSON object found in the model response")


def normalize_for_agreement(value: object) -> str:
    """Normalize only for voting; the selected original spelling is retained."""

    text = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    return re.sub(r"\s+", " ", text)


def canonicalize_region(value: object) -> str | None:
    """Return one canonical English region or ``None`` when it is invalid.

    Models sometimes copy both parts of a printed bilingual label, for example
    ``九龍 Kowloon``.  A valid result is normalized to English only.  Chinese-only
    checkbox labels are also accepted because the selected checkbox provides
    the evidence; unrelated address text is never treated as a region.
    """

    normalized = normalize_for_agreement(value)
    if not normalized:
        return None

    if "new territories" in normalized or "新界" in normalized:
        return "New Territories"
    if "hong kong" in normalized or "香港" in normalized:
        return "Hong Kong"
    if "kowloon" in normalized or "九龍" in normalized:
        return "Kowloon"
    return None


def clean_candidate(node: object) -> dict[str, str]:
    """Convert one model leaf into a strict ``value/state`` pair."""

    if not isinstance(node, dict):
        return {"value": "", "state": "uncertain"}
    value = unicodedata.normalize("NFKC", str(node.get("value", ""))).strip()
    state = str(node.get("state", "uncertain")).strip().lower()
    if state not in VALID_STATES:
        state = "uncertain"
    if state != "filled":
        value = ""
    elif not value:
        state = "uncertain"
    return {"value": value, "state": state}


def consensus_for_task(
    task: str,
    responses: Sequence[Mapping[str, object]],
    minimum_agreement: int,
) -> tuple[dict[str, dict[str, str]], list[dict[str, object]]]:
    """Select field values by agreement across independent image views.

    A value is accepted only when at least ``minimum_agreement`` views produce
    the same normalized value and state. Ties and low agreement become
    ``uncertain`` and are retained in the audit instead of being guessed.
    """

    if task not in TASK_FIELDS:
        raise KeyError(f"Unknown extraction task: {task}")
    if not responses:
        raise ValueError(f"No parsed responses supplied for task {task}")

    fields: dict[str, dict[str, str]] = {}
    audit: list[dict[str, object]] = []
    required = min(max(1, minimum_agreement), len(responses))

    for field in TASK_FIELDS[task]:
        candidates = [clean_candidate(response.get(field)) for response in responses]
        keys = [
            (candidate["state"], normalize_for_agreement(candidate["value"]))
            for candidate in candidates
        ]
        counts = Counter(keys)
        winning_key, votes = counts.most_common(1)[0]
        tied = list(counts.values()).count(votes) > 1

        if votes >= required and not tied:
            selected = next(
                candidate
                for candidate, key in zip(candidates, keys)
                if key == winning_key
            )
        else:
            selected = {"value": "", "state": "uncertain"}

        fields[field] = selected
        if len(counts) > 1 or selected["state"] == "uncertain":
            audit.append(
                {
                    "field": f"{task}.{field}",
                    "issue": "View disagreement or insufficient agreement",
                    "required_votes": required,
                    "candidates": candidates,
                }
            )
    return fields, audit


def _is_filled(item: Mapping[str, str]) -> bool:
    return item.get("state") == "filled" and bool(item.get("value"))


def _repair_shifted_district(
    section: dict[str, dict[str, str]],
    section_name: str,
    review: list[dict[str, object]],
) -> None:
    """Prevent a known district/locality from being published as a street.

    The prompt is the primary protection.  This conservative fallback runs
    only when District is blank and Street is an exact known locality.  It
    moves that value to District and leaves Street uncertain rather than
    publishing a confidently wrong street value.
    """

    street = section["street"]
    district = section["district"]
    if not _is_filled(street) or _is_filled(district):
        return

    normalized_street = normalize_for_agreement(street["value"])
    if normalized_street not in KNOWN_DISTRICT_VALUES:
        return

    district["value"] = street["value"]
    district["state"] = "filled"
    street["value"] = ""
    street["state"] = "uncertain"
    review.append(
        {
            "field": f"{section_name}.street",
            "issue": (
                "A known district/locality was returned as Street. It was "
                "moved to District; Street requires review."
            ),
        }
    )


def validate_and_combine(
    task_results: Mapping[str, Mapping[str, Mapping[str, str]]],
    consensus_audit: Sequence[Mapping[str, object]],
    form_id: str = "td320",
) -> tuple[dict[str, object], dict[str, object]]:
    """Combine task outputs, normalize safe formats and flag inconsistencies.

    This function never copies a name or address into another field. Values that
    cannot be validated remain visible and are flagged for human review.
    """

    review = [dict(item) for item in consensus_audit]
    identity = dict(
        task_results.get("identity_with_birth", task_results.get("identity", {}))
    )
    residential = dict(task_results.get("residential", {}))
    correspondence = dict(task_results.get("correspondence", {}))
    declaration = dict(task_results.get("declaration", {}))
    has_declaration = "declaration" in task_results

    for field in IDENTITY_FIELDS:
        identity.setdefault(field, {"value": "", "state": "uncertain"})
    if "identity_with_birth" in task_results:
        identity.setdefault("date_of_birth", {"value": "", "state": "uncertain"})
    for field in ADDRESS_FIELDS:
        residential.setdefault(field, {"value": "", "state": "uncertain"})
        correspondence.setdefault(field, {"value": "", "state": "uncertain"})
    correspondence.setdefault("telephone", {"value": "", "state": "uncertain"})
    if has_declaration:
        for field in DECLARATION_FIELDS:
            declaration.setdefault(field, {"value": "", "state": "uncertain"})

    phone = correspondence["telephone"]
    if _is_filled(phone):
        phone["value"] = re.sub(r"[\s().-]", "", phone["value"])
        if not re.fullmatch(r"\d{8}", phone["value"]):
            review.append({"field": "telephone", "issue": "Expected eight digits"})

    date = declaration.get("date", {})
    if _is_filled(date):
        date["value"] = re.sub(r"\s*([/.-])\s*", r"\1", date["value"])
        valid = False
        for date_format in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
            try:
                # This parses a form date, not a timezone-bearing timestamp.
                datetime.strptime(date["value"], date_format)  # noqa: DTZ007
                valid = True
                break
            except ValueError:
                pass
        if not valid:
            review.append({"field": "date", "issue": "Invalid date"})

    # Correct the precise, detectable version of the address-row shift before
    # validating regions. The actual Street stays uncertain if it was omitted
    # by the model; the code does not invent or copy another row into it.
    for section_name, section in (
        ("residential_address", residential),
        ("correspondence_address", correspondence),
    ):
        _repair_shifted_district(section, section_name, review)

        region = section["region"]
        if _is_filled(region):
            canonical = canonicalize_region(region["value"])
            if canonical:
                region["value"] = canonical
            else:
                review.append(
                    {"field": f"{section_name}.region", "issue": "Invalid region"}
                )
                # Never allow arbitrary address text or bilingual printed labels
                # to survive as a final Region value.
                region["value"] = ""
                region["state"] = "uncertain"

    # Identical non-empty addresses can be real, but are unsafe to accept silently.
    comparable = [
        field
        for field in ADDRESS_FIELDS
        if _is_filled(residential[field]) or _is_filled(correspondence[field])
    ]
    if len(comparable) >= 3 and all(
        _is_filled(residential[field])
        and _is_filled(correspondence[field])
        and normalize_for_agreement(residential[field]["value"])
        == normalize_for_agreement(correspondence[field]["value"])
        for field in comparable
    ):
        review.append(
            {
                "field": "correspondence_address",
                "issue": "Matches residential address; verify against the image",
            }
        )

    states = {
        "form_type": "filled",
        **{key: item["state"] for key, item in identity.items()},
        "residential_address": {
            key: item["state"] for key, item in residential.items()
        },
        "correspondence_address": {
            key: item["state"]
            for key, item in correspondence.items()
            if key != "telephone"
        },
        "telephone": correspondence["telephone"]["state"],
        **{key: item["state"] for key, item in declaration.items()},
    }
    data: dict[str, object] = {
        "form_type": form_id,
        **{key: item["value"] for key, item in identity.items()},
        "residential_address": {
            key: item["value"] for key, item in residential.items()
        },
        "correspondence_address": {
            key: item["value"]
            for key, item in correspondence.items()
            if key != "telephone"
        },
        "telephone": correspondence["telephone"]["value"],
        **{key: item["value"] for key, item in declaration.items()},
    }
    audit = {
        "status": "needs_review" if review else "passed_automated_checks",
        "review_items": review,
        "field_states": states,
    }
    return data, audit


def translate_keys(value: object, labels: Mapping[str, str]) -> object:
    """Recursively translate dictionary keys while leaving values unchanged."""

    if isinstance(value, dict):
        return {
            labels.get(key, key): translate_keys(item, labels)
            for key, item in value.items()
        }
    return value


def render_text(data: Mapping[str, object], labels: Mapping[str, str]) -> str:
    """Render one human-readable flat/nested form summary."""

    lines = []
    for key, value in data.items():
        label = labels.get(key, key)
        if isinstance(value, dict):
            lines.append(f"{label}:")
            lines.extend(
                f"  {labels.get(child, child)}: {entry}"
                for child, entry in value.items()
            )
        else:
            lines.append(f"{label}: {value}")
    return "\n".join(lines) + "\n"


def write_json(path: Path, value: object) -> None:
    """Write UTF-8 JSON with stable indentation."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_outputs(
    output_root: Path,
    image_path: Path,
    data: Mapping[str, object],
    audit: Mapping[str, object],
    raw: Mapping[str, object],
) -> Path:
    """Write English/Chinese text, JSON, audit and raw evidence files."""

    folder = output_root / image_path.stem
    folder.mkdir(parents=True, exist_ok=True)
    name = image_path.stem
    (folder / f"{name}_English.txt").write_text(
        render_text(data, ENGLISH_LABELS), encoding="utf-8"
    )
    (folder / f"{name}_Chinese.txt").write_text(
        render_text(data, CHINESE_LABELS), encoding="utf-8"
    )
    write_json(folder / f"{name}_English.json", data)
    write_json(folder / f"{name}_Chinese.json", translate_keys(data, CHINESE_LABELS))
    write_json(folder / f"{name}_audit.json", audit)
    write_json(folder / f"{name}_raw.json", raw)

    # Fail immediately if final JSON was accidentally rendered incorrectly.
    for language in ("English", "Chinese"):
        json.loads((folder / f"{name}_{language}.json").read_text(encoding="utf-8"))
    return folder


def list_images(
    folder: Path,
    extensions: Iterable[str],
    templates: Iterable[Path] = (),
) -> list[Path]:
    """List supported form images, excluding every registered template."""

    if not folder.is_dir():
        raise FileNotFoundError(f"Input folder not found: {folder.resolve()}")
    extension_set = {extension.lower() for extension in extensions}
    template_paths = {
        template.resolve() for template in templates if template.exists()
    }
    images = [
        path
        for path in folder.iterdir()
        if path.is_file()
        and path.suffix.lower() in extension_set
        and path.resolve() not in template_paths
    ]
    return sorted(images, key=lambda path: path.name.casefold())