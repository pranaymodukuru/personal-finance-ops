"""Subcategory assignment for personal finance transactions."""

import re
from typing import Any

_FOOD: list[tuple[re.Pattern, str]] = [
    (re.compile(r"rewe|netto|lidl|aldi|billa|edeka|penny|interspar|spicelands|transgourmet"
                r"|hofer|spar.*(markt|express|dankt|7544)|m\.s\.asia|jaffna|ocean indien|kaufland"
                r"|mlinar|pbz tspar|dookan|lebensmittel", re.I), "groceries"),
    (re.compile(r"takeaway|lieferando|lieferser", re.I), "delivery"),
    (re.compile(r"mcdonald|dunkin|burger king|subway|mc donald", re.I), "fast_food"),
    (re.compile(r"bäckerei|baeckerei|wienerroither|rubenbauer|\bder beck\b"
                r"|starbucks|café|cafe\b|kaffee", re.I), "bakery_cafe"),
]

_SHOPPING: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bh\.m\b|zaful|tom tailor|under armour|lpp deutschland"
                r"|stradun fashion|galeria|karstadt|deichmann|swarovski"
                r"|estee lauder|luxottica|etsy", re.I), "clothing_fashion"),
    (re.compile(r"media markt|apple store", re.I), "electronics"),
    (re.compile(r"xxxlutz|möbelix|moebelix|ikea|zwilling", re.I), "home_furniture"),
    (re.compile(r"\bintersport\b", re.I), "sports_outdoor"),
    (re.compile(r"dm.drogerie|dm markt|dm-drogerie|\bdm\b.*offenbach"
                r"|drogerie markt", re.I), "beauty_drugstore"),
    (re.compile(r"amazon|amzn|joinandsell", re.I), "general_online"),
]

_TRANSPORT: list[tuple[re.Pattern, str]] = [
    (re.compile(r"deutsche bahn|db vertrieb|dbvertrieb|bahnhof.*3654"
                r"|302970|01806101111|öbb|oebb|obb pv|\boebb\b", re.I), "train"),
    (re.compile(r"flixbus", re.I), "bus_coach"),
    (re.compile(r"travelgenio|airline|lufthansa|ryanair|easyjet|flight", re.I), "flight"),
    (re.compile(r"\brmv\b|vgf|mvv|automat \d{4}|public transport", re.I), "local_transit"),
    (re.compile(r"jadrolinija|ferry|ionios", re.I), "ferry"),
    (re.compile(r"airbnb", re.I), "accommodation_travel"),
    (re.compile(r"omio", re.I), "booking_platform"),
]

_UTILITIES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"mobilcom|drillisch|vodafone|premiumsim|\bo2\b|telekom"
                r"|sim card|mobile plan", re.I), "mobile_phone"),
    (re.compile(r"kabel deutschland|internet|dsl|cable", re.I), "internet_tv"),
    (re.compile(r"miete|kauselmann|tannert|bettinastrasse|rent payment"
                r"|rent share|gundlach", re.I), "rent"),
    (re.compile(r"nebenkosten|gez|rundfunk|heizung|strom|ancillary"
                r"|utility costs", re.I), "ancillary_costs"),
]

_ENTERTAINMENT: list[tuple[re.Pattern, str]] = [
    (re.compile(r"getyourguide|airbnb|omio|activity|tour booking", re.I), "travel_activities"),
    (re.compile(r"reservix|zoo|stadtkino|cinema|kino|sorted|event"
                r"|konzert|concert|tickets", re.I), "events_concerts"),
    (re.compile(r"steam|playstation|nintendo|epic games|gaming|\bgame\b", re.I), "gaming"),
    (re.compile(r"paddle|humble bundle|spotify|netflix|disney|youtube"
                r"|streaming|subscription|software", re.I), "software_subscriptions"),
]

_INCOME: list[tuple[re.Pattern, str]] = [
    (re.compile(r"tvarit|salary|gehalt", re.I), "salary"),
    (re.compile(r"gundlach|kauselmann|miete.*income|parkplatz.*income"
                r"|rent.*income|jalal|wg miete|wg kalt", re.I), "rental_income"),
    (re.compile(r"stripe|medium\.com|\bmedium\b", re.I), "freelance"),
    (re.compile(r"finanzamt|erstatt|steuer|fa fulda|tax refund", re.I), "tax_refund"),
    (re.compile(r"reimburs|erstattung|meeting reimburs", re.I), "reimbursement"),
    (re.compile(r"referral|bonus", re.I), "bonus_other"),
]

