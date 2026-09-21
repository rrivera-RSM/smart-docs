from __future__ import annotations

import hashlib
import ipaddress
import os
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from docgen.anonymizer.detectors import validate_dni, validate_nie, validate_spanish_iban
from docgen.anonymizer.models import DocumentLocation, Finding

ENTITY_LABELS = {
    "PERSON": "Persona",
    "ORGANIZATION": "Empresa u organizaci\u00f3n",
    "COUNTRY": "Pa\u00eds",
    "REGION": "Regi\u00f3n o provincia",
    "LOCALITY": "Localidad",
    "LOCATION": "Ubicaci\u00f3n",
    "ADDRESS": "Direcci\u00f3n",
    "MONEY": "Importe",
    "ES_DNI": "DNI",
    "ES_NIE": "NIE",
    "ES_TAX_ID": "NIF / CIF",
    "ES_SOCIAL_SECURITY": "Seguridad Social",
    "PASSPORT": "Pasaporte",
    "VEHICLE_PLATE": "Matr\u00edcula",
    "ES_IBAN": "IBAN",
    "CREDIT_CARD": "Tarjeta",
    "SWIFT": "C\u00f3digo SWIFT",
    "EMAIL": "Correo electr\u00f3nico",
    "ES_PHONE": "Tel\u00e9fono",
    "URL": "URL",
    "IP_ADDRESS": "Direcci\u00f3n IP",
    "DATE_OF_BIRTH": "Fecha de nacimiento",
    "AGE": "Edad",
}
TOKEN_PREFIXES = {
    "PERSON": "PERS", "ORGANIZATION": "EMP", "COUNTRY": "PAIS",
    "REGION": "REG", "LOCALITY": "LOC", "LOCATION": "LOC",
    "ADDRESS": "DIR", "MONEY": "IMP", "ES_DNI": "DNI", "ES_NIE": "NIE",
    "ES_TAX_ID": "NIF", "ES_SOCIAL_SECURITY": "NSS", "PASSPORT": "PASS",
    "VEHICLE_PLATE": "MAT", "ES_IBAN": "IBAN", "CREDIT_CARD": "TARJ",
    "SWIFT": "SWIFT", "EMAIL": "EMAIL", "ES_PHONE": "TEL", "URL": "URL",
    "IP_ADDRESS": "IP", "DATE_OF_BIRTH": "FNAC", "AGE": "EDAD",
}
ALL_CATEGORIES = tuple(ENTITY_LABELS)

COUNTRIES = {
    "alemania", "argentina", "australia", "belgica", "brasil", "canada", "chile",
    "china", "colombia", "dinamarca", "ecuador", "espana", "estados unidos",
    "francia", "india", "irlanda", "italia", "japon", "luxemburgo", "mexico",
    "noruega", "paises bajos", "peru", "polonia", "portugal", "reino unido",
    "rumania", "suecia", "suiza", "uruguay", "venezuela",
}
REGIONS = {
    "andalucia", "aragon", "asturias", "cantabria", "castilla-la mancha",
    "castilla y leon", "cataluna", "comunidad de madrid", "comunidad valenciana",
    "extremadura", "galicia", "islas baleares", "islas canarias", "la rioja",
    "navarra", "pais vasco", "region de murcia",
}
LOCALITIES = {
    "a coruna", "albacete", "alcala de henares", "alicante", "almeria", "barcelona",
    "bilbao", "burgos", "cadiz", "castellon", "cordoba", "girona", "granada",
    "guadalajara", "huelva", "jaen", "las palmas de gran canaria", "leon", "lleida",
    "logrono", "madrid", "malaga", "murcia", "oviedo", "palma", "pamplona",
    "salamanca", "san sebastian", "santa cruz de tenerife", "santander",
    "santiago de compostela", "segovia", "sevilla", "tarragona", "toledo",
    "valencia", "valladolid", "vigo", "vitoria-gasteiz", "zaragoza",
}

ISO_ALPHA2_CODES = frozenset(
    "AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL "
    "BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV "
    "CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD "
    "GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM "
    "IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK "
    "LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW "
    "MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR "
    "PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS "
    "ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY "
    "UZ VA VC VE VG VI VN VU WF WS XK YE YT ZA ZM ZW".split()
)

