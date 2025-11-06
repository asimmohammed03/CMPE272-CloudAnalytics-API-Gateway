from fastapi import APIRouter, Query, HTTPException
import boto3, json

router = APIRouter(prefix="/aws", tags=["aws"])

# AWS Pricing is only in us-east-1
pricing = boto3.client("pricing", region_name="us-east-1")

def _first_price_usd(price_item: dict) -> float | None:
    """Extract first OnDemand USD price from AWS price list item."""
    terms = price_item.get("terms", {}).get("OnDemand", {})
    for term in terms.values():
        dims = term.get("priceDimensions", {})
        for d in dims.values():
            usd = d.get("pricePerUnit", {}).get("USD")
            if usd is not None:
                try:
                    return float(usd)
                except ValueError:
                    continue
    return None

@router.get("/prices")
def ec2_on_demand_price(
    instance_type: str = Query(..., example="t3.micro"),
    location: str = Query("US East (N. Virginia)"),
    operating_system: str = Query("Linux"),
    tenancy: str = Query("Shared"),
    preinstalled_sw: str = Query("NA"),
    capacity_status: str = Query("Used"),
):
    """
    Returns current OnDemand price for an EC2 instance type in a given AWS location.
    """
    filters = [
        {"Type":"TERM_MATCH","Field":"servicecode","Value":"AmazonEC2"},
        {"Type":"TERM_MATCH","Field":"instanceType","Value": instance_type},
        {"Type":"TERM_MATCH","Field":"location","Value": location},
        {"Type":"TERM_MATCH","Field":"operatingSystem","Value": operating_system},
        {"Type":"TERM_MATCH","Field":"tenancy","Value": tenancy},
        {"Type":"TERM_MATCH","Field":"preInstalledSw","Value": preinstalled_sw},
        {"Type":"TERM_MATCH","Field":"capacitystatus","Value": capacity_status},
    ]
    try:
        resp = pricing.get_products(ServiceCode="AmazonEC2", Filters=filters)
    except Exception as e:
        raise HTTPException(500, f"AWS Pricing error: {e}")

    items = [json.loads(x) for x in resp.get("PriceList", [])]
    if not items:
        raise HTTPException(404, "No matching AWS price found")

    price = _first_price_usd(items[0])
    if price is None:
        raise HTTPException(404, "Could not extract USD price")

    prod = items[0]["product"]["attributes"]
    return {
        "provider": "AWS",
        "instanceType": prod.get("instanceType"),
        "location": prod.get("location"),
        "operatingSystem": prod.get("operatingSystem"),
        "tenancy": prod.get("tenancy"),
        "unitPrice": price,
        "unitOfMeasure": "Hrs"
    }
