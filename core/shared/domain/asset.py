from enum import Enum


class AssetFamily(str, Enum):
    REAL_ESTATE = "real_estate"
    INFRASTRUCTURE = "infrastructure"
    FINANCIAL = "financial"
    INTELLECTUAL_PROPERTY = "intellectual_property"
    COLLECTIBLE = "collectible"
    LIVESTOCK = "livestock"


class AssetClass(str, Enum):
    # Real Estate
    COMMERCIAL = "commercial"
    RESIDENTIAL = "residential"
    SILVER_TOWN = "silver_town"
    LOGISTICS = "logistics"
    HOTEL = "hotel"
    DATA_CENTER = "data_center"
    # Infrastructure
    SOLAR = "solar"
    WIND = "wind"
    # Financial
    BOND = "bond"
    LOAN = "loan"
    # Intellectual Property
    MUSIC_COPYRIGHT = "music_copyright"
    CONTENT_IP = "content_ip"
    # Collectible
    ART = "art"
    LUXURY = "luxury"
    # Livestock
    HANWOO = "hanwoo"


ASSET_CLASS_TO_FAMILY: dict[AssetClass, AssetFamily] = {
    AssetClass.COMMERCIAL: AssetFamily.REAL_ESTATE,
    AssetClass.RESIDENTIAL: AssetFamily.REAL_ESTATE,
    AssetClass.SILVER_TOWN: AssetFamily.REAL_ESTATE,
    AssetClass.LOGISTICS: AssetFamily.REAL_ESTATE,
    AssetClass.HOTEL: AssetFamily.REAL_ESTATE,
    AssetClass.DATA_CENTER: AssetFamily.REAL_ESTATE,
    AssetClass.SOLAR: AssetFamily.INFRASTRUCTURE,
    AssetClass.WIND: AssetFamily.INFRASTRUCTURE,
    AssetClass.BOND: AssetFamily.FINANCIAL,
    AssetClass.LOAN: AssetFamily.FINANCIAL,
    AssetClass.MUSIC_COPYRIGHT: AssetFamily.INTELLECTUAL_PROPERTY,
    AssetClass.CONTENT_IP: AssetFamily.INTELLECTUAL_PROPERTY,
    AssetClass.ART: AssetFamily.COLLECTIBLE,
    AssetClass.LUXURY: AssetFamily.COLLECTIBLE,
    AssetClass.HANWOO: AssetFamily.LIVESTOCK,
}