Validator = Callable[[str], bool]


@dataclass(frozen=True)
class DetectionRule:
    entity_type: str
    pattern: re.Pattern[str]
    validator: Validator
    confidence: float
    reason: str
    priority: int = 80
    capture_group: int | None = None


def _valid(_: str) -> bool:
    return True


def _compact(value: str) -> str:
    return re.sub(r"[\s./-]", "", value).upper()


def validate_luhn(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    total, parity = 0, len(digits) % 2
    for index, character in enumerate(digits):
        number = int(character)
        if index % 2 == parity:
            number = number * 2 - (9 if number > 4 else 0)
        total += number
    return total % 10 == 0


def validate_social_security(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    return len(digits) == 12 and 1 <= int(digits[:2]) <= 53 and int(digits[:10]) % 97 == int(digits[10:])


def validate_tax_id(value: str) -> bool:
    normalized = _compact(value)
    if validate_dni(normalized) or validate_nie(normalized):
        return True
    if not re.fullmatch(r"[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]", normalized):
        return False
    digits = [int(item) for item in normalized[1:8]]
    total = sum(digits[index] for index in (1, 3, 5))
    total += sum(sum(divmod(digits[index] * 2, 10)) for index in (0, 2, 4, 6))
    control = (10 - total % 10) % 10
    suffix, letter = normalized[-1], "JABCDEFGHI"[control]
    if normalized[0] in "PQRSNW":
        return suffix == letter
    if normalized[0] in "ABEH":
        return suffix == str(control)
    return suffix in {str(control), letter}


def validate_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def validate_swift(value: str) -> bool:
    normalized = re.sub(r"\s", "", value).upper()
    return bool(
        re.fullmatch(r"[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?", normalized)
        and normalized[4:6] in ISO_ALPHA2_CODES
    )


def validate_passport_number(value: str) -> bool:
    normalized = re.sub(r"[\s-]", "", value).upper()
    return bool(
        re.fullmatch(r"[A-Z0-9]{6,9}", normalized)
        and any(character.isdigit() for character in normalized)
        and len(set(normalized)) > 1
    )


PASSPORT_VALUE_PATTERN = re.compile(
    r"(?<![A-Z0-9])[A-Z0-9](?:[\s-]?[A-Z0-9]){5,8}(?![A-Z0-9])",
    re.I,
)

RULES = (
    DetectionRule("ES_NIE", re.compile(r"(?<![A-Z0-9])[XYZ][\s.-]?\d{7}[\s.-]?[A-Z](?![A-Z0-9])", re.I), validate_nie, .99, "NIE con letra de control valida.", 100),
    DetectionRule("ES_DNI", re.compile(r"(?<![A-Z0-9])\d{8}[\s.-]?[A-Z](?![A-Z0-9])", re.I), validate_dni, .99, "DNI con letra de control valida.", 100),
    DetectionRule("ES_TAX_ID", re.compile(r"(?<![A-Z0-9])[ABCDEFGHJNPQRSUVW]\s?\d{7}\s?[0-9A-J](?![A-Z0-9])", re.I), validate_tax_id, .99, "Identificador fiscal con control valido.", 100),
    DetectionRule("ES_IBAN", re.compile(r"(?<![A-Z0-9])ES(?:[\s-]?\d){22}(?![A-Z0-9])", re.I), validate_spanish_iban, .99, "IBAN espanol con checksum MOD-97 valido.", 100),
    DetectionRule("CREDIT_CARD", re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"), validate_luhn, .98, "Tarjeta con checksum Luhn valido.", 100),
    DetectionRule("ES_SOCIAL_SECURITY", re.compile(r"(?<!\d)\d{2}[\s/-]?\d{8}[\s/-]?\d{2}(?!\d)"), validate_social_security, .98, "Numero de Seguridad Social con control valido.", 100),
    DetectionRule(
        "PASSPORT",
        re.compile(
            r"(?ix)\b(?:n(?:[.º°o]*|[úu]mero)\s+de\s+)?"
            r"(?:pasaporte|passport|documento\s+de\s+viaje)"
            r"(?:\s+(?:n(?:[.º°o]*|[úu]mero)|num(?:ero)?\.?|number|no\.?))?"
            r"\s*[:#-]?\s*([A-Z0-9](?:[\s-]?[A-Z0-9]){5,8})(?![A-Z0-9])"
        ),
        validate_passport_number,
        .92,
        "Numero de pasaporte asociado explicitamente a un documento de viaje.",
        92,
        1,
    ),
    DetectionRule("EMAIL", re.compile(r"(?<![\w.+-])[\w.+-]+@(?:[\w-]+\.)+[A-Z]{2,}(?![\w-])", re.I), _valid, .97, "Direccion de correo con estructura valida.", 95),
    DetectionRule("URL", re.compile(r"(?<![\w@])(?:https?://|www\.)[^\s<>()]+", re.I), _valid, .93, "Direccion web explicita.", 90),
    DetectionRule("IP_ADDRESS", re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])"), validate_ip, .96, "Direccion IP valida.", 95),
    DetectionRule("SWIFT", re.compile(r"\b[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b"), validate_swift, .88, "Codigo BIC/SWIFT con pais ISO valido."),
    DetectionRule("ES_PHONE", re.compile(r"(?<!\d)(?:\+34[\s.-]?)?[6789]\d{2}(?:[\s.-]?\d{3}){2}(?!\d)"), _valid, .86, "Numero de telefono espanol."),
    DetectionRule("VEHICLE_PLATE", re.compile(r"\b\d{4}[\s-]?[BCDFGHJKLMNPRSTVWXYZ]{3}\b", re.I), _valid, .91, "Matricula espanola moderna.", 90),
    DetectionRule("MONEY", re.compile(r"(?<!\w)(?:\u20ac|EUR|USD|GBP|\$|\u00a3)\s?\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?|\b\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?\s?(?:\u20ac|euros?|EUR|USD|d[o\u00f3]lares?|GBP|libras?)(?!\w)|\b(?:un|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|cien|mil|mill[o\u00f3]n(?:es)?)(?:\s+\w+){0,4}\s+(?:euros?|d[o\u00f3]lares?|libras?)\b", re.I), _valid, .90, "Cantidad asociada explicitamente a una moneda.", 90),
    DetectionRule("DATE_OF_BIRTH", re.compile(r"(?i)(?:(?:fecha\s+de\s+nacimiento|nacid[oa]\s+el)\s*[:\-]?\s*)(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+de\s+[a-z\u00c0-\u017f]+\s+de\s+\d{4})"), _valid, .91, "Fecha vinculada explicitamente al nacimiento.", 90),
    DetectionRule("AGE", re.compile(r"(?i)(?:(?:edad|tiene)\s*[:\-]?\s*)\d{1,3}\s*(?:a\u00f1os)?"), _valid, .82, "Edad expresada en contexto personal."),
    DetectionRule("ADDRESS", re.compile(r"(?i)\b(?:calle|c/|avenida|avda\.?|paseo|plaza|camino|carretera|ronda)\s+[A-Z\u00c0-\u017f][\w\u00c0-\u017f.' -]{2,70}?(?:,?\s+(?:numero|n[\u00ba\u00b0o]\.?|num\.?)?\s*\d+[A-Z]?)(?:,?\s*\d{5})?"), _valid, .87, "Direccion postal con tipo de via y numero."),
    DetectionRule("ORGANIZATION", re.compile(r"\b[A-Z\u00c0-\u017f][\w\u00c0-\u017f&.' -]{1,70}?\s+(?:S\.?\s?[LA]\.?|S\.?L\.?U\.?|S\.?A\.?U\.?|Ltd\.?|Limited|GmbH|LLP|Inc\.?)\b", re.I), _valid, .89, "Nombre seguido de una forma juridica reconocida.", 88),
    DetectionRule("PERSON", re.compile(r"(?i)(?:(?:don|do\u00f1a|sr\.?|sra\.?|nombre|cliente|emplead[oa]|representad[oa]\s+por)\s*[:\-]?\s+)([A-Z\u00c0-\u017f][a-z\u00c0-\u017f]+(?:\s+(?:de|del|la|las|los|y))?(?:\s+[A-Z\u00c0-\u017f][a-z\u00c0-\u017f]+){1,4})"), _valid, .78, "Nombre completo junto a un indicador personal.", 70, 1),
)


def context_snippet(text: str, start: int, end: int, radius: int = 64) -> str:
    left, right = max(0, start - radius), min(len(text), end + radius)
    return ("\u2026" if left else "") + text[left:right].replace("\n", " ") + ("\u2026" if right < len(text) else "")


def finding_id(location: DocumentLocation | str | object, entity_type: str, start: int, end: int, value: str, source: str = "") -> str:
    location_id = location.id if isinstance(location, DocumentLocation) else str(location)
    return hashlib.sha256(f"{location_id}:{entity_type}:{start}:{end}:{value}:{source}".encode()).hexdigest()[:20]


def _accentless(value: str) -> str:
    return "".join(character for character in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(character))


STRUCTURAL_LABELS = frozenset({
    "iban", "dni", "nie", "nif", "cif", "swift", "bic", "contacto",
    "trabajador", "trabajadora", "empresa", "telefono", "email", "correo",
    "domicilio", "direccion", "localidad", "fecha", "nacimiento", "edad",
    "pasaporte", "nacionalidad", "cuenta", "tarjeta", "portal", "responsable",
    "coordinador", "proveedor", "cliente",
})


def _is_structural_label(value: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", _accentless(value)).strip()
    return normalized in STRUCTURAL_LABELS


def _is_explicitly_non_entity_context(text: str, start: int, end: int) -> bool:
    """Ignore NER hits which the surrounding sentence explicitly defines as labels or project names."""
    sentence_start = max(text.rfind(separator, 0, start) for separator in (".", ";", "\n")) + 1
    sentence_ends = [position for separator in (".", ";", "\n") if (position := text.find(separator, end)) >= 0]
    sentence_end = min(sentence_ends, default=len(text))
    before = _accentless(text[sentence_start:start])
    after = _accentless(text[end:sentence_end])
    sentence = _accentless(text[sentence_start:sentence_end])

    if re.search(r"\bnegativ\w*\s+ambigu\w*\b", sentence):
        return True
    if re.search(r"\b(?:proyecto|fase)\b[^.;:\n]{0,80}\b(?:se\s+denomina|se\s+llama)\s*$", before):
        return True
    return bool(re.match(r"(?:\s+y\s+[^.;:\n]{1,60})?\s+son\s+nombres?\s+de\s+proyecto\b", after))

class RuleBasedDetector:
    name = "Reglas locales"
    ready = True

    def detect(self, text: str, location: DocumentLocation | str) -> list[Finding]:
        findings: list[Finding] = []
        for rule in RULES:
            for match in rule.pattern.finditer(text):
                start, end = match.span(rule.capture_group) if rule.capture_group is not None else match.span()
                value = text[start:end]
                if rule.validator(value):
                    findings.append(Finding(
                        id=finding_id(location, rule.entity_type, start, end, value, self.name),
                        entity_type=rule.entity_type, label=ENTITY_LABELS[rule.entity_type], value=value,
                        replacement=f"[{TOKEN_PREFIXES[rule.entity_type]}]", location=location,
                        start=start, end=end, context=context_snippet(text, start, end),
                        confidence=rule.confidence, sources=(self.name,), reason=rule.reason, priority=rule.priority,
                    ))
        location_label = (
            _accentless(location.label.casefold())
            if isinstance(location, DocumentLocation)
            else ""
        )
        if (
            "pasaporte" in location_label
            and not any(item.entity_type == "PASSPORT" for item in findings)
        ):
            for match in PASSPORT_VALUE_PATTERN.finditer(text):
                value = match.group(0)
                if not validate_passport_number(value):
                    continue
                findings.append(Finding(
                    id=finding_id(
                        location,
                        "PASSPORT",
                        match.start(),
                        match.end(),
                        value,
                        self.name,
                    ),
                    entity_type="PASSPORT",
                    label=ENTITY_LABELS["PASSPORT"],
                    value=value,
                    replacement=f"[{TOKEN_PREFIXES['PASSPORT']}]",
                    location=location,
                    start=match.start(),
                    end=match.end(),
                    context=context_snippet(text, match.start(), match.end()),
                    confidence=.92,
                    sources=(self.name,),
                    reason="Numero de pasaporte en una celda etiquetada como pasaporte.",
                    priority=92,
                ))
        folded = _accentless(text)
        for entity_type, values, confidence in (("COUNTRY", COUNTRIES, .84), ("REGION", REGIONS, .84), ("LOCALITY", LOCALITIES, .80)):
            for value in sorted(values, key=len, reverse=True):
                for match in re.finditer(rf"(?<!\w){re.escape(value)}(?!\w)", folded, re.I):
                    start, end = match.span()
                    findings.append(Finding(
                        id=finding_id(location, entity_type, start, end, text[start:end], "Gazetteer local"),
                        entity_type=entity_type, label=ENTITY_LABELS[entity_type], value=text[start:end],
                        replacement=f"[{TOKEN_PREFIXES[entity_type]}]", location=location,
                        start=start, end=end, context=context_snippet(text, start, end), confidence=confidence,
                        sources=("Gazetteer local",), reason="Coincidencia con un catalogo geografico local versionado.", priority=65,
                    ))
        return findings


class NoOpNerDetector:
    name = "NER desactivado explicitamente"
    ready = True
    model_version = "rules-only"
    detail = "Modo de reglas solicitado mediante SMARTDOCS_NER_MODE=rules."

    def detect(self, text: str, location: object) -> list[Finding]:
        return []


class UnavailableNerDetector:
    name = "Transformer espanol"
    ready = False
    model_version = "unavailable"

    def __init__(self, detail: str) -> None:
        self.detail = detail

    def detect(self, text: str, location: object) -> list[Finding]:
        return []


class PresidioNerDetector:
    name = "Presidio + RoBERTa espanol"

    def __init__(self, model_path: str) -> None:
        self.ready, self.detail, self.model_version, self._engine = False, "", Path(model_path).name, None
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NerModelConfiguration, TransformersNlpEngine
            configuration = NerModelConfiguration(
                model_to_presidio_entity_mapping={"PER": "PERSON", "PERSON": "PERSON", "ORG": "ORGANIZATION", "ORGANIZATION": "ORGANIZATION", "LOC": "LOCATION", "LOCATION": "LOCATION"},
                labels_to_ignore=["O", "MISC"], aggregation_strategy="simple", stride=64, alignment_mode="expand",
            )
            nlp_engine = TransformersNlpEngine(models=[{"lang_code": "es", "model_name": {"spacy": "es_core_news_sm", "transformers": model_path}}], ner_model_configuration=configuration)
            nlp_engine.load()
            self._engine = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["es"])
            self.ready, self.detail = True, "Modelo local precargado y listo."
        except Exception as exc:
            self.detail = f"No se ha podido cargar el modelo local: {exc.__class__.__name__}."

    def detect(self, text: str, location: DocumentLocation | str) -> list[Finding]:
        if not self.ready or self._engine is None:
            return []
        results = self._engine.analyze(text=text, language="es", entities=["PERSON", "ORGANIZATION", "LOCATION"], score_threshold=.45)
        findings: list[Finding] = []
        for result in results:
            value = text[result.start:result.end]
            if _is_structural_label(value) or _is_explicitly_non_entity_context(text, result.start, result.end):
                continue
            findings.append(Finding(
                id=finding_id(location, result.entity_type, result.start, result.end, value, self.name),
                entity_type=result.entity_type, label=ENTITY_LABELS[result.entity_type], value=value,
                replacement=f"[{TOKEN_PREFIXES[result.entity_type]}]", location=location,
                start=result.start, end=result.end, context=context_snippet(text, result.start, result.end),
                confidence=float(result.score), sources=(self.name,), reason="Entidad identificada por el modelo contextual espanol.", priority=50,
            ))
        return findings


def create_ner_detector() -> NoOpNerDetector | UnavailableNerDetector | PresidioNerDetector:
    if os.getenv("SMARTDOCS_NER_MODE", "required").strip().lower() == "rules":
        return NoOpNerDetector()
    model_path = os.getenv("SMARTDOCS_NER_MODEL_PATH", ".models/roberta-base-bne-capitel-ner-plus").strip()
    if not Path(model_path).exists():
        return UnavailableNerDetector("Configura SMARTDOCS_NER_MODEL_PATH con el modelo local; no hay descargas en ejecucion.")
    return PresidioNerDetector(model_path)