_SAVINGS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"scalable|sparplan|etf|fonds|invest|broker", re.I), "etf_investments"),
    (re.compile(r"binance|coinbase|crypto|bitcoin", re.I), "crypto"),
    (re.compile(r"lebensversicherung|volkswohl", re.I), "pension_insurance"),
]

_FEES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"n26.*member|n26 smart|membership fee", re.I), "bank_fees"),
    (re.compile(r"zahlungsabsicherung|payment protection|absicherung"
                r"|insurance fee|interest charge", re.I), "card_fees"),
    (re.compile(r"scalable.*prime|prime.*scalable|prime bis", re.I), "platform_fees"),
]

_HEALTHCARE: list[tuple[re.Pattern, str]] = [
    (re.compile(r"mcfit|rsg group|betterme|fitness|gym", re.I), "gym_fitness"),
    (re.compile(r"medicorum|arzt|apotheke|doctor|pharmacy|hospital|klinik", re.I), "medical"),
]

_OTHER: list[tuple[re.Pattern, str]] = [
    (re.compile(r"atm|geldautomat|cash withdrawal|sparkasse.*atm", re.I), "cash_atm"),
    (re.compile(r"donation|spende|hilft|sangh|relief|charity|covid.*donat", re.I), "donation"),
    (re.compile(r"magistrat|adac|übersetzung|fuehrerschein|government"
                r"|behörde|\bamt\b", re.I), "government_fees"),
    (re.compile(r"hotel|accommodation|übernachtung|stay|imperial ostrava", re.I), "accommodation"),
]

_TRANSFER: list[tuple[re.Pattern, str]] = [
    (re.compile(r"american express|amex|advanzia", re.I), "credit_card_payment"),
    (re.compile(r"wise|transferwise", re.I), "international_transfer"),
    (re.compile(r"paypal", re.I), "payment_platform"),
    (re.compile(r"scalable|broker|investment|sparplan", re.I), "investment_transfer"),
    (re.compile(r"moneybeam|shreya|jalal|praetzas|nutakki", re.I), "person_transfer"),
]

_ATM_PM = re.compile(r"atm", re.I)


def assign_subcategory(row: dict[str, Any]) -> str:
    """Map (category, receiver, description, payment_method) → subcategory string."""
    cat = str(row.get("category", "")).lower()
    text = (str(row.get("receiver", "")) + " " + str(row.get("description", ""))).lower()
    pm = str(row.get("payment_method", "")).lower()

    if cat == "food":
        for pattern, label in _FOOD:
            if pattern.search(text):
                return label
        return "dining_out"

    if cat == "shopping":
        for pattern, label in _SHOPPING:
            if pattern.search(text):
                return label
        return "other_shopping"

    if cat == "transport":
        for pattern, label in _TRANSPORT:
            if pattern.search(text):
                return label
        return "other_transport"

    if cat == "utilities":
        for pattern, label in _UTILITIES:
            if pattern.search(text):
                return label
        return "other_utilities"

    if cat == "entertainment":
        for pattern, label in _ENTERTAINMENT:
            if pattern.search(text):
                return label
        return "other_entertainment"

    if cat == "income":
        for pattern, label in _INCOME:
            if pattern.search(text):
                return label
        return "other_income"

    if cat == "savings":
        for pattern, label in _SAVINGS:
            if pattern.search(text):
                return label
        return "other_savings"

    if cat == "fees":
        for pattern, label in _FEES:
            if pattern.search(text):
                return label
        return "other_fees"

    if cat == "healthcare":
        for pattern, label in _HEALTHCARE:
            if pattern.search(text):
                return label
        return "other_healthcare"

    if cat == "other":
        if pm == "atm" or _ATM_PM.search(text):
            return "cash_atm"
        for pattern, label in _OTHER:
            if pattern.search(text):
                return label
        return "miscellaneous"

    if cat == "transfer":
        for pattern, label in _TRANSFER:
            if pattern.search(text):
                return label
        return "other_transfer"

    if cat == "insurance":
        return "insurance"

    return "unclassified"
